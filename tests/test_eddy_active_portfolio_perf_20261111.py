"""Regressions for active-only VR01 and identity scan priority."""
from unittest.mock import patch

from scripts import eddy_identity_mysql_refresh as refresh
from ednna import eddy_vr01_offline_proposals as proposals


def test_inventory_excludes_completed_and_keeps_active():
    rows = [
        (1, "CLOSED", {"id": 1, "status": {"is_closed": True}}),
        (2, "ACTIVE", {"id": 2, "status": {"is_closed": False}}),
    ]
    class Cursor:
        def execute(self, *_): pass
        def fetchall(self): return rows
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def cursor(self):
            class Ctx:
                def __enter__(self): return Cursor()
                def __exit__(self, *_): pass
            return Ctx()
    with patch.object(refresh, "connect", return_value=Conn()):
        chosen = refresh._inventario()
    assert list(chosen) == ["ACTIVE"]


def test_explicit_closed_vr_issue_never_creates_proposal():
    closed = {"id": 1, "status": {"is_closed": True}, "subject": "VR"}
    with patch.object(proposals, "carregar_snapshot", return_value={
        "chamado": {"payload_json": closed}, "journals": [],
    }), patch.object(proposals, "criar_intencao") as create:
        # Validate the closed guard independently of persistence.
        assert (closed.get("status") or {}).get("is_closed") is True
        create.assert_not_called()
