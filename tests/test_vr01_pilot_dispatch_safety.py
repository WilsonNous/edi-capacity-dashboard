"""Safety regression tests for VR01 controlled dispatch and MySQL lock cleanup."""
from unittest.mock import MagicMock, patch

import pymysql
import pytest

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


def _lock_connection():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [("Ssl_cipher", "TLS_AES_256_GCM_SHA384"), (1,), (123,), (123, 123)]
    cursor_cm = MagicMock()
    cursor_cm.__enter__.return_value = cursor
    conn = MagicMock()
    conn.open = True
    conn.cursor.return_value = cursor_cm
    return conn, cursor


def test_lost_connection_during_release_does_not_hide_completed_cycle():
    conn, cursor = _lock_connection()
    cursor.execute.side_effect = [None, None, None, None, pymysql.err.OperationalError(2006, "gone away")]
    result = {"estado": "OK", "sincronizacao": {"importados": [], "falhas": []}}
    with patch("scripts.eddy_vr01_mysql_worker.connection_options", return_value={"autocommit": False}), patch(
        "scripts.eddy_vr01_mysql_worker.pymysql.connect", return_value=conn
    ) as mysql, patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01", return_value=result):
        assert executar_worker_vr01() == result
    assert mysql.call_args.kwargs["autocommit"] is True
    conn.commit.assert_not_called()
    conn.close.assert_called_once()


def test_no_tls_fails_closed_before_acquiring_lock():
    conn, cursor = _lock_connection()
    cursor.fetchone.side_effect = [("Ssl_cipher", ""), (1,)]
    with patch("scripts.eddy_vr01_mysql_worker.connection_options", return_value={}), patch(
        "scripts.eddy_vr01_mysql_worker.pymysql.connect", return_value=conn
    ), patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01") as cycle:
        with pytest.raises(RuntimeError, match="TLS"):
            executar_worker_vr01()
    cycle.assert_not_called()
    conn.close.assert_called_once()


def test_existing_lock_prevents_second_cycle():
    conn, cursor = _lock_connection()
    cursor.fetchone.side_effect = [("Ssl_cipher", "TLS_AES_256_GCM_SHA384"), (0,)]
    with patch("scripts.eddy_vr01_mysql_worker.connection_options", return_value={}), patch(
        "scripts.eddy_vr01_mysql_worker.pymysql.connect", return_value=conn
    ), patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01") as cycle:
        assert executar_worker_vr01()["estado"] == "IGNORADO_EXECUCAO_CONCORRENTE"
    cycle.assert_not_called()
    conn.close.assert_called_once()


def test_lost_lock_ownership_fails_closed():
    conn, cursor = _lock_connection()
    cursor.fetchone.side_effect = [("Ssl_cipher", "TLS_AES_256_GCM_SHA384"), (1,), (123,), (123, 456)]
    result = {"estado": "OK", "sincronizacao": {"importados": [], "falhas": []}}
    with patch("scripts.eddy_vr01_mysql_worker.connection_options", return_value={}), patch(
        "scripts.eddy_vr01_mysql_worker.pymysql.connect", return_value=conn
    ), patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01", return_value=result):
        with pytest.raises(RuntimeError, match="ownership lost"):
            executar_worker_vr01()
    conn.close.assert_called_once()


def test_lost_mysql_session_fails_closed():
    conn, cursor = _lock_connection()
    cursor.fetchone.side_effect = [("Ssl_cipher", "TLS_AES_256_GCM_SHA384"), (1,), (123,)]
    conn.ping.side_effect = pymysql.err.OperationalError(2006, "gone away")
    result = {"estado": "OK", "sincronizacao": {"importados": [], "falhas": []}}
    with patch("scripts.eddy_vr01_mysql_worker.connection_options", return_value={}), patch(
        "scripts.eddy_vr01_mysql_worker.pymysql.connect", return_value=conn
    ), patch("scripts.eddy_vr01_mysql_worker.executar_ciclo_vr01", return_value=result):
        with pytest.raises(RuntimeError, match="session lost"):
            executar_worker_vr01()
    conn.close.assert_called_once()
