"""Scheduler routing: offline-first is strictly local and opt-in."""
from unittest.mock import patch

from scripts import eddy_vr01_mysql_cycle as scheduler


def test_offline_mode_skips_all_external_work(monkeypatch):
    monkeypatch.setenv("EDDY_VR01_OFFLINE_FIRST", "true")
    with patch.object(scheduler, "executar_ciclo_local_vr01", return_value={"estado": "LOCAL"}) as local, \
         patch.object(scheduler, "sincronizar_carteira_vr_mysql") as sync, \
         patch.object(scheduler, "reconciliar_envios_vr01") as graph, \
         patch.object(scheduler, "executar_fila_vr01") as dispatch:
        result = scheduler.executar_ciclo_vr01()
    assert result == {"estado": "LOCAL"}
    local.assert_called_once_with()
    sync.assert_not_called()
    graph.assert_not_called()
    dispatch.assert_not_called()


def test_legacy_mode_remains_explicitly_unchanged(monkeypatch):
    monkeypatch.delenv("EDDY_VR01_OFFLINE_FIRST", raising=False)
    with patch.object(scheduler, "sincronizar_carteira_vr_mysql", return_value={"cobertura_completa": False}) as sync, \
         patch.object(scheduler, "operacao_vr_mysql", return_value={"chamados": []}):
        result = scheduler.executar_ciclo_vr01()
    sync.assert_called_once_with()
    assert result["estado"] == "DEGRADADO_MYSQL_SOMENTE_LEITURA"
