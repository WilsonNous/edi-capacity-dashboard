import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.eddy_archive_legacy_knowledge import inventariar, TABLES


class LegacyKnowledgeArchiveTests(unittest.TestCase):
    def test_inventory_is_read_only_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "copy.db"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE regras_treinaveis (id TEXT, estado TEXT)")
                conn.execute("INSERT INTO regras_treinaveis VALUES ('R1', 'HOMOLOGADA')")
            before = path.read_bytes()
            report, rows = inventariar(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "regras_treinaveis")
            self.assertEqual(len(rows[0][1]), 64)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(report), len(TABLES))
            self.assertEqual(rows, inventariar(path)[1])

    def test_corrupt_copy_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "copy.db"
            path.write_bytes(b"broken sqlite")
            with self.assertRaises(sqlite3.DatabaseError):
                inventariar(path)
            self.assertEqual(path.read_bytes(), b"broken sqlite")

    def test_missing_copy_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.db"
            with self.assertRaises(FileNotFoundError):
                inventariar(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
