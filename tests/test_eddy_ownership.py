import unittest

from ednna.eddy_ownership import (
    Ownership, OwnershipError, OwnershipState, confirm_claim, confirm_return,
    handoff_notice, request_claim, request_return, set_work_state,
)


class OwnershipProtocolTests(unittest.TestCase):
    def setUp(self):
        self.item = Ownership(issue_id=47851, original_assignee_id=12,
                              eddy_assignee_id=99, version="2026-10-23T10:00:00Z")

    def test_happy_path_with_confirmations(self):
        pending = request_claim(self.item, current_assignee_id=12,
                                current_version=self.item.version)
        self.assertEqual(pending.state, OwnershipState.CLAIM_PENDING)
        owned = confirm_claim(pending, redmine_assignee_id=99,
                              new_version="v2", evidence="redmine-journal-101")
        waiting = set_work_state(owned, OwnershipState.WAITING_THIRD_PARTY)
        human = set_work_state(waiting, OwnershipState.HUMAN_REQUIRED)
        returning = request_return(human, current_assignee_id=99, current_version="v2")
        returned = confirm_return(returning, redmine_assignee_id=12,
                                  new_version="v3", evidence="redmine-journal-102")
        notice = handoff_notice(returned, actions="Historico analisado",
                                next_action="Validar documento")
        self.assertEqual(notice["recipient_assignee_id"], 12)
        self.assertEqual(notice["redmine_evidence"], "redmine-journal-102")

    def test_changed_version_blocks_claim(self):
        result = request_claim(self.item, current_assignee_id=12, current_version="changed")
        self.assertEqual(result.state, OwnershipState.CONFLICT)

    def test_other_assignee_blocks_claim(self):
        result = request_claim(self.item, current_assignee_id=15,
                               current_version=self.item.version)
        self.assertEqual(result.state, OwnershipState.CONFLICT)

    def test_no_work_without_confirmed_claim(self):
        with self.assertRaises(OwnershipError):
            set_work_state(self.item, OwnershipState.HUMAN_REQUIRED)

    def test_wrong_redmine_confirmation_blocks_claim(self):
        pending = request_claim(self.item, current_assignee_id=12,
                                current_version=self.item.version)
        result = confirm_claim(pending, redmine_assignee_id=12,
                               new_version="v2", evidence="journal")
        self.assertEqual(result.state, OwnershipState.CONFLICT)

    def test_no_notice_before_confirmed_return(self):
        with self.assertRaises(OwnershipError):
            handoff_notice(self.item, actions="analisado", next_action="verificar")

    def test_changed_owner_blocks_return(self):
        pending = request_claim(self.item, current_assignee_id=12,
                                current_version=self.item.version)
        owned = confirm_claim(pending, redmine_assignee_id=99,
                              new_version="v2", evidence="journal")
        human = set_work_state(owned, OwnershipState.HUMAN_REQUIRED)
        result = request_return(human, current_assignee_id=42, current_version="v2")
        self.assertEqual(result.state, OwnershipState.CONFLICT)

    def test_no_false_return_confirmation(self):
        pending = request_claim(self.item, current_assignee_id=12,
                                current_version=self.item.version)
        owned = confirm_claim(pending, redmine_assignee_id=99,
                              new_version="v2", evidence="journal")
        human = set_work_state(owned, OwnershipState.HUMAN_REQUIRED)
        returning = request_return(human, current_assignee_id=99, current_version="v2")
        result = confirm_return(returning, redmine_assignee_id=99,
                                new_version="v3", evidence="journal")
        self.assertEqual(result.state, OwnershipState.CONFLICT)


if __name__ == "__main__":
    unittest.main()
