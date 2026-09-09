from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


TZ_BRASIL = ZoneInfo("America/Sao_Paulo")


def _db_path() -> Path:
    configurado = os.getenv("EDNNA_DB_PATH")

    if configurado:
        return Path(configurado)

    if Path("/home/data").exists():
        return Path("/home/data/ednna.db")

    return Path("data/ednna.db")


def _agora() -> datetime:
    return datetime.now(TZ_BRASIL)


def _iso(valor: datetime) -> str:
    return valor.isoformat(timespec="seconds")


def _conectar() -> sqlite3.Connection:
    caminho = _db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(caminho, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def inicializar_acompanhamento() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acoes_operacionais (
                chamado_id INTEGER NOT NULL,
                regra_id TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'RASCUNHO',
                enviado_em TEXT,
                prazo_resposta_em TEXT,
                resposta_recebida_em TEXT,
                atualizado_em TEXT NOT NULL,
                observacao TEXT,
                PRIMARY KEY (chamado_id, regra_id)
            )
            """
        )


def _adicionar_dias_uteis(inicio: datetime, dias: int) -> datetime:
    atual = inicio
    adicionados = 0

    while adicionados < max(dias, 0):
        atual += timedelta(days=1)

        if atual.weekday() < 5:
            adicionados += 1

    return atual


def obter_acompanhamento(chamado_id: int, regra_id: str) -> dict:
    inicializar_acompanhamento()

    with _conectar() as conn:
        row = conn.execute(
            """
            SELECT *
              FROM acoes_operacionais
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (int(chamado_id), str(regra_id)),
        ).fetchone()

    if row is None:
        return {
            "chamado_id": int(chamado_id),
            "regra_id": str(regra_id),
            "estado": "RASCUNHO",
            "enviado_em": "",
            "prazo_resposta_em": "",
            "resposta_recebida_em": "",
            "observacao": "",
        }

    dados = dict(row)

    if dados.get("estado") == "AGUARDANDO_RESPOSTA" and dados.get("prazo_resposta_em"):
        try:
            if _agora() > datetime.fromisoformat(dados["prazo_resposta_em"]):
                dados["estado"] = "PRAZO_VENCIDO"
        except Exception:
            pass

    return dados


def registrar_envio(
    chamado_id: int,
    regra_id: str,
    prazo_dias_uteis: int = 1,
) -> dict:
    inicializar_acompanhamento()
    agora = _agora()
    prazo = _adicionar_dias_uteis(agora, int(prazo_dias_uteis or 0))

    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO acoes_operacionais (
                chamado_id, regra_id, estado, enviado_em,
                prazo_resposta_em, resposta_recebida_em, atualizado_em
            )
            VALUES (?, ?, 'AGUARDANDO_RESPOSTA', ?, ?, NULL, ?)
            ON CONFLICT(chamado_id, regra_id)
            DO UPDATE SET
                estado = 'AGUARDANDO_RESPOSTA',
                enviado_em = excluded.enviado_em,
                prazo_resposta_em = excluded.prazo_resposta_em,
                resposta_recebida_em = NULL,
                atualizado_em = excluded.atualizado_em
            """,
            (
                int(chamado_id),
                str(regra_id),
                _iso(agora),
                _iso(prazo),
                _iso(agora),
            ),
        )

    return obter_acompanhamento(chamado_id, regra_id)


def registrar_resposta(chamado_id: int, regra_id: str) -> dict:
    inicializar_acompanhamento()
    agora = _agora()

    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO acoes_operacionais (
                chamado_id, regra_id, estado,
                resposta_recebida_em, atualizado_em
            )
            VALUES (?, ?, 'RESPOSTA_RECEBIDA', ?, ?)
            ON CONFLICT(chamado_id, regra_id)
            DO UPDATE SET
                estado = 'RESPOSTA_RECEBIDA',
                resposta_recebida_em = excluded.resposta_recebida_em,
                atualizado_em = excluded.atualizado_em
            """,
            (
                int(chamado_id),
                str(regra_id),
                _iso(agora),
                _iso(agora),
            ),
        )

    return obter_acompanhamento(chamado_id, regra_id)


def rotulo_estado(estado: str) -> str:
    return {
        "RASCUNHO": "⚪ Rascunho",
        "AGUARDANDO_RESPOSTA": "🟡 Aguardando resposta",
        "PRAZO_VENCIDO": "🔴 Prazo de resposta vencido",
        "RESPOSTA_RECEBIDA": "🟢 Resposta recebida",
    }.get(str(estado or ""), str(estado or "Sem estado"))
