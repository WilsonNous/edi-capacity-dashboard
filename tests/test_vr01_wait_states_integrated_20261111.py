"""Regression: VR01 wait states must not be mistaken for executable actions."""
from unittest.mock import patch

from ednna.eddy_vr01_lifecycle import VR01Evidence, VR01State, next_transition


def _evidence(**changes):
    values = dict(original_owner_id=97, eddy_owner_id=301,
                  redmine_assignee_id=301, redmine_snapshot_fresh=True,
                  original_owner_persisted=True)
    values.update(changes)
    return VR01Evidence(**values)


def test_missing_blueprint_contact_is_wait_not_unknown_operation():
    action, target = next_transition(VR01State.AGUARDA_CONTATO_BP, _evidence())
    assert action == "AGUARDA_CONTATO_BP_VALIDADO"
    assert target == VR01State.AGUARDA_CONTATO_BP


def test_verified_blueprint_contact_advances_to_send():
    action, target = next_transition(
        VR01State.AGUARDA_CONTATO_BP,
        _evidence(blueprint_recipient_verified=True),
    )
    assert action == "SOLICITAR_AUTORIZACAO_PORTAL"
    assert target == VR01State.SOLICITACAO_ENVIADA


def test_unconfirmed_customer_reply_is_not_authorization():
    action, target = next_transition(
        VR01State.AGUARDA_CONFIRMACAO_CLIENTE,
        _evidence(graph_send_confirmed=True),
    )
    assert action == "ACOMPANHAR_E_COBRAR"
    assert target == VR01State.AGUARDA_CONFIRMACAO_CLIENTE


def test_missing_bp_contact_never_calls_operation_readiness():
    from ednna import eddy_vr01_integrated as mod
    ledger = {
        "original_owner_id": 97, "eddy_owner_id": 301,
        "operacao_pendente": None, "fase": "AGUARDA_CONTATO_BP",
        "envio_graph_confirmado": 0, "autorizacao_confirmada": 0,
        "confirmacao_evidence_id": None, "evidencias_registradas": 0,
        "notificado": 0,
    }
    issue = {"id": 50318, "updated_on": "2026-11-11T12:00:00Z",
             "assigned_to": {"id": 301}}
    with patch.object(mod, "_context", return_value={
        "chamado_id": 50318, "original_owner_id": 97,
        "cliente": "MAMBO", "cnpj": "00000000000000",
    }), patch.object(mod, "_identity", return_value=301), \
         patch.object(mod, "_load", return_value=ledger), \
         patch.object(mod, "_valid_bp", return_value=None), \
         patch.object(mod, "verificar_prontidao_operacao_vr01",
                      side_effect=AssertionError("readiness should not run")):
        result = mod.planejar_vr01(execute=True, verified_issue=issue)
    assert result["estado"] == "AGUARDANDO_PRECONDICAO"
    assert result["bloqueio_ciclo"] == "AGUARDA_CONTATO_BP_VALIDADO"
    assert result["externo"] is False
