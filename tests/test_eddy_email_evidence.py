import unittest

from ednna.eddy_email_evidence import (
    journals_com_evidencias, normalizar_evidencia_email, nota_resposta_redmine,
)
from ednna.eddy_vr_followup import planejar_followup


class EmailEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "chamado_id": 49227, "tipo": "ENVIO_CONFIRMADO",
            "message_id": "mail-abc", "provedor": "MicrosoftGraph",
            "endereco": "atendimento@example.com",
            "ocorrido_em": "2026-10-20T10:00:00-03:00",
        }

    def test_confirmed_send_starts_48h(self):
        journals = journals_com_evidencias([], [self.base, self.base], 49227)
        self.assertEqual(len(journals), 1)
        result = planejar_followup(
            {"chamado_id": 49227, "estado": "AGUARDANDO_CONFIRMACAO_VR",
             "acao": "VERIFICAR_RESPOSTA_VR"},
            journals, agora="2026-10-22T13:00:01+00:00",
        )
        self.assertEqual(result["situacao"], "FOLLOWUP_VENCIDO")

    def test_reply_stops_followup(self):
        reply = {**self.base, "tipo": "RESPOSTA_RECEBIDA",
                 "message_id": "mail-reply", "corpo_texto": "Estamos analisando.",
                 "ocorrido_em": "2026-10-21T10:00:00-03:00"}
        journals = journals_com_evidencias([], [self.base, reply], 49227)
        result = planejar_followup(
            {"chamado_id": 49227, "estado": "AGUARDANDO_CONFIRMACAO_VR",
             "acao": "VERIFICAR_RESPOSTA_VR"},
            journals, agora="2026-10-23T13:00:00+00:00",
        )
        self.assertEqual(result["situacao"], "RESPOSTA_RECEBIDA")

    def test_full_response_in_redmine_note(self):
        reply = {**self.base, "tipo": "RESPOSTA_RECEBIDA",
                 "corpo_texto": "Linha 1\nLinha 2"}
        note = nota_resposta_redmine(reply, 49227, analise="Aguardar",
                                     fase="AGUARDANDO", proxima_acao="FOLLOWUP")
        self.assertIn("Linha 1\nLinha 2", note)
        self.assertIn("ANÁLISE DO EDDY", note)

    def test_unverified_send_rejected(self):
        with self.assertRaises(ValueError):
            normalizar_evidencia_email({**self.base, "tipo": "ENVIADO"}, 49227)

    def test_missing_timezone_rejected(self):
        with self.assertRaises(ValueError):
            normalizar_evidencia_email(
                {**self.base, "ocorrido_em": "2026-10-20T10:00:00"}, 49227)


if __name__ == "__main__":
    unittest.main()
