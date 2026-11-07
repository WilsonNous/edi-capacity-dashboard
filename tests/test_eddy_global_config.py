"""Global EDDY settings migration contract."""
from ednna.eddy_global_config import setting, enabled
from ednna.eddy_vr01_operation_readiness import verificar_prontidao_operacao_vr01


def test_global_fallback_for_new_rules():
    assert enabled("EDDY_VR01_EXTERNAL_ENABLED", environ={"EDDY_EXTERNAL_ENABLED": "true"})
    assert setting("EDDY_VR01_INTERVAL_SECONDS", environ={"EDDY_INTERVAL_SECONDS": "600"}) == "600"


def test_legacy_explicit_override_preserved():
    env = {"EDDY_EXTERNAL_ENABLED": "true", "EDDY_VR01_EXTERNAL_ENABLED": "false"}
    assert not enabled("EDDY_VR01_EXTERNAL_ENABLED", environ=env)


def test_readiness_respects_global_gate():
    env = {"EDDY_DB_ENGINE": "mysql", "EDDY_EXTERNAL_ENABLED": "true",
           "EDDY_REDMINE_MYSQL_AUDIT_READY": "true",
           "EDDY_DB_HOST": "db", "EDDY_DB_USER": "u",
           "EDDY_DB_PASSWORD": "p", "EDDY_DB_NAME": "d"}
    result = verificar_prontidao_operacao_vr01("ASSUMIR_REDMINE", environ=env)
    assert result["pronto"] is True
    env["EDDY_VR01_EXTERNAL_ENABLED"] = "false"
    assert verificar_prontidao_operacao_vr01("ASSUMIR_REDMINE", environ=env)["pronto"] is False
