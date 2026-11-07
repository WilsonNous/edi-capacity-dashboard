"""Durable Blueprint evidence extracted from Redmine attachments into MySQL.

The operational VR01 path reads this table only. Remote discovery is performed
by the separate enrichment worker, not by every five-minute cycle.
"""
from __future__ import annotations

import json
from ednna.mysql_storage import connect

DDL = """CREATE TABLE IF NOT EXISTS eddy_blueprint_identity_evidence (
    blueprint_id BIGINT NOT NULL PRIMARY KEY,
    cliente VARCHAR(255) NOT NULL,
    cnpjs_json TEXT NOT NULL,
    fonte VARCHAR(64) NOT NULL,
    atualizado_em DATETIME NOT NULL,
    KEY idx_bp_identity_cliente (cliente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def preparar():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)


def registrar_bp(cliente, blueprint_id, cnpjs, *, fonte="REDMINE_BLUEPRINT"):
    """Persist all distinct CNPJs, including ambiguous multi-establishment BPs."""
    digits = sorted({str(x) for x in cnpjs if str(x).isdigit() and len(str(x)) == 14})
    preparar()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO eddy_blueprint_identity_evidence
                   (blueprint_id, cliente, cnpjs_json, fonte, atualizado_em)
                   VALUES (%s,%s,%s,%s,UTC_TIMESTAMP())
                   ON DUPLICATE KEY UPDATE cliente=VALUES(cliente),
                   cnpjs_json=VALUES(cnpjs_json), fonte=VALUES(fonte),
                   atualizado_em=VALUES(atualizado_em)""",
                (int(blueprint_id), str(cliente).strip(),
                 json.dumps(digits), fonte))
    return {"blueprint_id": int(blueprint_id), "quantidade_cnpjs": len(digits)}


def consultar_cliente(cliente):
    preparar()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT blueprint_id, cnpjs_json FROM eddy_blueprint_identity_evidence
                   WHERE cliente=%s ORDER BY blueprint_id""", (cliente,))
            rows = cur.fetchall()
    found = set()
    ids = []
    for bp_id, raw in rows:
        ids.append(int(bp_id))
        found.update(json.loads(raw))
    return {"blueprint_ids": ids, "cnpjs": found}
