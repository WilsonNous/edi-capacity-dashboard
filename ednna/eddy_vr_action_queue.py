"""VR01 durable action planning. No automatic outbound transport.

A pending action is an intent, not evidence of a sent email. The unique
(issue, action, source Redmine version) key avoids duplicate proposals.
Actions are never requeued for a terminal ticket; dispatch requires a
separate provider-confirmed, idempotent sender and a fresh Redmine preflight.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from ednna.mysql_storage import connect
from ednna.eddy_vr_continuity import decidir_continuidade_vr

DDL = """CREATE TABLE IF NOT EXISTS eddy_vr01_action_queue (
    action_key CHAR(64) NOT NULL PRIMARY KEY,
    chamado_id BIGINT NOT NULL,
    redmine_updated_on VARCHAR(48) NOT NULL,
    etapa VARCHAR(96) NOT NULL,
    acao VARCHAR(96) NOT NULL,
    destino VARCHAR(96) NULL,
    situacao VARCHAR(32) NOT NULL DEFAULT 'PENDENTE',
    criado_em TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_vr01_pending (situacao, criado_em),
    KEY idx_vr01_issue (chamado_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""

def criar_intencao(issue: dict, journals: list[dict]) -> dict:
    if issue.get("_eddy_journals_completos") is not True:
        return {"situacao": "BLOQUEADO_HISTORICO_INCOMPLETO"}
    version = str(issue.get("updated_on") or "")
    if not version:
        return {"situacao": "BLOQUEADO_VERSAO_AUSENTE"}
    decision = decidir_continuidade_vr(issue, journals)
    if decision["acao"] == "NENHUMA":
        return {"situacao": "TERMINAL"}
    action = decision["acao"]
    # Actions with unresolved recipient or ambiguous evidence are not dispatchable.
    key = hashlib.sha256(f'VR01:{issue["id"]}:{version}:{action}'.encode()).hexdigest()
    return {"situacao": "PENDENTE", "action_key": key, "chamado_id": int(issue["id"]),
            "redmine_updated_on": version, "etapa": decision["etapa"],
            "acao": action, "destino": decision.get("destino")}

def registrar_intencoes(snapshots: list[tuple[dict, list[dict]]]) -> dict:
    """Store idempotent intents. Never send emails or update Redmine."""
    planned = [criar_intencao(issue, journals) for issue, journals in snapshots]
    actionable = [x for x in planned if x["situacao"] == "PENDENTE"]
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)
            for item in actionable:
                cursor.execute(
                    """INSERT IGNORE INTO eddy_vr01_action_queue
                       (action_key, chamado_id, redmine_updated_on, etapa, acao, destino)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    tuple(item[k] for k in ("action_key", "chamado_id", "redmine_updated_on",
                                            "etapa", "acao", "destino"))
                )
    return {"avaliados": len(planned), "intencoes": len(actionable),
            "bloqueados": sum(x["situacao"].startswith("BLOQUEADO") for x in planned),
            "envios_realizados": 0, "redmine_escritas": 0}
