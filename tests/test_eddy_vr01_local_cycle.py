"""Offline-first cycle contract: no Redmine dependency."""
from unittest.mock import patch

from ednna import eddy_vr01_local_cycle as cycle


def test_local_cycle_uses_only_mysql_projection():
    with patch.object(cycle, "operacao_vr_mysql", return_value={"chamados": [{"chamado_id": 49227}]}) as op:
        result = cycle.executar_ciclo_local_vr01()
    op.assert_called_once_with()
    assert result["estado"] == "VR01_ANALISE_LOCAL_SOMENTE_LEITURA"
    assert result["redmine_consultas"] == 0
    assert result["redmine_escritas"] == 0
    assert result["envios_realizados"] == 0
    assert result["acoes_externas_autorizadas"] is False


def test_local_cycle_fails_closed_without_mysql():
    with patch.object(cycle, "operacao_vr_mysql", side_effect=ConnectionError("offline")):
        result = cycle.executar_ciclo_local_vr01()
    assert result["estado"] == "BLOQUEADO_MYSQL_INDISPONIVEL"
    assert result["redmine_escritas"] == result["envios_realizados"] == 0
