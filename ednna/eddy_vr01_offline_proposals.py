"""Durable, non-dispatchable VR01 proposals built exclusively from MySQL snapshots.

OBSERVACIONAL is deliberately distinct from PENDENTE: the external dispatcher
must never consume an offline proposal as an authorized send.
"""
from __future__ import annotations

import json

from ednna.eddy_vr_action_queue import DDL, criar_intencao
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.mysql_storage import connect

PILOT_IDS = (50318, 49119, 48786, 50120)


def preparar_intencoes_locais(ids=PILOT_IDS) -> dict:
    planned = []
    blocked = []
    for issue_id in ids:
        stored = carregar_snapshot(issue_id)
        if not stored:
            blocked.append({"chamado_id": issue_id, "motivo": "SNAPSHOT_AUSENTE"})
            continue
        payload = stored["chamado"].get("payload_json")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError):
                payload = None
        if not isinstance(payload, dict) or payload.get("id") != issue_id:
            blocked.append({"chamado_id": issue_id, "motivo": "SNAPSHOT_INVALIDO"})
            continue
        journals = [
            {"notes": row.get("notas") or "", "created_on": row.get("criado_em")}
            for row in stored.get("journals", [])
        ]
        proposal = criar_intencao(payload, journals)
        if proposal["situacao"] == "PENDENTE":
            planned.append(proposal)
        else:
            blocked.append({"chamado_id": issue_id, "motivo": proposal["situacao"]})
    # A DB error must fail the cycle: do not report persisted intents on failure.
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)
            for item in planned:
                cursor.execute(
                    """INSERT IGNORE INTO eddy_vr01_action_queue
                    (action_key, chamado_id, redmine_updated_on, etapa, acao, destino, situacao)
                    VALUES (%s,%s,%s,%s,%s,%s,'OBSERVACIONAL')""",
                    tuple(item[k] for k in ("action_key", "chamado_id", "redmine_updated_on",
                                            "etapa", "acao", "destino")),
                )
    return {
        "estado": "PROPOSTAS_OBSERVACIONAIS_PERSISTIDAS",
        "avaliados": len(ids),
        "propostas": len(planned),
        "bloqueados": blocked,
        "situacao_fila": "OBSERVACIONAL",
        "acoes_externas_autorizadas": False,
        "envios_realizados": 0,
        "redmine_escritas": 0,
    }
