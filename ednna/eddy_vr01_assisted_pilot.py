"""Assisted VR01 pilot: verified owner capture, durable ledger, no external effects.

This module never writes to Redmine, sends mail, or changes ticket assignments.
The caller supplies a freshly fetched Redmine issue; no network call occurs here.
"""
from __future__ import annotations

from ednna.eddy_ownership import Ownership, OwnershipError, OwnershipState
from ednna.eddy_ownership_mysql import load_ownership, save_transition
from ednna.eddy_vr_original_owner import capturar_responsavel_original, verificar_devolucao

PILOT_ISSUE_ID = 49227


def capturar_piloto_assistido(issue: dict, *, automation_user_id: int) -> dict:
    """Persist original ownership once, before any external takeover.

    Concurrent duplicate captures fail closed through the existing InnoDB ledger.
    Existing records are never overwritten or silently re-captured.
    """
    if not isinstance(issue, dict) or type(issue.get("id")) is not int or issue["id"] != PILOT_ISSUE_ID:
        raise OwnershipError("PILOTO_FORA_ESCOPO")
    if type(automation_user_id) is not int or automation_user_id <= 0:
        raise OwnershipError("AUTOMACAO_NAO_IDENTIFICADA")
    captured = capturar_responsavel_original(issue, automation_user_id)
    if load_ownership(PILOT_ISSUE_ID) is not None:
        raise OwnershipError("RESPONSAVEL_JA_CAPTURADO_REVISAR")
    item = Ownership(
        issue_id=captured["chamado_id"],
        original_assignee_id=captured["original_owner_id"],
        eddy_assignee_id=automation_user_id,
        version=captured["captured_updated_on"],
        state=OwnershipState.CAPTURED,
    )
    revision = save_transition(item, expected_revision=None)
    return {
        "estado": "CAPTURADO_AUDITADO",
        "chamado_id": item.issue_id,
        "original_owner_id": item.original_assignee_id,
        "redmine_updated_on": item.version,
        "revision": revision,
        "efeitos_externos": 0,
    }


def avaliar_devolucao_assistida(issue: dict) -> dict:
    """Read-only handoff assessment against the persisted original owner.

    A matching assignee alone is insufficient: the ledger must show RETURNED
    with evidence, otherwise the result is blocked for human review.
    """
    if not isinstance(issue, dict) or type(issue.get("id")) is not int or issue["id"] != PILOT_ISSUE_ID:
        return {"confirmado": False, "motivo": "PILOTO_FORA_ESCOPO"}
    stored = load_ownership(PILOT_ISSUE_ID)
    if stored is None:
        return {"confirmado": False, "motivo": "RESPONSAVEL_NAO_PERSISTIDO"}
    item, revision = stored
    if item.state != OwnershipState.RETURNED or not item.last_evidence:
        return {"confirmado": False, "motivo": "DEVOLUCAO_NAO_AUDITADA", "revision": revision}
    result = verificar_devolucao(issue, {
        "chamado_id": item.issue_id,
        "original_owner_id": item.original_assignee_id,
    })
    return {**result, "revision": revision}
