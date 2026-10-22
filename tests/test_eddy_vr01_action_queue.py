import unittest
from ednna.eddy_vr_action_queue import criar_intencao
from ednna.eddy_vr_continuity import decidir_continuidade_vr

class Vr01QueueTests(unittest.TestCase):
    def issue(self, issue_id=49227, status="Em Andamento", tracker="EDI - Inclusão de EC/Domc"):
        return {"id": issue_id, "updated_on": "2026-10-19T11:16:00Z",
                "_eddy_journals_completos": True,
                "subject": "VR BENEFICIO - INCLUSÃO DE ESTABELECIMENTO",
                "tracker": {"name": tracker}, "status": {"name": status}}

    def test_idempotent_intent(self):
        issue = self.issue()
        a = criar_intencao(issue, [])
        b = criar_intencao(issue, [])
        self.assertEqual(a["action_key"], b["action_key"])
        self.assertEqual(a["situacao"], "PENDENTE")

    def test_incomplete_snapshot_blocked(self):
        issue = self.issue()
        issue.pop("_eddy_journals_completos")
        self.assertEqual(criar_intencao(issue, [])["situacao"], "BLOQUEADO_HISTORICO_INCOMPLETO")

    def test_terminal_not_queued(self):
        self.assertEqual(criar_intencao(self.issue(status="Concluído"), [])["situacao"], "TERMINAL")

    def test_inclusion_subject_overrides_missing_file_tracker(self):
        issue = self.issue(48255, tracker="EDI - Falta de Arquivo")
        decision = decidir_continuidade_vr(issue, [])
        self.assertNotEqual(decision["acao"], "VALIDAR_E_SOLICITAR_TODOS_NSAS")

    def test_vr_provider_not_customer(self):
        issue = self.issue(48786)
        journals = [{"created_on": "2026-09-18", "notes":
                     "De: conciliacao@vr.com.br\nO estabelecimento deve realizar a habilitação através do portal, e dar o aceite."}]
        self.assertEqual(decidir_continuidade_vr(issue, journals)["acao"], "COBRAR_HABILITACAO_PORTAL")

    def test_sander_vr_reply_triggers_customer_movement(self):
        issue = self.issue()
        journals = [{"created_on": "2026-10-19", "notes":
                     "De: conciliacao@vr.com.br\nTodos os CNPJs entram automaticamente no arquivo VR_NETUNNA_SANDER."}]
        self.assertEqual(decidir_continuidade_vr(issue, journals)["acao"], "CONSULTAR_MOVIMENTACAO_CLIENTE")

if __name__ == "__main__":
    unittest.main()
