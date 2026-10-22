"""VR01 must never send when Redmine journal coverage is unverified."""
import unittest
from unittest.mock import patch, MagicMock
from ednna.eddy_vr_dispatcher import _approved_message

class VR01SafetyTests(unittest.TestCase):
    def test_reject_unapproved_or_mismatched_revision(self):
        action = {"action_key": "a", "redmine_updated_on": "v1",
                  "acao": "COBRAR_HABILITACAO_PORTAL", "chamado_id": 49227}
        good = {"redmine_updated_on": "v1", "acao": action["acao"],
                "to": "valid@example.org", "subject": "VR #49227",
                "body": "Solicitamos retorno."}
        self.assertIsNone(_approved_message(action, {"a": dict(good, redmine_updated_on="v2")}))
        self.assertIsNone(_approved_message(action, {"a": dict(good, to="not-an-email")}))
        self.assertEqual(_approved_message(action, {"a": good})["to"], "valid@example.org")

if __name__ == "__main__":
    unittest.main()
