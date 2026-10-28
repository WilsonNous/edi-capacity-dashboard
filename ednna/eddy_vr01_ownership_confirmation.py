"""Read-only authoritative confirmation of VR01 ownership transitions.

This adapter accepts a fresh Redmine issue supplied by the caller; it never
fetches or modifies Redmine and never sends messages. A pending transition
remains pending on missing/ambiguous evidence.
"""
from __future__ import annotations

from ednna.eddy_ownership import (
    OwnershipError, OwnershipState, confirm_claim, confirm_return,
)
from ednna.eddy_ownership_mysql import load_ownership, save_transition

PILOT_ISSUE_ID = 49227


def confirmar_atribuicao_observada(issue: dict, *, evidencia: str) -> dict:
    """Confirm an already performed external assignment, or fail closed.

    The caller is responsible for obtaining a fresh authoritative issue
    response *after* the externally approved Redmine write.
    """
    if not isinstance(issue, dict) or type(issue.get("id")) is not int or issue["id"] != PILOT_ISSUE_ID:
        raise OwnershipError("PILOTO_FORA_ESCOPO")
    if not isinstance(evidencia, str) or not evidencia.strip():
        raise OwnershipError("EVIDENCIA_AUSENTE")
    assignee = issue.get("assigned_to")
    if not isinstance(assignee, dict) or type(assignee.get("id")) is not int or assignee["id"] <= 0:
        raise OwnershipError("RESPONSAVEL_NAO_CONFIRMADO")
    version = issue.get("updated_on")
    if not isinstance(version, str) or not version.strip():
        raise OwnershipError("VERSAO_REDMINE_AUSENTE")
    stored = load_ownership(PILOT_ISSUE_ID)
    if stored is None:
        raise OwnershipError("RESPONSAVEL_ORIGINAL_NAO_PERSISTIDO")
    item, revision = stored
    if item.issue_id != PILOT_ISSUE_ID:
        raise OwnershipError("LEDGER_DIVERGENTE")
    if item.state == OwnershipState.CLAIM_PENDING:
        target = item.eddy_assignee_id
        confirm = confirm_claim
    elif item.state == OwnershipState.RETURN_PENDING:
        target = item.original_assignee_id
        confirm = confirm_return
    else:
        raise OwnershipError("NENHUMA_ATRIBUICAO_PENDENTE")
    if assignee["id"] != target:
        # Do not overwrite a pending intent on ambiguous observations.
        raise OwnershipError("ATRIBUICAO_NAO_CONFIRMADA")
    if version.strip() == item.version:
        raise OwnershipError("VERSAO_NAO_AVANCOU")
    confirmed = confirm(
        item, redmine_assignee_id=assignee["id"],
        new_version=version.strip(), evidence=evidencia.strip(),
    )
    new_revision = save_transition(confirmed, expected_revision=revision)
    return {
        "estado": confirmed.state.value,
        "chamado_id": PILOT_ISSUE_ID,
        "responsavel_original_id": item.original_assignee_id,
        "responsavel_confirmado_id": assignee["id"],
        "revision": new_revision,
        "redmine_updated_on_confirmado": version.strip(),
        "redmine_consultas": 0,
        "redmine_escritas": 0,
        "envios_realizados": 0,
    }
