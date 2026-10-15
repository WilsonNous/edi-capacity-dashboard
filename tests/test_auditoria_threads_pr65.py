import unittest
from unittest.mock import patch
from ednna.auditoria_threads_graph import avaliar_candidatos, auditar_threads_ausentes


class TestAuditoriaGraph(unittest.TestCase):
    def setUp(self):
        self.item = {"chamado_id": 123, "enviado_em": "2026-10-15T10:00:00+00:00",
                     "estado_followup": "SEM_THREAD"}

    def test_candidato_unico_nao_autoriza_envio(self):
        m = [{"id": "m1", "conversationId": "c1", "sentDateTime": "2026-10-15T10:05:00Z"}]
        r = avaliar_candidatos(self.item, m)
        self.assertEqual(r["estado"], "CANDIDATO_UNICO_REVISAR")
        self.assertFalse(r["envio_permitido"])
        self.assertFalse(r["thread_reconstruida"])

    def test_multiplas_candidatas_e_anterior_ignorada(self):
        m = [
            {"id": "old", "conversationId": "c1", "sentDateTime": "2026-10-14T10:00:00Z"},
            {"id": "a", "conversationId": "c1", "sentDateTime": "2026-10-15T10:10:00Z"},
            {"id": "b", "conversationId": "c2", "sentDateTime": "2026-10-15T10:15:00Z"},
        ]
        r = avaliar_candidatos(self.item, m)
        self.assertEqual(r["candidatos"], 2)
        self.assertEqual(r["estado"], "MULTIPLAS_CANDIDATAS_REVISAR")

    def test_graph_indisponivel_nao_libera(self):
        with patch("ednna.email_sender.listar_emails_enviados_por_chamado", side_effect=TimeoutError("x")):
            r = auditar_threads_ausentes([self.item])
        self.assertEqual(r["itens"][0]["estado"], "GRAPH_INDISPONIVEL")
        self.assertEqual(r["threads_liberadas"], 0)


if __name__ == "__main__":
    unittest.main()
