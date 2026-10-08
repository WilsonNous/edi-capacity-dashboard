import unittest
from ednna.contexto_continuidade_universal import avaliar_contexto, reconciliar_graph


class ContextoUniversalTest(unittest.TestCase):
    def test_atuacao_humana_sem_graph_nao_reinicia(self):
        r = avaliar_contexto(49446, houve_atuacao=True)
        self.assertEqual(r['estado'], 'ATUACAO_PREVIA_RECONCILIAR_GRAPH')
        self.assertTrue(r['reconciliacao_graph_necessaria'])
        self.assertFalse(r['primeiro_envio_automatico_permitido'])

    def test_resposta_redirecionamento_tem_prioridade(self):
        r = avaliar_contexto(49446, houve_atuacao=True, envio_confirmado=True,
                             retorno={'classificacao': 'REDIRECIONAMENTO_CANAL'})
        self.assertEqual(r['estado'], 'REDIRECIONAMENTO_PENDENTE')

    def test_graph_localiza_envio_humano_e_resposta(self):
        r = reconciliar_graph(
            49446, caixa_postal="edi@netunna.com.br", houve_atuacao=True,
            buscar_enviados=lambda **kwargs: [{"sentDateTime": "2026-10-05T12:57:00Z", "conversationId": "abc"}],
            buscar_resposta=lambda **kwargs: {"id": "resp", "receivedDateTime": "2026-10-08T12:14:00Z", "conversationId": "abc"},
        )
        self.assertTrue(r["resposta_encontrada"])
        self.assertEqual(r["conversation_id"], "abc")
        self.assertFalse(r["primeiro_envio_automatico_permitido"])

    def test_graph_falha_bloqueia_envio(self):
        def falha(**kwargs):
            raise RuntimeError("timeout")
        r = reconciliar_graph(49446, caixa_postal="edi@netunna.com.br",
                             buscar_enviados=falha, buscar_resposta=falha)
        self.assertEqual(r["estado"], "GRAPH_INDISPONIVEL")
        self.assertFalse(r["primeiro_envio_automatico_permitido"])

    def test_transacao_confirmada(self):
        r = avaliar_contexto(123, envio_confirmado=True)
        self.assertEqual(r['estado'], 'ACOMPANHAMENTO_TRANSACIONAL')


if __name__ == '__main__':
    unittest.main()
