"""VR01 integrated pilot safety checks; no external effects."""
from unittest.mock import patch

from ednna.eddy_vr01_integrated import planejar_vr01, registrar_confirmacao_revisada


def test_dry_run_never_initializes_ledger_or_writes_redmine():
    issue = {"assigned_to": {"id": 97}, "updated_on": "2026-10-30T12:00:00Z"}
    with patch("ednna.eddy_vr01_integrated._identity", return_value=999), \
         patch("ednna.eddy_vr01_integrated._read_issue", return_value=issue), \
         patch("ednna.eddy_vr01_integrated._load", return_value=None), \
         patch("ednna.eddy_vr01_integrated._initialize") as init, \
         patch("ednna.eddy_vr01_integrated._redmine_update") as redmine:
        result = planejar_vr01()
        assert result["estado"] == "AGUARDA_INICIALIZACAO_MYSQL"
        init.assert_not_called()
        redmine.assert_not_called()


def test_reviewer_cannot_confirm_without_reconciled_evidence():
    with patch("ednna.eddy_vr01_integrated._load", return_value={"fase": "AGUARDA_CONFIRMACAO_CLIENTE"}), \
         patch("ednna.eddy_vr01_integrated.connect") as connect:
        conn = connect.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = (0,)
        try:
            registrar_confirmacao_revisada(message_id="not-in-graph", revisado_por="analista")
            assert False, "Should fail closed"
        except RuntimeError as exc:
            assert "nao conciliada" in str(exc)
        assert not any("UPDATE eddy_vr01_lifecycle_audit" in str(c)
                       for c in cur.execute.call_args_list)


def test_external_operation_requires_specific_approval():
    from ednna.eddy_vr01_integrated import _approval
    issue = {"updated_on": "2026-10-30T12:00:00Z"}
    for approvals in ({}, {"ASSUMIR_REDMINE": {"issue_id": 50318,
                                               "redmine_updated_on": "stale"}}):
        try:
            _approval("ASSUMIR_REDMINE", approvals, issue)
            assert False, "Missing or stale approval accepted"
        except PermissionError:
            pass


def test_receipt_is_never_automatically_validated():
    import inspect
    import ednna.eddy_vr01_integrated as module
    assert "VALIDAR_RECEBIMENTO_ARQUIVOS" not in inspect.getsource(module)


def test_external_step_rejects_unexpected_redmine_owner():
    issue = {"id": 50318, "assigned_to": {"id": 777}, "updated_on": "2026-11-06T12:00:00Z"}
    row = {"fase": "AGUARDA_CONTATO_BP", "original_owner_id": 97,
           "eddy_owner_id": 166, "operacao_pendente": None}
    with patch("ednna.eddy_vr01_integrated._identity", return_value=166), \
         patch("ednna.eddy_vr01_integrated._read_issue", return_value=issue), \
         patch("ednna.eddy_vr01_integrated._load", return_value=row), \
         patch("ednna.eddy_vr01_integrated._reserve") as reserve:
        result = planejar_vr01(execute=True)
        assert result["estado"] == "BLOQUEADO_RESPONSAVEL_DIVERGENTE"
        reserve.assert_not_called()


def test_post_handoff_allows_original_owner_without_false_block():
    issue = {"id": 50318, "assigned_to": {"id": 97}, "updated_on": "2026-11-06T12:00:00Z"}
    row = {"fase": "NOTIFICACAO_INTERNA_CONFIRMADA", "original_owner_id": 97,
           "eddy_owner_id": 166, "operacao_pendente": None,
           "autorizacao_confirmada": 1, "confirmacao_evidence_id": "graph-1",
           "envio_graph_confirmado": 1, "evidencias_registradas": 1,
           "notificado": 1}
    with patch("ednna.eddy_vr01_integrated._identity", return_value=166), \
         patch("ednna.eddy_vr01_integrated._read_issue", return_value=issue), \
         patch("ednna.eddy_vr01_integrated._load", return_value=row), \
         patch("ednna.eddy_vr01_integrated.verificar_prontidao_operacao_vr01",
               return_value={"pronto": False, "bloqueios": ["TESTE"]}):
        result = planejar_vr01(execute=True)
        assert result["estado"] != "BLOQUEADO_RESPONSAVEL_DIVERGENTE"
