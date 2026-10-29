import unittest
from unittest.mock import patch

from ednna.eddy_vr_mysql_sync import _snapshot, sincronizar_carteira_vr_mysql
from datetime import datetime, timezone


class TestVRMySQLSync(unittest.TestCase):
    def test_persists_canonical_redmine_client_field(self):
        issue = {"id": 50318, "subject": "VR Beneficios",
                 "status": {"name": "Novo"}, "journals": [],
                 "custom_fields": [{"id": 1, "value": "SUPERMERCADOS MAMBO"},
                                   {"id": 5, "value": "VR BENEFICIOS"}]}
        row, _ = _snapshot(issue, datetime.now(timezone.utc))
        self.assertEqual(row["cliente"], "SUPERMERCADOS MAMBO")

    def test_validates_journal_history(self):
        with self.assertRaises(ValueError):
            _snapshot({"id": 1, "subject": "VR Beneficios", "status": {"name": "Novo"}},
                      datetime.now(timezone.utc))

    @patch("ednna.eddy_vr_mysql_sync.salvar_snapshot")
    @patch("ednna.eddy_vr_mysql_sync.buscar_detalhes_chamado")
    @patch("ednna.eddy_vr_mysql_sync.buscar_chamados_projetos")
    def test_imports_without_redmine_writes(self, list_issues, details, save):
        issue = {
            "id": 49227, "subject": "VR Beneficios - inclusao",
            "status": {"name": "Novo"}, "journals": [
                {"id": 700, "notes": "Aguardando", "created_on": "2026-10-20T12:00:00Z"}
            ]
        }
        list_issues.return_value = [issue]
        details.return_value = issue
        result = sincronizar_carteira_vr_mysql()
        self.assertEqual(result["importados"], [49227])
        self.assertTrue(result["cobertura_completa"])
        self.assertEqual(result["envios_realizados"], 0)
        save.assert_called_once()

    @patch("ednna.eddy_vr_mysql_sync.buscar_chamados_projetos", return_value=None)
    def test_fails_closed_when_redmine_unavailable(self, _):
        with self.assertRaises(ValueError):
            sincronizar_carteira_vr_mysql()


if __name__ == "__main__":
    unittest.main()
