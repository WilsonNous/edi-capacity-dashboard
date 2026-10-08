import unittest
from ednna.contexto_continuidade_universal import avaliar_contexto


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

    def test_transacao_confirmada(self):
        r = avaliar_contexto(123, envio_confirmado=True)
        self.assertEqual(r['estado'], 'ACOMPANHAMENTO_TRANSACIONAL')


if __name__ == '__main__':
    unittest.main()
