import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from ednna.mysql_panel_bridge import converter_issue, importar_snapshot_painel_mysql


class MySQLPanelBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "painel.db"
        stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TABLE snapshots (chave TEXT, payload_json TEXT, atualizado_em TEXT)")
            con.execute("INSERT INTO snapshots VALUES (?, ?, ?)", (
                "issues|status=open|limit=100",
                json.dumps([{"id": 123, "subject": "Inclusão", "status": {"name": "Aberto"},
                             "custom_fields": [{"id": 1, "value": "Cliente A"}]}]),
                stamp,
            ))

    def test_dry_run_never_writes(self):
        with patch("ednna.mysql_panel_bridge.salvar_snapshot") as save:
            result = importar_snapshot_painel_mysql(str(self.path))
        self.assertEqual(result["selecionados"], 1)
        self.assertEqual(result["gravados"], 0)
        save.assert_not_called()

    def test_apply_maps_original_issue_and_writes(self):
        with patch("ednna.mysql_panel_bridge.salvar_snapshot") as save:
            result = importar_snapshot_painel_mysql(str(self.path), aplicar=True)
        self.assertEqual(result["gravados"], 1)
        self.assertEqual(save.call_args.args[0]["id"], 123)
        self.assertEqual(save.call_args.args[0]["estado"], "Aberto")

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):
            converter_issue({"id": "1.5"}, "2026-10-19")

    def test_old_snapshot_rejected(self):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE snapshots SET atualizado_em='2020-01-01T00:00:00-03:00'")
        with patch("ednna.mysql_panel_bridge.salvar_snapshot") as save:
            with self.assertRaises(ValueError):
                importar_snapshot_painel_mysql(str(self.path), aplicar=True)
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
