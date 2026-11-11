import pytest

@pytest.fixture(autouse=True)
def _mock_pending_queue():
    from unittest.mock import patch
    with patch('scripts.eddy_identity_mysql_refresh._registrar_pendente'), patch('scripts.eddy_identity_mysql_refresh._limpar_pendente'):
        yield

"""Regression: a failed Redmine probe cannot pin the global BP scan cursor."""
from unittest.mock import patch

from scripts import eddy_identity_mysql_refresh as refresh


def test_failed_redmine_discovery_advances_scan_cursor():
    issue = {"id": 31592}
    with (
        patch.object(refresh, "_inventario", return_value={"CLIENTE_A": issue}),
        patch.object(refresh, "_cooldown_active", return_value=False),
        patch.object(refresh, "_lote", return_value=[("CLIENTE_A", issue)]),
        patch.object(refresh, "_confirmar_progresso") as advance,
        patch.object(refresh, "_set_cooldown") as cooldown,
        patch(
            "ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
            return_value={"descoberta": [{"status": "CONTEXTO_INDISPONIVEL"}], "resultados": []},
        ),
        patch("ednna.eddy_client_identity.resolver_identidade_cliente") as resolve,
    ):
        result = refresh.executar_uma_vez()
    advance.assert_called_once_with("CLIENTE_A")
    cooldown.assert_called_once_with()
    resolve.assert_not_called()
    assert result["interrompido_por_redmine"] is True
    assert result["cursor_avancado_apos_falha"] is True
    assert result["ultimo_cliente_tentado"] == "CLIENTE_A"
    assert result["indisponiveis"] == 1


def test_successful_discovery_advances_cursor_normally():
    issue = {"id": 31592}
    with (
        patch.object(refresh, "_inventario", return_value={"CLIENTE_A": issue}),
        patch.object(refresh, "_cooldown_active", return_value=False),
        patch.object(refresh, "_lote", return_value=[("CLIENTE_A", issue)]),
        patch.object(refresh, "_confirmar_progresso") as advance,
        patch.object(refresh, "_set_cooldown") as cooldown,
        patch(
            "ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
            return_value={"descoberta": [{"status": "BLUEPRINT_NAO_LOCALIZADO"}], "resultados": []},
        ),
        patch(
            "ednna.eddy_client_identity.resolver_identidade_cliente",
            return_value={"estado": "IDENTIDADE_NAO_RESOLVIDA"},
        ),
    ):
        result = refresh.executar_uma_vez()
    advance.assert_called_once_with("CLIENTE_A")
    cooldown.assert_not_called()
    assert result["cursor_avancado_apos_falha"] is False
    assert result["sem_blueprint"] == 1
