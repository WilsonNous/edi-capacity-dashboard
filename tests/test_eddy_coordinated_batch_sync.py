"""Regression tests for coordinated EDDY persistence and safe discovery defaults."""
from contextlib import contextmanager
from unittest.mock import patch

from scripts import sync_eddy_mysql as sync
from scripts import eddy_vr01_mysql_scheduler as scheduler


def test_batch_upsert_is_one_call_and_preserves_json():
    class Cursor:
        def __init__(self):
            self.calls = []
        def executemany(self, sql, rows):
            self.calls.append((sql, rows))
    cursor = Cursor()
    rows = [{"id": 1, "payload_json": {"id": 1}, "sincronizado_em": "now"},
            {"id": 2, "payload_json": {"id": 2}, "sincronizado_em": "now"}]
    sync._persistir_lote(cursor, rows)
    assert len(cursor.calls) == 1
    sql, values = cursor.calls[0]
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert len(values) == 2
    assert '"id": 1' in values[0][sync.CHAMADO_FIELDS.index("payload_json")]


def test_batch_failure_propagates_without_individual_retry():
    class Cursor:
        def executemany(self, sql, rows):
            raise RuntimeError("mysql unavailable")
    try:
        sync._persistir_lote(Cursor(), [{"id": 1, "sincronizado_em": "now"}])
    except RuntimeError as exc:
        assert "mysql unavailable" in str(exc)
    else:
        raise AssertionError("batch failure must propagate")


def test_blueprint_remote_discovery_is_opt_in(monkeypatch):
    monkeypatch.delenv("EDDY_VR01_BLUEPRINT_AUTO_SYNC", raising=False)
    monkeypatch.delenv("EDDY_VR01_PILOT_OBSERVE", raising=False)
    with patch.object(scheduler, "executar_worker_vr01",
                      return_value={"estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS"}):
        with patch("ednna.mysql_blueprint_participants.descobrir_e_sincronizar_participantes_mysql",
                   side_effect=AssertionError("unexpected Redmine request")):
            result = scheduler.executar_uma_vez()
    assert result["estado"] == "VR01_ANALISE_LOCAL_COM_PROPOSTAS"
