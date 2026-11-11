"""Blueprint contact recovery regressions for the VR01 portfolio."""
from unittest.mock import patch, MagicMock

from ednna.mysql_blueprint_participants import recuperar_contatos_blueprint


def test_existing_bp_contacts_skip_redmine_and_mysql_probe():
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql",
               return_value=[{"email": "verified@example.org"}]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql") as discover, \
         patch("ednna.mysql_blueprint_participants.connect") as connect:
        result = recuperar_contatos_blueprint(48786, "246")
    assert result["estado"] == "CONTATOS_BP_JA_DISPONIVEIS"
    discover.assert_not_called()
    connect.assert_not_called()


def test_recovery_imports_only_verified_bp_source():
    conn = MagicMock()
    cursor = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql",
               side_effect=[[], [{"email": "verified@example.org"}]]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
               return_value={"fontes_descobertas": 1}) as discover, \
         patch("ednna.mysql_blueprint_participants.connect", return_value=conn):
        result = recuperar_contatos_blueprint(49119, "185")
    assert result["estado"] == "CONTATOS_BP_RECUPERADOS"
    discover.assert_called_once_with({49119: "185"}, aplicar=True, skip_imported=True)


def test_cooldown_prevents_repeat_discovery():
    conn = MagicMock()
    cursor = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.rowcount = 0
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql",
               return_value=[]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql") as discover, \
         patch("ednna.mysql_blueprint_participants.connect", return_value=conn):
        result = recuperar_contatos_blueprint(48786, "246")
    assert result["estado"] == "AGUARDA_RECONSULTA_BP"
    discover.assert_not_called()


def test_diagnostic_ignores_establishment_cnpj_on_issue():
    from ednna.eddy_vr01_portfolio_cycle import diagnosticar_identificacao_cliente
    issue = {"custom_fields": [
        {"id": 1, "name": "Clientes", "value": "246"},
        {"name": "CNPJ", "value": "12.345.678/0001-90"},
    ]}
    with patch("ednna.eddy_vr01_portfolio_cycle.clientes_do_redmine", return_value=["246"]):
        result = diagnosticar_identificacao_cliente(issue, {"estado": "CNPJ_NAO_LOCALIZADO_BP"})
    assert result["motivos"] == ["CNPJ_NAO_LOCALIZADO_BP"]
    assert result["origem_identidade"] == "BLUEPRINT"
    assert result["cnpj_estabelecimento_nao_utilizado"] is True


def test_diagnostic_does_not_require_issue_cnpj_when_bp_resolved():
    from ednna.eddy_vr01_portfolio_cycle import diagnosticar_identificacao_cliente
    issue = {"custom_fields": [{"id": 1, "name": "Clientes", "value": "185"}]}
    with patch("ednna.eddy_vr01_portfolio_cycle.clientes_do_redmine", return_value=["185"]):
        result = diagnosticar_identificacao_cliente(issue, {"estado": "RESOLVIDO", "cnpj": "12345678000190"})
    assert result["motivos"] == []
    assert "CNPJ_AUSENTE" not in result["motivos"]
