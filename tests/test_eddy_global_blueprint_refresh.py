import pytest

@pytest.fixture(autouse=True)
def _mock_pending_queue():
    from unittest.mock import patch
    with patch('scripts.eddy_identity_mysql_refresh._registrar_pendente'), patch('scripts.eddy_identity_mysql_refresh._limpar_pendente'):
        yield

"""Global Blueprint regressions: coverage, source integrity and no external writes."""
from unittest.mock import patch

from scripts.eddy_identity_mysql_refresh import executar_uma_vez
from ednna.mysql_blueprint_participants import descobrir_e_sincronizar_participantes_mysql


def test_global_worker_handles_non_vr_and_no_remote_second_walk():
    chosen = {"ALFA": {"id": 11}, "BETA": {"id": 22}}
    with patch("scripts.eddy_identity_mysql_refresh._cooldown_active", return_value=False), \
         patch("scripts.eddy_identity_mysql_refresh._set_cooldown"), \
         patch("scripts.eddy_identity_mysql_refresh._inventario", return_value=chosen), \
         patch("scripts.eddy_identity_mysql_refresh._lote",
               return_value=list(chosen.items())), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
               side_effect=[
                   {"resultados": [], "descoberta": [{"status": "BLUEPRINT_NAO_LOCALIZADO"}]},
                   {"resultados": [{"status": "IMPORTADO"}], "descoberta": [{"status": "CONTEXTO_RESOLVIDO"}]},
               ]) as discovery, \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente",
               side_effect=[{"estado": "SEM_BP_MYSQL"}, {"estado": "RESOLVIDO"}]) as identity, \
         patch("scripts.eddy_identity_mysql_refresh._confirmar_progresso") as checkpoint:
        stats = executar_uma_vez()
    assert stats["clientes"] == 2
    assert stats["consultados"] == 2
    assert stats["sem_blueprint"] == 1
    assert stats["bp_sincronizados"] == 1
    assert identity.call_args_list[0].kwargs["allow_remote"] is False
    assert discovery.call_count == 2
    assert [call.args[0] for call in checkpoint.call_args_list] == ["ALFA", "BETA"]


def test_redmine_failure_stops_cycle_and_advances_scan_cursor():
    with patch("scripts.eddy_identity_mysql_refresh._cooldown_active", return_value=False), \
         patch("scripts.eddy_identity_mysql_refresh._set_cooldown"), \
         patch("scripts.eddy_identity_mysql_refresh._inventario",
               return_value={"A": {"id": 1}, "B": {"id": 2}}), \
         patch("scripts.eddy_identity_mysql_refresh._lote",
               return_value=[("A", {"id": 1}), ("B", {"id": 2})]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
               return_value={"resultados": [], "descoberta": [{"status": "CONTEXTO_INDISPONIVEL"}]}) as discovery, \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente") as identity, \
         patch("scripts.eddy_identity_mysql_refresh._confirmar_progresso") as checkpoint:
        stats = executar_uma_vez()
    assert stats["interrompido_por_redmine"]
    assert stats["falhas_descoberta"] == 1
    assert discovery.call_count == 1
    identity.assert_not_called()
    checkpoint.assert_called_once_with("A")
    assert stats["cursor_avancado_apos_falha"] is True


def test_discovery_imports_only_verified_blueprint_root():
    with patch("ednna.mysql_blueprint_participants._descobrir_fontes_redmine",
               return_value=({11, 12, 13}, 12)), \
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql",
               return_value={"resultados": [], "redmine_escritas": 0, "emails_enviados": 0}) as sync:
        result = descobrir_e_sincronizar_participantes_mysql({11: "ALFA"}, aplicar=True)
    sync.assert_called_once_with({12: "ALFA"}, aplicar=True, skip_imported=True)
    assert result["descoberta"][0]["blueprint_id"] == 12


def test_discovery_does_not_import_operational_excel_without_bp():
    with patch("ednna.mysql_blueprint_participants._descobrir_fontes_redmine",
               return_value=({11, 13}, None)), \
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql") as sync:
        result = descobrir_e_sincronizar_participantes_mysql({11: "ALFA"}, aplicar=True)
    sync.assert_not_called()
    assert result["descoberta"][0]["status"] == "BLUEPRINT_NAO_LOCALIZADO"


def test_cached_resolved_identity_invalidated_by_conflicting_bp_mysql():
    from ednna.eddy_client_identity import resolver_identidade_cliente
    issue = {"id": 11, "custom_fields": []}
    with patch("ednna.eddy_vr_mysql_sync.clientes_do_redmine", return_value=[]), \
         patch("ednna.eddy_client_identity_store.consultar",
               return_value={"estado": "RESOLVIDO", "cnpj": "12345678000190"}), \
         patch("ednna.eddy_blueprint_mysql_evidence.identidade_de_bp_mysql",
               return_value={"estado": "CNPJ_AMBIGUO", "blueprint_ids": [12, 13]}), \
         patch("ednna.eddy_client_identity_store.registrar") as registrar:
        result = resolver_identidade_cliente(
            issue, cliente_override="ALFA", allow_remote=False, refresh_mysql=True)
    assert result["estado"] == "CNPJ_AMBIGUO"
    assert result["cnpj"] is None
    registrar.assert_called_once()
    assert registrar.call_args.args[1]["estado"] == "CNPJ_AMBIGUO"


def test_checkpoint_includes_failed_client_to_avoid_starvation():
    with patch("scripts.eddy_identity_mysql_refresh._cooldown_active", return_value=False), \
         patch("scripts.eddy_identity_mysql_refresh._set_cooldown"), \
         patch("scripts.eddy_identity_mysql_refresh._inventario",
               return_value={"A": {"id": 1}, "B": {"id": 2}, "C": {"id": 3}}), \
         patch("scripts.eddy_identity_mysql_refresh._lote",
               return_value=[("A", {"id": 1}), ("B", {"id": 2}), ("C", {"id": 3})]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
               side_effect=[
                   {"resultados": [], "descoberta": [{"status": "CONTEXTO_RESOLVIDO"}]},
                   {"resultados": [], "descoberta": [{"status": "CONTEXTO_INDISPONIVEL"}]},
               ]) as discovery, \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente",
               return_value={"estado": "RESOLVIDO"}), \
         patch("scripts.eddy_identity_mysql_refresh._confirmar_progresso") as checkpoint:
        stats = executar_uma_vez()
    assert stats["interrompido_por_redmine"] is True
    assert discovery.call_count == 2
    assert [call.args[0] for call in checkpoint.call_args_list] == ["A", "B"]
    assert stats["cursor_avancado_apos_falha"] is True

def test_global_bp_worker_defers_redmine_until_cooldown_expires():
    with patch("scripts.eddy_identity_mysql_refresh._inventario",
               return_value={"A": {"id": 1}}), \
         patch("scripts.eddy_identity_mysql_refresh._cooldown_active",
               return_value=True), \
         patch("scripts.eddy_identity_mysql_refresh._lote") as batch:
        result = executar_uma_vez()
    assert result["estado"] == "REDMINE_COOLDOWN"
    assert result["retry_seconds"] >= 60
    batch.assert_not_called()


def test_global_bp_retry_delay_is_bounded():
    from scripts.eddy_identity_mysql_refresh import _retry_delay_seconds
    with patch.dict("os.environ", {"EDDY_BP_REDMINE_RETRY_SECONDS": "2"}):
        assert _retry_delay_seconds() == 60
    with patch.dict("os.environ", {"EDDY_BP_REDMINE_RETRY_SECONDS": "99999"}):
        assert _retry_delay_seconds() == 3600
