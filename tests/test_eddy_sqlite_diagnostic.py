import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.eddy_sqlite_diagnostic import diagnosticar_sqlite


class EDDYSQLiteDiagnosticTests(unittest.TestCase):
    def test_missing_database_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.db"
            self.assertEqual(diagnosticar_sqlite(str(path))["status"], "AUSENTE")
            self.assertFalse(path.exists())

    def test_valid_database_is_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.db"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE example (id INTEGER)")
            self.assertEqual(diagnosticar_sqlite(str(path))["status"], "INTEGRO")

    def test_corruption_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.db"
            original = b"not sqlite data"
            path.write_bytes(original)
            self.assertIn(diagnosticar_sqlite(str(path))["status"], {"CORROMPIDO", "INACESSIVEL_OU_CORROMPIDO"})
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
