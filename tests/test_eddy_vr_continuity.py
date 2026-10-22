import unittest
from ednna.eddy_vr_continuity import decidir_continuidade_vr

def issue(n):
    return {"id": n, "subject": "VR - Inclusão de estabelecimento", "status": {"name": "Em andamento"}}

def note(sender, message, when):
    return {"created_on": when, "notes": f"De: {sender}\n{message}"}

class ContinuityTests(unittest.TestCase):
    def test_48786_client_portal_followup(self):
        d = decidir_continuidade_vr(issue(48786), [
            note("conciliacao@vr.com.br", "O estabelecimento deve realizar habilitação no portal e dar o aceite.", "2026-09-18")])
        self.assertEqual(d["acao"], "COBRAR_HABILITACAO_PORTAL")
        self.assertEqual(d["destino"], "CLIENTE")

    def test_49227_ask_movement_before_human(self):
        d = decidir_continuidade_vr(issue(49227), [
            note("jessica@redesander.com.br", "Todos já estão aparecendo no portal.", "2026-09-29"),
            note("conciliacao@vr.com.br", "Todos os CNPJs entram automaticamente no arquivo VR_NETUNNA_SANDER.", "2026-10-19")])
        self.assertEqual(d["acao"], "CONSULTAR_MOVIMENTACAO_CLIENTE")

    def test_movement_confirmation_routes_to_human(self):
        d = decidir_continuidade_vr(issue(49227), [
            note("conciliacao@vr.com.br", "Entram automaticamente no arquivo VR_NETUNNA_SANDER.", "2026-10-19"),
            note("jessica@redesander.com.br", "Já temos vendas realizadas.", "2026-10-20")])
        self.assertEqual(d["acao"], "COBRAR_VALIDACAO_RECEPCAO")

    def test_terminal_never_notifies(self):
        obj = issue(48255)
        obj["status"] = {"name": "Concluído", "is_closed": True}
        self.assertEqual(decidir_continuidade_vr(obj, [])["acao"], "NENHUMA")

    def test_vr_reply_is_not_customer_confirmation(self):
        d = decidir_continuidade_vr(issue(48786), [
            note("conciliacao@vr.com.br", "Após o aceite no portal o fluxo será iniciado.", "2026-09-18")])
        self.assertEqual(d["etapa"], "HABILITACAO_CLIENTE_PENDENTE")

if __name__ == "__main__":
    unittest.main()
