import unittest
from unittest.mock import patch, MagicMock
from ednna.eddy_vr_decision_audit import preparar_decisao, registrar_decisao


class TestVRDecisionAudit(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "chamado": {"id": 49289, "origem": "VR BENEFICIO",
                        "estado": "Concluído",
                        "payload_json": {"id": 49289, "subject": "VR BENEFICIOS",
                                         "status": {"name": "Concluído"}}},
            "journals": [{"id": 1, "notas": "Recepção TEIACARD confirmada"}],
        }

    @patch("ednna.eddy_vr_decision_audit.carregar_snapshot")
    def test_deterministic_digest(self, load):
        load.return_value = self.snapshot
        first = preparar_decisao(49289)
        second = preparar_decisao(49289)
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(first["decisao"]["acao"], "NENHUMA")

    @patch("ednna.eddy_vr_decision_audit.carregar_snapshot", return_value=None)
    def test_missing_snapshot(self, load):
        with self.assertRaises(ValueError):
            preparar_decisao(49227)

    @patch("ednna.eddy_vr_decision_audit.connect")
    @patch("ednna.eddy_vr_decision_audit.carregar_snapshot")
    def test_persist_idempotent_sql_and_no_external_execution(self, load, connect):
        load.return_value = self.snapshot
        cursor = MagicMock()
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        result = registrar_decisao(49289)
        self.assertFalse(result["execucao_externa"])
        sql = cursor.execute.call_args.args[0]
        self.assertIn("ON DUPLICATE KEY", sql)
        self.assertNotIn("UPDATE eddy_chamados", sql)


if __name__ == "__main__":
    unittest.main()
