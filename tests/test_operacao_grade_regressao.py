"""Regressão: a grade de acompanhamentos não pode depender de por_chamado."""
import ast
import unittest
from pathlib import Path


class GradeOperacaoTest(unittest.TestCase):
    def test_sort_nao_usa_variavel_inexistente(self):
        codigo = Path("pages/Operacao.py").read_text(encoding="utf-8")
        arvore = ast.parse(codigo)
        sorts = [
            node for node in ast.walk(arvore)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sort"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "registros"
        ]
        self.assertTrue(sorts, "Ordenação da grade não encontrada")
        for sort in sorts:
            nomes = {n.id for n in ast.walk(sort) if isinstance(n, ast.Name)}
            self.assertNotIn("por_chamado", nomes)
            self.assertIn("pd", nomes)


if __name__ == "__main__":
    unittest.main()
