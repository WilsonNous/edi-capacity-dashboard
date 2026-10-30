"""Pure VR01 lifecycle tests; no Redmine, Graph or MySQL side effects."""
from dataclasses import replace

from ednna.eddy_vr01_lifecycle import VR01Evidence, VR01State, next_transition


def evidence(**kwargs):
    base = VR01Evidence(
        original_owner_id=97, eddy_owner_id=999,
        redmine_assignee_id=999, redmine_snapshot_fresh=True,
        original_owner_persisted=True, blueprint_recipient_verified=True,
        graph_send_confirmed=True,
    )
    return replace(base, **kwargs)


def test_assumption_requires_original_owner_and_persistence():
    ev = evidence(redmine_assignee_id=97)
    assert next_transition(VR01State.PRONTO_PARA_ASSUMIR, ev)[0] == "ASSUMIR_REDMINE"
    assert next_transition(VR01State.PRONTO_PARA_ASSUMIR, replace(ev, original_owner_persisted=False))[0] == "BLOQUEADO_ORIGEM"


def test_eddy_remains_owner_without_customer_confirmation():
    ev = evidence()
    assert next_transition(VR01State.AGUARDA_CONFIRMACAO_CLIENTE, ev) == (
        "ACOMPANHAR_E_COBRAR", VR01State.AGUARDA_CONFIRMACAO_CLIENTE)
    assert next_transition(VR01State.EVIDENCIAS_REGISTRADAS, ev)[0] == "BLOQUEADO_EVIDENCIAS"


def test_devolution_only_after_confirmation_and_redmine_evidence():
    ev = evidence(customer_portal_authorization_confirmed=True, redmine_evidence_recorded=True)
    assert next_transition(VR01State.EVIDENCIAS_REGISTRADAS, ev) == (
        "DEVOLVER_AO_RESPONSAVEL_ORIGINAL", VR01State.DEVOLVIDO_ORIGEM)
    assert next_transition(VR01State.DEVOLVIDO_ORIGEM, ev)[0] == "AGUARDA_DEVOLUCAO_CONFIRMADA"
    assert next_transition(VR01State.DEVOLVIDO_ORIGEM, replace(ev, redmine_assignee_id=97))[0] == "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA"


def test_no_bp_no_request_and_no_graph_proof_no_monitor():
    assert next_transition(VR01State.AGUARDA_CONTATO_BP, evidence(blueprint_recipient_verified=False))[0] == "AGUARDA_CONTATO_BP_VALIDADO"
    assert next_transition(VR01State.SOLICITACAO_ENVIADA, evidence(graph_send_confirmed=False))[0] == "AGUARDA_CONCILIACAO_GRAPH"


def test_no_shortcut_to_notification_without_confirmed_handoff():
    ev = evidence(customer_portal_authorization_confirmed=True, redmine_evidence_recorded=True)
    assert next_transition(VR01State.DEVOLVIDO_ORIGEM, ev)[0] != "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA"


def test_fails_closed_when_eddy_not_assigned_or_snapshot_stale():
    assert next_transition(VR01State.AGUARDA_CONFIRMACAO_CLIENTE, evidence(redmine_assignee_id=97))[0] == "BLOQUEADO_ATRIBUICAO"
    assert next_transition(VR01State.AGUARDA_CONFIRMACAO_CLIENTE, evidence(redmine_snapshot_fresh=False))[0] == "BLOQUEADO_SNAPSHOT"


def test_no_auto_file_receipt_validation():
    import inspect
    from ednna import eddy_vr01_lifecycle
    assert "VALIDAR_RECEBIMENTO_ARQUIVOS" not in inspect.getsource(eddy_vr01_lifecycle)
