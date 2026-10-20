import unittest
from unittest.mock import patch
from scripts.eddy_vr01_open_inventory import inventariar_vr_abertos


class VRInventoryTests(unittest.TestCase):
    @patch("scripts.eddy_vr01_open_inventory.buscar_detalhes_chamado")
    @patch("scripts.eddy_vr01_open_inventory.buscar_chamados_projetos")
    def test_only_vr_open_candidates(self, list_issues, detail):
        list_issues.return_value = [
            {"id": 1, "subject": "VR BENEFICIOS - inclusão"},
            {"id": 2, "subject": "REDE - inclusão"},
        ]
        detail.return_value = {"id": 1, "subject": "VR BENEFICIOS - inclusão",
                               "status": {"name": "Aguardando"}, "journals": []}
        result = inventariar_vr_abertos()
        self.assertEqual(result["candidatos_vr_encontrados"], 1)
        self.assertEqual(len(result["detalhes_validos"]), 1)
        detail.assert_called_once()

    @patch("scripts.eddy_vr01_open_inventory.buscar_detalhes_chamado")
    @patch("scripts.eddy_vr01_open_inventory.buscar_chamados_projetos")
    def test_missing_history_is_reported(self, list_issues, detail):
        list_issues.return_value = [{"id": 1, "subject": "VR BENEFICIO"}]
        detail.return_value = {"id": 1, "subject": "VR BENEFICIO"}
        result = inventariar_vr_abertos()
        self.assertEqual(len(result["falhas"]), 1)
        self.assertEqual(result["detalhes_validos"], [])


if __name__ == "__main__":
    unittest.main()
