import unittest
from unittest.mock import patch

from ednna.simrede_francimar import (
    FRANCIMAR, classificar_ocorrencias_simrede,
    diagnosticar_mensagem, _mensagens_paginadas,
)


def mensagem(assunto, corpo="", remetente=FRANCIMAR):
    return {
        "from": {"emailAddress": {"address": remetente}},
        "subject": assunto,
        "body": {"content": corpo},
        "conversationId": "conv-1",
        "id": "msg-1",
    }


class TestSimRede(unittest.TestCase):
    def test_classificacao_pelo_assunto(self):
        resultado = classificar_ocorrencias_simrede(mensagem("STONE - falta de arquivo"))
        self.assertEqual([(r["player"], r["tipo"]) for r in resultado],
                         [("STONE", "FALTA_ARQUIVO")])

    def test_remetente_diferente_nao_classifica(self):
        self.assertEqual(classificar_ocorrencias_simrede(
            mensagem("STONE - falta de arquivo", remetente="outro@example.com")), [])

    def test_motivos_sem_expor_conteudo(self):
        self.assertEqual(diagnosticar_mensagem(mensagem("STONE")), "TIPO_NAO_RECONHECIDO")
        self.assertEqual(diagnosticar_mensagem(mensagem("falta de arquivo")), "PLAYER_NAO_RECONHECIDO")
        self.assertEqual(diagnosticar_mensagem(mensagem("Bom dia")), "PLAYER_E_TIPO_NAO_RECONHECIDOS")

    @patch("ednna.simrede_francimar._graph_get")
    def test_paginacao(self, get):
        get.side_effect = [
            {"value": [{"id": "a"}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"},
            {"value": [{"id": "b"}]},
        ]
        resultado = list(_mensagens_paginadas("edi@example.com", 5))
        self.assertEqual([x["id"] for x in resultado], ["a", "b"])
        self.assertEqual(get.call_count, 2)

    @patch("ednna.simrede_francimar._graph_get")
    def test_paginacao_limite(self, get):
        get.return_value = {"value": [{"id": "a"}, {"id": "b"}]}
        self.assertEqual(len(list(_mensagens_paginadas("edi@example.com", 1))), 1)


if __name__ == "__main__":
    unittest.main()
