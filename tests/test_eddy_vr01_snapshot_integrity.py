import json
import unittest
from unittest.mock import MagicMock, patch

from ednna.eddy_vr_mysql_operation import _snapshot_elegivel
from ednna.mysql_panel_bridge import importar_snapshot_painel_mysql


class VR01SnapshotIntegrityTests(unittest.TestCase):
    def test_incomplete_snapshot_not_operational(self):
        self.assertFalse(_snapshot_elegivel({"payload_json": {"status": {"name": "Novo"}}}))
        self.assertTrue(_snapshot_elegivel({"payload_json": {
            "_eddy_journals_completos": True, "status": {"name": "Em andamento"}
        }}))

    def test_terminal_snapshot_not_operational(self):
        self.assertFalse(_snapshot_elegivel({"payload_json": {
            "_eddy_journals_completos": True, "status": {"name": "Concluído"}
        }}))

    @patch("ednna.mysql_panel_bridge.connect")
    @patch("ednna.mysql_panel_bridge._upsert")
    @patch("ednna.mysql_panel_bridge.extrair_snapshot_painel")
    def test_bulk_import_preserves_complete_payload_same_version(self, extract, upsert, connect):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
        issue = {"id": 49227, "updated_on": "2026-10-20T17:00:00Z",
                 "status": {"name": "Em andamento"}, "custom_fields": []}
        extract.return_value = ([issue], stamp)
        cursor = MagicMock()
        cursor.fetchone.return_value = (json.dumps({
            **issue, "_eddy_journals_completos": True,
            "journals": [{"id": 99, "notes": "Resposta VR"}],
        }),)
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        importar_snapshot_painel_mysql("unused", aplicar=True)
        row = upsert.call_args.args[3]
        self.assertTrue(row["payload_json"]["_eddy_journals_completos"])
        self.assertEqual(row["payload_json"]["journals"][0]["id"], 99)

    @patch("ednna.mysql_panel_bridge.connect")
    @patch("ednna.mysql_panel_bridge._upsert")
    @patch("ednna.mysql_panel_bridge.extrair_snapshot_painel")
    def test_new_version_invalidates_complete_marker(self, extract, upsert, connect):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
        issue = {"id": 49227, "updated_on": "2026-10-21T17:00:00Z",
                 "status": {"name": "Em andamento"}, "custom_fields": []}
        extract.return_value = ([issue], stamp)
        cursor = MagicMock()
        cursor.fetchone.return_value = (json.dumps({
            **issue, "updated_on": "2026-10-20T17:00:00Z",
            "_eddy_journals_completos": True,
        }),)
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        importar_snapshot_painel_mysql("unused", aplicar=True)
        row = upsert.call_args.args[3]
        self.assertNotIn("_eddy_journals_completos", row["payload_json"])


if __name__ == "__main__":
    unittest.main()
