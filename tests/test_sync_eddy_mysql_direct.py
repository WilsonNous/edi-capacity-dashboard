"""Direct Redmine -> MySQL sync regression tests (no SQLite bridge)."""
from datetime import datetime
import pytest
from scripts import sync_eddy_mysql as sync


def issue(number):
    return {"id": number, "subject": f"Case {number}",
            "status": {"name": "Aberto"}, "updated_on": "2026-10-26T12:00:00Z"}


def test_direct_sync_does_not_read_sqlite(monkeypatch):
    writes = []
    monkeypatch.setattr(sync, "listar_abertos_confirmados",
                        lambda: {"confirmado": True, "chamados": [issue(1), issue(2)]})
    monkeypatch.setattr(sync, "salvar_snapshot", lambda row: writes.append(row))
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
