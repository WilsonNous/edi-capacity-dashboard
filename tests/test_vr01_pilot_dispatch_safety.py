"""Safety regression tests for VR01 controlled dispatch and MySQL lock cleanup."""
from unittest.mock import MagicMock, patch

from ednna.eddy_vr_dispatcher import _approved_message
from scripts.eddy_vr01_mysql_worker import executar_worker_vr01


def test_approved_message_adds_institutional_cc(monkeypatch):
    monkeypatch.delenv("EDNNA_EMAIL_CC_PADRAO", raising=False)
    action = {"action_key": "a", "redmine_updated_on": "v1", "acao": "VALIDAR_E_SOLICITAR_TODOS_NSAS", "chamado_id": 47851}
    approved = {"a": {"redmine_updated_on": "v1", "acao": action["acao"],
                      "to": "vr@example.com", "cc": ["owner@netunna.com.br"],
                      "subject": "Solicitacao #47851", "body": "NSAs 339 e 355"}}
    msg = _approved_message(action, approved)
    assert msg["to"] == "vr@example.com"
    assert "owner@netunna.com.br" in msg["cc"]
    assert {"bpo@netunna.com.br", "edi@netunna.com.br", "consultores@netunna.com.br"} <= set(msg["cc"])


def test_approved_message_rejects_invalid_cc():
    action = {"action_key": "a", "redmine_updated_on": "v1", "acao": "X", "chamado_id": 47851}
    approved = {"a": {"redmine_updated_on": "v1", "acao": "X", "to": "vr@example.com",
                      "cc": ["not-an-email"], "subject": "#47851", "body": "text"}}
    assert _approved_message(action, approved) is None


def test_lost_connection_during_release_does_not_hide_completed_cycle():
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)
    cursor.execute.side_effect = [None, RuntimeError("MySQL gone away")]
    cursor_cm = MagicMock()
    cursor_cm.__enter__.return_value = cursor
    conn = MagicMock()
    conn.cursor.return_value = cursor_cm
    conn_cm = MagicMock()
    conn_cm.__enter__.return_value = conn
    result = {"estado": "OK", "sincronizacao": {"importados": [], "falhas": []}}
    with patch("scripts.eddy_vr01_mysql_worker.connect", return_value=conn_cm), patch(
        "scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01", return_value=result
    ):
        assert executar_worker_vr01() == result
