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
