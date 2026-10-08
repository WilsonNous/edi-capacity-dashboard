"""Regression gates for Redmine outage and rejected ticket quarantine."""
import ast
import unittest
from pathlib import Path
from ednna.status_guard import chamado_em_quarentena


class RedmineSafetyTest(unittest.TestCase):
    def test_rejected_ticket_is_quarantined(self):
        self.assertTrue(chamado_em_quarentena(47173))
        self.assertFalse(chamado_em_quarentena(47152))

    def test_point_read_cannot_bypass_global_breaker(self):
        source = Path("redmine_api.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        funcs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == "buscar_detalhes_chamado"]
        self.assertEqual(len(funcs), 1)
        calls = [node for node in ast.walk(funcs[0]) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "_get"]
        self.assertEqual(len(calls), 1)
        kwargs = {kw.arg: kw.value for kw in calls[0].keywords}
        self.assertIsInstance(kwargs["ignorar_circuit_breaker_global"], ast.Constant)
        self.assertIs(kwargs["ignorar_circuit_breaker_global"].value, False)

    def test_demand_queue_consults_quarantine(self):
        source = Path("ednna/motor_inclusoes_operacional.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "gerar_demandas_operacionais"]
        self.assertEqual(len(funcs), 1)
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == "chamado_em_quarentena"
                            for n in ast.walk(funcs[0])))


if __name__ == "__main__":
    unittest.main()
