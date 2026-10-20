import unittest
from ednna.eddy_vr_observability import resumir_operacao_vr


class TestVROperationProjection(unittest.TestCase):
    def test_does_not_claim_actions_performed(self):
        batch = {"somente_leitura": True, "falhas": [],
                 "chamados": [{"chamado_id": 49227,
                               "fase_eddy": "AGUARDANDO_CONFIRMACAO_VR",
                               "proxima_acao": "VERIFICAR_RESPOSTA_VR",
                               "followup": "VALIDAR_ENVIO",
                               "evidencia_envio_confirmada": False}]}
        report = resumir_operacao_vr(batch)
        self.assertEqual(report["indicadores"]["voce"], 1)
        self.assertEqual(report["indicadores"]["realizado"], 0)
        self.assertFalse(report["chamados"][0]["documentacao_redmine_confirmada"])

    def test_fails_on_duplicate(self):
        item = {"chamado_id": 1}
        with self.assertRaises(ValueError):
            resumir_operacao_vr({"somente_leitura": True, "chamados": [item, item]})

    def test_failures_are_exceptions(self):
        result = resumir_operacao_vr({"somente_leitura": True, "chamados": [],
                                     "falhas": [{"chamado_id": 5, "erro": "ValueError"}]})
        self.assertEqual(result["indicadores"]["excecoes"], 1)


if __name__ == "__main__":
    unittest.main()
