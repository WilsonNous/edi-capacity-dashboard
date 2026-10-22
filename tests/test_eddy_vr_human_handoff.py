import unittest

from ednna.eddy_vr_human_handoff import encaminhar_validacao_inclusao


ISSUE = {"id": 48255, "subject": "MAMBO - VR BENEFICIOS - Inclusão de 71676316002947",
         "status": {"name": "Em andamento", "is_closed": False}}
OWNER = {"nome": "Responsável EDI", "email": "responsavel@example.org"}


class HumanHandoffTests(unittest.TestCase):
    def test_requires_human_validation_after_customer_confirmation(self):
        result = encaminhar_validacao_inclusao(
            ISSUE, resposta_cliente_confirmada=True,
            validacao_tecnica_confirmada=False, responsavel_humano=OWNER)
        self.assertEqual(result["situacao"], "VALIDACAO_HUMANA_PENDENTE")
        self.assertTrue(result["notificar"])
        self.assertFalse(result["execucao_externa"])
        self.assertFalse(result["conclusao_automatica_permitida"])
        self.assertIn("48255", result["assunto"])

    def test_never_notifies_terminal_issue(self):
        issue = {**ISSUE, "status": {"name": "Concluído", "is_closed": True}}
        result = encaminhar_validacao_inclusao(
            issue, resposta_cliente_confirmada=True,
            validacao_tecnica_confirmada=False, responsavel_humano=OWNER)
        self.assertEqual(result["situacao"], "TERMINAL")
        self.assertFalse(result["notificar"])

    def test_no_unverified_email_or_owner(self):
        result = encaminhar_validacao_inclusao(
            ISSUE, resposta_cliente_confirmada=False,
            validacao_tecnica_confirmada=False, responsavel_humano=OWNER)
        self.assertFalse(result["notificar"])
        result = encaminhar_validacao_inclusao(
            ISSUE, resposta_cliente_confirmada=True,
            validacao_tecnica_confirmada=False, responsavel_humano=None)
        self.assertEqual(result["situacao"], "RESPONSAVEL_HUMANO_NAO_RESOLVIDO")
        self.assertFalse(result["notificar"])


if __name__ == "__main__":
    unittest.main()
