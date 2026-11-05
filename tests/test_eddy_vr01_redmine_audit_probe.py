"""Audit probe never writes or confuses read access with write homologation."""
from unittest.mock import MagicMock, patch

from ednna.eddy_vr01_redmine_audit_probe import diagnosticar_auditoria_assuncao

MOD = "ednna.eddy_vr01_redmine_audit_probe"
ROW = {"fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97,
       "eddy_owner_id": 999, "operacao_pendente": None}
ISSUE = {"assigned_to": {"id": 97}, "updated_on": "2026-11-05T15:15:00Z"}


def _probe(row=ROW, issue=ISSUE):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (0,)
    with patch(f"{MOD}._identity", return_value=999), \
         patch(f"{MOD}._load", return_value=row), \
         patch(f"{MOD}._read_issue", return_value=issue) as read, \
         patch(f"{MOD}.connect", return_value=conn), \
         patch("ednna.eddy_vr01_integrated._redmine_update") as update:
        result = diagnosticar_auditoria_assuncao()
    update.assert_not_called()
    return result, read, cursor


def test_clean_preflight_does_not_homologate_write():
    result, read, cursor = _probe()
    assert result["preflight_apto"] is True
    assert result["homologado"] is False
    assert result["execucao_externa"] is False
    assert result["bloqueios"] == ["TESTE_ESCRITA_E_RECONCILIACAO_NAO_HOMOLOGADO"]
    read.assert_called_once_with(50318)
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[0].lstrip().upper().startswith("SELECT")


def test_missing_ledger_does_not_query_redmine():
    result, read, _ = _probe(row=None)
    assert "LEDGER_AUSENTE" in result["bloqueios"]
    read.assert_not_called()


def test_pending_operation_blocks():
    result, _, _ = _probe(row={**ROW, "operacao_pendente": "ASSUMIR_REDMINE"})
    assert "RECONCILIACAO_PENDENTE" in result["bloqueios"]
    assert result["preflight_apto"] is False


def test_assignee_mismatch_blocks():
    result, _, _ = _probe(issue={"assigned_to": {"id": 999}, "updated_on": "now"})
    assert "RESPONSAVEL_ATUAL_DIVERGENTE" in result["bloqueios"]
    assert result["homologado"] is False


def test_missing_version_blocks():
    result, _, _ = _probe(issue={"assigned_to": {"id": 97}})
    assert "VERSAO_REDMINE_AUSENTE" in result["bloqueios"]
