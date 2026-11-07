"""Blueprint evidence persistence regression: no live MySQL or Redmine."""
from unittest.mock import patch

from ednna.eddy_blueprint_mysql_evidence import identidade_de_bp_mysql


def test_persisted_bp_evidence_unblocks_participant_only_bp():
    with patch("ednna.eddy_blueprint_identity_evidence.consultar_cliente",
               return_value={"blueprint_ids": [500], "cnpjs": {"12345678000190"}}), \
         patch("ednna.eddy_blueprint_mysql_evidence.candidatos_bp_mysql",
               return_value=({500}, {})):
        result = identidade_de_bp_mysql("CLIENTE TESTE")
    assert result["estado"] == "RESOLVIDO"
    assert result["cnpj"] == "12345678000190"


def test_multiple_bp_cnpjs_are_not_silently_selected():
    with patch("ednna.eddy_blueprint_identity_evidence.consultar_cliente",
               return_value={"blueprint_ids": [500], "cnpjs": {"12345678000190", "98765432000110"}}), \
         patch("ednna.eddy_blueprint_mysql_evidence.candidatos_bp_mysql",
               return_value=({500}, {})):
        result = identidade_de_bp_mysql("CLIENTE TESTE")
    assert result["estado"] == "CNPJ_AMBIGUO"
    assert result["cnpj"] is None
