from ednna.eddy_vr_internal_validation import aprovar_acao_interna

ISSUE = {"id": 49227, "updated_on": "2026-10-26T10:00:00Z",
         "status": {"name": "Aguardando Retorno Adquirente"}}
ACTION = {"action_key": "a"*64, "chamado_id": 49227,
          "redmine_updated_on": ISSUE["updated_on"],
          "acao": "COBRAR_VALIDACAO_RECEPCAO", "destino": "RESPONSAVEL_REDMINE"}


def test_approval_matches_dispatcher_schema():
    result = aprovar_acao_interna(ACTION, ISSUE, approved_email="operador@netunna.com.br")
    assert result["estado"] == "APROVACAO_PREPARADA"
    assert result["approval"]["to"] == "operador@netunna.com.br"
    assert result["approval"]["redmine_updated_on"] == ACTION["redmine_updated_on"]
    assert result["envios_realizados"] == 0


def test_reject_stale_or_wrong_action():
    assert aprovar_acao_interna({**ACTION, "redmine_updated_on": "old"}, ISSUE, approved_email="operador@netunna.com.br")["estado"] == "BLOQUEADO_VERSAO"
    assert aprovar_acao_interna({**ACTION, "acao": "COBRAR_CLIENTE"}, ISSUE, approved_email="operador@netunna.com.br")["estado"] == "BLOQUEADO_ACAO"
    assert aprovar_acao_interna(ACTION, ISSUE, approved_email="outsider@example.com")["estado"] == "AGUARDA_DESTINATARIO_HOMOLOGADO"
