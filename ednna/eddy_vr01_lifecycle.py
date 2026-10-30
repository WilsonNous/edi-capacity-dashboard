"""EDDY VR01: pure, fail-closed lifecycle decisions.

No network, database writes, or side effects. A separate, audited executor
must perform and confirm each Redmine/Graph operation before advancing.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VR01State(str, Enum):
    PRONTO_PARA_ASSUMIR = "PRONTO_PARA_ASSUMIR"
    ASSUMIDO_EDDY = "ASSUMIDO_EDDY"
    AGUARDA_CONTATO_BP = "AGUARDA_CONTATO_BP"
    SOLICITACAO_ENVIADA = "SOLICITACAO_ENVIADA"
    AGUARDA_CONFIRMACAO_CLIENTE = "AGUARDA_CONFIRMACAO_CLIENTE"
    CONFIRMACAO_RECEBIDA = "CONFIRMACAO_RECEBIDA"
    EVIDENCIAS_REGISTRADAS = "EVIDENCIAS_REGISTRADAS"
    DEVOLVIDO_ORIGEM = "DEVOLVIDO_ORIGEM"
    NOTIFICACAO_INTERNA_CONFIRMADA = "NOTIFICACAO_INTERNA_CONFIRMADA"


@dataclass(frozen=True)
class VR01Evidence:
    original_owner_id: int
    eddy_owner_id: int
    redmine_assignee_id: int
    redmine_snapshot_fresh: bool = False
    original_owner_persisted: bool = False
    blueprint_recipient_verified: bool = False
    graph_send_confirmed: bool = False
    customer_portal_authorization_confirmed: bool = False
    redmine_evidence_recorded: bool = False
    internal_notification_confirmed: bool = False


def next_transition(state: VR01State, ev: VR01Evidence) -> tuple[str, VR01State]:
    """Return next permitted operation and state after confirmed execution.

    Returned state is a *target*, not proof of execution. Caller must keep
    current state until the operation is durably confirmed and reconciled.
    """
    if (type(ev.original_owner_id) is not int or ev.original_owner_id <= 0
            or type(ev.eddy_owner_id) is not int or ev.eddy_owner_id <= 0
            or ev.original_owner_id == ev.eddy_owner_id):
        return "BLOQUEADO_IDENTIDADE", state
    if not ev.redmine_snapshot_fresh:
        return "BLOQUEADO_SNAPSHOT", state
    if state == VR01State.PRONTO_PARA_ASSUMIR:
        if not ev.original_owner_persisted or ev.redmine_assignee_id != ev.original_owner_id:
            return "BLOQUEADO_ORIGEM", state
        return "ASSUMIR_REDMINE", VR01State.ASSUMIDO_EDDY
    if state == VR01State.ASSUMIDO_EDDY:
        if ev.redmine_assignee_id != ev.eddy_owner_id:
            return "AGUARDA_ASSUNCAO_CONFIRMADA", state
        return "BUSCAR_CONTATO_BP", VR01State.AGUARDA_CONTATO_BP
    if state == VR01State.AGUARDA_CONTATO_BP:
        if ev.redmine_assignee_id != ev.eddy_owner_id:
            return "BLOQUEADO_ATRIBUICAO", state
        if not ev.blueprint_recipient_verified:
            return "AGUARDA_CONTATO_BP_VALIDADO", state
        return "SOLICITAR_AUTORIZACAO_PORTAL", VR01State.SOLICITACAO_ENVIADA
    if state == VR01State.SOLICITACAO_ENVIADA:
        if ev.redmine_assignee_id != ev.eddy_owner_id:
            return "BLOQUEADO_ATRIBUICAO", state
        if not ev.graph_send_confirmed:
            return "AGUARDA_CONCILIACAO_GRAPH", state
        return "MONITORAR_CLIENTE", VR01State.AGUARDA_CONFIRMACAO_CLIENTE
    if state == VR01State.AGUARDA_CONFIRMACAO_CLIENTE:
        if ev.redmine_assignee_id != ev.eddy_owner_id:
            return "BLOQUEADO_ATRIBUICAO", state
        if not ev.customer_portal_authorization_confirmed:
            return "ACOMPANHAR_E_COBRAR", state
        return "CONFIRMACAO_VALIDADA", VR01State.CONFIRMACAO_RECEBIDA
    if state == VR01State.CONFIRMACAO_RECEBIDA:
        if ev.redmine_assignee_id != ev.eddy_owner_id:
            return "BLOQUEADO_ATRIBUICAO", state
        if not ev.customer_portal_authorization_confirmed:
            return "BLOQUEADO_CONFIRMACAO", state
        return "REGISTRAR_EVIDENCIAS_REDMINE", VR01State.EVIDENCIAS_REGISTRADAS
    if state == VR01State.EVIDENCIAS_REGISTRADAS:
        if not ev.customer_portal_authorization_confirmed or not ev.redmine_evidence_recorded:
            return "BLOQUEADO_EVIDENCIAS", state
        if ev.redmine_assignee_id != ev.eddy_owner_id:
            return "BLOQUEADO_ATRIBUICAO", state
        return "DEVOLVER_AO_RESPONSAVEL_ORIGINAL", VR01State.DEVOLVIDO_ORIGEM
    if state == VR01State.DEVOLVIDO_ORIGEM:
        if not ev.customer_portal_authorization_confirmed or not ev.redmine_evidence_recorded:
            return "BLOQUEADO_EVIDENCIAS", state
        if ev.redmine_assignee_id != ev.original_owner_id:
            return "AGUARDA_DEVOLUCAO_CONFIRMADA", state
        return "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA", VR01State.NOTIFICACAO_INTERNA_CONFIRMADA
    if state == VR01State.NOTIFICACAO_INTERNA_CONFIRMADA:
        return ("CONCLUIDO" if ev.internal_notification_confirmed
                else "AGUARDA_CONCILIACAO_NOTIFICACAO"), state
    return "BLOQUEADO_ESTADO", state
