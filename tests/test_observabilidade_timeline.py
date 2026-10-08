import unittest
from ednna.observabilidade import url_chamado, status_evento

class ObservabilidadeTimelineTest(unittest.TestCase):
    def test_link_chamado(self):
        self.assertEqual(url_chamado(45069), 'https://chamados.nteia.com/issues/45069')
        self.assertEqual(url_chamado(None), '')
    def test_nao_confunde_tentativa_com_sucesso(self):
        self.assertEqual(status_evento({'nivel':'INFO','evento':'Tentativa de follow-up'}), 'Registrada / verificar resultado')
        self.assertEqual(status_evento({'nivel':'INFO','evento':'Follow-up enviado','detalhe':'envio confirmado'}), 'Concluída')
    def test_bloqueio_e_falha(self):
        self.assertEqual(status_evento({'nivel':'BLOCKED','evento':'Envio bloqueado'}), 'Bloqueada')
        self.assertEqual(status_evento({'nivel':'ERROR','evento':'Falha no Redmine'}), 'Falha')

if __name__ == '__main__':
    unittest.main()
