"""VR01 source-of-truth regression: only the dedicated sync polls Redmine."""
from unittest.mock import patch

from scripts import eddy_vr01_mysql_cycle as cycle


def test_default_cycle_is_mysql_only(monkeypatch):
    monkeypatch.delenv("EDDY_VR01_OFFLINE_FIRST", raising=False)
    monkeypatch.delenv("EDDY_VR01_CYCLE_SOURCE", raising=False)
    expected = {"estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS"}
    with patch.object(cycle, "executar_ciclo_mysql_operacional", return_value=expected) as local, \
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


def test_mysql_cycle_reconciles_and_dispatches_after_verified_evidence(monkeypatch):
    from ednna import eddy_vr01_offline_proposals as offline
    with patch.object(cycle, "executar_ciclo_local_vr01", return_value={"estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS"}), \
         patch.object(offline, "listar_chamados_vr_mysql", return_value=(48786, 49119, 50428)), \
         patch.object(cycle, "reconciliar_envios_vr01", return_value={"estado": "EVIDENCIAS_RECONCILIADAS"}) as sent, \
         patch.object(cycle, "reconciliar_respostas_vr01", return_value={"estado": "RESPOSTAS_RECONCILIADAS", "respostas": 1}) as inbox, \
         patch.object(cycle, "verificar_prontidao_vr01", return_value={"pronto": True}), \
         patch.object(cycle, "executar_fila_vr01", return_value={"envios_confirmados": 0}) as dispatch:
        result = cycle.executar_ciclo_mysql_operacional()
    assert result["estado"] == "CICLO_VR01_MYSQL_COM_EXECUTOR_CONTROLADO"
    sent.assert_called_once_with([48786, 49119, 50428])
    inbox.assert_called_once_with([48786, 49119, 50428])
    dispatch.assert_called_once_with()


def test_reply_50428_partial_scan_blocks_dispatch():
    from ednna import eddy_vr01_offline_proposals as offline
    with patch.object(cycle, "executar_ciclo_local_vr01", return_value={"estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS"}), \
         patch.object(offline, "listar_chamados_vr_mysql", return_value=(50428,)), \
         patch.object(cycle, "reconciliar_envios_vr01", return_value={"estado": "EVIDENCIAS_RECONCILIADAS"}), \
         patch.object(cycle, "reconciliar_respostas_vr01", return_value={"estado": "PARCIAL_SEM_GRAVACAO"}), \
         patch.object(cycle, "executar_fila_vr01") as dispatch:
        result = cycle.executar_ciclo_mysql_operacional()
    assert result["estado"] == "BLOQUEADO_RECONCILIACAO"
    dispatch.assert_not_called()


def test_executor_48786_49119_redmine_unavailable_fails_closed():
    from ednna import eddy_vr01_offline_proposals as offline
    with patch.object(cycle, "executar_ciclo_local_vr01", return_value={"estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS"}), \
         patch.object(offline, "listar_chamados_vr_mysql", return_value=(48786, 49119)), \
         patch.object(cycle, "reconciliar_envios_vr01", side_effect=RuntimeError("redmine unavailable")), \
         patch.object(cycle, "executar_fila_vr01") as dispatch:
        result = cycle.executar_ciclo_mysql_operacional()
    assert result["estado"] == "BLOQUEADO_RECONCILIACAO"
    assert result["envios_realizados"] == 0
    dispatch.assert_not_called()
