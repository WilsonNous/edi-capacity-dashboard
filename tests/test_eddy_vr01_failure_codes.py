"""Safe operational VR01 error classification regression tests."""
from ednna.eddy_vr01_portfolio_cycle import _codigo_falha_vr01


def test_known_internal_executor_failures():
    assert _codigo_falha_vr01(RuntimeError("Assuncao Redmine nao confirmada"), "EXECUTOR_VR01") == "ASSUNCAO_NAO_CONFIRMADA"
    assert _codigo_falha_vr01(RuntimeError("Transicao nao reconciliada"), "EXECUTOR_VR01") == "TRANSICAO_MYSQL_NAO_RECONCILIADA"
    assert _codigo_falha_vr01(RuntimeError("Responsavel original divergente: nao assumir"), "EXECUTOR_VR01") == "RESPONSAVEL_ORIGINAL_DIVERGENTE"


def test_unknown_exception_never_leaks_credentials_or_url():
    secret = "https://redmine.example/private?token=secret"
    code = _codigo_falha_vr01(RuntimeError(secret), "EXECUTOR_VR01")
    assert code == "EXECUTOR_RUNTIME_NAO_CLASSIFICADO"
    assert secret not in code


def test_preflight_is_distinct_from_executor():
    error = RuntimeError("Redmine preflight bloqueado")
    assert _codigo_falha_vr01(error, "PREFLIGHT_REDMINE") == "REDMINE_PREFLIGHT_INDISPONIVEL"
    assert _codigo_falha_vr01(error, "EXECUTOR_VR01") == "REDMINE_PREFLIGHT_BLOQUEADO"
