import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.eddy_sqlite_triage import inspect_directory


class TestSqliteTriage(unittest.TestCase):
    def test_reports_valid_database_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "eddy.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE evidencias (id INTEGER PRIMARY KEY)")
                conn.execute("INSERT INTO evidencias VALUES (1)")
            result = inspect_directory(Path(tmp))
            self.assertTrue(result["somente_leitura"])
            self.assertEqual(result["bancos"][0]["integridade"], "ok")
            with sqlite3.connect(db_path) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0], 1)

    def test_reports_corruption_without_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.db"
            path.write_bytes(b"not a sqlite database")
            result = inspect_directory(Path(tmp))
            self.assertEqual(result["bancos"][0]["integridade"], "erro")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
