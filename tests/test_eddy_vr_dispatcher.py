import unittest
from unittest.mock import patch
from ednna.eddy_vr_dispatcher import _approved_message, executar_fila_vr01

ACTION = {"action_key": "a" * 64, "chamado_id": 49227,
          "redmine_updated_on": "2026-10-21T12:00:00Z",
          "acao": "CONSULTAR_MOVIMENTACAO_CLIENTE"}
APPROVED = {"redmine_updated_on": ACTION["redmine_updated_on"],
            "acao": ACTION["acao"], "to": "cliente@example.com",
            "subject": "VR #49227 acompanhamento", "body": "Solicitamos confirmacao."}

class TestVR01Dispatcher(unittest.TestCase):
    def test_explicit_approval_required(self):
        self.assertIsNone(_approved_message(ACTION, {}))
        self.assertIsNone(_approved_message(ACTION, {ACTION["action_key"]: {**APPROVED, "to": "invalid"}}))
        self.assertIsNone(_approved_message(ACTION, {ACTION["action_key"]: {**APPROVED, "redmine_updated_on": "old"}}))
        self.assertEqual(_approved_message(ACTION, {ACTION["action_key"]: APPROVED})["to"], "cliente@example.com")

    def test_readiness_blocks_without_mysql_or_graph(self):
        with patch("ednna.eddy_vr_dispatcher.verificar_prontidao_vr01",
                   return_value={"pronto": False, "bloqueios": ["EXECUCAO_EXTERNA_DESABILITADA"]}):
            with patch("ednna.eddy_vr_dispatcher.connect") as db:
                with patch("ednna.eddy_vr_dispatcher.enviar_email_graph") as send:
                    result = executar_fila_vr01()
                    self.assertEqual(result["estado"], "BLOQUEADO_PRONTIDAO")
                    db.assert_not_called()
                    send.assert_not_called()

if __name__ == "__main__":
    unittest.main()
