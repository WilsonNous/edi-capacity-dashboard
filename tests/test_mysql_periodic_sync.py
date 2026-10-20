import sys
import types
import unittest
from unittest.mock import patch

from scripts.sync_eddy_mysql import sincronizar_uma_vez


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.redmine = types.ModuleType("redmine_api")
        self.redmine.REDMINE_PROJECT_IDS = [5, 42]
        self.redmine.buscar_chamados_projetos = lambda **kw: [{"id": 1}, {"id": 2}]
        self.redmine.obter_diagnostico_redmine = lambda: {"fonte_dados": "redmine"}
        self.patcher = patch.dict(sys.modules, {"redmine_api": self.redmine})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_confirmed_refresh_imports(self):
        with patch("scripts.sync_eddy_mysql.extrair_snapshot_painel", return_value=([{"id": 1}, {"id": 2}], "now")), \\
             patch("scripts.sync_eddy_mysql.importar_snapshot_painel_mysql", return_value={"selecionados": 2}) as imp:
            result = sincronizar_uma_vez()
        self.assertTrue(result["redmine_confirmado"])
        imp.assert_called_once()

    def test_stale_fallback_never_imports(self):
        self.redmine.obter_diagnostico_redmine = lambda: {"fonte_dados": "painel_sqlite_contingencia"}
        with patch("scripts.sync_eddy_mysql.importar_snapshot_painel_mysql") as imp:
            with self.assertRaises(RuntimeError):
                sincronizar_uma_vez()
            imp.assert_not_called()

    def test_mismatched_ids_never_imports(self):
        with patch("scripts.sync_eddy_mysql.extrair_snapshot_painel", return_value=([{"id": 1}, {"id": 3}], "now")), \\
             patch("scripts.sync_eddy_mysql.importar_snapshot_painel_mysql") as imp:
            with self.assertRaises(RuntimeError):
                sincronizar_uma_vez()
            imp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
