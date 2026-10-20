import unittest
from unittest.mock import patch
from ednna.eddy_vr_redmine_import import importar_chamado_vr


class VRImportTests(unittest.TestCase):
    @patch("ednna.eddy_vr_redmine_import.buscar_detalhes_chamado")
    def test_disallow_other_issue(self, fetch):
        with self.assertRaises(ValueError):
            importar_chamado_vr(123)
        fetch.assert_not_called()

    @patch("ednna.eddy_vr_redmine_import.salvar_snapshot")
    @patch("ednna.eddy_vr_redmine_import.buscar_detalhes_chamado")
    def test_import_journals(self, fetch, save):
        fetch.return_value = {"id": 49227, "subject": "REDE SANDER - VR BENEFICIO",
                              "status": {"name": "Aguardando"},
                              "journals": [{"id": 10, "notes": "Consulta encaminhada",
                                            "user": {"name": "Operador"}}]}
        result = importar_chamado_vr(49227)
        self.assertEqual(result["journals_importados"], 1)
        self.assertEqual(save.call_args.args[1][0]["chamado_id"], 49227)
        self.assertEqual(save.call_args.args[1][0]["notas"], "Consulta encaminhada")

    @patch("ednna.eddy_vr_redmine_import.salvar_snapshot")
    @patch("ednna.eddy_vr_redmine_import.buscar_detalhes_chamado")
    def test_missing_journals_fails_closed(self, fetch, save):
        fetch.return_value = {"id": 49289, "subject": "VR BENEFICIOS"}
        with self.assertRaises(ValueError):
            importar_chamado_vr(49289)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
