"""Regression tests for safe VR01 failure classification."""
from ednna.eddy_vr01_portfolio_cycle import _codigo_falha_vr01


def test_known_executor_failure_is_actionable():
    assert _codigo_falha_vr01(RuntimeError("Assuncao Redmine nao confirmada"), "EXECUTOR_VR01") == "ASSUNCAO_NAO_CONFIRMADA"
    assert _codigo_falha_vr01(RuntimeError("Transicao nao reconciliada"), "EXECUTOR_VR01") == "TRANSICAO_MYSQL_NAO_RECONCILIADA"


def test_unknown_executor_failure_does_not_leak_payload():
    secret = "https://internal.example/?token=very-sensitive"
    code = _codigo_falha_vr01(RuntimeError(secret), "EXECUTOR_VR01")
    assert code == "EXECUTOR_RUNTIME_NAO_CLASSIFICADO"
    assert secret not in code


def test_preflight_is_distinct_from_executor():
    assert _codigo_falha_vr01(RuntimeError("Redmine preflight bloqueado"), "PREFLIGHT_REDMINE") == "REDMINE_PREFLIGHT_INDISPONIVEL"
    assert _codigo_falha_vr01(RuntimeError("Redmine preflight bloqueado"), "EXECUTOR_VR01") == "REDMINE_PREFLIGHT_BLOQUEADO"
