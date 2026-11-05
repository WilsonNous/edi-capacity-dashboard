"""Regression tests for VR01 pending assignment reconciliation."""
import unittest
from unittest.mock import patch

from ednna import eddy_vr01_integrated as vr


class AssignmentReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "fase": "PRONTO_PARA_ASSUMIR",
            "operacao_pendente": "ASSUMIR_REDMINE",
            "original_owner_id": 97,
            "eddy_owner_id": 166,
        }

    @patch.object(vr, "_advance")
    @patch.object(vr, "_event")
    @patch.object(vr, "_read_issue")
    @patch.object(vr, "_identity", return_value=166)
    @patch.object(vr, "_load")
    def test_confirmed_assignment_advances_without_put(self, load, identity, read, event, advance):
        load.return_value = self.row
        read.return_value = {"assigned_to": {"id": 166}}
        result = vr.reconciliar_assuncao_pendente()
        self.assertEqual(result["estado"], "ASSUNCAO_RECONCILIADA")
        event.assert_called_once_with("ASSUNCAO_EDDY", "166")
        advance.assert_called_once_with("PRONTO_PARA_ASSUMIR", "ASSUMIR_REDMINE", "ASSUMIDO_EDDY")

    @patch.object(vr, "_advance")
    @patch.object(vr, "_event")
    @patch.object(vr, "_read_issue", side_effect=TimeoutError())
    @patch.object(vr, "_identity", return_value=166)
    @patch.object(vr, "_load")
    def test_timeout_keeps_reservation(self, load, identity, read, event, advance):
        load.return_value = self.row
        self.assertEqual(vr.reconciliar_assuncao_pendente()["estado"], "RECONCILIACAO_ADIADA")
        event.assert_not_called()
        advance.assert_not_called()

    @patch.object(vr, "_advance")
    @patch.object(vr, "_event")
    @patch.object(vr, "_read_issue", return_value={"assigned_to": {"id": 97}})
    @patch.object(vr, "_identity", return_value=166)
    @patch.object(vr, "_load")
    def test_original_owner_keeps_reservation(self, load, identity, read, event, advance):
        load.return_value = self.row
        self.assertEqual(vr.reconciliar_assuncao_pendente()["estado"], "AGUARDA_CONFIRMACAO_REDMINE")
        event.assert_not_called()
        advance.assert_not_called()


if __name__ == "__main__":
    unittest.main()
