"""Read-only source adapter: Redmine panel snapshot -> EDDY MySQL.

Explicit invocation only. Does not initialize operational SQLite or send anything.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ednna.mysql_snapshot_repository import CHAMADO_FIELDS, _upsert
from ednna.mysql_storage import connect
from time import perf_counter

BR = ZoneInfo("America/Sao_Paulo")


def extrair_snapshot_painel(caminho: str) -> tuple[list[dict], str]:
    path = Path(caminho)
    if not path.is_file():
        raise FileNotFoundError(f"Snapshot do Painel não encontrado: {path}")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute(
            """SELECT payload_json, atualizado_em FROM snapshots
               WHERE chave LIKE '%|status=open|%'
               ORDER BY atualizado_em DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise ValueError("Nenhum snapshot status=open no Painel")
    items = json.loads(row[0])
    if not isinstance(items, list):
        raise ValueError("Payload do snapshot não é uma lista")
    return items, str(row[1] or "")


def _nome(value) -> str:
    return str((value or {}).get("name") or "") if isinstance(value, dict) else ""


def converter_issue(issue: dict, sincronizado_em: str) -> dict:
    issue_id = issue.get("id")
    if isinstance(issue_id, bool) or not str(issue_id).isdigit() or int(issue_id) <= 0:
        raise ValueError("ID Redmine inválido")
    fields = {str(x.get("id")): x.get("value") for x in issue.get("custom_fields", []) if isinstance(x, dict)}
    return {
        "id": int(issue_id),
        "cliente": str(fields.get("1") or ""),
        "origem": str(fields.get("5") or ""),
        "responsavel": _nome(issue.get("assigned_to")),
        "projeto": _nome(issue.get("project")),
        "tipo": _nome(issue.get("tracker")),
        "estado": _nome(issue.get("status")),
        "prioridade": _nome(issue.get("priority")),
        "assunto": str(issue.get("subject") or ""),
        "criado_em": str(issue.get("created_on") or ""),
        "alterado_em": str(issue.get("updated_on") or ""),
        "tempo_aberto_dias": None,
        "payload_json": issue,
        "sincronizado_em": sincronizado_em,
    }


def importar_snapshot_painel_mysql(caminho: str, *, limite: int = 50, aplicar: bool = False) -> dict:
    if not 1 <= limite <= 500:
        raise ValueError("limite deve estar entre 1 e 500")
    items, atualizado_em = extrair_snapshot_painel(caminho)
    if not atualizado_em:
        raise ValueError("Snapshot sem data: não importar")
    try:
        stamp = datetime.fromisoformat(atualizado_em.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=BR)
        age = (datetime.now(BR) - stamp.astimezone(BR)).total_seconds()
    except ValueError as exc:
        raise ValueError("Data de snapshot inválida") from exc
    if age < -300 or age > 3600:
        raise ValueError("Snapshot fora da janela de 60 minutos; atualizar Redmine antes de importar")
    selected = items[:limite]
    converted = [converter_issue(issue, atualizado_em) for issue in selected]
    ids = [row["id"] for row in converted]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs duplicados no snapshot")
    duracao = 0.0
    if aplicar and converted:
        inicio = perf_counter()
        # Uma conexão TLS por importação; transações atômicas em lotes de 50.
        # Uma falha interrompe a carga, sem confirmar o lote defeituoso.
        for offset in range(0, len(converted), 50):
            with connect() as conn:
                with conn.cursor() as cursor:
                    for row in converted[offset:offset + 50]:
                        # The general panel importer must not discard the
                        # journal-complete VR snapshot written by the dedicated
                        # Redmine worker. Both writers share eddy_chamados.
                        cursor.execute(
                            "SELECT payload_json FROM eddy_chamados WHERE id=%s FOR UPDATE",
                            (row["id"],),
                        )
                        previous_row = cursor.fetchone()
                        if previous_row and previous_row[0]:
                            try:
                                previous = json.loads(previous_row[0]) if isinstance(previous_row[0], str) else previous_row[0]
                            except (ValueError, TypeError):
                                previous = None
                            if (
                                isinstance(previous, dict)
                                and previous.get("_eddy_journals_completos") is True
                                and str(previous.get("updated_on") or "") == str(row["payload_json"].get("updated_on") or "")
                            ):
                                row = {**row, "payload_json": previous}
                        _upsert(cursor, 'eddy_chamados', CHAMADO_FIELDS, row)
        duracao = round(perf_counter() - inicio, 3)
    return {
        "origem": "painel.db/status=open",
        "snapshot_em": atualizado_em,
        "total_origem": len(items),
        "selecionados": len(converted),
        "gravados": len(converted) if aplicar else 0,
        "duracao_gravacao_s": duracao,
        "lote": 50,
        "modo": "apply" if aplicar else "dry-run",
        "journals": "não importados",
        "automacoes": "suspensas",
    }
