import unittest
from unittest.mock import patch

from ednna.eddy_vr_origin import identificar_vr
from ednna.eddy_vr_rule import avaliar_vr


class VRRealPortfolioTests(unittest.TestCase):
    def test_five_redmine_export_subjects(self):
        subjects = {
            49227: "REDE SANDER - VR BENEFICIO - INCLUSÃO DE ESTABELECIMENTO",
            49119: "POSTOS ROTA- VR BENEFICIOS- Abertura de Relacionamento",
            48255: "MAMBO-VR BENEFICIOS - Inclusão de 71676316002947",
            48786: "POSTOS ANDREZZA - VR BENEFICIOS - Inclusão de estabelecimentos",
            47851: "SUPERMERCADOSMAMBO - VRBENEFICIO - Falta de arquivo - Chamado filho",
        }
        for issue_id, subject in subjects.items():
            with self.subTest(issue_id=issue_id):
                self.assertTrue(identificar_vr({
                    "id": issue_id, "subject": subject,
                    "custom_fields": [{"id": 5, "value": "VR BENEFICIO"}],
                }))

    @patch("redmine_api.traduzir_custom_field", return_value="VR BENEFICIO")
    def test_numeric_origin_code(self, translate):
        self.assertTrue(identificar_vr({"subject": "Inclusão", "custom_fields": [
            {"id": 5, "value": "123"}
        ]}))
        translate.assert_called_once_with("123", 5)

    @patch("redmine_api.traduzir_custom_field", return_value="OUTRA ADQUIRENTE")
    def test_unknown_origin_not_inferred_from_subject(self, _):
        self.assertFalse(identificar_vr({
            "subject": "VR BENEFICIO - teste", "custom_fields": [
                {"id": 5, "value": "999"}
            ]
        }))

    def test_missing_file_is_not_inclusion(self):
        issue = {
            "id": 47851, "subject": "SUPERMERCADOSMAMBO - VRBENEFICIO - Falta de arquivo",
            "tracker": {"name": "EDI - Falta de Arquivo"},
            "status": {"name": "Aberto"},
            "custom_fields": [{"id": 5, "value": "VR BENEFICIO"}],
            "description": "NSA 339 e novo salto 355",
        }
        result = avaliar_vr(issue, [])
        self.assertEqual(result["acao"], "INVESTIGAR_NSA_E_ARQUIVOS")
        self.assertFalse(result["execucao_externa"])


if __name__ == "__main__":
    unittest.main()
