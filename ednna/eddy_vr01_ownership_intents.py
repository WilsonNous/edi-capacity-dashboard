"""VR01 supervised claim/return intentions, with no Redmine network or writes.

The caller must supply a freshly fetched issue; an external adapter executes
approved writes and then separately confirms them with authoritative evidence.
"""
from __future__ import annotations

from ednna.eddy_ownership import OwnershipError, OwnershipState, request_claim, request_return
from ednna.eddy_ownership_mysql import load_ownership, save_transition

PILOT_ISSUE_ID = 49227


def _verified(issue: dict, item) -> tuple[int, str]:
    if not isinstance(issue, dict) or type(issue.get("id")) is not int or issue["id"] != PILOT_ISSUE_ID:
        raise OwnershipError("PILOTO_FORA_ESCOPO")
    assignee = issue.get("assigned_to")
    if not isinstance(assignee, dict) or type(assignee.get("id")) is not int:
        raise OwnershipError("RESPONSAVEL_NAO_CONFIRMADO")
    version = str(issue.get("updated_on") or "").strip()
    if not version:
        raise OwnershipError("VERSAO_REDMINE_AUSENTE")
    if item.issue_id != PILOT_ISSUE_ID:
        raise OwnershipError("LEDGER_DIVERGENTE")
    return assignee["id"], version


def preparar_intencao_atribuicao(issue: dict, *, destino: str) -> dict:
    """Persist a pending intent only after matching authoritative preflight.

    Never performs the Redmine assignment. Conflicts do not create a new intent.
    """
    if destino not in ("eddy", "original"):
        raise OwnershipError("DESTINO_INVALIDO")
    stored = load_ownership(PILOT_ISSUE_ID)
    if stored is None:
        raise OwnershipError("RESPONSAVEL_ORIGINAL_NAO_PERSISTIDO")
    item, revision = stored
    assignee, version = _verified(issue, item)
    if destino == "eddy":
        if item.state != OwnershipState.CAPTURED:
            raise OwnershipError("ASSUNCAO_ESTADO_INVALIDO")
        pending = request_claim(item, current_assignee_id=assignee, current_version=version)
        target = item.eddy_assignee_id
    else:
        if item.state != OwnershipState.HUMAN_REQUIRED:
            raise OwnershipError("DEVOLUCAO_ESTADO_INVALIDO")
        pending = request_return(item, current_assignee_id=assignee, current_version=version)
        target = item.original_assignee_id
    if pending.state == OwnershipState.CONFLICT:
        raise OwnershipError("CONFLITO_REDMINE_REVISAR")
    new_revision = save_transition(pending, expected_revision=revision)
    return {
        "estado": pending.state.value,
        "chamado_id": item.issue_id,
        "destino_assignee_id": target,
        "responsavel_original_id": item.original_assignee_id,
        "redmine_updated_on_preflight": version,
        "revision": new_revision,
        "redmine_escritas": 0,
        "envios_realizados": 0,
        "requer_aprovacao_externa": True,
    }
