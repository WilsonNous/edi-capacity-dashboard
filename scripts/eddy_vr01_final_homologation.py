"""Deterministic VR01 end-to-end homologation; no DB, HTTP, or Graph access.

All evidence here is SYNTHETIC. This is a test of the decision engine,
never evidence of a real customer reply, Redmine update, or sent email.
"""
from __future__ import annotations

import json

from ednna.eddy_vr01_lifecycle import VR01Evidence, VR01State, next_transition

ORIGINAL = 97
EDDY = 166
ISSUE = 50318

# State, expected operation, target, assignee, confirmed synthetic evidence.
STEPS = (
    (VR01State.PRONTO_PARA_ASSUMIR, "ASSUMIR_REDMINE", VR01State.ASSUMIDO_EDDY, ORIGINAL, {}),
    (VR01State.ASSUMIDO_EDDY, "BUSCAR_CONTATO_BP", VR01State.AGUARDA_CONTATO_BP, EDDY, {}),
    (VR01State.AGUARDA_CONTATO_BP, "SOLICITAR_AUTORIZACAO_PORTAL", VR01State.SOLICITACAO_ENVIADA, EDDY, {"blueprint_recipient_verified": True}),
    (VR01State.SOLICITACAO_ENVIADA, "MONITORAR_CLIENTE", VR01State.AGUARDA_CONFIRMACAO_CLIENTE, EDDY, {"graph_send_confirmed": True}),
    (VR01State.AGUARDA_CONFIRMACAO_CLIENTE, "CONFIRMACAO_VALIDADA", VR01State.CONFIRMACAO_RECEBIDA, EDDY, {"customer_portal_authorization_confirmed": True}),
    (VR01State.CONFIRMACAO_RECEBIDA, "REGISTRAR_EVIDENCIAS_REDMINE", VR01State.EVIDENCIAS_REGISTRADAS, EDDY, {"customer_portal_authorization_confirmed": True}),
    (VR01State.EVIDENCIAS_REGISTRADAS, "DEVOLVER_AO_RESPONSAVEL_ORIGINAL", VR01State.DEVOLVIDO_ORIGEM, EDDY, {"customer_portal_authorization_confirmed": True, "redmine_evidence_recorded": True}),
    (VR01State.DEVOLVIDO_ORIGEM, "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA", VR01State.NOTIFICACAO_INTERNA_CONFIRMADA, ORIGINAL, {"customer_portal_authorization_confirmed": True, "redmine_evidence_recorded": True}),
    (VR01State.NOTIFICACAO_INTERNA_CONFIRMADA, "CONCLUIDO", VR01State.NOTIFICACAO_INTERNA_CONFIRMADA, ORIGINAL, {"internal_notification_confirmed": True}),
)


def evidence(assignee: int, **flags: bool) -> VR01Evidence:
    return VR01Evidence(original_owner_id=ORIGINAL, eddy_owner_id=EDDY,
                        redmine_assignee_id=assignee, redmine_snapshot_fresh=True,
                        original_owner_persisted=True, **flags)


def homologar() -> dict:
    """Exercise all nine decisions and fail-closed gates in memory only."""
    trace = []
    state = VR01State.PRONTO_PARA_ASSUMIR
    for source, expected, target, assignee, flags in STEPS:
        if state != source:
            raise AssertionError(f"Sequencia divergente: {state} != {source}")
        operation, next_state = next_transition(state, evidence(assignee, **flags))
        if (operation, next_state) != (expected, target):
            raise AssertionError(f"{source.value}: {(operation, next_state)} != {(expected, target)}")
        trace.append({"fase": source.value, "operacao_simulada": operation,
                      "alvo_simulado": target.value})
        state = next_state

    gates = (
        ("snapshot_antigo", VR01State.PRONTO_PARA_ASSUMIR,
         VR01Evidence(ORIGINAL, EDDY, ORIGINAL), "BLOQUEADO_SNAPSHOT"),
        ("origem_divergente", VR01State.PRONTO_PARA_ASSUMIR,
         evidence(EDDY), "BLOQUEADO_ORIGEM"),
        ("bp_sem_validacao", VR01State.AGUARDA_CONTATO_BP,
         evidence(EDDY), "AGUARDA_CONTATO_BP_VALIDADO"),
        ("graph_sem_confirmacao", VR01State.SOLICITACAO_ENVIADA,
         evidence(EDDY), "AGUARDA_CONCILIACAO_GRAPH"),
        ("cliente_sem_confirmacao", VR01State.AGUARDA_CONFIRMACAO_CLIENTE,
         evidence(EDDY), "ACOMPANHAR_E_COBRAR"),
        ("evidencia_redmine_ausente", VR01State.EVIDENCIAS_REGISTRADAS,
         evidence(EDDY, customer_portal_authorization_confirmed=True), "BLOQUEADO_EVIDENCIAS"),
        ("devolucao_nao_confirmada", VR01State.DEVOLVIDO_ORIGEM,
         evidence(EDDY, customer_portal_authorization_confirmed=True,
                  redmine_evidence_recorded=True), "AGUARDA_DEVOLUCAO_CONFIRMADA"),
        ("notificacao_nao_conciliada", VR01State.NOTIFICACAO_INTERNA_CONFIRMADA,
         evidence(ORIGINAL), "AGUARDA_CONCILIACAO_NOTIFICACAO"),
    )
    for name, source, ev, expected in gates:
        operation, target = next_transition(source, ev)
        if operation != expected or target != source:
            raise AssertionError(f"Guarda {name} falhou: {operation}, {target}")
    return {"chamado_id": ISSUE, "tipo": "HOMOLOGACAO_SINTETICA_SEM_EFEITOS",
            "resultado": "APROVADO", "transicoes": trace,
            "guardas_verificadas": [name for name, *_ in gates],
            "redmine_escritas": 0, "emails_enviados": 0,
            "mysql_escritas": 0, "producao_liberada": False}


if __name__ == "__main__":
    print(json.dumps(homologar(), ensure_ascii=False, indent=2))
