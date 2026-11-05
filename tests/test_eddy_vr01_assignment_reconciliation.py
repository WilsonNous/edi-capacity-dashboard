"""Reconciliation diagnostics: read-only, fail-closed, no Redmine writes."""
from unittest.mock import MagicMock, patch

from ednna.eddy_vr01_assignment_reconciliation import diagnosticar_reconciliacao_assuncao

MODULE = "ednna.eddy_vr01_assignment_reconciliation"


def run_case(*, phase="PRONTO_PARA_ASSUMIR", assignee=97,
             pending=None, events=(), original=97, eddy=166):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (phase, original, eddy, pending)
    cursor.fetchall.return_value = list(events)
    issue = {"assigned_to": {"id": assignee}, "updated_on": "2026-11-05T17:00:00Z"}
    with patch(f"{MODULE}.connect", return_value=connection), \
         patch(f"{MODULE}._identity", return_value=166), \
         patch(f"{MODULE}._read_issue", return_value=issue):
        result = diagnosticar_reconciliacao_assuncao()
    sql = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
    assert len(sql) == 2
    assert all(statement.lstrip().startswith("SELECT") for statement in sql)
    return result


def test_initial_state_waits_for_authorized_assignment():
    result = run_case()
    assert result["situacao"] == "AGUARDA_ASSUNCAO_AUTORIZADA"
    assert not result["reconciliado"]
    assert result["operacao_pendente"] is None


def test_success_requires_redmine_mysql_and_matching_event():
    result = run_case(phase="ASSUMIDO_EDDY", assignee=166,
                      events=(("ASSUNCAO_EDDY", "166"),))
    assert result["situacao"] == "ASSUNCAO_CONFIRMADA"
    assert result["reconciliado"]


def test_put_timeout_with_assignee_changed_stays_manual():
    result = run_case(assignee=166, pending="ASSUMIR_REDMINE")
    assert result["situacao"] == "REDMINE_ATRIBUIDO_MYSQL_PENDENTE"
    assert not result["reconciliado"]
    assert "RECONCILIACAO_MANUAL_NECESSARIA" in result["bloqueios"]


def test_put_timeout_without_change_stays_manual():
    result = run_case(assignee=97, pending="ASSUMIR_REDMINE")
    assert result["situacao"] == "DIVERGENCIA_REQUER_ANALISE_MANUAL"
    assert not result["reconciliado"]


def test_mysql_advanced_without_event_is_not_reconciled():
    result = run_case(phase="ASSUMIDO_EDDY", assignee=166)
    assert result["situacao"] == "DIVERGENCIA_REQUER_ANALISE_MANUAL"
    assert not result["reconciliado"]


def test_mismatched_ledger_identity_blocks():
    result = run_case(original=123)
    assert "IDENTIDADE_LEDGER_DIVERGENTE" in result["bloqueios"]
    assert not result["reconciliado"]
