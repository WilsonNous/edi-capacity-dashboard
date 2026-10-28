"""No-network contract tests for VR01 ownership confirmation."""
import unittest
from unittest.mock import patch

from ednna.eddy_ownership import Ownership, OwnershipError, OwnershipState
from ednna.eddy_vr01_ownership_confirmation import confirmar_atribuicao_observada

MODULE = "ednna.eddy_vr01_ownership_confirmation"


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.item = Ownership(
            issue_id=49227, original_assignee_id=12, eddy_assignee_id=99,
            version="2026-10-28T12:00:00Z", state=OwnershipState.CLAIM_PENDING,
        )

    def test_claim_confirmation(self):
        issue = {"id": 49227, "assigned_to": {"id": 99},
                 "updated_on": "2026-10-28T12:01:00Z"}
        with patch(f"{MODULE}.load_ownership", return_value=(self.item, 3)), \
             patch(f"{MODULE}.save_transition", return_value=4) as save:
            result = confirmar_atribuicao_observada(issue, evidencia="Redmine GET after approved claim")
        self.assertEqual(result["estado"], OwnershipState.OWNED.value)
        self.assertEqual(result["redmine_escritas"], 0)
        self.assertEqual(save.call_args.kwargs["expected_revision"], 3)

    def test_return_confirmation(self):
        item = Ownership(issue_id=49227, original_assignee_id=12, eddy_assignee_id=99,
                         version="v2", state=OwnershipState.RETURN_PENDING)
        issue = {"id": 49227, "assigned_to": {"id": 12}, "updated_on": "v3"}
        with patch(f"{MODULE}.load_ownership", return_value=(item, 5)), \
             patch(f"{MODULE}.save_transition", return_value=6):
            result = confirmar_atribuicao_observada(issue, evidencia="Fresh Redmine read")
        self.assertEqual(result["estado"], OwnershipState.RETURNED.value)

    def test_mismatch_does_not_persist(self):
        issue = {"id": 49227, "assigned_to": {"id": 12}, "updated_on": "v3"}
        with patch(f"{MODULE}.load_ownership", return_value=(self.item, 3)), \
             patch(f"{MODULE}.save_transition") as save:
            with self.assertRaisesRegex(OwnershipError, "ATRIBUICAO_NAO_CONFIRMADA"):
                confirmar_atribuicao_observada(issue, evidencia="Fresh Redmine read")
            save.assert_not_called()

    def test_same_version_does_not_persist(self):
        issue = {"id": 49227, "assigned_to": {"id": 99},
                 "updated_on": self.item.version}
        with patch(f"{MODULE}.load_ownership", return_value=(self.item, 3)), \
             patch(f"{MODULE}.save_transition") as save:
            with self.assertRaisesRegex(OwnershipError, "VERSAO_NAO_AVANCOU"):
                confirmar_atribuicao_observada(issue, evidencia="Fresh Redmine read")
            save.assert_not_called()

    def test_missing_evidence_blocks(self):
        with self.assertRaisesRegex(OwnershipError, "EVIDENCIA_AUSENTE"):
            confirmar_atribuicao_observada({"id": 49227}, evidencia="")


if __name__ == "__main__":
    unittest.main()
