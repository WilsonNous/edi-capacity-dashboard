import os
os.environ.setdefault("EDDY_INTELLIGENCE_TOKEN", "test-secret")

from fastapi.testclient import TestClient
from eddy_api.main import app

client = TestClient(app)
HEADERS={"Authorization":"Bearer test-secret","X-EDNNA-Contract-Version":"1"}

def test_handshake():
    r=client.get("/api/intelligence/handshake",headers=HEADERS)
    assert r.status_code==200
    data=r.json()
    assert data["contract_version"]=="1"
    assert data["specialist_id"]=="eddy"
    assert "edi.status.get" in data["capabilities"]

def test_authentication():
    assert client.get("/api/intelligence/handshake",headers={"X-EDNNA-Contract-Version":"1"}).status_code==401

def test_contract_version():
    h={**HEADERS,"X-EDNNA-Contract-Version":"999"}
    assert client.get("/api/intelligence/handshake",headers=h).status_code==422

def test_unknown_capability():
    r=client.post("/api/intelligence/query",headers=HEADERS,json={"capability":"edi.unknown","input":{},"trace_id":"t-1"})
    assert r.status_code==404

def test_trace_and_conservative_player():
    r=client.post("/api/intelligence/query",headers=HEADERS,json={"capability":"edi.player.inspect","input":{"player":"PLUXEE"},"trace_id":"trace-123"})
    assert r.status_code==200
    d=r.json()
    assert d["trace_id"]=="trace-123"
    assert d["requires_human"] is True
    assert d["confidence"] < .5

def test_action_is_dry_run_only():
    payload={"capability":"edi.operation.execute","input":{},"trace_id":"t-action","idempotency_key":"k-1","dry_run":True}
    d=client.post("/api/intelligence/action",headers=HEADERS,json=payload).json()
    assert d["state"]=="not_executed"
    payload["dry_run"]=False
    assert client.post("/api/intelligence/action",headers=HEADERS,json=payload).status_code==403

def test_status_lookup_never_replays():
    r=client.get("/api/intelligence/actions/k-1",headers=HEADERS)
    assert r.status_code==200 and r.json()["state"]=="unknown"


def test_api_service_does_not_depend_on_streamlit_ui():
    import sys
    assert "ui.operational_data" not in sys.modules

def test_api_import_does_not_start_operational_worker():
    import ednna.monitor_respostas as monitor
    assert monitor._THREAD is None or not monitor._THREAD.is_alive()
