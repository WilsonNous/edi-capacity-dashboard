"""VR01 internal validation pilot safety tests."""
from ednna.eddy_vr_internal_validation import preparar_validacao_interna

ISSUE = {"id": 49227, "updated_on": "2026-10-20T10:00:00Z",
         "status": {"name": "Aguardando Retorno Adquirente"}}
DECISION = {"acao": "COBRAR_VALIDACAO_RECEPCAO", "destino": "RESPONSAVEL_REDMINE"}


def test_pilot_prepares_only_approved_internal_address():
    result = preparar_validacao_interna(ISSUE, DECISION, approved_email="operador@netunna.com.br")
    assert result["estado"] == "PRONTO_PARA_APROVACAO_ENVIO_INTERNO"
    assert result["envios_realizados"] == 0
    assert "#49227" in result["assunto"]


def test_missing_or_external_recipient_blocked():
    for email in ("", "cliente@example.com", "not-an-email"):
        assert preparar_validacao_interna(ISSUE, DECISION, approved_email=email)["estado"] == "AGUARDA_DESTINATARIO_HOMOLOGADO"


def test_other_issue_and_terminal_blocked():
    assert preparar_validacao_interna({**ISSUE, "id": 49289}, DECISION, approved_email="operador@netunna.com.br")["estado"] == "BLOQUEADO_FORA_PILOTO"
    closed = {**ISSUE, "status": {"name": "Concluído", "is_closed": True}}
    assert preparar_validacao_interna(closed, DECISION, approved_email="operador@netunna.com.br")["estado"] == "BLOQUEADO_CHAMADO_TERMINAL"


def test_unapproved_action_blocked():
    assert preparar_validacao_interna(ISSUE, {**DECISION, "acao": "COBRAR_CLIENTE"}, approved_email="operador@netunna.com.br")["estado"] == "BLOQUEADO_DECISAO"
