"""Redmine waiting-client status contract after confirmed Graph send."""
from unittest.mock import patch, Mock
import pytest
from ednna import eddy_vr01_integrated as vr


def test_status_resolves_by_name_without_hardcoded_id():
    response = Mock()
    response.json.return_value = {"issue_statuses": [
        {"id": 8, "name": "Em andamento"},
        {"id": 17, "name": "Aguardando Cliente"},
    ]}
    with patch("requests.get", return_value=response):
        assert vr._redmine_aguardando_cliente_status_id() == 17


def test_status_missing_fails_without_guessing():
    response = Mock()
    response.json.return_value = {"issue_statuses": [{"id": 8, "name": "Em andamento"}]}
    with patch("requests.get", return_value=response):
        with pytest.raises(RuntimeError, match="Aguardando Cliente"):
            vr._redmine_aguardando_cliente_status_id()


def test_redmine_update_sends_status_and_note():
    response = Mock()
    with patch("requests.put", return_value=response) as put:
        with vr.escopo_vr01(50318, 97, "CLIENTE", "71676316003323"):
            vr._redmine_update(status_id=17, notes="Aguardando retorno")
    payload = put.call_args.kwargs["json"]["issue"]
    assert payload["status_id"] == 17
    assert payload["notes"] == "Aguardando retorno"
