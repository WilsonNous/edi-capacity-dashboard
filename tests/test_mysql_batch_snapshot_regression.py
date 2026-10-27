"""Regression: batch cursor must use the issue id when locking snapshot."""
from datetime import datetime
from ednna.mysql_snapshot_repository import salvar_snapshot

class Cursor:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params):
        self.calls.append((sql, params))
    def fetchone(self):
        return None

def test_shared_cursor_uses_issue_id_without_nameerror():
    cursor = Cursor()
    salvar_snapshot({"id": 49227, "sincronizado_em": datetime(2026, 10, 27), "payload_json": {"updated_on": "2026-10-27T14:00:00Z"}}, cursor=cursor)
    assert cursor.calls[0][1] == (49227,)
    assert "FOR UPDATE" in cursor.calls[0][0]
    assert any("INSERT INTO eddy_chamados" in sql for sql, _ in cursor.calls)
