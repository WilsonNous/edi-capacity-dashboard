"""Tests for read-only client-source diagnostic."""
from unittest.mock import patch

from scripts import eddy_vr01_client_diagnostic as module


def test_reports_field_metadata_without_leaking_other_values():
    snapshot = {"chamado": {"cliente": None, "payload_json": {
        "id": 50318, "project": {"name": "EDI"}, "tracker": {"name": "Inclusão"},
        "custom_fields": [
            {"id": 1, "name": "Cliente", "value": ""},
            {"id": 5, "name": "Origem", "value": "SEGREDO_NAO_EXIBIR"},
        ],
    }}}
    with patch.object(module, "carregar_snapshot", return_value=snapshot):
        result = module.diagnosticar((50318,))
    issue = result["chamados"][0]
    assert issue["cliente_campo_1"] == ""
    assert issue["custom_fields"][1]["preenchido"] is True
    assert "SEGREDO_NAO_EXIBIR" not in str(result)
    assert result["mysql_escritas"] == 0


def test_missing_snapshot():
    with patch.object(module, "carregar_snapshot", return_value=None):
        assert module.diagnosticar((48786,))["chamados"][0]["estado"] == "SNAPSHOT_AUSENTE"
