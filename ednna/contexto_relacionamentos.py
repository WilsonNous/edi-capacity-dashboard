from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from ednna.armazenamento import conectar
from redmine_api import buscar_detalhes_chamado, issue_para_linha
from painel_cache import adquirir_lock as painel_adquirir_lock, liberar_lock as painel_liberar_lock


# ============================================================
# EDNNA — CONTEXTO HISTÓRICO DE RELACIONAMENTOS
# v3.24
#
# Somente leitura. Este módulo NÃO envia e-mails, NÃO altera
# status e NÃO executa cancelamentos.
# ============================================================

CACHE_HORAS_HISTORICO = 168  # 7 dias: histórico concluído muda raramente
CACHE_MINUTOS_ABERTO = 120  # 2h: evita avalanche de GETs ao navegar na Central

PLAYER_ALIASES = {
    "GETNET": ("GETNET",),
    "REDECARD": ("REDECARD", "REDE CARD", "REDE"),
    "SENFF": ("SENFF",),
    "SANTANDER": ("SANTANDER",),
    "ITAU": ("ITAU", "ITAÚ"),
    "PAGSEGURO": ("PAGSEGURO", "PAG SEGURO"),
    "VERO": ("VERO",),
    "BANRISUL": ("BANRISUL",),
    "CAIXA": ("CAIXA",),
    "BRADESCO": ("BRADESCO",),
    "SICOOB": ("SICOOB",),
    "SICREDI": ("SICREDI",),
    "SAFRAPAY": ("SAFRAPAY", "SAFRA PAY"),
    "BTG PACTUAL": ("BTG PACTUAL", "BTG"),
    "VALECARD": ("VALECARD", "VALE CARD"),
    "TRUCKPAG": ("TRUCKPAG", "TRUCK PAG"),
    "POLICARD": ("POLICARD", "POLI CARD"),
    "GREENCARD": ("GREENCARD", "GREEN CARD"),
    "TICKETLOG": ("TICKETLOG", "TICKET LOG"),
    "VEROCHEQUE": ("VEROCHEQUE", "VERO CHEQUE"),
}


def _norm(valor: Any) -> str:
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _inicializar_cache() -> None:
    with conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contexto_relacionamentos_cache (
                chamado_id INTEGER PRIMARY KEY,
                payload_json TEXT NOT NULL,
                estado TEXT,
                atualizado_em TEXT NOT NULL
            )
            """
        )


def _cache_obter(chamado_id: int) -> dict | None:
    _inicializar_cache()
    with conectar() as conn:
        row = conn.execute(
            "SELECT payload_json, estado, atualizado_em FROM contexto_relacionamentos_cache WHERE chamado_id = ?",
            (int(chamado_id),),
        ).fetchone()
    if not row:
        return None
    try:
        atualizado = datetime.fromisoformat(str(row["atualizado_em"]))
        if atualizado.tzinfo is None:
            atualizado = atualizado.replace(tzinfo=timezone.utc)
        estado = _norm(row["estado"])
        ttl = timedelta(
            minutes=CACHE_MINUTOS_ABERTO
            if estado not in {"CONCLUIDO", "REJEITADA", "FECHADO", "RESOLVIDO"}
            else CACHE_HORAS_HISTORICO * 60
        )
        if _agora_utc() - atualizado > ttl:
            return None
        return json.loads(row["payload_json"])
    except Exception:
        return None


def _cache_obter_stale(chamado_id: int) -> dict | None:
    """Retorna a última cópia mesmo expirada, para contingência."""
    _inicializar_cache()
    with conectar() as conn:
        row = conn.execute(
            "SELECT payload_json FROM contexto_relacionamentos_cache WHERE chamado_id = ?",
            (int(chamado_id),),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload_json"])
    except Exception:
        return None

def _cache_salvar(chamado_id: int, issue: dict) -> None:
    _inicializar_cache()
    estado = ((issue.get("status") or {}).get("name") or "")
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO contexto_relacionamentos_cache(chamado_id, payload_json, estado, atualizado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chamado_id) DO UPDATE SET
                payload_json=excluded.payload_json,
                estado=excluded.estado,
                atualizado_em=excluded.atualizado_em
            """,
            (
                int(chamado_id),
                json.dumps(issue, ensure_ascii=False, default=str),
                estado,
                _agora_utc().isoformat(timespec="seconds"),
            ),
        )


def _buscar_issue(chamado_id: int, *, force: bool = False) -> dict:
    chamado_id = int(chamado_id)
    if not force:
        cached = _cache_obter(chamado_id)
        if cached:
            return cached

    # Lock compartilhado por chamado: duas sessões não consultam o mesmo histórico.
    chave_lock = f"ednna:issue_contexto:{chamado_id}"
    dono = f"ctx:{chamado_id}:{id(object())}"
    if not painel_adquirir_lock(chave_lock, dono, ttl_seconds=90):
        stale = _cache_obter_stale(chamado_id)
        if stale:
            print(f"[EDNNA] Contexto histórico | #{chamado_id} em atualização por outra sessão | usando cache", flush=True)
            return stale
        # Sem cache, evita duplicar a consulta externa; falha rápido para a UI.
        raise RuntimeError(f"Contexto do chamado #{chamado_id} já está sendo atualizado por outra sessão.")

    try:
        # Outra sessão pode ter preenchido o cache antes de adquirirmos o lock.
        if not force:
            cached = _cache_obter(chamado_id)
            if cached:
                return cached
        try:
            issue = buscar_detalhes_chamado(
                chamado_id,
                incluir_journals=True,
                incluir_relacoes=True,
            )
            _cache_salvar(chamado_id, issue)
            return issue
        except Exception:
            stale = _cache_obter_stale(chamado_id)
            if stale:
                print(f"[EDNNA] Contexto histórico | Redmine indisponível para #{chamado_id} | usando cache anterior", flush=True)
                return stale
            raise
    finally:
        painel_liberar_lock(chave_lock, dono)


def _ids_relacionados(issue: dict) -> list[int]:
    atual = int(issue.get("id") or 0)
    ids: set[int] = set()
    for rel in issue.get("relations", []) or []:
        a = int(rel.get("issue_id") or 0)
        b = int(rel.get("issue_to_id") or 0)
        outro = b if a == atual else a if b == atual else 0
        if outro:
            ids.add(outro)
    return sorted(ids)


def _texto_issue(issue: dict) -> str:
    partes = [
        issue.get("subject", ""),
        issue.get("description", ""),
        ((issue.get("tracker") or {}).get("name") or ""),
    ]
    for journal in issue.get("journals", []) or []:
        notas = journal.get("notes") or ""
        if notas:
            partes.append(notas)
    return "\n".join(str(x) for x in partes if x)


def _players_no_texto(texto: str) -> list[str]:
    n = _norm(texto)
    encontrados: list[str] = []
    for player, aliases in PLAYER_ALIASES.items():
        if any(re.search(rf"(?<![A-Z0-9]){re.escape(_norm(alias))}(?![A-Z0-9])", n) for alias in aliases):
            encontrados.append(player)
    return encontrados


def _players_issue(issue: dict) -> list[str]:
    # Assunto/descrição têm prioridade. Origem traduzida complementa.
    texto = "\n".join([
        str(issue.get("subject") or ""),
        str(issue.get("description") or ""),
    ])
    players = set(_players_no_texto(texto))
    try:
        linha = issue_para_linha(issue)
        players.update(_players_no_texto(str(linha.get("Origem") or "")))
    except Exception:
        pass
    return sorted(players)


def _tipo_evento(issue: dict) -> str:
    texto = _norm(" ".join([
        str((issue.get("tracker") or {}).get("name") or ""),
        str(issue.get("subject") or ""),
        str(issue.get("description") or ""),
    ]))
    if any(x in texto for x in ("CANCELAR TRAFEGO", "CANCELAMENTO DE TRAFEGO", "CANCELAMENTO TRAFEGO", "EXCLUIR E INATIVAR")):
        return "CANCELAMENTO"
    if "INCLUSAO" in texto:
        return "INCLUSAO"
    if "ABERTURA RELACIONAMENTO" in texto or re.search(r"\bAR\b", texto):
        return "ABERTURA"
    if "IMPORTACAO DE ARQUIVOS" in texto or "IMPLANTACAO" in texto:
        return "IMPLANTACAO"
    if any(x in texto for x in ("FALTA DE ARQUIVO", "FALTA ARQUIVO", "ARQUIVO FALTANTE", "NAO RECEBIMENTO", "NÃO RECEBIMENTO")):
        return "FALTA_ARQUIVO"
    if any(x in texto for x in ("ALTERACAO", "ALTERAÇÃO", "DOMICILIO BANCARIO", "DOMICÍLIO BANCÁRIO")):
        return "ALTERACAO"
    return "OUTRO"


def _data_evento(issue: dict) -> str:
    return str(issue.get("closed_on") or issue.get("updated_on") or issue.get("created_on") or "")


def _status_fechado(issue: dict) -> bool:
    status = _norm((issue.get("status") or {}).get("name"))
    return bool(issue.get("closed_on")) or status in {"CONCLUIDO", "FECHADO", "RESOLVIDO", "REJEITADA"}


def _eh_blueprint_raiz(issue: dict) -> bool:
    tracker = _norm((issue.get("tracker") or {}).get("name"))
    assunto = _norm(issue.get("subject"))
    projeto = _norm((issue.get("project") or {}).get("name"))
    return (
        "NOVO CLIENTE" in tracker
        or "NOVO CLIENTE" in assunto
        or ("BLUEPRINT" in projeto and "NOVO CLIENTE" in tracker)
    )


def _resumo_issue(issue: dict) -> dict:
    return {
        "id": int(issue.get("id") or 0),
        "assunto": str(issue.get("subject") or ""),
        "tipo": str((issue.get("tracker") or {}).get("name") or ""),
        "estado": str((issue.get("status") or {}).get("name") or ""),
        "projeto": str((issue.get("project") or {}).get("name") or ""),
        "evento": _tipo_evento(issue),
        "players": _players_issue(issue),
        "data": _data_evento(issue),
    }


def analisar_contexto_cancelamento(chamado_id: int, *, force: bool = False) -> dict:
    """Reconstrói, em modo somente leitura, o contexto histórico de um cancelamento."""
    raiz = _buscar_issue(chamado_id, force=force)
    texto_raiz = _texto_issue(raiz)
    players_alvo = _players_no_texto(texto_raiz)
    escopo = "TOTAL" if len(players_alvo) > 1 or "TODO" in _norm(texto_raiz) else "PLAYER"

    # 1) relações diretas do cancelamento; procura a raiz Blueprint/Novo Cliente.
    diretos: dict[int, dict] = {}
    blueprint: dict | None = None
    for rid in _ids_relacionados(raiz):
        try:
            issue = _buscar_issue(rid, force=force)
            diretos[rid] = issue
            if blueprint is None and _eh_blueprint_raiz(issue):
                blueprint = issue
        except Exception as exc:
            print(f"[EDNNA] Contexto histórico | falha relação direta #{rid}: {exc}", flush=True)

    # 2) se houver Blueprint, percorre suas relações; senão usa relações diretas.
    universo: dict[int, dict] = {int(raiz.get("id") or chamado_id): raiz, **diretos}
    if blueprint:
        universo[int(blueprint.get("id") or 0)] = blueprint
        for rid in _ids_relacionados(blueprint):
            if rid == int(chamado_id) or rid in universo:
                continue
            try:
                universo[rid] = _buscar_issue(rid, force=force)
            except Exception as exc:
                print(f"[EDNNA] Contexto histórico | falha relação Blueprint #{rid}: {exc}", flush=True)

    eventos_por_player: dict[str, list[dict]] = {}
    for iid, issue in universo.items():
        if iid == int(chamado_id):
            continue
        if _eh_blueprint_raiz(issue):
            continue
        resumo = _resumo_issue(issue)
        if resumo["evento"] == "OUTRO":
            continue
        for player in resumo["players"]:
            eventos_por_player.setdefault(player, []).append(resumo)

    # Se o cancelamento declara players, eles são o universo alvo.
    # Caso contrário, usamos os players reconstruídos no histórico.
    players_considerados = players_alvo or sorted(eventos_por_player)
    relacionamentos: list[dict] = []

    for player in players_considerados:
        eventos = sorted(eventos_por_player.get(player, []), key=lambda x: x.get("data") or "")
        cancelamentos = [e for e in eventos if e["evento"] == "CANCELAMENTO" and _norm(e["estado"]) in {"CONCLUIDO", "FECHADO", "RESOLVIDO"}]
        positivos = [e for e in eventos if e["evento"] in {"ABERTURA", "IMPLANTACAO", "INCLUSAO"}]

        ultimo_cancel = cancelamentos[-1] if cancelamentos else None
        posteriores = []
        if ultimo_cancel:
            posteriores = [e for e in positivos if (e.get("data") or "") > (ultimo_cancel.get("data") or "")]

        if ultimo_cancel and not posteriores:
            estado = "CANCELADO_CONFIRMADO"
        elif positivos:
            estado = "RELACIONAMENTO_LOCALIZADO"
        else:
            estado = "DADOS_INSUFICIENTES"

        fontes = sorted({int(e["id"]) for e in eventos if e.get("id")})
        relacionamentos.append({
            "player": player,
            "estado": estado,
            "fontes": fontes,
            "eventos": eventos,
            "cancelamento_anterior": int(ultimo_cancel["id"]) if ultimo_cancel else None,
        })

    return {
        "chamado_id": int(chamado_id),
        "cliente": str(issue_para_linha(raiz).get("Clientes") or ""),
        "assunto": str(raiz.get("subject") or ""),
        "escopo": escopo,
        "blueprint_id": int(blueprint.get("id") or 0) if blueprint else None,
        "players_alvo": players_alvo,
        "relacionamentos": relacionamentos,
        "chamados_consultados": len(universo),
        "modo": "SOMENTE_LEITURA",
    }


def buscar_issue_contexto(chamado_id: int, *, force: bool = False) -> dict:
    """Expõe a leitura cacheada usada pelo planejador, sem alterar o Redmine."""
    return _buscar_issue(int(chamado_id), force=force)


def analisar_contexto_operacional(chamado_id: int, *, force: bool = False) -> dict:
    """Reconstrói o contexto operacional do chamado usando o BP/Novo Cliente como raiz histórica.

    A fonte continua sendo o Redmine. O contexto é somente leitura e preserva a
    proveniência de cada evento. BP é a raiz histórica; eventos posteriores
    determinam o estado conhecido mais recente do relacionamento.
    """
    raiz = _buscar_issue(chamado_id, force=force)

    diretos: dict[int, dict] = {}
    blueprint: dict | None = raiz if _eh_blueprint_raiz(raiz) else None
    for rid in _ids_relacionados(raiz):
        try:
            issue = _buscar_issue(rid, force=force)
            diretos[rid] = issue
            if blueprint is None and _eh_blueprint_raiz(issue):
                blueprint = issue
        except Exception as exc:
            print(f"[EDNNA] Contexto operacional | falha relação direta #{rid}: {exc}", flush=True)

    universo: dict[int, dict] = {int(raiz.get("id") or chamado_id): raiz, **diretos}
    if blueprint:
        bid = int(blueprint.get("id") or 0)
        if bid:
            universo[bid] = blueprint
        for rid in _ids_relacionados(blueprint):
            if rid in universo:
                continue
            try:
                universo[rid] = _buscar_issue(rid, force=force)
            except Exception as exc:
                print(f"[EDNNA] Contexto operacional | falha relação BP #{rid}: {exc}", flush=True)

    eventos: list[dict] = []
    eventos_por_player: dict[str, list[dict]] = {}
    for iid, issue in universo.items():
        if _eh_blueprint_raiz(issue):
            continue
        resumo = _resumo_issue(issue)
        if resumo["evento"] == "OUTRO" and iid != int(chamado_id):
            continue
        eventos.append(resumo)
        for player in resumo.get("players", []) or []:
            eventos_por_player.setdefault(player, []).append(resumo)

    relacionamentos: list[dict] = []
    for player in sorted(eventos_por_player):
        evs = sorted(eventos_por_player[player], key=lambda x: x.get("data") or "")
        cancelamentos = [e for e in evs if e["evento"] == "CANCELAMENTO" and _norm(e["estado"]) in {"CONCLUIDO", "FECHADO", "RESOLVIDO"}]
        positivos = [e for e in evs if e["evento"] in {"ABERTURA", "IMPLANTACAO", "INCLUSAO", "ALTERACAO"}]
        ultimo_cancel = cancelamentos[-1] if cancelamentos else None
        posteriores = [e for e in positivos if ultimo_cancel and (e.get("data") or "") > (ultimo_cancel.get("data") or "")]
        if ultimo_cancel and not posteriores:
            estado = "CANCELADO_CONFIRMADO"
        elif positivos:
            estado = "RELACIONAMENTO_LOCALIZADO"
        else:
            estado = "DADOS_INSUFICIENTES"
        relacionamentos.append({
            "player": player, "estado": estado,
            "fontes": sorted({int(e["id"]) for e in evs if e.get("id")}),
            "eventos": evs,
            "cancelamento_anterior": int(ultimo_cancel["id"]) if ultimo_cancel else None,
        })

    linha_raiz = issue_para_linha(raiz)
    return {
        "chamado_id": int(chamado_id),
        "cliente": str(linha_raiz.get("Clientes") or ""),
        "assunto": str(raiz.get("subject") or ""),
        "tipo": str((raiz.get("tracker") or {}).get("name") or ""),
        "estado": str((raiz.get("status") or {}).get("name") or ""),
        "evento_atual": _tipo_evento(raiz),
        "blueprint_id": int(blueprint.get("id") or 0) if blueprint else None,
        "relacionamentos": relacionamentos,
        "eventos": sorted(eventos, key=lambda x: x.get("data") or ""),
        "chamados_consultados": len(universo),
        "modo": "SOMENTE_LEITURA",
    }
