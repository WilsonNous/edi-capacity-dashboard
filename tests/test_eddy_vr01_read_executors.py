"""Offline unit tests for VR01 read-side executors."""
import unittest
from ednna.eddy_vr01_read_executors import (
    read_redmine_journals, monitor_graph_replies, verificar_validacao_adquirente,
)


class VR01ReadExecutorsTests(unittest.TestCase):
    def test_journals_retry_and_sort(self):
        calls = []
        def fetch():
            calls.append(1)
            if len(calls) == 1:
                raise TimeoutError("timeout")
            return {"issue": {"id": 50318, "assigned_to": {"id": 97},
                    "journals": [{"id": 3, "created_on": "2026-11-05"},
                                 {"id": 1, "created_on": "2026-11-04"}]}}
        result = read_redmine_journals(fetch=fetch, sleep=lambda _: None)
        self.assertTrue(result["confirmado"])
        self.assertEqual([j["id"] for j in result["journals"]], [1, 3])
        self.assertEqual(len(calls), 2)

    def test_journals_exhausted(self):
        def fail():
            raise TimeoutError()
        result = read_redmine_journals(fetch=fail, sleep=lambda _: None, attempts=3)
        self.assertEqual(result["estado"], "REDMINE_INDISPONIVEL")

    def test_journals_missing_is_not_success(self):
        result = read_redmine_journals(fetch=lambda: {"issue": {"id": 50318}},
                                       sleep=lambda _: None)
        self.assertFalse(result["confirmado"])

    def test_reply_is_not_authorization(self):
        def messages(**kwargs):
            return [{"conversationId": "c", "id": "m", "receivedDateTime": "2026-11-05T20:01:00Z",
                     "from": {"emailAddress": {"address": "client@example.org"}}}]
        result = monitor_graph_replies(caixa_postal="edi@example.org", conversation_id="c",
                                       sent_at="2026-11-05T20:00:00Z", list_messages=messages)
        self.assertEqual(len(result["respostas"]), 1)
        self.assertFalse(result["autorizacao_confirmada"])

    def test_acquirer_requires_both_independent_evidences(self):
        self.assertFalse(verificar_validacao_adquirente(
            portal_evidence_id="p", arquivo_evidence_id="a")["validado"])
        self.assertFalse(verificar_validacao_adquirente(
            portal_evidence_id="p", arquivo_evidence_id="a",
            verificador=lambda kind, key: kind == "AUTORIZACAO_PORTAL")["validado"])
        self.assertTrue(verificar_validacao_adquirente(
            portal_evidence_id="p", arquivo_evidence_id="a",
            verificador=lambda kind, key: True)["validado"])


if __name__ == "__main__":
    unittest.main()
