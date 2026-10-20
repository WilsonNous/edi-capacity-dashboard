import unittest
from datetime import datetime, timezone
from ednna.eddy_vr_followup import planejar_followup

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
DECISION = {"chamado_id": 49227, "estado": "AGUARDANDO_CONFIRMACAO_VR",
            "acao": "VERIFICAR_RESPOSTA_VR"}


class FollowupTests(unittest.TestCase):
    def test_no_verified_send(self):
        r = planejar_followup(DECISION, [{"notas": "Consulta enviada"}], agora=NOW)
        self.assertEqual(r["situacao"], "VALIDAR_ENVIO")

    def test_due_after_48h(self):
        r = planejar_followup(DECISION, [
            {"criado_em": "2026-10-18T12:00:00+00:00", "evidencia_envio": True}
        ], agora=NOW)
        self.assertEqual(r["situacao"], "FOLLOWUP_VENCIDO")

    def test_waiting(self):
        r = planejar_followup(DECISION, [
            {"criado_em": "2026-10-19T12:00:00+00:00", "evidencia_envio": True}
        ], agora=NOW)
        self.assertEqual(r["situacao"], "AGUARDANDO_PRAZO")

    def test_reply_suspends(self):
        r = planejar_followup(DECISION, [
            {"criado_em": "2026-10-17T12:00:00+00:00", "evidencia_envio": True},
            {"criado_em": "2026-10-18T12:00:00+00:00", "evidencia_resposta": True}
        ], agora=NOW)
        self.assertEqual(r["situacao"], "RESPOSTA_RECEBIDA")

    def test_terminal(self):
        r = planejar_followup({"chamado_id": 49289, "estado": "CONCLUIDO",
                               "acao": "NENHUMA"}, [], agora=NOW)
        self.assertEqual(r["situacao"], "SEM_FOLLOWUP")


if __name__ == "__main__":
    unittest.main()
