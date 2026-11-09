"""VR01 portfolio bridge eligibility and CNPJ validation."""
from unittest.mock import patch
from ednna import eddy_vr01_portfolio_cycle as module


def test_cnpj_requires_single_explicit_redmine_field():
    assert module._cnpj({"custom_fields": [
        {"name": "CNPJ", "value": "12.345.678/0001-99"}
    ]}) == "12345678000199"
    assert module._cnpj({"custom_fields": []}) is None
    assert module._cnpj({"custom_fields": [
        {"name": "CNPJ", "value": ["12.345.678/0001-99", "98.765.432/0001-11"]}
    ]}) is None


def test_missing_snapshot_does_not_execute_any_external_action():
    with patch.object(module, "listar_chamados_vr_mysql", return_value=(50671,)), \
         patch.object(module, "carregar_snapshot", return_value=None):
        result = module.executar_carteira_vr01()
    assert result["avaliados"] == 1
    assert result["chamados"][0]["estado"] == "SEM_SNAPSHOT"
    assert result["execucao_externa"] is False


def test_incomplete_history_is_observational_when_execution_disabled():
    issue = {"id": 50318, "_eddy_journals_completos": False,
             "subject": "VR BENEFICIO", "status": {"is_closed": False}}
    snapshot = {"chamado": {"payload_json": issue}, "journals": []}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \
         patch.object(module, "_recuperar_historico") as recover:
        result = module.executar_carteira_vr01(ids=(50318,), execute=False)
    assert result["chamados"][0]["estado"] == "HISTORICO_INCOMPLETO"
    recover.assert_not_called()


def test_incomplete_history_recovers_using_shared_sync_only_in_execute_mode():
    issue = {"id": 50318, "_eddy_journals_completos": False,
             "subject": "VR BENEFICIO", "status": {"is_closed": False}}
    snapshot = {"chamado": {"payload_json": issue}, "journals": []}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \
         patch.object(module, "_recuperar_historico", return_value=None) as recover:
        result = module.executar_carteira_vr01(ids=(50318,), execute=True)
    recover.assert_called_once_with(50318, issue)
    assert result["chamados"][0]["estado"] == "HISTORICO_INCOMPLETO"
    assert result["execucao_externa"] is False


def test_history_recovery_uses_existing_reader_and_snapshot_writer():
    issue = {"id": 50318}
    detail = {"id": 50318, "journals": []}
    row = {"id": 50318, "payload_json": {"_eddy_journals_completos": True}}
    with patch("ednna.redmine_resilient_reads.detalhe_com_retomada",
               return_value={"detalhe": detail}) as read, \
         patch("ednna.eddy_vr_mysql_sync._snapshot", return_value=(row, [])), \
         patch("ednna.mysql_snapshot_repository.salvar_snapshot") as save, \
         patch.object(module, "carregar_snapshot", return_value={"chamado": row}) as load:
        assert module._recuperar_historico(50318, issue) == {"chamado": row}
    read.assert_called_once_with(issue, force=True)
    save.assert_called_once_with(row, [])
    load.assert_called_once_with(50318)


def test_auto_portal_approval_is_scoped_to_issue_and_fresh_version():
    live = {"id": 50671, "updated_on": "2026-11-07T10:00:00Z"}
    ledger = {"fase": "AGUARDA_CONTATO_BP", "operacao_pendente": None,
              "envio_graph_confirmado": 0}
    assert module._aprovacoes_automaticas_portal(
        50671, live, ledger, enabled_flag=True
    ) == {"SOLICITAR_AUTORIZACAO_PORTAL": {
        "issue_id": 50671, "redmine_updated_on": live["updated_on"]}}
    assert module._aprovacoes_automaticas_portal(
        50671, live, ledger, enabled_flag=False) == {}
    assert module._aprovacoes_automaticas_portal(
        50671, {}, ledger, enabled_flag=True) == {}
    assert module._aprovacoes_automaticas_portal(
        50671, live, {**ledger, "operacao_pendente": "SOLICITAR_AUTORIZACAO_PORTAL"},
        enabled_flag=True) == {}
    assert module._aprovacoes_automaticas_portal(
        50671, live, {**ledger, "envio_graph_confirmado": 1},
        enabled_flag=True) == {}
    assert module._aprovacoes_automaticas_portal(
        50671, live, {**ledger, "fase": "AGUARDA_CONFIRMACAO_CLIENTE"},
        enabled_flag=True) == {}


def test_existing_portal_email_reconciles_without_resending():
    from unittest.mock import MagicMock
    ledger = {"fase": "AGUARDA_CONTATO_BP", "operacao_pendente": None,
              "envio_graph_confirmado": 0}
    message = {"subject": "VR01 #50318", "sentDateTime": "2026-11-06T12:00:00Z",
               "internetMessageId": "<existing@example.com>",
               "toRecipients": [{"emailAddress": {"address": "bp@example.com"}}]}
    with patch("ednna.eddy_global_config.setting", return_value="edi@example.com"), \
         patch("ednna.eddy_vr01_email_templates.assunto_vr01",
               return_value="VR01 #50318"), \
         patch("ednna.email_sender.listar_emails_enviados_por_chamado",
               return_value=[message]) as lookup, \
         patch("ednna.eddy_vr01_integrated._context",
               return_value={"cliente": "MAMBO"}), \
         patch("ednna.eddy_vr01_integrated._valid_bp",
               return_value={"email": "bp@example.com", "source_id": 42}), \
         patch("ednna.eddy_vr01_integrated._reserve", return_value=True) as reserve, \
         patch("ednna.eddy_vr01_integrated._event") as event, \
         patch("ednna.eddy_vr01_integrated._advance") as advance, \
         patch("ednna.redmine_outbox.registrar_ou_enfileirar",
               return_value={"pendente": True}) as outbox:
        result = module._reconciliar_solicitacao_existente(
            50318, {"updated_on": "2026-11-07T10:00:00Z"}, ledger)
    assert result["estado"] == "ENVIO_EXISTENTE_RECONCILIADO"
    assert result["envios_realizados"] == 0
    lookup.assert_called_once()
    reserve.assert_called_once()
    event.assert_called_once()
    outbox.assert_called_once()
    assert advance.call_args.kwargs["envio_graph_confirmado"] == 1


def test_ambiguous_existing_mail_never_advances_lifecycle():
    ledger = {"fase": "AGUARDA_CONTATO_BP", "operacao_pendente": None}
    with patch("ednna.eddy_global_config.setting", return_value="edi@example.com"), \
         patch("ednna.eddy_vr01_email_templates.assunto_vr01",
               return_value="VR01 #50318"), \
         patch("ednna.email_sender.listar_emails_enviados_por_chamado",
               return_value=[{"subject": "VR01 #50318", "sentDateTime": "2026-11-06T12:00:00Z",
                              "internetMessageId": "id", "toRecipients": []}]), \
         patch("ednna.eddy_vr01_integrated._context",
               return_value={"cliente": "MAMBO"}), \
         patch("ednna.eddy_vr01_integrated._valid_bp",
               return_value={"email": "bp@example.com", "source_id": 42}), \
         patch("ednna.eddy_vr01_integrated._reserve") as reserve:
        result = module._reconciliar_solicitacao_existente(
            50318, {"updated_on": "2026-11-07T10:00:00Z"}, ledger)
    assert result["estado"] == "ENVIO_AMBIGUO"
    reserve.assert_not_called()


def test_cnpj_diagnostic_accepts_formatted_value():
    with patch.object(module, "clientes_do_redmine", return_value=["CLIENTE"]):
        result = module.diagnosticar_identificacao_cliente({
            "custom_fields": [{"name": "CNPJ", "value": "12.345.678/0001-99"}]
        })
    assert result["quantidade_cnpjs_validos"] == 1
    assert result["motivos"] == []


def test_portfolio_error_reports_safe_stage_without_leaking_exception():
    with patch.object(module, "carregar_snapshot", side_effect=RuntimeError("secret")):
        result = module.executar_carteira_vr01(ids=(50318,))
    item = result["chamados"][0]
    assert item["estado"] == "FALHA_SEGURA"
    assert item["erro"] == "RuntimeError"
    assert item["etapa_falha"] == "CARREGAR_SNAPSHOT"
    assert "secret" not in str(item)


def test_existing_ledger_observer_failure_is_isolated_and_never_sends():
    issue = {"id": 50318, "_eddy_journals_completos": True,
             "subject": "VR BENEFICIO", "status": {"is_closed": False},
             "assigned_to": {"id": 97},
             "custom_fields": [{"id": 1, "name": "Clientes", "value": "CLIENTE"}]}
    snapshot = {"chamado": {"payload_json": issue, "cliente": "CLIENTE"}}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \
         patch.object(module, "clientes_do_redmine", return_value=["CLIENTE"]), \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente",
               return_value={"cnpj": "12345678000199", "estado": "OK"}), \
         patch("ednna.eddy_vr01_integrated._load",
               return_value={"original_owner_id": 97}), \
         patch("ednna.eddy_vr01_integrated._identity", return_value=100), \
         patch("ednna.eddy_vr01_integrated.planejar_vr01",
               side_effect=RuntimeError("internal secret")):
        result = module.executar_carteira_vr01(ids=(50318,), execute=False)
    item = result["chamados"][0]
    assert item["estado"] == "FALHA_SEGURA"
    assert item["etapa_falha"] == "OBSERVAR_ESTADO_MYSQL"
    assert item["erro"] == "RuntimeError"
    assert item["execucao_externa"] is False
    assert "internal secret" not in str(result)


def test_observation_does_not_require_executor_identity_or_redmine():
    from ednna import eddy_vr01_integrated as integrated
    ledger = {"fase": "AGUARDA_CONFIRMACAO_CLIENTE",
              "operacao_pendente": None, "notificado": 0}
    with patch.object(integrated, "_load", return_value=ledger), \
         patch.object(integrated, "_identity",
                      side_effect=RuntimeError("executor unavailable")) as identity, \
         patch.object(integrated, "_read_issue",
                      side_effect=RuntimeError("Redmine unavailable")) as read:
        result = integrated.planejar_vr01(execute=False)
    assert result["estado"] == "OBSERVACAO_LOCAL"
    assert result["fase"] == "AGUARDA_CONFIRMACAO_CLIENTE"
    assert result["externo"] is False
    identity.assert_not_called()
    read.assert_not_called()


def test_waiting_customer_monitors_inbox_without_redmine_preflight():
    issue = {"id": 50318, "_eddy_journals_completos": True,
             "subject": "VR BENEFICIO", "updated_on": "v1",
             "status": {"is_closed": False}, "assigned_to": {"id": 166},
             "custom_fields": [{"id": 1, "name": "Clientes", "value": "CLIENTE"}]}
    snapshot = {"chamado": {"payload_json": issue, "cliente": "CLIENTE"}, "journals": []}
    ledger = {"original_owner_id": 97, "eddy_owner_id": 166,
              "fase": "AGUARDA_CONFIRMACAO_CLIENTE", "autorizacao_confirmada": 0,
              "operacao_pendente": None, "envio_graph_confirmado": 1}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \
         patch.object(module, "clientes_do_redmine", return_value=["CLIENTE"]), \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente",
               return_value={"cnpj": "12345678000199", "estado": "RESOLVIDO"}), \
         patch("ednna.eddy_vr01_integrated._load", return_value=ledger), \
         patch("ednna.eddy_vr01_integrated._identity", return_value=166), \
         patch("ednna.eddy_vr01_integrated._read_issue") as read, \
         patch("ednna.eddy_vr01_integrated.planejar_vr01",
               return_value={"estado": "AGUARDANDO_RETORNO_CLIENTE", "externo": False}), \
         patch("ednna.eddy_global_config.enabled", return_value=True), \
         patch("ednna.eddy_vr_inbox_reconciliation.reconciliar_respostas_vr01",
               return_value={"estado": "RESPOSTAS_RECONCILIADAS", "respostas": 0}) as inbox:
        result = module.executar_carteira_vr01(ids=[50318], execute=True)
    item = result["chamados"][0]
    assert item["estado"] == "AGUARDANDO_RETORNO_CLIENTE"
    assert item["preflight_redmine"] == "DISPENSADO_AGUARDANDO_CLIENTE"
    assert item["inbox"]["respostas"] == 0
    assert result["execucao_externa"] is False
    read.assert_not_called()
    inbox.assert_called_once_with([50318])


def test_unconfirmed_eddy_ownership_still_requires_redmine_preflight():
    issue = {"id": 50318, "_eddy_journals_completos": True,
             "subject": "VR BENEFICIO", "updated_on": "v1",
             "status": {"is_closed": False}, "assigned_to": {"id": 97},
             "custom_fields": [{"id": 1, "name": "Clientes", "value": "CLIENTE"}]}
    snapshot = {"chamado": {"payload_json": issue, "cliente": "CLIENTE"}, "journals": []}
    ledger = {"original_owner_id": 97, "eddy_owner_id": 166,
              "fase": "AGUARDA_CONFIRMACAO_CLIENTE", "autorizacao_confirmada": 0,
              "operacao_pendente": None, "envio_graph_confirmado": 1}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \
         patch.object(module, "clientes_do_redmine", return_value=["CLIENTE"]), \
         patch("ednna.eddy_client_identity.resolver_identidade_cliente",
               return_value={"cnpj": "12345678000199", "estado": "RESOLVIDO"}), \
         patch("ednna.eddy_vr01_integrated._load", return_value=ledger), \
         patch("ednna.eddy_vr01_integrated._identity", return_value=166), \
         patch("ednna.eddy_vr01_integrated._read_issue",
               side_effect=RuntimeError("unavailable")) as read:
        result = module.executar_carteira_vr01(ids=[50318], execute=True)
    assert result["chamados"][0]["estado"] == "FALHA_SEGURA"
    assert result["chamados"][0]["etapa_falha"] == "PREFLIGHT_REDMINE"
    read.assert_called_once()


def test_executor_reuses_verified_issue_without_second_preflight():
    from ednna import eddy_vr01_integrated as integrated
    live = {"id": 48786, "updated_on": "v1", "assigned_to": {"id": 166}}
    ledger = {"original_owner_id": 97, "eddy_owner_id": 166,
              "fase": "AGUARDA_CONFIRMACAO_CLIENTE", "operacao_pendente": None,
              "envio_graph_confirmado": 1, "autorizacao_confirmada": 0,
              "confirmacao_evidence_id": None, "evidencias_registradas": 0,
              "notificado": 0}
    with integrated.escopo_vr01(48786, 97, "CLIENTE", "12345678000199"), \
         patch.object(integrated, "_identity", return_value=166), \
         patch.object(integrated, "_read_issue") as read, \
         patch.object(integrated, "_load", return_value=ledger):
        result = integrated.planejar_vr01(execute=True, verified_issue=live)
    assert result["estado"] == "AGUARDANDO_RETORNO_CLIENTE"
    read.assert_not_called()


def test_executor_rejects_verified_issue_for_different_ticket():
    from ednna import eddy_vr01_integrated as integrated
    with integrated.escopo_vr01(48786, 97, "CLIENTE", "12345678000199"), \
         patch.object(integrated, "_identity", return_value=166), \
         patch.object(integrated, "_read_issue") as read:
        try:
            integrated.planejar_vr01(execute=True, verified_issue={
                "id": 49119, "updated_on": "v1"})
        except RuntimeError as exc:
            assert "identidade" in str(exc)
        else:
            assert False, "Mismatched issue must be rejected"
    read.assert_not_called()
