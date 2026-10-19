import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ednna.recovery_guard import persistencia_operacional_disponivel


class RecoveryGuardTests(unittest.TestCase):
    def test_mysql_never_activates_legacy_inclusion_queue(self):
        with patch.dict(os.environ, {"EDDY_DB_ENGINE": "mysql"}):
            self.assertFalse(persistencia_operacional_disponivel())

    def test_missing_legacy_file_fails_closed(self):
        with patch.dict(os.environ, {"EDDY_DB_ENGINE": "sqlite", "EDNNA_DB_PATH": "/tmp/eddy-missing-test-db-9d0e.db"}):
            self.assertFalse(persistencia_operacional_disponivel())

    def test_corrupt_legacy_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ednna.db"
            path.write_bytes(b"not a sqlite database")
            with patch.dict(os.environ, {"EDDY_DB_ENGINE": "sqlite", "EDNNA_DB_PATH": str(path)}):
                self.assertFalse(persistencia_operacional_disponivel())

    def test_valid_legacy_file_can_be_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ednna.db"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE demo (id INTEGER)")
            with patch.dict(os.environ, {"EDDY_DB_ENGINE": "sqlite", "EDNNA_DB_PATH": str(path)}):
                self.assertTrue(persistencia_operacional_disponivel())


if __name__ == "__main__":
    unittest.main()
