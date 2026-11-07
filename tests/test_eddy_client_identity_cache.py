"""Identity-cache regression tests; no live Redmine or MySQL required."""
from unittest.mock import patch

from ednna.eddy_client_identity import resolver_identidade_cliente
from ednna.eddy_client_identity_store import ttl_seconds, registrar


ISSUE = {"id": 47851, "custom_fields": [{"id": 1, "name": "Clientes", "value": "CLIENTE TESTE"}]}


def test_cache_hit_never_queries_redmine():
    value = {"estado": "RESOLVIDO", "cliente": "CLIENTE TESTE",
             "cnpj": "12345678000190", "origem": "MYSQL"}
    with patch("ednna.eddy_client_identity_store.consultar", return_value=value), \
         patch("ednna.mysql_blueprint_participants._descobrir_fontes_redmine",
               side_effect=AssertionError("Redmine must not be consulted")):
        assert resolver_identidade_cliente(ISSUE) == value


def test_mysql_unavailable_does_not_flood_redmine():
    with patch("ednna.eddy_client_identity_store.consultar", side_effect=OSError):
        assert resolver_identidade_cliente(ISSUE)["estado"] == "IDENTIDADE_MYSQL_INDISPONIVEL"


def test_source_outage_uses_stale_identity_for_offline_analysis():
    stale = {"estado": "RESOLVIDO", "cnpj": "12345678000190", "origem": "MYSQL"}
    with patch("ednna.eddy_client_identity_store.consultar", side_effect=[None, stale]), \
         patch("ednna.mysql_blueprint_participants._descobrir_fontes_redmine",
               side_effect=TimeoutError):
        result = resolver_identidade_cliente(ISSUE)
    assert result["desatualizado"] is True


def test_network_failure_never_persisted():
    assert registrar("CLIENTE TESTE", {"estado": "FONTE_BP_INDISPONIVEL"}) is False


def test_weekly_ttl_default():
    with patch.dict("os.environ", {}, clear=True):
        assert ttl_seconds() == 604800
