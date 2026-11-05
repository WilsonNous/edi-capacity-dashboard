"""Contract tests for the first real VR01 transition, without external I/O.

These tests exercise the actual orchestrator while replacing only the Redmine,
MySQL and readiness boundaries. No production flag or ticket is changed.
"""
from copy import deepcopy
from unittest.mock import patch

import pytest

from ednna.eddy_vr01_integrated import planejar_vr01

MODULE = "ednna.eddy_vr01_integrated"
VERSION = "2026-11-05T15:00:00Z"
APPROVAL = {"ASSUMIR_REDMINE": {"issue_id": 50318, "redmine_updated_on": VERSION}}
ORIGINAL = {"assigned_to": {"id": 97}, "updated_on": VERSION}
ASSUMED = {"assigned_to": {"id": 456}, "updated_on": "2026-11-05T15:00:01Z"}


class SimulatedAssignment:
    def __init__(self, *, timeout=False, confirm=True):
        self.row = {"fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97,
                    "eddy_owner_id": 456, "operacao_pendente": None,
                    "envio_graph_confirmado": 0, "autorizacao_confirmada": 0,
                    "confirmacao_evidence_id": None, "evidencias_registradas": 0,
                    "notificado": 0}
        self.timeout = timeout
        self.confirm = confirm
        self.writes = []
        self.events = []
        self.reads = 0
        self.reservations = 0

    def read(self, issue_id):
        assert issue_id == 50318
        self.reads += 1
        return deepcopy(ORIGINAL if self.reads == 1 or not self.confirm else ASSUMED)

    def reserve(self, phase, operation):
        self.reservations += 1
        assert phase == "PRONTO_PARA_ASSUMIR"
        assert operation == "ASSUMIR_REDMINE"
        if self.row["operacao_pendente"]:
            return False
        self.row["operacao_pendente"] = operation
        return True

    def update(self, *, assigned_to_id=None, notes=""):
        assert self.row["operacao_pendente"] == "ASSUMIR_REDMINE"
        assert assigned_to_id == 456
        assert not notes
        self.writes.append(assigned_to_id)
        if self.timeout:
            raise TimeoutError("Redmine PUT result unknown")

    def event(self, name, reference):
        self.events.append((name, reference))

    def advance(self, phase, operation, target, **fields):
        assert (phase, operation, target) == (
            "PRONTO_PARA_ASSUMIR", "ASSUMIR_REDMINE", "ASSUMIDO_EDDY")
        assert self.row["operacao_pendente"] == operation
        assert not fields
        self.row["fase"] = target
        self.row["operacao_pendente"] = None

    def execute(self, approval=None, *, ready=True):
        with patch(f"{MODULE}._identity", return_value=456), \
             patch(f"{MODULE}._load", side_effect=lambda: deepcopy(self.row)), \
             patch(f"{MODULE}._read_issue", side_effect=self.read), \
             patch(f"{MODULE}._reserve", side_effect=self.reserve), \
             patch(f"{MODULE}._redmine_update", side_effect=self.update), \
             patch(f"{MODULE}._event", side_effect=self.event), \
             patch(f"{MODULE}._advance", side_effect=self.advance), \
             patch(f"{MODULE}.verificar_prontidao_operacao_vr01",
                   return_value={"pronto": ready, "bloqueios": [] if ready else
                                 ["AUDITORIA_REDMINE_NAO_HOMOLOGADA"]}):
            return planejar_vr01(execute=True, approvals=approval or {})


def test_assumption_requires_versioned_approval_before_any_write():
    sim = SimulatedAssignment()
    with pytest.raises(PermissionError):
        sim.execute()
    assert sim.reservations == 0
    assert sim.writes == []
    assert sim.events == []


def test_assumption_rejects_stale_version_before_reservation():
    sim = SimulatedAssignment()
    with pytest.raises(PermissionError):
        sim.execute({"ASSUMIR_REDMINE": {
            "issue_id": 50318, "redmine_updated_on": "outdated"}})
    assert sim.reservations == 0
    assert sim.writes == []


def test_success_confirms_redmine_then_event_then_mysql_phase():
    sim = SimulatedAssignment()
    result = sim.execute(APPROVAL)
    assert result["estado"] == "TRANSICAO_CONFIRMADA"
    assert sim.reads == 2
    assert sim.writes == [456]
    assert sim.events == [("ASSUNCAO_EDDY", "456")]
    assert sim.row["fase"] == "ASSUMIDO_EDDY"
    assert sim.row["operacao_pendente"] is None


def test_timeout_leaves_pending_and_never_blindly_retries():
    sim = SimulatedAssignment(timeout=True)
    with pytest.raises(TimeoutError):
        sim.execute(APPROVAL)
    assert sim.writes == [456]
    assert sim.events == []
    assert sim.row["fase"] == "PRONTO_PARA_ASSUMIR"
    assert sim.row["operacao_pendente"] == "ASSUMIR_REDMINE"
    # A new invocation must refuse a second PUT until manual reconciliation.
    result = sim.execute(APPROVAL)
    assert result["estado"] == "AGUARDA_RECONCILIACAO_MANUAL"
    assert sim.writes == [456]


def test_unconfirmed_readback_leaves_pending_without_audit_event():
    sim = SimulatedAssignment(confirm=False)
    with pytest.raises(RuntimeError, match="nao confirmada"):
        sim.execute(APPROVAL)
    assert sim.writes == [456]
    assert sim.events == []
    assert sim.row["operacao_pendente"] == "ASSUMIR_REDMINE"


def test_unhomologated_gate_blocks_before_reservation():
    sim = SimulatedAssignment()
    result = sim.execute(APPROVAL, ready=False)
    assert result["estado"] == "BLOQUEADO_PRONTIDAO"
    assert sim.reservations == 0
    assert sim.writes == []
