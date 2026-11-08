"""Global Blueprint regressions: coverage, source integrity and no external writes."""
from unittest.mock import patch

from scripts.eddy_identity_mysql_refresh import executar_uma_vez
from ednna.mysql_blueprint_participants import descobrir_e_sincronizar_participantes_mysql


def test_global_worker_handles_non_vr_and_no_remote_second_walk():
    chosen = {"ALFA": {"id": 11}, "BETA": {"id": 22}}
    with patch("scripts.eddy_identity_mysql_refresh._inventario", return_value=chosen), \
         patch("scripts.eddy_identity_mysql_refresh._lote",
               return_value=list(chosen.items())), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
               side_effect=[
                   {"resultados": [], "descoberta": [{"status": "BLUEPRINT_NAO_LOCALIZADO"}]},
                   {"resultados": [{"status": "IMPORTADO"}], "descoberta": [{"status": "CONTEXTO_RESOLVIDO"}]},
               ]) as discovery, \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente",
               side_effect=[{"estado": "SEM_BP_MYSQL"}, {"estado": "RESOLVIDO"}]) as identity:
        stats = executar_uma_vez()
    assert stats["clientes"] == 2
    assert stats["consultados"] == 2
    assert stats["sem_blueprint"] == 1
    assert stats["bp_sincronizados"] == 1
    assert identity.call_args_list[0].kwargs["allow_remote"] is False
    assert discovery.call_count == 2


def test_redmine_failure_stops_this_cycle_but_does_not_lose_cursor():
    with patch("scripts.eddy_identity_mysql_refresh._inventario",
               return_value={"A": {"id": 1}, "B": {"id": 2}}), \
         patch("scripts.eddy_identity_mysql_refresh._lote",
               return_value=[("A", {"id": 1}), ("B", {"id": 2})]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
               return_value={"resultados": [], "descoberta": [{"status": "CONTEXTO_INDISPONIVEL"}]}) as discovery, \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente") as identity:
        stats = executar_uma_vez()
    assert stats["interrompido_por_redmine"]
    assert stats["falhas_descoberta"] == 1
    assert discovery.call_count == 1
    identity.assert_not_called()


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
