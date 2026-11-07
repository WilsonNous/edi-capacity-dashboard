"""Storage budget regression checks without production database access."""
import os
import unittest
from unittest.mock import patch

from ednna import mysql_storage


class StorageBudgetTest(unittest.TestCase):
    def test_warning_is_advisory(self):
        with patch.object(mysql_storage, "storage_health",
                          return_value={"database_bytes": 600 * 1024 * 1024, "table_count": 8}):
            result = mysql_storage.storage_budget(warning_mb=512)
        self.assertTrue(result["over_budget"])
        self.assertEqual(result["table_count"], 8)

    def test_small_database_is_within_budget(self):
        with patch.object(mysql_storage, "storage_health",
                          return_value={"database_bytes": 10 * 1024 * 1024, "table_count": 4}):
            self.assertFalse(mysql_storage.storage_budget(warning_mb=512)["over_budget"])

    def test_reject_nonpositive_budget(self):
        with self.assertRaises(ValueError):
            mysql_storage.storage_budget(warning_mb=0)


if __name__ == "__main__":
    unittest.main()
