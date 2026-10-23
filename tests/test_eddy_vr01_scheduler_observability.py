"""Regression checks for the VR01 scheduler's distinct planning/dispatch metrics."""
import json
from unittest.mock import patch

from scripts import eddy_vr01_mysql_scheduler as scheduler


def test_planner_counts_not_confused_with_dispatch(caplog):
    result = {
        "estado": "CICLO_VR01_COM_EXECUTOR_CONTROLADO",
        "sincronizacao": {
            "abertos_consultados": 282, "vr_identificados": 4,
            "importados": [1, 2, 3, 4], "reutilizados_mysql": [],
            "falhas": [], "cobertura_completa": True,
        },
        "fila": {"avaliados": 4, "intencoes": 2, "bloqueados": 1},
        "execucao": {"estado": "BLOQUEADO_PRONTIDAO_OU_RECONCILIACAO"},
        "prontidao_externa": {"bloqueios": ["EXECUCAO_EXTERNA_DESABILITADA"]},
    }
    with patch.object(scheduler, "executar_worker_vr01", return_value=result):
        with caplog.at_level("INFO", logger="eddy.vr01.scheduler"):
            assert scheduler.executar_uma_vez() is result
    payload = json.loads(caplog.records[-1].message.split("] ", 1)[1])
    assert payload["planejamento"] == {"avaliados": 4, "intencoes": 2, "bloqueados": 1}
    assert payload["acoes_avaliadas"] == 0
    assert payload["cobertura_completa"] is True


def test_degraded_cycle_reports_reason_without_fake_planning(caplog):
    result = {
        "estado": "DEGRADADO_MYSQL_SOMENTE_LEITURA",
        "sincronizacao": {
            "cobertura_completa": False,
            "motivo": "Redmine nao confirmou refresh remoto",
        },
        "operacao": {"carteira_confirmada_agora": False},
    }
    with patch.object(scheduler, "executar_worker_vr01", return_value=result):
        with caplog.at_level("INFO", logger="eddy.vr01.scheduler"):
            scheduler.executar_uma_vez()
    payload = json.loads(caplog.records[-1].message.split("] ", 1)[1])
    assert payload["planejamento"]["avaliados"] is None
    assert payload["motivo_degradacao"] == "Redmine nao confirmou refresh remoto"
    assert payload["redmine_confirmado_agora"] is False
