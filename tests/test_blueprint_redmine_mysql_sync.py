"""Direct Redmine -> MySQL Blueprint path must remain SQLite-independent."""
from unittest.mock import patch
from ednna.mysql_blueprint_participants import sincronizar_blueprints_redmine_mysql


def test_blueprint_direct_dry_run_does_not_open_mysql_or_sqlite():
    with patch("redmine_api.buscar_detalhes_chamado", return_value={"attachments": []}), \
         patch("ednna.mysql_blueprint_participants.connect", side_effect=AssertionError("mysql accessed")), \
         patch("ednna.blueprint_knowledge._init", side_effect=AssertionError("sqlite accessed")):
        result = sincronizar_blueprints_redmine_mysql({48786: "POSTOS ANDREAZZA"})
    assert result["modo"] == "DRY_RUN"
    assert result["mysql_escritas_habilitadas"] is False
    assert result["redmine_escritas"] == 0
    assert result["emails_enviados"] == 0


def test_blueprint_direct_rejects_unresolved_client():
    result = sincronizar_blueprints_redmine_mysql({48786: ""}, aplicar=True)
    assert result["resultados"][0]["status"] == "CLIENTE_NAO_RESOLVIDO"
    assert result["participantes_processados"] == 0


def test_blueprint_direct_dry_run_with_skip_imported_never_queries_mysql():
    with patch("redmine_api.buscar_detalhes_chamado", return_value={"attachments": []}), \
         patch("ednna.mysql_blueprint_participants.connect", side_effect=AssertionError("mysql accessed")):
        result = sincronizar_blueprints_redmine_mysql(
            {48786: "POSTOS ANDREAZZA"}, skip_imported=True)
    assert result["modo"] == "DRY_RUN"
    assert result["participantes_reutilizados"] == 0
