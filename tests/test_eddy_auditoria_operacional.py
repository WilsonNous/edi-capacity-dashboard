from unittest.mock import patch
from eddy_api import service


def test_auditoria_desligamento_nao_transfere_chamados():
    issues = [
        {"id": 1, "assigned_to": {"name": "Helena Granella"}, "status": {"name": "Em andamento"}},
        {"id": 2, "assigned_to": {"name": "Vitória Lima"}, "status": {"name": "Em andamento"}},
    ]
    with patch.object(service, "_active_snapshot", return_value=(issues, "2026-10-13T10:00:00")):
        result, _, _, _, human = service.staff_departure_audit({"person": "Helena"})
    assert result["matched_count"] == 1
    assert result["issues"][0]["id"] == 1
    assert result["transfers_performed"] == 0
    assert human is True


def test_snapshot_ausente_nao_significa_zero_validado():
    with patch.object(service, "_active_snapshot", return_value=([], None)):
        result, _, _, warnings, _ = service.staff_departure_audit({"person": "Helena"})
    assert result["complete"] is False
    assert warnings


def test_capacidades_sem_falsa_promessa_de_execucao():
    with patch.object(service, "_local_metrics", return_value={"executions": 3, "followups": 2, "under_monitoring": 1}):
        with patch.object(service, "listar_homologacoes_mais_recentes", return_value=[]):
            result, _, _, _, human = service.operations_readiness({})
    assert result["opening_executor"] == "NOT_IMPLEMENTED"
    assert result["missing_file_executor"] == "NOT_IMPLEMENTED"
    assert result["recorded_executions"] == 3
    assert human is True


def test_listagem_regras_usa_catalogo():
    with patch.object(service, "listar_homologacoes_mais_recentes", return_value=[{"regra_id": "A", "estado": "ATIVA"}]):
        result, _, _, _, _ = service.rule_list({})
    assert result["total"] == 1

def test_worker_dedicado_nao_inicia_em_import():
    from ednna import worker_operacional
    assert callable(worker_operacional.main)
    from ednna import monitor_respostas
    assert monitor_respostas._THREAD is None or not monitor_respostas._THREAD.is_alive()


def test_planejar_falta_arquivo_confirmada_sem_efeitos_externos():
    demand = {
        "player": "VERO", "cliente": "Cliente de teste",
        "arquivo_esperado": "arquivo.txt", "janela_vencida": True,
        "dia_util_confirmado": True, "entrega_esperada_confirmada": True,
        "recepcao_verificada": True, "arquivo_recebido": False,
    }
    result, _, _, _, human = service.case_plan({
        "operation": "FALTA_ARQUIVO", "issue_id": 123, "demand": demand
    })
    assert result["assessment"]["estado"] == "FALTA_CONFIRMADA"
    assert result["execution"] == "NOT_PERFORMED"
    assert result["external_messages_sent"] == 0
    assert result["redmine_updates"] == 0
    assert human is True


def test_planejamento_nao_aceita_operacao_desconhecida():
    import pytest
    with pytest.raises(ValueError, match="operation"):
        service.case_plan({"operation": "INCLUSAO"})


def test_abertura_exige_regra_identificada():
    import pytest
    with pytest.raises(ValueError, match="rule_id"):
        service.case_plan({"operation": "ABERTURA", "demand": {}})



def test_homologacao_47851_lacuna_historica_nao_confirma_ausencia_atual():
    """PDF #47851: Mambo/VR Benefício, convênio 38722, NSA 339 e 355.

    As capturas demonstram saltos históricos, não a recepção atual.
    O motor não deve concluir falta confirmada nem executar comunicação.
    """
    demand = {
        "player": "VR BENEFICIO",
        "cliente": "SUPERMERCADOS MAMBO",
        "arquivo_esperado": "NSA 339 e NSA 355 / convenio 38722",
        "janela_vencida": True,
        "dia_util_confirmado": True,
        "entrega_esperada_confirmada": True,
        "recepcao_verificada": False,
        "arquivo_recebido": None,
    }
    result, _, _, _, human = service.case_plan({
        "operation": "FALTA_ARQUIVO", "issue_id": 47851, "demand": demand
    })
    assert result["assessment"]["estado"] == "AGUARDANDO_CONFERENCIA_RECEPCAO"
    assert result["assessment"]["executavel"] is False
    assert result["execution"] == "NOT_PERFORMED"
    assert result["external_messages_sent"] == 0
    assert result["redmine_updates"] == 0
    assert human is True


def test_homologacao_47851_dados_desconhecidos_nao_sao_inferidos_do_pdf():
    demand = {
        "player": "VR BENEFICIO",
        "cliente": "SUPERMERCADOS MAMBO",
        "arquivo_esperado": "NSA 339 / convenio 38722",
        "recepcao_verificada": False,
    }
    result, _, _, _, _ = service.case_plan({
        "operation": "FALTA_ARQUIVO", "issue_id": 47851, "demand": demand
    })
    assert result["assessment"]["estado"] == "AGUARDANDO_DADOS"
    assert "janela_vencida" in result["assessment"]["dados_pendentes"]
    assert "entrega_esperada_confirmada" in result["assessment"]["dados_pendentes"]
    assert result["execution"] == "NOT_PERFORMED"
