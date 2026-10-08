import unittest
from ednna.interpretacao_retorno import interpretar_retorno

RETORNO = """Bom dia, Prezados, As solicitações de configuração para compartilhamento de dados financeiros
(arquivos EDI) somente serão realizadas mediante o envio do termo devidamente preenchido
e assinado pelo proprietário ou responsável legal da empresa. Preferencialmente,
solicitamos também o envio de um documento com foto do responsável.
Por questões de segurança e conformidade, não serão aceitas solicitações sem o termo formalizado.
Protocolo de atendimento: 70706
Atenciosamente,
Em 01/10/2026 EDI NN escreveu:
Solicitamos a inclusão de estabelecimento. Cliente POSTOS ROTA."""

class InterpretacaoRetornoTest(unittest.TestCase):
    def test_greencard_exige_documentacao_e_bloqueia_followup(self):
        r = interpretar_retorno(RETORNO, assunto="GREENCARD - Inclusão de Estabelecimento - POSTOS ROTA - CN: 49394", recebido_em="2026-10-01T11:51:00-03:00")
        self.assertEqual(r["classificacao"], "PENDENCIA_DOCUMENTAL")
        self.assertEqual(r["protocolo"], "70706")
        self.assertFalse(r["followup_externo_permitido"])
        self.assertTrue(r["requer_validacao_humana"])
        self.assertEqual(len(r["documentos_obrigatorios"]), 1)
        self.assertEqual(len(r["documentos_recomendados"]), 1)
        self.assertNotIn("Solicitamos a inclusão", r["evidencia"])
        self.assertEqual(r["prazo_revisao_em"], "2026-10-03T11:51:00-03:00")

    def test_ambiguidade_nao_autoriza_envio(self):
        r = interpretar_retorno("Bom dia. Estamos verificando.", assunto="GREENCARD")
        self.assertEqual(r["classificacao"], "REVISAO_HUMANA")
        self.assertFalse(r["followup_externo_permitido"])
        self.assertTrue(r["requer_validacao_humana"])

    def test_nao_confunde_texto_citado_com_exigencia_nova(self):
        r = interpretar_retorno("Recebido, obrigado.\nEm 01/10/2026 EDI escreveu:\nSomente serão realizadas mediante o envio do termo assinado.", assunto="GREENCARD")
        self.assertEqual(r["classificacao"], "REVISAO_HUMANA")

if __name__ == "__main__":
    unittest.main()
