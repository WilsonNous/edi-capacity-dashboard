import unittest
from unittest.mock import patch

from scripts.eddy_vr01_mysql_cycle import executar_ciclo_vr01


class VRMySQLCycleTests(unittest.TestCase):
    @patch("scripts.eddy_vr01_mysql_cycle.operacao_vr_mysql")
    @patch("scripts.eddy_vr01_mysql_cycle.sincronizar_carteira_vr_mysql")
    def test_blocks_partial_sync(self, sync, operation):
        sync.return_value = {"cobertura_completa": False, "importados": [1]}
        result = executar_ciclo_vr01()
        self.assertEqual(result["estado"], "BLOQUEADO_SINCRONIZACAO_PARCIAL")
        operation.assert_not_called()

    @patch("scripts.eddy_vr01_mysql_cycle.operacao_vr_mysql")
    @patch("scripts.eddy_vr01_mysql_cycle.sincronizar_carteira_vr_mysql")
    def test_blocks_missing_mysql_records(self, sync, operation):
        sync.return_value = {"cobertura_completa": True, "importados": [1]}
        operation.return_value = {"chamados": []}
        result = executar_ciclo_vr01()
        self.assertEqual(result["estado"], "BLOQUEADO_DIVERGENCIA_MYSQL")

    @patch("scripts.eddy_vr01_mysql_cycle.operacao_vr_mysql")
    @patch("scripts.eddy_vr01_mysql_cycle.sincronizar_carteira_vr_mysql")
    def test_reports_success_without_sends(self, sync, operation):
        sync.return_value = {"cobertura_completa": True, "importados": [1]}
        operation.return_value = {"chamados": [{"chamado_id": 1}]}
        result = executar_ciclo_vr01()
        self.assertEqual(result["estado"], "AVALIADO_SOMENTE_LEITURA")
        self.assertEqual(result["envios_realizados"], 0)
        self.assertEqual(result["redmine_escritas"], 0)


if __name__ == "__main__":
    unittest.main()
