"""Offline tests for strict Redmine pagination and sequential page recovery."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

source = (Path(__file__).resolve().parents[1] / "redmine_api.py").read_text(encoding="utf-8")
module = ast.parse(source)
functions = {n.name: n for n in module.body if isinstance(n, ast.FunctionDef)}
ns = {}
exec(compile(ast.Module(body=[functions["_validar_paginas_redmine"], functions["buscar_chamados_projeto"]], type_ignores=[]), "<pagination>", "exec"), ns)


def page(offset, total=201, count=100):
    return {"total_count": total, "issues": [{"id": i + 1} for i in range(offset, offset + count)]}


class RedminePaginationTests(unittest.TestCase):
    def test_complete_listing(self):
        pages = {0: page(0), 100: page(100), 200: page(200, count=1)}
        self.assertEqual(len(ns["_validar_paginas_redmine"](pages, 201, 100)), 201)

    def test_missing_page_fails_closed(self):
        with self.assertRaises(ValueError):
            ns["_validar_paginas_redmine"]({0: page(0), 200: page(200, count=1)}, 201, 100)

    def test_total_count_changed_fails_closed(self):
        with self.assertRaises(ValueError):
            ns["_validar_paginas_redmine"]({0: page(0), 100: page(100, total=202), 200: page(200, count=1)}, 201, 100)

    def test_duplicate_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            ns["_validar_paginas_redmine"]({0: page(0), 100: page(0, count=100), 200: page(200, count=1)}, 201, 100)

    def test_short_page_fails_closed(self):
        with self.assertRaises(ValueError):
            ns["_validar_paginas_redmine"]({0: page(0), 100: page(100, count=99), 200: page(200, count=1)}, 201, 100)

    def test_sequential_pages_and_single_page_recovery(self):
        calls = []
        def get(path, params):
            calls.append(params["offset"])
            if params["offset"] == 100 and calls.count(100) == 1:
                raise ConnectionError("intermittent TCP")
            return page(params["offset"], count=1 if params["offset"] == 200 else 100)
        ns["_get"] = get
        with self.assertRaises(ConnectionError):
            ns["buscar_chamados_projeto"](5)
        self.assertEqual(calls, [0, 100])
        # Actual per-page retries are provided by _get, not by restarting listing.
        calls.clear()
        def recovered_get(path, params):
            calls.append(params["offset"])
            return page(params["offset"], count=1 if params["offset"] == 200 else 100)
        ns["_get"] = recovered_get
        self.assertEqual(len(ns["buscar_chamados_projeto"](5)), 201)
        self.assertEqual(calls, [0, 100, 200])

    def test_empty_result_valid(self):
        self.assertEqual(ns["_validar_paginas_redmine"]({0: {"total_count": 0, "issues": []}}, 0, 100), [])


if __name__ == "__main__":
    unittest.main()
