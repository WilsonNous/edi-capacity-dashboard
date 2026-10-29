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


def test_offline_cycle_reports_real_proposals_and_blockers(caplog):
    result = {
        "estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS",
        "propostas": {
            "estado": "PROPOSTAS_OBSERVACIONAIS_PERSISTIDAS",
            "avaliados": 4,
            "propostas": 3,
            "bloqueados": [{"chamado_id": 50120, "motivo": "SNAPSHOT_AUSENTE"}],
            "situacao_fila": "OBSERVACIONAL",
        },
        "operacao": {
            "total_snapshots_vr": 4,
            "chamados": [{"chamado_id": 50318}, {"chamado_id": 49119},
                         {"chamado_id": 48786}, {"chamado_id": 50120}],
        },
        "envios_realizados": 0,
        "redmine_escritas": 0,
    }
    with patch.object(scheduler, "executar_worker_vr01", return_value=result):
        with caplog.at_level("INFO", logger="eddy.vr01.scheduler"):
            scheduler.executar_uma_vez()
    payload = json.loads(caplog.records[-1].message.split("] ", 1)[1])
    assert payload["modo_offline"] is True
    assert payload["planejamento"]["avaliados"] == 4
    assert payload["planejamento"]["intencoes"] == 3
    assert payload["planejamento"]["bloqueados"] == 1
    assert payload["planejamento"]["detalhes_bloqueios"] == [
        {"chamado_id": 50120, "motivo": "SNAPSHOT_AUSENTE"}
    ]
    assert payload["planejamento"]["situacao_fila"] == "OBSERVACIONAL"
    assert payload["total_snapshots_vr_mysql"] == 4
    assert len(payload["chamados_vr_mysql"]) == 4
    assert payload["envios_realizados"] == 0
    assert payload["redmine_escritas"] == 0
