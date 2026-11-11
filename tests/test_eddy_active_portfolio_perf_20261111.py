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


def test_closed_issue_is_blocked_before_intent_creation():
    closed = {"id": 1, "status": {"is_closed": True}, "subject": "VR"}
    class Cursor:
        rowcount = 0
        def execute(self, *_): pass
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def cursor(self):
            class Ctx:
                def __enter__(self): return Cursor()
                def __exit__(self, *_): pass
            return Ctx()
    with patch.object(proposals, "carregar_snapshot", return_value={
        "chamado": {"payload_json": closed}, "journals": [],
    }), patch.object(proposals, "criar_intencao") as create, \
         patch.object(proposals, "connect", return_value=Conn()):
        result = proposals.preparar_intencoes_locais(ids=[1])
    assert result["bloqueados"] == [
        {"chamado_id": 1, "motivo": "CHAMADO_CONCLUIDO_HISTORICO"}
    ]
    create.assert_not_called()
