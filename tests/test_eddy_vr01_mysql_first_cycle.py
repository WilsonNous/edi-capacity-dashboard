"""VR01 source-of-truth regression: only the dedicated sync polls Redmine."""
from unittest.mock import patch

from scripts import eddy_vr01_mysql_cycle as cycle


def test_default_cycle_is_mysql_only(monkeypatch):
    monkeypatch.delenv("EDDY_VR01_OFFLINE_FIRST", raising=False)
    monkeypatch.delenv("EDDY_VR01_CYCLE_SOURCE", raising=False)
    expected = {"estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS"}
    with patch.object(cycle, "executar_ciclo_local_vr01", return_value=expected) as local, \
         patch.object(cycle, "sincronizar_carteira_vr_mysql") as remote:
        assert cycle.executar_ciclo_vr01() == expected
    local.assert_called_once_with()
    remote.assert_not_called()


def test_explicit_offline_mode_stays_mysql_only(monkeypatch):
    monkeypatch.setenv("EDDY_VR01_OFFLINE_FIRST", "true")
    monkeypatch.setenv("EDDY_VR01_CYCLE_SOURCE", "redmine")
    with patch.object(cycle, "executar_ciclo_local_vr01", return_value={"estado": "LOCAL"}) as local, \
         patch.object(cycle, "sincronizar_carteira_vr_mysql") as remote:
        assert cycle.executar_ciclo_vr01()["estado"] == "LOCAL"
    local.assert_called_once_with()
    remote.assert_not_called()


def test_redmine_mode_is_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("EDDY_VR01_OFFLINE_FIRST", "false")
    monkeypatch.setenv("EDDY_VR01_CYCLE_SOURCE", "redmine")
    with patch.object(cycle, "sincronizar_carteira_vr_mysql",
                      return_value={"cobertura_completa": False, "motivo": "UNAVAILABLE"}) as sync, \
         patch.object(cycle, "operacao_vr_mysql", return_value={"chamados": []}), \
         patch.object(cycle, "executar_ciclo_local_vr01") as local:
        result = cycle.executar_ciclo_vr01()
    assert result["estado"] == "DEGRADADO_MYSQL_SOMENTE_LEITURA"
    sync.assert_called_once_with()
    local.assert_not_called()
