"""Fail-closed, idempotent VR01 pilot ledger bootstrap.

Only a fresh, active Redmine preflight may authorize creation of a local
MySQL lifecycle row. No Graph sends, Redmine writes, or phase advances.
"""
from __future__ import annotations

from ednna import eddy_vr01_integrated as pilot


def inicializar_piloto_local() -> dict:
    row = pilot._load()
    if row is not None:
        # Existing audit rows are never reset, overwritten or auto-advanced.
        return {"chamado_id": pilot.ISSUE_ID, "estado": "JA_INICIALIZADO",
                "fase": row["fase"], "execucao_externa": False}
    eddy_id = pilot._identity()
    # The remote check is mandatory for the *initial* local write only.
    issue = pilot._read_issue(pilot.ISSUE_ID)
    if pilot._assignee(issue) != pilot.ORIGINAL_OWNER_ID:
        return {"chamado_id": pilot.ISSUE_ID,
                "estado": "BLOQUEADO_RESPONSAVEL_ORIGINAL",
                "execucao_externa": False}
    if not issue.get("updated_on"):
        return {"chamado_id": pilot.ISSUE_ID,
                "estado": "BLOQUEADO_VERSAO_REDMINE",
                "execucao_externa": False}
    row = pilot._initialize(issue, eddy_id)
    if not row or row["original_owner_id"] != pilot.ORIGINAL_OWNER_ID or row["eddy_owner_id"] != eddy_id:
        return {"chamado_id": pilot.ISSUE_ID,
                "estado": "BLOQUEADO_IDENTIDADE_MYSQL",
                "execucao_externa": False}
    return {"chamado_id": pilot.ISSUE_ID,
            "estado": "INICIALIZADO_MYSQL",
            "fase": row["fase"], "execucao_externa": False}
