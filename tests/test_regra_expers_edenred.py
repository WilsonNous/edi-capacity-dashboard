import unittest
from ednna.regra_expers_edenred import (
    classificar_demanda, preparar_despacho, interpretar_orientacao_retorno,
    CAIXA_POSTAL, CONCILIACAO,
)


class RegraExpersTest(unittest.TestCase):
    def test_canais(self):
        for texto in ("ausência de arquivo", "inclusão de contrato na caixa postal",
                      "alertas", "ausência de vendas no arquivo", "cancelamento de caixa postal"):
            with self.subTest(texto=texto):
                self.assertEqual(classificar_demanda(texto)["destinatario"], CONCILIACAO)
        self.assertEqual(classificar_demanda("abertura de caixa postal")["destinatario"], CAIXA_POSTAL)

    def test_ambiguidade_bloqueada(self):
        self.assertEqual(classificar_demanda("abrir e cancelar caixa postal")["tipo"], "REVISAO_HUMANA")
        self.assertFalse(preparar_despacho(49446, cliente="SIM REDE", descricao_demanda="preciso de ajuda")["ok"])

    def test_rascunho_nao_dispara(self):
        r = preparar_despacho(49446, cliente="SIM REDE", descricao_demanda="Ausência de arquivo de conciliação")
        self.assertTrue(r["ok"])
        self.assertFalse(r["envio_executado"])
        self.assertTrue(r["requer_validacao_humana"])
        self.assertEqual(r["para"], [CONCILIACAO])
        self.assertIn("49446", r["assunto"])

    def test_resposta_nao_e_sucesso(self):
        texto = ("O canal de Concilia Ticket é exclusivo para suporte na abertura de caixa postal. "
                 "Para ausência de arquivo encaminhar à equipe CONCILIAÇÃO ELETRÔNICA "
                 "(conciliacaoeletronica-br@edenred.com).")
        d = interpretar_orientacao_retorno(texto, assunto="EXPERS SIM REDE CN: 49446")
        self.assertEqual(d["classificacao"], "REDIRECIONAMENTO_CANAL")
        self.assertFalse(d["followup_externo_permitido"])


if __name__ == "__main__":
    unittest.main()
