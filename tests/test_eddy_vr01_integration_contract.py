"""Integrated VR01 contract: Redmine, Blueprint, Graph and MySQL boundaries.

Runs against deterministic fakes, never real customer services.
"""
from unittest.mock import patch

from ednna.eddy_vr01_integrated import planejar_vr01


def test_redmine_bp_graph_mysql_end_to_end_without_external_calls():
    state = {
        "fase": "PRONTO_PARA_ASSUMIR", "original_owner_id": 97,
        "eddy_owner_id": 999, "operacao_pendente": None,
        "envio_graph_confirmado": 0, "autorizacao_confirmada": 0,
        "confirmacao_evidence_id": None, "evidencias_registradas": 0,
        "notificado": 0, "destinatario": None, "bp_source_id": None,
    }
    issue = {"assigned_to": {"id": 97}, "updated_on": "version-1"}
    events = []
    graph_sends = []
    sent_subjects = set()
    bp = {"email": "cliente@example.invalid", "source_id": 5,
          "documento_id": 10, "chamado_id": 123}
    def reserve(phase, operation):
        assert state["fase"] == phase and state["operacao_pendente"] is None
        state["operacao_pendente"] = operation
        return True
    def advance(phase, operation, target, **fields):
        assert state["fase"] == phase and state["operacao_pendente"] == operation
        state.update(fields)
        state["fase"] = target
        state["operacao_pendente"] = None
    def redmine_update(*, assigned_to_id=None, notes=""):
        if assigned_to_id is not None:
            issue["assigned_to"]["id"] = assigned_to_id
        if notes:
            assert "Recebimento dos arquivos ainda nao validado" in notes
            events.append(("REDMINE_NOTE", notes))
    def send(**kwargs):
        assert kwargs["chamado_id"] == 50318
        assert kwargs["para"][0] in ("cliente@example.invalid", "analista@example.invalid")
        graph_sends.append(kwargs)
        sent_subjects.add(kwargs["assunto"])
        return {"status": "accepted"}
    def locate(*, remetente, assunto):
        return ({"id": "graph-sent-" + str(len(graph_sends)),
                 "sentDateTime": "2026-10-30T17:00:00Z"}
                if assunto in sent_subjects else {})
    def approval(op):
        item = {"issue_id": 50318, "redmine_updated_on": "version-1"}
        if op == "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA":
            item["to"] = "analista@example.invalid"
        return {op: item}
    with patch("ednna.eddy_vr01_integrated._identity", return_value=999), \
         patch("ednna.eddy_vr01_integrated._read_issue", return_value=issue), \
         patch("ednna.eddy_vr01_integrated._load", return_value=state), \
         patch("ednna.eddy_vr01_integrated._valid_bp", return_value=bp), \
         patch("ednna.eddy_vr01_integrated._reserve", side_effect=reserve), \
         patch("ednna.eddy_vr01_integrated._advance", side_effect=advance), \
         patch("ednna.eddy_vr01_integrated._redmine_update", side_effect=redmine_update), \
         patch("ednna.eddy_vr01_integrated._event",
               side_effect=lambda *a: events.append(a)), \
         patch("ednna.eddy_vr01_integrated._timeline", return_value="historico auditado"), \
         patch("ednna.eddy_vr_readiness.verificar_prontidao_vr01",
               return_value={"pronto": True}), \
         patch("ednna.eddy_vr01_integrated.verificar_prontidao_vr01",
               return_value={"pronto": True}), \
         patch("ednna.email_sender.enviar_email_graph", side_effect=send), \
         patch("ednna.email_sender.localizar_email_enviado", side_effect=locate), \
         patch.dict("os.environ", {"EDNNA_EMAIL_FROM": "eddy@example.invalid"}):
        for op in ("ASSUMIR_REDMINE", "BUSCAR_CONTATO_BP",
                   "SOLICITAR_AUTORIZACAO_PORTAL", "MONITORAR_CLIENTE"):
            result = planejar_vr01(execute=True, approvals=approval(op))
            assert result["acao"] == op
            assert result["estado"] == "TRANSICAO_CONFIRMADA"
        waiting = planejar_vr01(execute=True)
        assert waiting["acao"] == "ACOMPANHAR_E_COBRAR"
        assert issue["assigned_to"]["id"] == 999
        assert len(graph_sends) == 1
        # Authorization is supplied by an independently reviewed Graph evidence.
        state["autorizacao_confirmada"] = 1
        state["confirmacao_evidence_id"] = "graph-reply-reviewed-1"
        for op in ("CONFIRMACAO_VALIDADA", "REGISTRAR_EVIDENCIAS_REDMINE",
                   "DEVOLVER_AO_RESPONSAVEL_ORIGINAL",
                   "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA"):
            result = planejar_vr01(execute=True, approvals=approval(op))
            assert result["acao"] == op
            assert result["estado"] == "TRANSICAO_CONFIRMADA"
        done = planejar_vr01()
        assert done["acao"] == "CONCLUIDO"
    assert state["fase"] == "NOTIFICACAO_INTERNA_CONFIRMADA"
    assert issue["assigned_to"]["id"] == 97
    assert len(graph_sends) == 2
    assert any(e[0] == "REDMINE_NOTE" for e in events)
    assert "historico auditado" in graph_sends[-1]["corpo"]
