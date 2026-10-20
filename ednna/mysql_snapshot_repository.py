"""Opt-in MySQL snapshot repository; no external actions or SQLite migration.

Callers must bootstrap schema version 2 before writing. Journals require a
parent chamado. All writes are idempotent and transactional.
"""
from __future__ import annotations

import json
from typing import Any

from ednna.mysql_storage import connect


CHAMADO_FIELDS = (
    "id", "cliente", "origem", "responsavel", "projeto", "tipo", "estado",
    "prioridade", "assunto", "criado_em", "alterado_em",
    "tempo_aberto_dias", "payload_json", "sincronizado_em",
)
JOURNAL_FIELDS = (
    "id", "chamado_id", "autor", "criado_em", "notas",
    "detalhes_json", "sincronizado_em",
)


def _values(row: dict[str, Any], fields: tuple[str, ...]) -> tuple:
    if any(row.get(key) is None for key in ("id", "sincronizado_em")):
        raise ValueError("id and sincronizado_em are required")
    values = []
    for field in fields:
        value = row.get(field)
        if field.endswith("_json") and value is not None and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, default=str)
        values.append(value)
    return tuple(values)


def _upsert(cursor, table: str, fields: tuple[str, ...], row: dict) -> None:
    placeholders = ", ".join(["%s"] * len(fields))
    columns = ", ".join(fields)
    updates = ", ".join(
        f"{field}=VALUES({field})" for field in fields if field != "id"
    )
    cursor.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}",
        _values(row, fields),
    )


def salvar_snapshot(chamado: dict, journals: list[dict] | None = None) -> None:
    """Atomically upsert a Redmine issue and its journals; never send emails."""
    journals = journals or []
    chamado_id = chamado.get("id")
    if chamado_id is None:
        raise ValueError("chamado id required")
    for journal in journals:
        if journal.get("chamado_id") != chamado_id:
            raise ValueError("journal belongs to a different chamado")
    with connect() as conn:
        with conn.cursor() as cursor:
            # Generic issue-only refreshes must not erase a newer, journal-complete
            # Redmine snapshot used by rule engines for safe resume.
            incoming = chamado.get("payload_json") or {}
            if isinstance(incoming, str):
                try:
                    incoming = json.loads(incoming)
                except (TypeError, ValueError):
                    incoming = {}
            if not isinstance(incoming, dict) or incoming.get("_eddy_journals_completos") is not True:
                cursor.execute("SELECT payload_json FROM eddy_chamados WHERE id=%s FOR UPDATE", (chamado_id,))
                existing = cursor.fetchone()
                if existing and existing[0]:
                    try:
                        previous = json.loads(existing[0]) if isinstance(existing[0], str) else existing[0]
                    except (ValueError, TypeError):
                        previous = {}
                    if isinstance(previous, dict) and previous.get("_eddy_journals_completos") is True:
                        # Do not reuse a historical completeness marker for newer issue versions.
                        # Preserve old journal snapshot until the dedicated journal sync updates it.
                        if str(previous.get("updated_on") or "") == str(incoming.get("updated_on") or ""):
                            chamado = {**chamado, "payload_json": previous}
                        else:
                            incoming.pop("_eddy_journals_completos", None)
            _upsert(cursor, "eddy_chamados", CHAMADO_FIELDS, chamado)
            for journal in journals:
                _upsert(cursor, "eddy_journals", JOURNAL_FIELDS, journal)


def carregar_snapshot(chamado_id: int) -> dict | None:
    """Read a stored issue and journals without changing operational state."""
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT " + ", ".join(CHAMADO_FIELDS)
                + " FROM eddy_chamados WHERE id = %s", (chamado_id,),
            )
            issue = cursor.fetchone()
            if issue is None:
                return None
            cursor.execute(
                "SELECT " + ", ".join(JOURNAL_FIELDS)
                + " FROM eddy_journals WHERE chamado_id = %s ORDER BY id",
                (chamado_id,),
            )
            journals = cursor.fetchall()
    return {
        "chamado": dict(zip(CHAMADO_FIELDS, issue)),
        "journals": [dict(zip(JOURNAL_FIELDS, row)) for row in journals],
    }
