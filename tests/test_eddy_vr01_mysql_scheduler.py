import unittest
from unittest.mock import patch

from scripts.eddy_vr01_mysql_scheduler import intervalo_segundos, executar_uma_vez


class VR01SchedulerTests(unittest.TestCase):
    def test_interval_defaults_to_fifteen_minutes(self):
        self.assertEqual(intervalo_segundos(None), 900)

    def test_rejects_aggressive_polling(self):
        with self.assertRaises(ValueError):
            intervalo_segundos("10")
        with self.assertRaises(ValueError):
            intervalo_segundos("abc")

    @patch("scripts.eddy_vr01_mysql_scheduler.executar_worker_vr01")
    def test_reports_read_only_cycle_without_external_actions(self, worker):
        worker.return_value = {
            "estado": "AVALIADO_SOMENTE_LEITURA",
            "sincronizacao": {
                "abertos_consultados": 292, "vr_identificados": 5,
                "importados": [47851], "reutilizados_mysql": [48255],
                "falhas": [],
            },
            "envios_realizados": 0, "redmine_escritas": 0,
        }
        with self.assertLogs("eddy.vr01.scheduler", level="INFO") as captured:
            result = executar_uma_vez()
        self.assertEqual(result["envios_realizados"], 0)
        self.assertEqual(result["redmine_escritas"], 0)
        self.assertIn('"reutilizados_mysql": 1', captured.output[0])
        worker.assert_called_once_with()

    @patch("scripts.eddy_vr01_mysql_scheduler.executar_worker_vr01")
    def test_reports_degraded_state(self, worker):
        worker.return_value = {
            "estado": "DEGRADADO_MYSQL_SOMENTE_LEITURA",
            "sincronizacao": {"falhas": []},
            "envios_realizados": 0, "redmine_escritas": 0,
        }
        with self.assertLogs("eddy.vr01.scheduler", level="INFO") as captured:
            executar_uma_vez()
        self.assertIn("DEGRADADO_MYSQL_SOMENTE_LEITURA", captured.output[0])


if __name__ == "__main__":
    unittest.main()
