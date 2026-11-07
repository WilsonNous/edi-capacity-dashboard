"""MySQL routing and fail-closed regression tests for EDDY action tracking."""
import os
import tempfile
import unittest
from unittest.mock import patch

from ednna import acompanhamento_acoes as actions


class ActionMigrationTest(unittest.TestCase):
    def test_reply_interpretation_routes_to_mysql(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ednna.db")
            with patch.dict(os.environ, {"EDDY_DB_ENGINE": "mysql", "EDNNA_DB_PATH": path}):
                with patch("ednna.mysql_interpretacoes_retorno.registrar",
                           return_value={"classificacao": "AGUARDAR_TERCEIRO"}) as save:
                    result = actions.registrar_interpretacao_retorno(
                        50318, "VR01", corpo="Resposta", graph_message_id="graph-1")
                self.assertEqual(result["classificacao"], "AGUARDAR_TERCEIRO")
                save.assert_called_once()
                with patch("ednna.mysql_interpretacoes_retorno.ultima",
                           return_value={"classificacao": "AGUARDAR_TERCEIRO"}):
                    self.assertEqual(
                        actions.ultima_interpretacao_retorno(50318, "VR01")["classificacao"],
                        "AGUARDAR_TERCEIRO")
                with self.assertRaisesRegex(RuntimeError, "ACOMPANHAMENTO_SQLITE_DESATIVADO"):
                    actions._conectar()
                self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
