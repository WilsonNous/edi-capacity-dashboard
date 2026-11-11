"""Blueprint contact recovery regressions for the VR01 portfolio."""
from unittest.mock import patch, MagicMock

from ednna.eddy_vr01_portfolio_cycle import _recuperar_contatos_bp_pendentes


def test_existing_bp_contacts_skip_redmine_and_mysql_probe():
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql",
               return_value=[{"email": "verified@example.org"}]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql") as discover, \
         patch("ednna.mysql_storage.connect") as connect:
        result = _recuperar_contatos_bp_pendentes(48786, "246")
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
         patch("ednna.mysql_storage.connect", return_value=conn):
        result = _recuperar_contatos_bp_pendentes(49119, "185")
    assert result["estado"] == "CONTATOS_BP_RECUPERADOS"
    discover.assert_called_once_with({49119: "185"}, aplicar=True, skip_imported=True)


def test_cooldown_prevents_repeat_discovery():
    conn = MagicMock()
    cursor = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.rowcount = 0
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql",
               return_value=[]), \
         patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql") as discover, \
         patch("ednna.mysql_storage.connect", return_value=conn):
        result = _recuperar_contatos_bp_pendentes(48786, "246")
    assert result["estado"] == "AGUARDA_RECONSULTA_BP"
    discover.assert_not_called()
