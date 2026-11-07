"""Durable, shared EDDY Blueprint identity cache (MySQL, no SQLite).

Identity changes slowly: keep resolved and unresolved discovery results for a
configurable period, while preserving provenance and multiple CNPJs.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from ednna.mysql_storage import connect

DDL = """CREATE TABLE IF NOT EXISTS eddy_client_identity (
    cliente VARCHAR(255) NOT NULL PRIMARY KEY,
    estado VARCHAR(64) NOT NULL,
    cnpj CHAR(14) NULL,
    blueprint_id BIGINT NULL,
    quantidade_cnpjs INT NOT NULL DEFAULT 0,
    atualizado_em DATETIME NOT NULL,
    KEY idx_eddy_identity_refresh (atualizado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def ttl_seconds():
    raw = os.getenv("EDDY_CLIENT_IDENTITY_TTL_SECONDS", "604800")
    try:
        return max(900, int(raw))
    except (TypeError, ValueError):
        return 604800


def preparar():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)


def consultar(cliente):
    """Return fresh cached result, or None. Do not turn DB errors into Redmine calls."""
    preparar()
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT estado, cnpj, blueprint_id, quantidade_cnpjs, atualizado_em
                   FROM eddy_client_identity WHERE cliente=%s""", (cliente,))
            row = cursor.fetchone()
    if not row:
        return None
    estado, cnpj, bp_id, quantidade, updated = row
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)
    if updated.tzinfo:
        updated = updated.astimezone(timezone.utc).replace(tzinfo=None)
    if datetime.now(timezone.utc).replace(tzinfo=None) - updated > timedelta(seconds=ttl_seconds()):
        return None
    result = {"estado": estado, "cnpj": cnpj, "origem": "MYSQL",
              "quantidade_cnpjs": int(quantidade or 0)}
    if bp_id is not None:
        result["blueprint_id"] = int(bp_id)
    if estado == "RESOLVIDO":
        result["cliente"] = cliente
    return result


def registrar(cliente, resultado):
    """Persist discovery only when it is a definite result, not a network failure."""
    estado = str(resultado.get("estado") or "")
    if estado not in {"RESOLVIDO", "BLUEPRINT_NAO_LOCALIZADO",
                      "CNPJ_NAO_LOCALIZADO_BP", "CNPJ_AMBIGUO"}:
        return False
    preparar()
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO eddy_client_identity
                   (cliente, estado, cnpj, blueprint_id, quantidade_cnpjs, atualizado_em)
                   VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP())
                   ON DUPLICATE KEY UPDATE estado=VALUES(estado),
                   cnpj=VALUES(cnpj), blueprint_id=VALUES(blueprint_id),
                   quantidade_cnpjs=VALUES(quantidade_cnpjs),
                   atualizado_em=VALUES(atualizado_em)""",
                (cliente, estado, resultado.get("cnpj"), resultado.get("blueprint_id"),
                 int(resultado.get("quantidade_cnpjs") or (1 if resultado.get("cnpj") else 0))))
    return True
