"""VR01 bootstrap safety: fresh preflight, idempotency, and no external effects."""
from unittest.mock import patch

import pytest
from ednna.eddy_vr01_bootstrap import inicializar_piloto_local
from scripts import eddy_vr01_mysql_scheduler as scheduler

MODULE = "ednna.eddy_vr01_integrated"


def test_missing_ledger_initializes_only_after_verified_owner():
    issue = {"assigned_to": {"id": 97}, "updated_on": "2026-11-05T12:00:00Z"}
    row = {"fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97, "eddy_owner_id": 999}
    with patch(f"{MODULE}._load", return_value=None), \
         patch(f"{MODULE}._identity", return_value=999), \
         patch(f"{MODULE}._read_issue", return_value=issue) as read, \
         patch(f"{MODULE}._initialize", return_value=row) as init, \
         patch(f"{MODULE}._redmine_update") as write:
        result = inicializar_piloto_local()
    assert result["estado"] == "INICIALIZADO_MYSQL"
    assert result["execucao_externa"] is False
    read.assert_called_once_with(50318)
    init.assert_called_once_with(issue, 999)
    write.assert_not_called()


def test_existing_ledger_never_reads_redmine_or_reinitializes():
    with patch(f"{MODULE}._load", return_value={"fase": "AGUARDA_CONFIRMACAO_CLIENTE"}), \
         patch(f"{MODULE}._read_issue") as read, \
         patch(f"{MODULE}._initialize") as init:
        result = inicializar_piloto_local()
    assert result["estado"] == "JA_INICIALIZADO"
    read.assert_not_called()
    init.assert_not_called()


def test_wrong_owner_never_initializes():
    with patch(f"{MODULE}._load", return_value=None), \
         patch(f"{MODULE}._identity", return_value=999), \
         patch(f"{MODULE}._read_issue", return_value={"assigned_to": {"id": 999}, "updated_on": "now"}), \
         patch(f"{MODULE}._initialize") as init:
        result = inicializar_piloto_local()
    assert result["estado"] == "BLOQUEADO_RESPONSAVEL_ORIGINAL"
    init.assert_not_called()


def test_missing_redmine_version_never_initializes():
    with patch(f"{MODULE}._load", return_value=None), \
         patch(f"{MODULE}._identity", return_value=999), \
         patch(f"{MODULE}._read_issue", return_value={"assigned_to": {"id": 97}}), \
         patch(f"{MODULE}._initialize") as init:
        result = inicializar_piloto_local()
    assert result["estado"] == "BLOQUEADO_VERSAO_REDMINE"
    init.assert_not_called()


def test_preflight_timeout_fails_closed():
    with patch(f"{MODULE}._load", return_value=None), \
         patch(f"{MODULE}._identity", return_value=999), \
         patch(f"{MODULE}._read_issue", side_effect=TimeoutError("Redmine unavailable")), \
         patch(f"{MODULE}._initialize") as init:
        with pytest.raises(TimeoutError):
            inicializar_piloto_local()
    init.assert_not_called()


def test_conflicting_persisted_identity_never_advances():
    issue = {"assigned_to": {"id": 97}, "updated_on": "now"}
    with patch(f"{MODULE}._load", return_value=None), \
         patch(f"{MODULE}._identity", return_value=999), \
         patch(f"{MODULE}._read_issue", return_value=issue), \
         patch(f"{MODULE}._initialize", return_value={
             "fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97, "eddy_owner_id": 888}):
        assert inicializar_piloto_local()["estado"] == "BLOQUEADO_IDENTIDADE_MYSQL"


def test_scheduler_bootstrap_before_observation_without_execution(monkeypatch):
    monkeypatch.setenv("EDDY_VR01_PILOT_OBSERVE", "true")
    monkeypatch.setenv("EDDY_VR01_PILOT_BOOTSTRAP", "true")
    monkeypatch.setenv("EDDY_VR01_BLUEPRINT_AUTO_SYNC", "false")
    monkeypatch.setattr(scheduler, "_LAST_PILOT_BOOTSTRAP_ATTEMPT", 0.0)
    with patch.object(scheduler, "executar_worker_vr01", return_value={"estado": "OK"}), \
         patch("ednna.eddy_vr01_bootstrap.inicializar_piloto_local",
               return_value={"estado": "INICIALIZADO_MYSQL"}) as init, \
         patch("ednna.eddy_vr01_integrated_scheduler.ciclo_piloto",
               return_value={"estado": "OBSERVACAO_LOCAL"}) as observe:
        assert scheduler.executar_uma_vez()["estado"] == "OK"
        assert scheduler.executar_uma_vez()["estado"] == "OK"
    init.assert_called_once()
    assert observe.call_count == 2
    assert all(call.kwargs == {"execute": False} for call in observe.call_args_list)
