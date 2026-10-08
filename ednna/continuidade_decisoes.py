"""Materialização local, idempotente e auditável da continuidade legada.

Não executa e-mails, mudanças no Redmine ou transferências de responsável.
A classificação de responsabilidade só produz proposta de próxima ação.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ednna.acompanhamento_acoes import ultima_interpretacao_retorno

_SCHEMA = 1
_ESTADOS_HUMANOS = {"DECISAO_HUMANA", "INDETERMINADO", "DEVOLVER_ORIGEM"}


def _db_path() -> Path:
    return Path(os.getenv("EDNNA_DB_PATH", "/home/data/ednna.db"))


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("""CREATE TABLE IF NOT EXISTS continuidade_decisoes (
        chamado_id INTEGER PRIMARY KEY,
        regra_id TEXT NOT NULL DEFAULT '',
        decisao TEXT NOT NULL,
        estado TEXT NOT NULL,
        proxima_acao TEXT NOT NULL,
        responsavel_id INTEGER,
        responsavel_nome TEXT NOT NULL DEFAULT '',
        motivo TEXT NOT NULL DEFAULT '',
        evidencia TEXT NOT NULL DEFAULT '',
        prazo_revisao_em TEXT NOT NULL DEFAULT '',
        assinatura TEXT NOT NULL,
        versao INTEGER NOT NULL,
        atualizado_em TEXT NOT NULL
    )""")
    return conn


def _prazo_interno(agora: datetime) -> str:
    # Revisão interna; nunca é autorização para cobrança externa.
    return (agora + timedelta(hours=48)).isoformat(timespec="seconds")


def _proposta(item: dict, agora: datetime) -> dict:
    cid = int(item["chamado_id"])
    regra = str(item.get("regra_id") or "")
    decisao = str(item.get("decisao") or "INDETERMINADO")
    atual = item.get("responsavel_atual") or {}
    origem = item.get("responsavel_origem") or {}
    interpretacao = ultima_interpretacao_retorno(cid, regra)
    evidencia = str(interpretacao.get("evidencia") or "")
    prazo = str(interpretacao.get("prazo_revisao_em") or "")
    if interpretacao.get("classificacao") == "PENDENCIA_DOCUMENTAL":
        estado = "AGUARDANDO_DOCUMENTACAO"
        proxima = str(interpretacao.get("proxima_acao") or "Validar documentos exigidos")
        decisao = "VALIDACAO_HUMANA_DOCUMENTOS"
    elif decisao == "MANTER_RESPONSAVEL_ATUAL":
        estado = "ACOMPANHAMENTO_HUMANO"
        proxima = "Manter responsável atual e revisar pendência no prazo interno"
    elif decisao == "AGUARDAR_TERCEIRO":
        estado = "AGUARDANDO_TERCEIRO"
        proxima = "Acompanhar resposta pela thread transacional existente"
    elif decisao == "ACAO_EDDY_DUE":
        estado = "REVISAO_RETORNO"
        proxima = "Interpretar retorno e confirmar evidências antes de nova ação"
    else:
        estado = "REVISAO_HUMANA"
        proxima = "Validar histórico e definir responsável sem transferência automática"
    pessoa = atual if atual.get("id") else origem
    try:
        responsavel_id = int(pessoa["id"]) if pessoa.get("id") else None
    except (ValueError, TypeError):
        responsavel_id = None
    return {
        "chamado_id": cid, "regra_id": regra, "decisao": decisao,
        "estado": estado, "proxima_acao": proxima,
        "responsavel_id": responsavel_id,
        "responsavel_nome": str(pessoa.get("nome") or ""),
        "motivo": str(item.get("motivo") or ""),
        "evidencia": evidencia[:700],
        "prazo_revisao_em": prazo,
    }


def materializar_decisoes(itens: list[dict], *, agora: datetime | None = None) -> dict:
    """Atualiza somente decisões que mudaram. Preserva o prazo da decisão estável."""
    import hashlib
    agora = agora or datetime.now(timezone.utc)
    resultado = {"analisados": 0, "novos": 0, "alterados": 0, "inalterados": 0, "erros": 0}
    with _connect() as conn:
        for item in itens:
            try:
                proposta = _proposta(item, agora)
                cid = proposta["chamado_id"]
                resultado["analisados"] += 1
                assinatura = hashlib.sha256(json.dumps(proposta, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                anterior = conn.execute("SELECT assinatura, prazo_revisao_em FROM continuidade_decisoes WHERE chamado_id=?", (cid,)).fetchone()
                if anterior and anterior["assinatura"] == assinatura:
                    resultado["inalterados"] += 1
                    continue
                if not proposta["prazo_revisao_em"]:
                    # Prazo interno conta a partir da primeira classificação; não reinicia em cada ciclo.
                    proposta["prazo_revisao_em"] = (anterior["prazo_revisao_em"] if anterior else "") or _prazo_interno(agora)
                conn.execute("""INSERT INTO continuidade_decisoes
                    (chamado_id, regra_id, decisao, estado, proxima_acao,
                     responsavel_id, responsavel_nome, motivo, evidencia, prazo_revisao_em,
                     assinatura, versao, atualizado_em)
                    VALUES (:chamado_id, :regra_id, :decisao, :estado, :proxima_acao,
                            :responsavel_id, :responsavel_nome, :motivo, :evidencia, :prazo_revisao_em,
                            :assinatura, :versao, :atualizado_em)
                    ON CONFLICT(chamado_id) DO UPDATE SET
                    regra_id=excluded.regra_id, decisao=excluded.decisao,
                    estado=excluded.estado, proxima_acao=excluded.proxima_acao,
                    responsavel_id=excluded.responsavel_id, responsavel_nome=excluded.responsavel_nome,
                    motivo=excluded.motivo, evidencia=excluded.evidencia,
                    prazo_revisao_em=excluded.prazo_revisao_em, assinatura=excluded.assinatura,
                    versao=excluded.versao, atualizado_em=excluded.atualizado_em""",
                    {**proposta, "assinatura": assinatura, "versao": _SCHEMA, "atualizado_em": agora.isoformat()})
                resultado["alterados" if anterior else "novos"] += 1
            except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
                resultado["erros"] += 1
                print(f"[EDDY] Continuidade decisão | erro={type(exc).__name__}: {exc}", flush=True)
    return resultado


def obter_decisao(chamado_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM continuidade_decisoes WHERE chamado_id=?", (int(chamado_id),)).fetchone()
    return dict(row) if row else {}


def listar_decisoes(limite: int = 300) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM continuidade_decisoes ORDER BY atualizado_em DESC LIMIT ?", (max(1, min(int(limite), 2000)),)).fetchall()
    return [dict(r) for r in rows]
