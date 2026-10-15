"""Testes de isolamento e segurança do agendador de follow-ups."""
import sys
import types
import unittest
from unittest.mock import patch

from ednna.worker_followups import executar_ciclo_followups


class FollowupWorkerTests(unittest.TestCase):
    def test_executa_apenas_automaticos_e_limita_lote(self):
        chamados = [
            {"chamado_id": 1, "estado_followup": "FOLLOWUP_PRONTO", "modo_followup": "AUTOMATICO"},
            {"chamado_id": 2, "estado_followup": "FOLLOWUP_PRONTO", "modo_followup": "ASSISTIDO"},
            {"chamado_id": 3, "estado_followup": "AGUARDANDO_PRAZO", "modo_followup": "AUTOMATICO"},
            {"chamado_id": 4, "estado_followup": "FOLLOWUP_PRONTO", "modo_followup": "AUTOMATICO"},
        ]
        enviados = []
        fake = types.ModuleType("ednna.followup_engine")
        fake.avaliar_followups = lambda: {"itens": chamados, "automaticos_prontos": 2}
        fake.followup_automatico = lambda item: item["modo_followup"] == "AUTOMATICO"
        fake.executar_followup = lambda item: (enviados.append(item["chamado_id"]) or {"ok": True, "estado": "ENVIADO"})
        with patch.dict(sys.modules, {"ednna.followup_engine": fake}), patch.dict("os.environ", {"EDDY_FOLLOWUP_BATCH_SIZE": "1"}):
            resumo = executar_ciclo_followups()
        self.assertEqual(enviados, [1])
        self.assertEqual(resumo["sucessos"], 1)
        self.assertEqual(resumo["lote"], 1)

    def test_bloqueio_nao_contabiliza_sucesso(self):
        fake = types.ModuleType("ednna.followup_engine")
        fake.avaliar_followups = lambda: {"itens": [{"chamado_id": 10, "estado_followup": "FOLLOWUP_PRONTO"}], "automaticos_prontos": 1}
        fake.followup_automatico = lambda _: True
        fake.executar_followup = lambda _: {"ok": False, "estado": "PREFLIGHT_INDISPONIVEL"}
        with patch.dict(sys.modules, {"ednna.followup_engine": fake}):
            resumo = executar_ciclo_followups()
        self.assertEqual(resumo["sucessos"], 0)
        self.assertEqual(resumo["bloqueados"], 1)


if __name__ == "__main__":
    unittest.main()
