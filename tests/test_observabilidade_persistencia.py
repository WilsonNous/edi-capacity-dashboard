import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ednna import observabilidade as obs


class PersistenciaObservabilidadeTest(unittest.TestCase):
    def test_migracao_preserva_eventos_legados(self):
        with tempfile.TemporaryDirectory() as pasta:
            legado = Path(pasta) / "legado.db"
            persistente = Path(pasta) / "persistente.db"
            with patch.object(obs, "DB", legado), patch.object(obs, "LEGACY_DB", legado):
                obs.log_event("EMAIL", "Resposta monitorada", chamado_id=47659)
            with patch.object(obs, "DB", persistente), patch.object(obs, "LEGACY_DB", legado):
                eventos = obs.listar_eventos(chamado_id=47659)
                self.assertEqual(len(eventos), 1)
                self.assertTrue(persistente.exists())
                obs.log_event("REDMINE", "Atualizado", chamado_id=47659)
                self.assertEqual(len(obs.listar_eventos(chamado_id=47659)), 2)

if __name__ == "__main__":
    unittest.main()
