import unittest
from unittest.mock import patch

from scripts.eddy_vr01_batch_assessment import avaliar_carteira_vr


class VRBatchAssessmentTests(unittest.TestCase):
    @patch("scripts.eddy_vr01_batch_assessment.planejar_followup")
    @patch("scripts.eddy_vr01_batch_assessment.avaliar_vr")
    @patch("scripts.eddy_vr01_batch_assessment.buscar_detalhes_chamado")
    @patch("scripts.eddy_vr01_batch_assessment.buscar_chamados_projetos")
    def test_classifies_only_vr_and_reports_followup(self, listing, detail, evaluate, followup):
        listing.return_value = [{"id": 10, "subject": "VR BENEFICIOS - EC"},
                                {"id": 11, "subject": "REDE - EC"}]
        detail.return_value = {"id": 10, "subject": "VR BENEFICIOS - EC",
                               "status": {"name": "Aguardando"}, "journals": []}
        evaluate.return_value = {"chamado_id": 10, "estado": "AGUARDANDO_CONFIRMACAO_VR",
                                 "acao": "VERIFICAR_RESPOSTA_VR"}
        followup.return_value = {"situacao": "VALIDAR_ENVIO"}
        result = avaliar_carteira_vr()
        self.assertEqual(result["vr_identificados"], 1)
        self.assertEqual(result["avaliados"], 1)
        self.assertEqual(result["chamados"][0]["followup"], "VALIDAR_ENVIO")
        self.assertFalse(result["chamados"][0]["execucao_externa"])
        detail.assert_called_once()

    @patch("scripts.eddy_vr01_batch_assessment.buscar_detalhes_chamado")
    @patch("scripts.eddy_vr01_batch_assessment.buscar_chamados_projetos")
    def test_missing_history_fails_closed(self, listing, detail):
        listing.return_value = [{"id": 10, "subject": "VR BENEFICIO"}]
        detail.return_value = {"id": 10, "status": {"name": "Aberto"}}
        result = avaliar_carteira_vr()
        self.assertEqual(result["avaliados"], 0)
        self.assertEqual(len(result["falhas"]), 1)


if __name__ == "__main__":
    unittest.main()
