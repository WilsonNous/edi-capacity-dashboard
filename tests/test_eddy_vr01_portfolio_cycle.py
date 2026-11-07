"""VR01 portfolio bridge eligibility and CNPJ validation."""
from unittest.mock import patch
from ednna import eddy_vr01_portfolio_cycle as module


def test_cnpj_requires_single_explicit_redmine_field():
    assert module._cnpj({"custom_fields": [
        {"name": "CNPJ", "value": "12.345.678/0001-99"}
    ]}) == "12345678000199"
    assert module._cnpj({"custom_fields": []}) is None
    assert module._cnpj({"custom_fields": [
        {"name": "CNPJ", "value": ["12.345.678/0001-99", "98.765.432/0001-11"]}
    ]}) is None


def test_missing_snapshot_does_not_execute_any_external_action():
    with patch.object(module, "listar_chamados_vr_mysql", return_value=(50671,)), \
         patch.object(module, "carregar_snapshot", return_value=None):
        result = module.executar_carteira_vr01()
    assert result["avaliados"] == 1
    assert result["chamados"][0]["estado"] == "SEM_SNAPSHOT"
    assert result["execucao_externa"] is False
