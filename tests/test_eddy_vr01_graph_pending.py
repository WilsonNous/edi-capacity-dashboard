"""Safety regressions for Graph send reconciliation; no external calls."""
import unittest
from unittest.mock import patch
from ednna import eddy_vr01_integrated as vr


class GraphPendingTests(unittest.TestCase):
    def setUp(self):
        self.row = {"fase": "AGUARDA_CONTATO_BP",
                    "operacao_pendente": "SOLICITAR_AUTORIZACAO_PORTAL",
                    "original_owner_id": 97, "eddy_owner_id": 166}

    @patch("ednna.email_sender.localizar_email_enviado", return_value={})
    @patch.object(vr, "_identity", return_value=166)
    @patch.object(vr, "_load")
    @patch.dict("os.environ", {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"})
    def test_missing_sent_item_never_confirms(self, load, identity, locate):
        load.return_value = self.row
        self.assertEqual(vr.reconciliar_envio_graph_pendente()["estado"], "ENVIO_NAO_CONFIRMADO")

    @patch("ednna.email_sender.localizar_email_enviado", return_value={
        "id": "abc", "sentDateTime": "2026-11-05T20:00:00Z"})
    @patch.object(vr, "_identity", return_value=166)
    @patch.object(vr, "_load")
    @patch.dict("os.environ", {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"})
    def test_subject_match_does_not_advance_state(self, load, identity, locate):
        load.return_value = self.row
        result = vr.reconciliar_envio_graph_pendente()
        self.assertEqual(result["estado"], "ENVIO_LOCALIZADO_EXIGE_VALIDACAO_DESTINATARIOS")

    @patch("ednna.email_sender.localizar_email_enviado", side_effect=TimeoutError)
    @patch.object(vr, "_identity", return_value=166)
    @patch.object(vr, "_load")
    @patch.dict("os.environ", {"EDNNA_EMAIL_FROM": "edi@netunna.com.br"})
    def test_graph_timeout_does_not_retry_send(self, load, identity, locate):
        load.return_value = self.row
        self.assertEqual(vr.reconciliar_envio_graph_pendente()["estado"], "GRAPH_CONSULTA_ADIADA")


if __name__ == "__main__":
    unittest.main()
