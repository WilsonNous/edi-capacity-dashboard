"""Operation gates: independent dependencies, no bypass of external kill switch."""
from unittest.mock import patch

import pytest

from ednna.eddy_vr01_operation_readiness import (
    GRAPH_OPERATIONS, MYSQL_CREDENTIALS, GRAPH_CREDENTIALS,
    OPERATION_REQUIREMENTS, verificar_prontidao_operacao_vr01,
)
from ednna.eddy_vr01_integrated import planejar_vr01


def env_for(operation):
    env = {"EDDY_DB_ENGINE": "mysql", "EDDY_VR01_EXTERNAL_ENABLED": "true"}
    env.update({name: "test-value" for name in MYSQL_CREDENTIALS})
    if operation in GRAPH_OPERATIONS:
        env.update({name: "test-value" for name in GRAPH_CREDENTIALS})
    env.update({name: "true" for name in OPERATION_REQUIREMENTS[operation]})
    return env


@pytest.mark.parametrize("operation", tuple(OPERATION_REQUIREMENTS))
def test_each_operation_has_independent_readiness(operation):
    assert verificar_prontidao_operacao_vr01(operation, env_for(operation))["pronto"]


@pytest.mark.parametrize("operation", tuple(OPERATION_REQUIREMENTS))
def test_every_operation_requires_external_kill_switch(operation):
    env = env_for(operation)
    env["EDDY_VR01_EXTERNAL_ENABLED"] = "false"
    result = verificar_prontidao_operacao_vr01(operation, env)
    assert not result["pronto"]
    assert "EXECUCAO_EXTERNA_DESABILITADA" in result["bloqueios"]


@pytest.mark.parametrize("operation", tuple(OPERATION_REQUIREMENTS))
def test_each_required_homologation_blocks_only_its_operation(operation):
    for flag in OPERATION_REQUIREMENTS[operation]:
        env = env_for(operation)
        env[flag] = "false"
        assert not verificar_prontidao_operacao_vr01(operation, env)["pronto"]


def test_assumption_does_not_require_graph_recipient_or_reply():
    env = env_for("ASSUMIR_REDMINE")
    for key in ("EDDY_VR01_RECIPIENT_RESOLVER_READY",
                "EDDY_VR01_REPLY_RECONCILIATION_READY",
                "EDDY_VR01_TRANSPORT_MYSQL_READY"):
        env[key] = "false"
    assert verificar_prontidao_operacao_vr01("ASSUMIR_REDMINE", env)["pronto"]


def test_graph_send_needs_graph_credentials_and_recipient():
    env = env_for("SOLICITAR_AUTORIZACAO_PORTAL")
    env.pop("AZURE_CLIENT_SECRET")
    assert "CREDENCIAIS_AUSENTES" in verificar_prontidao_operacao_vr01(
        "SOLICITAR_AUTORIZACAO_PORTAL", env)["bloqueios"]


def test_unknown_operation_is_always_blocked():
    assert not verificar_prontidao_operacao_vr01("BYPASS", env_for("ASSUMIR_REDMINE"))["pronto"]


def test_integrated_executor_blocks_before_reservation_when_gate_fails():
    issue = {"assigned_to": {"id": 97}, "updated_on": "2026-11-05T15:01:00Z"}
    row = {"fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97,
           "eddy_owner_id": 999, "operacao_pendente": None,
           "envio_graph_confirmado": 0, "autorizacao_confirmada": 0,
           "confirmacao_evidence_id": None, "evidencias_registradas": 0,
           "notificado": 0}
    with patch("ednna.eddy_vr01_integrated._identity", return_value=999), \
         patch("ednna.eddy_vr01_integrated._read_issue", return_value=issue), \
         patch("ednna.eddy_vr01_integrated._load", return_value=row), \
         patch("ednna.eddy_vr01_integrated.verificar_prontidao_operacao_vr01",
               return_value={"pronto": False, "bloqueios": ["AUDITORIA_REDMINE_NAO_HOMOLOGADA"]}), \
         patch("ednna.eddy_vr01_integrated._reserve") as reserve, \
         patch("ednna.eddy_vr01_integrated._redmine_update") as write:
        result = planejar_vr01(execute=True, approvals={})
    assert result["estado"] == "BLOQUEADO_PRONTIDAO"
    assert result["bloqueios_prontidao"] == ["AUDITORIA_REDMINE_NAO_HOMOLOGADA"]
    reserve.assert_not_called()
    write.assert_not_called()


def test_ready_operation_still_requires_versioned_approval():
    issue = {"assigned_to": {"id": 97}, "updated_on": "2026-11-05T15:01:00Z"}
    row = {"fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97,
           "eddy_owner_id": 999, "operacao_pendente": None,
           "envio_graph_confirmado": 0, "autorizacao_confirmada": 0,
           "confirmacao_evidence_id": None, "evidencias_registradas": 0,
           "notificado": 0}
    with patch("ednna.eddy_vr01_integrated._identity", return_value=999), \
         patch("ednna.eddy_vr01_integrated._read_issue", return_value=issue), \
         patch("ednna.eddy_vr01_integrated._load", return_value=row), \
         patch("ednna.eddy_vr01_integrated.verificar_prontidao_operacao_vr01",
               return_value={"pronto": True, "bloqueios": []}), \
         patch("ednna.eddy_vr01_integrated._reserve") as reserve, \
         patch("ednna.eddy_vr01_integrated._redmine_update") as write:
        with pytest.raises(PermissionError):
            planejar_vr01(execute=True, approvals={})
    reserve.assert_not_called()
    write.assert_not_called()
