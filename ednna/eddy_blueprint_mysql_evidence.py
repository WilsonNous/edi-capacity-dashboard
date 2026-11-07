"""Reuse already synchronized MySQL Blueprint evidence before Redmine discovery.

Never infer CNPJ from a random establishment. A BP is a verified source only
when its stored issue is identified as a Blueprint and belongs to the client.
"""
from __future__ import annotations

import json

from ednna.mysql_storage import connect


def _decode(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            value = json.loads(payload)
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def candidatos_bp_mysql(cliente):
    """Find Blueprint IDs from existing participants and issue snapshots.

    Results are candidates, not proof of a single legal entity. A closed BP
    can be present in the participants table even if absent from open issues.
    """
    from ednna.mysql_blueprint_participants import _eh_bp_redmine

    ids = set()
    stored = {}
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT chamado_id FROM eddy_blueprint_participants
                   WHERE cliente=%s AND ativo=1""", (cliente,))
            ids.update(int(row[0]) for row in cursor.fetchall() if row[0])
            cursor.execute(
                """SELECT id, payload_json FROM eddy_chamados
                   WHERE cliente=%s""", (cliente,))
            for issue_id, payload in cursor.fetchall():
                issue = _decode(payload)
                if (int(issue.get("id") or 0) == int(issue_id)
                        and _eh_bp_redmine(issue)):
                    ids.add(int(issue_id))
                    stored[int(issue_id)] = issue
    return ids, stored


def identidade_de_bp_mysql(cliente):
    """Return a resolved identity only when all known BP candidates agree.

    Missing BP payloads are not evidence of missing CNPJ. They can still
    guide a targeted Redmine fetch outside the offline planning path.
    """
    from ednna.eddy_client_identity import cnpjs_blueprint
    from ednna.eddy_blueprint_identity_evidence import consultar_cliente
    persisted = consultar_cliente(cliente)
    ids, stored = candidatos_bp_mysql(cliente)
    if persisted["blueprint_ids"]:
        known = set(persisted["cnpjs"])
        if len(known) == 1 and not (ids - set(persisted["blueprint_ids"]) - stored.keys()):
            return {"estado": "RESOLVIDO", "cliente": cliente,
                    "cnpj": next(iter(known)), "blueprint_id": min(persisted["blueprint_ids"]),
                    "origem": "MYSQL_BP", "quantidade_cnpjs": 1}
        if len(known) > 1:
            return {"estado": "CNPJ_AMBIGUO", "cnpj": None,
                    "blueprint_ids": sorted(set(ids) | set(persisted["blueprint_ids"]))}
    if not ids:
        return {"estado": "SEM_BP_MYSQL", "cnpj": None}
    # A participant-only BP has no reliable CNPJ in the contacts table.
    if ids - stored.keys():
        return {"estado": "BP_MYSQL_SEM_IDENTIFICACAO", "cnpj": None,
                "blueprint_ids": sorted(ids)}
    cnpjs = set()
    for bp in stored.values():
        cnpjs.update(cnpjs_blueprint(bp))
    if len(cnpjs) != 1:
        return {"estado": "CNPJ_AMBIGUO" if cnpjs else "BP_MYSQL_SEM_IDENTIFICACAO",
                "cnpj": None, "blueprint_ids": sorted(ids)}
    return {"estado": "RESOLVIDO", "cliente": cliente,
            "cnpj": next(iter(cnpjs)), "blueprint_id": min(ids),
            "origem": "MYSQL_BP", "quantidade_cnpjs": 1}
