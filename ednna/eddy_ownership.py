"""Reusable, fail-closed ownership protocol for EDDY rules.

Pure state transitions: this module never calls Redmine, Graph or MySQL.
Adapters must persist transitions and obtain authoritative Redmine confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional


class OwnershipError(ValueError):
    """Unsafe or inconsistent ownership transition."""


class OwnershipState(str, Enum):
    CAPTURED = "CAPTURADO"
    CLAIM_PENDING = "ASSUNCAO_PENDENTE"
    OWNED = "EM_ATUACAO_EDDY"
    WAITING_THIRD_PARTY = "AGUARDANDO_TERCEIRO"
    HUMAN_REQUIRED = "INTERVENCAO_HUMANA"
    RETURN_PENDING = "DEVOLUCAO_PENDENTE"
    RETURNED = "DEVOLVIDO"
    CONFLICT = "CONFLITO_ATRIBUICAO"


@dataclass(frozen=True)
class Ownership:
    issue_id: int
    original_assignee_id: int
    eddy_assignee_id: int
    version: str
    state: OwnershipState = OwnershipState.CAPTURED
    last_evidence: Optional[str] = None

    def __post_init__(self):
        if self.issue_id <= 0 or self.original_assignee_id <= 0 or self.eddy_assignee_id <= 0:
            raise OwnershipError("Issue and assignee IDs must be positive")
        if self.original_assignee_id == self.eddy_assignee_id:
            raise OwnershipError("Original assignee must differ from EDDY")
        if not self.version:
            raise OwnershipError("Redmine version is mandatory")


def request_claim(item: Ownership, *, current_assignee_id: int, current_version: str) -> Ownership:
    if item.state != OwnershipState.CAPTURED:
        raise OwnershipError("Claim only allowed from captured state")
    if current_assignee_id != item.original_assignee_id or current_version != item.version:
        return replace(item, state=OwnershipState.CONFLICT)
    return replace(item, state=OwnershipState.CLAIM_PENDING)


def confirm_claim(item: Ownership, *, redmine_assignee_id: int, new_version: str,
                  evidence: str) -> Ownership:
    if item.state != OwnershipState.CLAIM_PENDING:
        raise OwnershipError("No pending claim")
    if not evidence or not new_version:
        raise OwnershipError("Redmine confirmation and version required")
    if redmine_assignee_id != item.eddy_assignee_id:
        return replace(item, state=OwnershipState.CONFLICT)
    return replace(item, state=OwnershipState.OWNED, version=new_version,
                   last_evidence=evidence)


def set_work_state(item: Ownership, state: OwnershipState) -> Ownership:
    if item.state not in (OwnershipState.OWNED, OwnershipState.WAITING_THIRD_PARTY):
        raise OwnershipError("EDDY has no confirmed ownership")
    if state not in (OwnershipState.OWNED, OwnershipState.WAITING_THIRD_PARTY,
                     OwnershipState.HUMAN_REQUIRED):
        raise OwnershipError("Invalid work state")
    return replace(item, state=state)


def request_return(item: Ownership, *, current_assignee_id: int,
                   current_version: str) -> Ownership:
    if item.state != OwnershipState.HUMAN_REQUIRED:
        raise OwnershipError("Human intervention not requested")
    if current_assignee_id != item.eddy_assignee_id or current_version != item.version:
        return replace(item, state=OwnershipState.CONFLICT)
    return replace(item, state=OwnershipState.RETURN_PENDING)


def confirm_return(item: Ownership, *, redmine_assignee_id: int,
                   new_version: str, evidence: str) -> Ownership:
    if item.state != OwnershipState.RETURN_PENDING:
        raise OwnershipError("No pending return")
    if not evidence or not new_version:
        raise OwnershipError("Redmine confirmation and version required")
    if redmine_assignee_id != item.original_assignee_id:
        return replace(item, state=OwnershipState.CONFLICT)
    return replace(item, state=OwnershipState.RETURNED, version=new_version,
                   last_evidence=evidence)


def handoff_notice(item: Ownership, *, actions: str, next_action: str) -> dict:
    """Draft notice only after confirmed Redmine return; never sends mail."""
    if item.state != OwnershipState.RETURNED or not item.last_evidence:
        raise OwnershipError("Do not notify before confirmed return")
    if not actions.strip() or not next_action.strip():
        raise OwnershipError("Auditable actions and human next step required")
    return {
        "issue_id": item.issue_id,
        "recipient_assignee_id": item.original_assignee_id,
        "subject": f"EDDY | Devolucao do chamado #{item.issue_id}",
        "actions": actions.strip(),
        "next_action": next_action.strip(),
        "redmine_evidence": item.last_evidence,
    }
