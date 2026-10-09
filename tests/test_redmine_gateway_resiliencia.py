"""Falha de capacidade local não deve derrubar o Redmine globalmente."""
from unittest.mock import patch

import pytest

import redmine_api


def test_gateway_ocupado_nao_abre_circuit_breaker():
    with (
        patch.object(redmine_api, "painel_circuit_breaker_ativo", return_value=False),
        patch("painel_cache.circuit_breaker_recuperacao_pendente", return_value=False),
        patch.object(redmine_api._RED_GATEWAY, "acquire", return_value=False),
        patch.object(redmine_api, "painel_abrir_circuit_breaker") as abrir,
        patch.object(redmine_api, "sleep"),
    ):
        with pytest.raises(TimeoutError, match="Gateway Redmine ocupado"):
            redmine_api._get("issues/48311.json", tentativas=1)
        abrir.assert_not_called()
