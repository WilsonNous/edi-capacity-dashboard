import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from ednna.central_envios import avaliar_janela_externa, exigir_janela_externa, JanelaExternaFechada

TZ = ZoneInfo("America/Sao_Paulo")


class CalendarioCentralEnviosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "feriados.json"
        self.path.write_text(json.dumps({
            "nacional:2026": ["2026-10-12"],
            "estadual:SC:2026": ["2026-08-11"],
            "municipal:SC:FLORIANOPOLIS:2026": ["2026-03-23"],
            "nacional:2027": [],
            "estadual:SC:2027": [],
            "municipal:SC:FLORIANOPOLIS:2027": []
        }))
        self.env = patch.dict("os.environ", {
            "EDDY_FERIADOS_ARQUIVO": str(self.path),
            "EDDY_ENVIO_UF": "SC",
            "EDDY_ENVIO_MUNICIPIO": "FLORIANOPOLIS",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def check(self, iso):
        return avaliar_janela_externa(agora=datetime.fromisoformat(iso).replace(tzinfo=TZ))

    def test_weekday_open(self):
        self.assertTrue(self.check("2026-10-08T10:00:00")["permitido"])

    def test_before_seven(self):
        self.assertEqual(self.check("2026-10-08T06:59:00")["proxima_janela"][:16], "2026-10-08T07:00")

    def test_after_nineteen(self):
        self.assertEqual(self.check("2026-10-08T19:00:00")["proxima_janela"][:16], "2026-10-09T07:00")

    def test_national_holiday(self):
        self.assertEqual(self.check("2026-10-12T10:00:00")["proxima_janela"][:16], "2026-10-13T07:00")

    def test_municipal_holiday(self):
        self.assertFalse(self.check("2026-03-23T10:00:00")["permitido"])

    def test_state_holiday(self):
        self.assertFalse(self.check("2026-08-11T10:00:00")["permitido"])

    def test_missing_calendar_fails_closed(self):
        self.path.unlink()
        with self.assertRaises(JanelaExternaFechada):
            exigir_janela_externa(agora=datetime(2026, 10, 8, 10, tzinfo=TZ))

    def test_missing_locality_fails_closed(self):
        with patch.dict("os.environ", {"EDDY_ENVIO_MUNICIPIO": ""}):
            with self.assertRaises(JanelaExternaFechada):
                exigir_janela_externa(agora=datetime(2026, 10, 8, 10, tzinfo=TZ))


if __name__ == "__main__":
    unittest.main()
