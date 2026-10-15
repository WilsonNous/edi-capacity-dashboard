"""Regressões da separação entre monitor Graph e outbox Redmine."""
import ast
from pathlib import Path
from unittest.mock import patch
import threading


def test_worker_redmine_independente_do_monitor():
    source = Path("ednna/worker_operacional.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'name="eddy-redmine-outbox"' in source
    assert 'EDDY_REDMINE_OUTBOX_INTERVAL_SECONDS' in source
    assert 'stop.wait(intervalo)' in source


def test_monitor_nao_reconcilia_quando_worker_dedicado_ativo():
    source = Path("ednna/monitor_respostas.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'if not _bool_env("EDDY_REDMINE_OUTBOX_WORKER_ENABLED", True):' in source
    assert 'reconciliar_redmine_pendentes(10)' in source


def test_worker_para_sem_consultar_redmine():
    from ednna.worker_operacional import loop_redmine_outbox
    stop = threading.Event()
    stop.set()
    with patch("ednna.redmine_outbox.reconciliar_redmine_pendentes") as reconcile:
        loop_redmine_outbox(stop)
        reconcile.assert_not_called()
