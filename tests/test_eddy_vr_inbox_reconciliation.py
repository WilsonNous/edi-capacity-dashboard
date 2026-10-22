import os
import unittest
from unittest.mock import patch, MagicMock
from ednna.eddy_vr_inbox_reconciliation import reconciliar_respostas_vr01

class TestInboxReconciliation(unittest.TestCase):
    def test_no_mailbox_blocks(self):
        with patch.dict(os.environ, {"EDNNA_EMAIL_FROM": ""}):
            self.assertEqual(reconciliar_respostas_vr01([49227])["estado"], "BLOQUEADO_CAIXA_NAO_CONFIGURADA")

    def test_graph_failure_does_not_persist(self):
        with patch.dict(os.environ, {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"}):
            with patch("ednna.eddy_vr_inbox_reconciliation.connect") as db:
                result = reconciliar_respostas_vr01([49227], buscar=lambda **kwargs: 1/0)
                self.assertEqual(result["estado"], "PARCIAL_SEM_GRAVACAO")
                db.assert_not_called()

    def test_reply_quarantines_pending_intent(self):
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        cm = MagicMock()
        cm.__enter__.return_value = conn
        with patch.dict(os.environ, {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"}):
            with patch("ednna.eddy_vr_inbox_reconciliation.connect", return_value=cm):
                result = reconciliar_respostas_vr01([49227,49227], buscar=lambda **kwargs: {
                    "internetMessageId": "<reply@example.com>",
                    "receivedDateTime": "2026-10-21T10:00:00Z"})
        self.assertEqual(result["respostas"], 1)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("REVISAR_RESPOSTA_RECEBIDA", cursor.execute.call_args_list[-1].args[0])

if __name__ == "__main__":
    unittest.main()
