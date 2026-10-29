"""Direct Redmine -> MySQL sync regression tests (no SQLite bridge)."""
from datetime import datetime
import pytest
from scripts import sync_eddy_mysql as sync


def issue(number):
    return {"id": number, "subject": f"Case {number}",
            "status": {"name": "Aberto"}, "updated_on": "2026-10-26T12:00:00Z"}


def test_direct_sync_does_not_read_sqlite(monkeypatch):
    writes = []
    monkeypatch.setattr(sync, "mapa_persistido", lambda field_id: {"347": "MAMBO"})
    monkeypatch.setattr(sync, "listar_abertos_confirmados",
                        lambda: {"confirmado": True, "chamados": [issue(1), issue(2)]})
    from contextlib import contextmanager
    @contextmanager
    def fake_connect():
        class Connection:
            @contextmanager
            def cursor(self):
                class Cursor:
                    def execute(self, sql, args):
                        assert "SELECT id, payload_json" in sql
                    def fetchall(self):
                        return []
                yield Cursor()
        yield Connection()
    monkeypatch.setattr(sync, "connect", fake_connect)
    monkeypatch.setattr(sync, "_upsert", lambda cursor, table, fields, row: writes.append(row))
    result = sync.sincronizar_uma_vez(painel="/nonexistent/legacy.db")
    assert result["origem"] == "redmine/status=open"
    assert result["gravados"] == 2
    assert [row["id"] for row in writes] == [1, 2]
    assert all(isinstance(row["alterado_em"], datetime) for row in writes)


def test_unconfirmed_redmine_does_not_write(monkeypatch):
    writes = []
    monkeypatch.setattr(sync, "listar_abertos_confirmados",
                        lambda: {"confirmado": False, "chamados": [issue(1)]})
    monkeypatch.setattr(sync, "salvar_snapshot", lambda row: writes.append(row))
    with pytest.raises(RuntimeError, match="não confirmou"):
        sync.sincronizar_uma_vez()
    assert not writes


def test_duplicate_ids_do_not_write(monkeypatch):
    writes = []
    monkeypatch.setattr(sync, "listar_abertos_confirmados",
                        lambda: {"confirmado": True, "chamados": [issue(1), issue(1)]})
    monkeypatch.setattr(sync, "salvar_snapshot", lambda row: writes.append(row))
    with pytest.raises(ValueError, match="duplicados"):
        sync.sincronizar_uma_vez()
    assert not writes


def test_client_code_is_resolved_without_guessing(monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def fake_connect():
        class Cursor:
            def execute(self, sql, args):
                pass
            def fetchall(self):
                return []
        class Connection:
            @contextmanager
            def cursor(self):
                yield Cursor()
        yield Connection()
    items = [dict(issue(1), custom_fields=[{"id": 1, "value": ["347"]}]),
             dict(issue(2), custom_fields=[{"id": 1, "value": ["999"]}])]
    monkeypatch.setattr(sync, "listar_abertos_confirmados", lambda: {"confirmado": True, "chamados": items})
    monkeypatch.setattr(sync, "mapa_persistido", lambda field_id: {"347": "MAMBO"})
    monkeypatch.setattr(sync, "connect", fake_connect)
    rows = []
    monkeypatch.setattr(sync, "_upsert", lambda cursor, table, fields, row: rows.append(row))
    result = sync.sincronizar_uma_vez()
    assert rows[0]["cliente"] == "MAMBO"
    assert rows[1]["cliente"] is None
    assert result["clientes_nao_resolvidos"] == ["999"]
