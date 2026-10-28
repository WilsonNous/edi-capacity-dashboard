import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "ednna" / "redmine_shared_inventory.py"
spec = importlib.util.spec_from_file_location("redmine_shared_inventory", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SharedInventoryTests(unittest.TestCase):
    def test_recent_confirmed_result_is_reused_without_refetch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "CACHE", Path(directory) / "inventory.json"):
                calls = []
                def fetch():
                    calls.append(1)
                    return {"confirmado": True, "fonte": "redmine", "chamados": [{"id": 49227}]}
                first = module.confirmed_inventory_for_mysql(fetch, now=lambda: 1000)
                second = module.confirmed_inventory_for_mysql(fetch, now=lambda: 1030)
                self.assertEqual(len(calls), 1)
                self.assertEqual(first["fonte"], "redmine")
                self.assertTrue(second["somente_observacao"])
                self.assertEqual(second["idade_s"], 30)

    def test_expired_result_is_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "CACHE", Path(directory) / "inventory.json"):
                calls = []
                def fetch():
                    calls.append(1)
                    return {"confirmado": True, "fonte": "redmine", "chamados": [{"id": 49227}]}
                module.confirmed_inventory_for_mysql(fetch, now=lambda: 1000)
                module.confirmed_inventory_for_mysql(fetch, now=lambda: 1100)
                self.assertEqual(len(calls), 2)

    def test_failed_remote_result_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "CACHE", Path(directory) / "inventory.json"):
                calls = []
                def fetch():
                    calls.append(1)
                    return {"confirmado": False, "fonte": "sqlite", "chamados": [{"id": 49227}]}
                module.confirmed_inventory_for_mysql(fetch, now=lambda: 1000)
                module.confirmed_inventory_for_mysql(fetch, now=lambda: 1001)
                self.assertEqual(len(calls), 2)

    def test_serialized_listing_calls_remote_and_never_reuses_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "CACHE", Path(directory) / "inventory.json"):
                calls = []
                def fetch():
                    calls.append(1)
                    return {"confirmado": True, "fonte": "redmine", "chamados": [{"id": 50318}]}
                module.serialized_redmine_listing(fetch)
                module.serialized_redmine_listing(fetch)
                self.assertEqual(len(calls), 2)

    def test_serialized_listing_does_not_retry_failed_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "CACHE", Path(directory) / "inventory.json"):
                calls = []
                def fetch():
                    calls.append(1)
                    raise OSError("remote unavailable")
                with self.assertRaises(OSError):
                    module.serialized_redmine_listing(fetch)
                self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
