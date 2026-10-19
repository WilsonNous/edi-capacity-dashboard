import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from ui.data_provenance import fonte_carteira

BR = ZoneInfo("America/Sao_Paulo")


class ProvenanceTests(unittest.TestCase):
    def test_recent_snapshot_uses_recorded_time(self):
        df = pd.DataFrame([{"_fonte_operacional": "painel.db/status=open",
                            "_snapshot_atualizado_em": "2026-10-19T16:30:00-03:00"}])
        result = fonte_carteira(df, agora=datetime(2026, 10, 19, 16, 40, tzinfo=BR))
        self.assertEqual(result["idade_minutos"], 10)
        self.assertIn("Redmine", result["fonte"])
        self.assertEqual(result["situacao"], "snapshot recente")

    def test_old_snapshot_is_flagged(self):
        df = pd.DataFrame([{"_fonte_operacional": "painel.db/status=open",
                            "_snapshot_atualizado_em": "2026-10-19T10:00:00"}])
        result = fonte_carteira(df, agora=datetime(2026, 10, 19, 17, tzinfo=BR))
        self.assertEqual(result["situacao"], "possivelmente desatualizado")

    def test_missing_or_corrupt_date_is_not_presented_as_fresh(self):
        for stamp in (None, "broken"):
            df = pd.DataFrame([{"_fonte_operacional": "ednna.db/fallback",
                                "_snapshot_atualizado_em": stamp}])
            self.assertIsNone(fonte_carteira(df)["atualizado_em"])

    def test_empty_frame_is_unavailable(self):
        self.assertEqual(fonte_carteira(pd.DataFrame())["situacao"], "sem dados")


if __name__ == "__main__":
    unittest.main()
