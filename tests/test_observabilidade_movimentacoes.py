import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ednna import observabilidade as obs


class MovimentacoesTest(unittest.TestCase):
    def test_eventos_distintos_por_chamado_e_ordem(self):
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(obs, "DB", Path(pasta) / "eventos.db"):
                obs.log_event("EMAIL", "Resposta recebida", chamado_id=49895)
                obs.log_event("REDMINE", "Retorno de e-mail atualizado no Redmine",
                              chamado_id=49895, detalhe="Atualização confirmada")
                obs.log_event("FOLLOWUP", "Follow-up enviado", chamado_id=45069,
                              detalhe="Envio confirmado")
                eventos = obs.listar_eventos(limite=10)
                self.assertEqual(len(eventos), 3)
                self.assertEqual(eventos[0]["chamado_id"], 45069)
                self.assertEqual(len(obs.listar_eventos(chamado_id=49895)), 2)
                self.assertEqual(obs.url_chamado(49895), "https://chamados.nteia.com/issues/49895")

    def test_deduplicacao_nao_apaga_movimentos_diferentes(self):
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(obs, "DB", Path(pasta) / "eventos.db"):
                obs.log_event("REDMINE", "Atualizando", chamado_id=49895, dedup_seconds=60)
                obs.log_event("REDMINE", "Atualizado", chamado_id=49895, dedup_seconds=60)
                self.assertEqual(len(obs.listar_eventos()), 2)


if __name__ == "__main__":
    unittest.main()
