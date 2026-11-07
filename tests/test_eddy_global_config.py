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


def test_eddy_canonical_names_override_legacy_without_breaking_existing_azure():
    from ednna.eddy_global_config import EDNNA_LEGACY_NAMES
    for suffix in EDNNA_LEGACY_NAMES:
        new, old = "EDDY_" + suffix, "EDNNA_" + suffix
        assert setting(new, environ={old: "legacy"}) == "legacy"
        assert setting(old, environ={old: "legacy"}) == "legacy"
        assert setting(new, environ={new: "canonical", old: "legacy"}) == "canonical"
        assert setting(old, environ={new: "canonical", old: "legacy"}) == "canonical"


def test_graph_readiness_accepts_new_eddy_sender_name():
    env = {
        "EDDY_DB_ENGINE": "mysql", "EDDY_VR01_EXTERNAL_ENABLED": "true",
        "EDDY_VR01_TRANSPORT_MYSQL_READY": "true",
        "EDDY_VR01_RECIPIENT_RESOLVER_READY": "true",
        "EDDY_DB_HOST": "db", "EDDY_DB_USER": "u",
        "EDDY_DB_PASSWORD": "p", "EDDY_DB_NAME": "d",
        "AZURE_TENANT_ID": "t", "AZURE_CLIENT_ID": "c",
        "AZURE_CLIENT_SECRET": "s", "EDDY_EMAIL_FROM": "edi@example.com",
    }
    result = verificar_prontidao_operacao_vr01("SOLICITAR_AUTORIZACAO_PORTAL", environ=env)
    assert result["pronto"] is True
