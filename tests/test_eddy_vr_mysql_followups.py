import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from ednna.eddy_vr_mysql_followups import listar_followups_vr01

class TestVR01Followups(unittest.TestCase):
    def test_confirmed_send_deadline_and_reply_block(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            (49227, datetime(2026, 10, 19, 10, tzinfo=timezone.utc)),
            (49289, datetime(2026, 10, 21, 10, tzinfo=timezone.utc)),
        ]
        cur.fetchone.side_effect = [(0,), (1,)]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        cm = MagicMock()
        cm.__enter__.return_value = conn
        with patch("ednna.eddy_vr_mysql_followups.connect", return_value=cm):
            result = listar_followups_vr01(agora="2026-10-22T12:00:00Z")
        self.assertEqual(result["followups"][0]["situacao"], "FOLLOWUP_VENCIDO")
        self.assertEqual(result["followups"][1]["situacao"], "RESPOSTA_RECEBIDA")
        self.assertEqual(result["envios_realizados"], 0)

if __name__ == "__main__":
    unittest.main()
