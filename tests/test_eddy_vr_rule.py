import unittest
from ednna.eddy_vr_rule import avaliar_vr


class VREddyTests(unittest.TestCase):
    def test_49289_concluido_nao_reprocessar(self):
        issue = {"id": 49289, "subject": "REDE SANTA LUCIA - VR BENEFICIOS", "status": {"name": "Concluído"}}
        resultado = avaliar_vr({"id": 49289, "origem": "VR BENEFICIO", "estado": "CONCLUÍDO", "payload_json": issue})
        self.assertEqual(resultado["estado"], "CONCLUIDO")
        self.assertEqual(resultado["acao"], "NENHUMA")

    def test_49227_com_consulta_ja_feita(self):
        issue = {"id": 49227, "subject": "REDE SANDER - VR BENEFICIO", "description": "Inclusão de estabelecimento"}
        journals = [{"notas": "O cliente confirmou a habilitação realizada. Olá, time VR, poderiam verificar? Não recebemos arquivos."}]
        resultado = avaliar_vr({"id": 49227, "origem": "VR BENEFICIO", "estado": "AGUARDANDO RETORNO ADQUIRENTE", "payload_json": issue}, journals)
        self.assertEqual(resultado["estado"], "AGUARDANDO_CONFIRMACAO_VR")
        self.assertEqual(resultado["acao"], "VERIFICAR_RESPOSTA_VR")
        self.assertFalse(resultado["execucao_externa"])

    def test_sem_journals_nao_inventa_historico(self):
        issue = {"id": 49227, "subject": "REDE SANDER - VR BENEFICIO", "description": "Cadastro já realizado e vinculado"}
        resultado = avaliar_vr({"id": 49227, "origem": "VR BENEFICIO", "estado": "Em andamento", "payload_json": issue})
        self.assertEqual(resultado["estado"], "AUTORIZACAO_NAO_COMPROVADA")

    def test_nao_elegivel(self):
        resultado = avaliar_vr({"id": 123, "origem": "GETNET", "payload_json": {"id": 123, "subject": "GETNET"}})
        self.assertEqual(resultado["acao"], "NENHUMA")

if __name__ == "__main__":
    unittest.main()
