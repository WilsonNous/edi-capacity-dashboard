import importlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CorruptSQLiteStartupTest(unittest.TestCase):
    def test_corrupt_database_does_not_crash_module_import(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ednna.db"
            path.write_bytes(b"not a valid sqlite database")
            env = dict(os.environ, EDNNA_DB_PATH=str(path))
            result = subprocess.run(
                [sys.executable, "-c", "import ednna.armazenamento"],
                env=env, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SQLite indisponivel", result.stdout)

    def test_existing_corruption_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ednna.db"
            original = b"not a valid sqlite database"
            path.write_bytes(original)
            env = dict(os.environ, EDNNA_DB_PATH=str(path))
            subprocess.run([sys.executable, "-c", "import ednna.armazenamento"],
                           env=env, capture_output=True, timeout=15)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
