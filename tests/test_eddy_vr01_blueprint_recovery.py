"""Regression tests for read-only Blueprint recovery status."""
from unittest.mock import patch

from scripts.eddy_vr01_blueprint_recovery import diagnosticar


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params):
        assert sql.lstrip().startswith("SELECT")
        assert params == ("SUPERMERCADOS MAMBO",)

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return Cursor(self.rows)


def test_missing_catalog_contacts_not_confused_with_missing_blueprint():
    with patch("scripts.eddy_vr01_blueprint_recovery.connect", return_value=Connection([])):
        result = diagnosticar()
    assert result["estado"] == "SEM_CONTATOS_PERSISTIDOS_REDMINE_NAO_VERIFICADO"
    assert result["mysql_escritas"] == 0
    assert result["redmine_consultado"] is False


def test_legacy_project_manager_is_visible_as_a_candidate_not_approved():
    rows = [("GERENTE/COORD. PROJETO", 11, 22, 50318, 33, "BP.xlsx", "cliente@example.org")]
    with patch("scripts.eddy_vr01_blueprint_recovery.connect", return_value=Connection(rows)):
        result = diagnosticar()
    assert result["gerentes_projeto_cliente"] == 1
    assert result["requer_aprovacao_destinatario"] is True


def test_catalog_failure_is_not_reported_as_missing_contacts():
    with patch("scripts.eddy_vr01_blueprint_recovery.connect", side_effect=ConnectionError):
        result = diagnosticar()
    assert result["estado"] == "CATALOGO_INDISPONIVEL"
