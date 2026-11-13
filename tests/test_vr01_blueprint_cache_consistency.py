"""Regression: cached client identity must not override changed Blueprint evidence."""
from unittest.mock import patch

from ednna.eddy_client_identity import resolver_identidade_cliente


ISSUE = {"id": 50100, "custom_fields": [{"id": 1, "name": "Clientes", "value": "246"}]}
CACHE = {"estado": "RESOLVIDO", "cnpj": "12345678000190", "cliente": "246"}


def test_fresh_cache_does_not_hide_new_ambiguous_blueprint():
    with patch("ednna.eddy_client_identity_store.consultar", return_value=CACHE), \\
         patch("ednna.eddy_blueprint_mysql_evidence.identidade_de_bp_mysql",
               return_value={"estado": "CNPJ_AMBIGUO", "cnpj": None, "blueprint_ids": [10, 11]}), \\
         patch("ednna.eddy_client_identity_store.registrar") as registrar, \\
         patch("ednna.eddy_vr_mysql_sync.clientes_do_redmine", return_value=["246"]):
        result = resolver_identidade_cliente(ISSUE, cliente_override="246")
    assert result["cnpj"] is None
    assert result["estado"] == "CNPJ_AMBIGUO"
    registrar.assert_called_once()


def test_fresh_cache_is_replaced_by_new_verified_blueprint_identity():
    new = {"estado": "RESOLVIDO", "cnpj": "98765432000199", "cliente": "246"}
    with patch("ednna.eddy_client_identity_store.consultar", return_value=CACHE), \\
         patch("ednna.eddy_blueprint_mysql_evidence.identidade_de_bp_mysql", return_value=new), \\
         patch("ednna.eddy_client_identity_store.registrar") as registrar, \\
         patch("ednna.eddy_vr_mysql_sync.clientes_do_redmine", return_value=["246"]):
        result = resolver_identidade_cliente(ISSUE, cliente_override="246")
    assert result["cnpj"] == new["cnpj"]
    registrar.assert_called_once_with("246", new)


def test_mysql_failure_blocks_cached_identity_use():
    with patch("ednna.eddy_client_identity_store.consultar", return_value=CACHE), \\
         patch("ednna.eddy_blueprint_mysql_evidence.identidade_de_bp_mysql",
               side_effect=RuntimeError("db unavailable")), \\
         patch("ednna.eddy_vr_mysql_sync.clientes_do_redmine", return_value=["246"]):
        result = resolver_identidade_cliente(ISSUE, cliente_override="246")
    assert result["cnpj"] is None
    assert result["estado"] == "IDENTIDADE_MYSQL_INDISPONIVEL"
