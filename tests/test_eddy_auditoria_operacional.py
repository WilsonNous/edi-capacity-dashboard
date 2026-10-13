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
