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
    with patch.object(module, "validar_pilotos", return_value=data) as validator:
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
