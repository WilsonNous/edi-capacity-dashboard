import unittest
from unittest.mock import MagicMock, patch

from scripts.eddy_vr01_mysql_worker import executar_worker_vr01


class TestVRWorker(unittest.TestCase):
    @patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01")
    @patch("scripts.eddy_vr01_mysql_worker.connect")
    def test_lock_unavailable_skips(self, connect, cycle):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (0,)
        connect.return_value.__enter__.return_value = conn
        result = executar_worker_vr01()
        self.assertEqual(result["estado"], "IGNORADO_EXECUCAO_CONCORRENTE")
        cycle.assert_not_called()

    @patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01")
    @patch("scripts.eddy_vr01_mysql_worker.connect")
    def test_success_releases_lock(self, connect, cycle):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        connect.return_value.__enter__.return_value = conn
        cycle.return_value = {
            "estado": "AVALIADO_SOMENTE_LEITURA",
            "sincronizacao": {"importados": [1], "falhas": []},
        }
        result = executar_worker_vr01()
        self.assertEqual(result["estado"], "AVALIADO_SOMENTE_LEITURA")
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("RELEASE_LOCK", cursor.execute.call_args.args[0])

    @patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01")
    @patch("scripts.eddy_vr01_mysql_worker.connect")
    def test_failure_releases_lock(self, connect, cycle):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        connect.return_value.__enter__.return_value = conn
        cycle.side_effect = RuntimeError("Redmine offline")
        with self.assertRaises(RuntimeError):
            executar_worker_vr01()
        self.assertIn("RELEASE_LOCK", cursor.execute.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
