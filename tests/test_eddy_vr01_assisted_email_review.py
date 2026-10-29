"""Safety tests for assisted email drafting; no outbound side effects."""
from unittest.mock import patch

from scripts import eddy_vr01_assisted_email_review as module


def test_drafts_only_reconciled_customer_habilitation_without_recipient():
    data = {"chamados": [
        {"chamado_id": 50318, "estado": "PROPOSTA_OBSERVACIONAL_CONFERIDA",
         "acao": "VERIFICAR_HABILITACAO_COM_CLIENTE", "versao_redmine": "2026-10-27"},
        {"chamado_id": 49119, "estado": "PROPOSTA_OBSERVACIONAL_CONFERIDA",
         "acao": "CLASSIFICAR_SOLICITACAO", "versao_redmine": "2026-10-01"},
        {"chamado_id": 48786, "estado": "PROPOSTA_DIVERGENTE_OU_NAO_OBSERVACIONAL",
         "acao": "VERIFICAR_HABILITACAO_COM_CLIENTE", "versao_redmine": "2026-09-18"},
    ]}
    with patch.object(module, "validar_pilotos", return_value=data) as validator, \
         patch.object(module, "candidatos_destinatarios", return_value={"candidatos": [], "fonte": "TESTE"}):
        result = module.preparar_revisao(ids=(50318, 49119, 48786))
    validator.assert_called_once_with((50318, 49119, 48786))
    assert result["minutas"] == 1
    assert result["envios_realizados"] == 0
    assert result["redmine_escritas"] == 0
    assert result["envio_automatico_habilitado"] is False
    draft = result["propostas"][0]
    assert draft["remetente"] == "edi@netunna.com.br"
    assert draft["destinatario"] is None
    assert draft["destinatario_validado"] is False
    assert draft["aprovado_para_envio"] is False
    assert "#50318" in draft["assunto"]
    assert result["propostas"][1]["estado"] == "REVISAO_HUMANA_SEM_MINUTA"
    assert result["propostas"][2]["estado"] == "BLOQUEADO_RECONCILIACAO"

def test_candidates_from_existing_extractor_exclude_internal_and_vr():
    issue = {"id": 50318, "subject": "Habilitação", "description": "Contato", "updated_on": "2026-10-27"}
    stored = {"chamado": {"payload_json": __import__("json").dumps(issue), "cliente": "CLIENTE TESTE"}}
    with patch.object(module, "carregar_snapshot", return_value=stored), \
         patch.object(module, "selecionar_contatos_cliente", return_value=[]), \
         patch.object(module, "_extrair_dados", return_value={
             "emails": ["cliente@example.com", "vr@vr.com.br",
                        "edi@netunna.com.br", "cliente@example.com"]}):
        result = module.candidatos_destinatarios(50318)
    assert result["candidatos"] == ["cliente@example.com"]
    assert result["fonte"] == "BLUEPRINT_E_EXTRATOR_OPERACIONAL"


def test_candidates_fail_closed_on_missing_snapshot():
    with patch.object(module, "carregar_snapshot", return_value=None):
        assert module.candidatos_destinatarios(50318)["candidatos"] == []

def test_blueprint_priority_and_provenance():
    issue = {"id": 50318, "subject": "Habilitação", "description": ""}
    stored = {"chamado": {"payload_json": issue, "cliente": "MAMBO"}}
    bp = [{"email": "financeiro@cliente.com"}, {"email": "gerente@cliente.com"},
          {"email": "interno@netunna.com.br"}]
    with patch.object(module, "carregar_snapshot", return_value=stored), \
         patch.object(module, "selecionar_contatos_cliente", return_value=bp) as selector, \
         patch.object(module, "_extrair_dados", return_value={"emails": ["outro@cliente.com"]}):
        result = module.candidatos_destinatarios(50318)
    selector.assert_called_once_with("MAMBO", limite=10)
    assert result["candidatos"] == [
        "financeiro@cliente.com", "gerente@cliente.com", "outro@cliente.com"]
    assert result["fontes_por_destinatario"]["gerente@cliente.com"] == "BLUEPRINT_PARTICIPANTES"
    assert result["estado_blueprint"] == "CONSULTADO"


def test_blueprint_sqlite_failure_falls_back_without_authorizing():
    issue = {"id": 48786, "subject": "Habilitação", "description": ""}
    stored = {"chamado": {"payload_json": issue, "cliente": "ANDREAZZA"}}
    with patch.object(module, "carregar_snapshot", return_value=stored), \
         patch.object(module, "selecionar_contatos_cliente", side_effect=RuntimeError("db corrupt")), \
         patch.object(module, "_extrair_dados", return_value={"emails": ["cliente@exemplo.com"]}):
        result = module.candidatos_destinatarios(48786)
    assert result["candidatos"] == ["cliente@exemplo.com"]
    assert result["estado_blueprint"] == "INDISPONIVEL_RuntimeError"

def test_old_mysql_snapshot_resolves_client_from_redmine_custom_field():
    issue = {"id": 50318, "subject": "Habilitação", "description": "",
             "custom_fields": [{"id": 1, "name": "Clientes", "value": "SUPERMERCADOS MAMBO"}]}
    stored = {"chamado": {"payload_json": issue, "cliente": None}}
    with patch.object(module, "carregar_snapshot", return_value=stored), \
         patch.object(module, "selecionar_contatos_cliente", return_value=[
             {"email": "gerente@cliente.com"}]) as selector, \
         patch.object(module, "_extrair_dados", return_value={"emails": []}):
        result = module.candidatos_destinatarios(50318)
    selector.assert_called_once_with("SUPERMERCADOS MAMBO", limite=10)
    assert result["cliente_blueprint"] == "SUPERMERCADOS MAMBO"
    assert result["candidatos"] == ["gerente@cliente.com"]

def test_multiselect_client_uses_blueprint_selector():
    issue = {"id": 50318, "subject": "VR Beneficios", "description": "",
             "custom_fields": [{"id": 1, "value": ["SUPERMERCADOS MAMBO"]}]}
    with patch.object(module, "carregar_snapshot", return_value={"chamado": {"payload_json": issue, "cliente": None}}), \
         patch.object(module, "selecionar_contatos_cliente", return_value=[]) as selector, \
         patch.object(module, "_extrair_dados", return_value={"emails": []}):
        result = module.candidatos_destinatarios(50318)
    selector.assert_called_once_with("SUPERMERCADOS MAMBO", limite=10)
    assert result["cliente_blueprint"] == "SUPERMERCADOS MAMBO"


def test_ambiguous_multiselect_blocks_blueprint_lookup():
    issue = {"id": 50318, "subject": "VR Beneficios", "description": "",
             "custom_fields": [{"id": 1, "value": ["A", "B"]}]}
    with patch.object(module, "carregar_snapshot", return_value={"chamado": {"payload_json": issue, "cliente": None}}), \
         patch.object(module, "selecionar_contatos_cliente") as selector, \
         patch.object(module, "_extrair_dados", return_value={"emails": []}):
        result = module.candidatos_destinatarios(50318)
    selector.assert_not_called()
    assert result["estado_blueprint"] == "MULTIPLOS_CLIENTES_REVISAO_HUMANA"
    assert result["cliente_blueprint"] == ""

def test_numeric_redmine_client_resolved_from_mysql_catalog():
    issue = {"id": 50318, "subject": "VR", "description": "",
             "custom_fields": [{"id": 1, "value": ["347"]}]}
    with patch.object(module, "carregar_snapshot", return_value={"chamado": {"payload_json": issue}}), \
         patch.object(module, "mapa_persistido", return_value={"347": "SUPERMERCADOS MAMBO"}), \
         patch.object(module, "selecionar_contatos_cliente", return_value=[]) as selector, \
         patch.object(module, "_extrair_dados", return_value={"emails": []}):
        result = module.candidatos_destinatarios(50318)
    selector.assert_called_once_with("SUPERMERCADOS MAMBO", limite=10)
    assert result["estado_catalogo_clientes"] == "RESOLVIDO_MYSQL"
    assert result["cliente_blueprint"] == "SUPERMERCADOS MAMBO"


def test_unknown_numeric_client_id_does_not_lookup_blueprint():
    issue = {"id": 48786, "subject": "VR", "description": "",
             "custom_fields": [{"id": 1, "value": ["246"]}]}
    with patch.object(module, "carregar_snapshot", return_value={"chamado": {"payload_json": issue}}), \
         patch.object(module, "mapa_persistido", return_value={}), \
         patch.object(module, "selecionar_contatos_cliente") as selector, \
         patch.object(module, "_extrair_dados", return_value={"emails": []}):
        result = module.candidatos_destinatarios(48786)
    selector.assert_not_called()
    assert result["estado_blueprint"] == "CLIENTE_ID_SEM_CATALOGO"
