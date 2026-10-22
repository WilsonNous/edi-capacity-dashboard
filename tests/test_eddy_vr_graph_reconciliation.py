import os
import unittest
from unittest.mock import patch, MagicMock
from ednna.eddy_vr_graph_reconciliation import reconciliar_envios_vr01

class TestVrGraphEvidence(unittest.TestCase):
    def test_missing_mailbox_blocks(self):
        with patch.dict(os.environ, {"EDNNA_EMAIL_FROM": ""}):
            self.assertEqual(reconciliar_envios_vr01([49227])["estado"], "BLOQUEADO_CAIXA_NAO_CONFIGURADA")

    def test_partial_graph_failure_never_persists(self):
        def fail(**kwargs):
            raise RuntimeError("graph offline")
        with patch.dict(os.environ, {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"}):
            with patch("ednna.eddy_vr_graph_reconciliation.connect") as db:
                result = reconciliar_envios_vr01([49227], buscar=fail)
                self.assertEqual(result["estado"], "PARCIAL_SEM_GRAVACAO")
                db.assert_not_called()

    def test_confirmed_sent_items_are_persisted_without_send(self):
        cursor = MagicMock()
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        cm = MagicMock()
        cm.__enter__.return_value = connection
        with patch.dict(os.environ, {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"}):
            with patch("ednna.eddy_vr_graph_reconciliation.connect", return_value=cm):
                result = reconciliar_envios_vr01([49227, 49227], buscar=lambda **kwargs: [
                    {"internetMessageId": "<sent@example.com>", "sentDateTime": "2026-10-19T10:00:00Z"}])
        self.assertEqual(result["consultados"], 1)
        self.assertEqual(result["evidencias"], 1)
        self.assertEqual(result["envios_realizados"], 0)
        self.assertEqual(cursor.execute.call_count, 1)

if __name__ == "__main__":
    unittest.main()
