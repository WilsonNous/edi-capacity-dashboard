import unittest
from unittest.mock import patch

from ednna import telemetria_redmine as telemetria


class TestTelemetriaRedmine(unittest.TestCase):
    def setUp(self):
        with telemetria._LOCK:
            telemetria._EVENTOS.clear()
            telemetria._ULTIMO_LOG = 0.0

    def test_taxa_sucesso_e_tipos_de_timeout(self):
        with patch.object(telemetria, "monotonic", return_value=1000.0):
            with patch("builtins.print"):
                telemetria.registrar_resultado("OK", 0.5)
                resumo = telemetria.registrar_resultado("TIMEOUT_CONEXAO", 12.0)
        self.assertEqual(resumo["total"], 2)
        self.assertEqual(resumo["sucessos"], 1)
        self.assertEqual(resumo["timeout_conexao"], 1)
        self.assertEqual(resumo["taxa_sucesso_pct"], 50.0)
        self.assertEqual(resumo["latencia_ok_media_s"], 0.5)

    def test_janela_expira_eventos_antigos(self):
        with patch("builtins.print"):
            with patch.object(telemetria, "monotonic", return_value=1000.0):
                telemetria.registrar_resultado("TIMEOUT_CONEXAO", 8.0)
            with patch.object(telemetria, "monotonic", return_value=1400.0):
                resumo = telemetria.registrar_resultado("OK", 0.4)
        self.assertEqual(resumo["total"], 1)
        self.assertEqual(resumo["taxa_sucesso_pct"], 100.0)

    def test_snapshot_sem_dados_sensiveis(self):
        with patch("builtins.print"):
            telemetria.registrar_resultado("OK", 0.2)
        snapshot = telemetria.obter_saude_redmine()
        self.assertEqual(snapshot["por_tipo"], {"OK": 1})
        self.assertNotIn("chamado", str(snapshot).lower())


if __name__ == "__main__":
    unittest.main()
