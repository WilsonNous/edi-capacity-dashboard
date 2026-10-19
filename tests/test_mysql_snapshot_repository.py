"""Offline tests: no database credentials or network required."""
import unittest
from unittest.mock import patch

from ednna import mysql_snapshot_repository as repository


class Cursor:
    def __init__(self):
        self.calls = []
        self.rows = []

    def execute(self, sql, args):
        self.calls.append((sql, args))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.rows.pop(0) if self.rows else []


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self

    def __enter__(self):
        return self._cursor

    def __exit__(self, *args):
        return False


class SnapshotTests(unittest.TestCase):
    def test_upsert_issue_and_journal_parameterized(self):
        cursor = Cursor()
        with patch.object(repository, "connect", return_value=Connection(cursor)):
            repository.salvar_snapshot(
                {"id": 42, "sincronizado_em": "2026-10-19", "payload_json": {"x": 1}},
                [{"id": 7, "chamado_id": 42, "sincronizado_em": "2026-10-19"}],
            )
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn("ON DUPLICATE KEY UPDATE", cursor.calls[0][0])
        self.assertIn("%s", cursor.calls[0][0])
        self.assertIn('{"x": 1}', cursor.calls[0][1])

    def test_mismatched_journal_rejected_before_write(self):
        with patch.object(repository, "connect") as connect:
            with self.assertRaises(ValueError):
                repository.salvar_snapshot(
                    {"id": 42, "sincronizado_em": "2026-10-19"},
                    [{"id": 7, "chamado_id": 43, "sincronizado_em": "2026-10-19"}],
                )
            connect.assert_not_called()

    def test_missing_id_rejected(self):
        with self.assertRaises(ValueError):
            repository._values({"sincronizado_em": "now"}, repository.CHAMADO_FIELDS)


if __name__ == "__main__":
    unittest.main()
