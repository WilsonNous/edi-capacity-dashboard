"""Existing VR01 scheduler must never execute integrated pilot actions."""
from unittest.mock import patch
from scripts.eddy_vr01_mysql_scheduler import executar_uma_vez


def test_observation_opt_in_calls_integrated_dry_run_only():
    with patch.dict("os.environ", {"EDDY_VR01_PILOT_OBSERVE": "true", "EDDY_VR01_PILOT_BOOTSTRAP": "false"}), \
         patch("scripts.eddy_vr01_mysql_scheduler.executar_worker_vr01",
               return_value={"estado": "OK"}), \
         patch("ednna.eddy_vr01_integrated_scheduler.ciclo_piloto",
               return_value={"chamado_id": 50318, "acao": "ASSUMIR_REDMINE"}) as pilot:
        assert executar_uma_vez()["estado"] == "OK"
        pilot.assert_called_once_with(execute=False)


def test_observation_disabled_by_default():
    with patch.dict("os.environ", {"EDDY_VR01_PILOT_OBSERVE": "false"}), \
         patch("scripts.eddy_vr01_mysql_scheduler.executar_worker_vr01",
               return_value={"estado": "OK"}), \
         patch("ednna.eddy_vr01_integrated_scheduler.ciclo_piloto") as pilot:
        executar_uma_vez()
        pilot.assert_not_called()


def test_observation_failure_does_not_stop_existing_worker():
    with patch.dict("os.environ", {"EDDY_VR01_PILOT_OBSERVE": "true"}), \
         patch("scripts.eddy_vr01_mysql_scheduler.executar_worker_vr01",
               return_value={"estado": "OK"}), \
         patch("ednna.eddy_vr01_integrated_scheduler.ciclo_piloto",
               side_effect=RuntimeError("offline")):
        assert executar_uma_vez()["estado"] == "OK"


def test_portfolio_mode_skips_fixed_pilot_and_uses_dynamic_issue_list():
    from scripts import eddy_vr01_mysql_scheduler as scheduler
    with patch.dict("os.environ", {
        "EDDY_VR01_PORTFOLIO_ENABLED": "true",
        "EDDY_VR01_PILOT_OBSERVE": "true",
        "EDDY_VR01_PILOT_BOOTSTRAP": "true",
        "EDDY_VR01_PILOT_BP_AUTO_ADVANCE": "true",
        "EDDY_VR01_REPLY_RECONCILIATION_READY": "true",
        "EDDY_VR01_EXTERNAL_ENABLED": "false",
    }), patch.object(scheduler, "executar_worker_vr01", return_value={"estado": "OK"}), \
         patch("ednna.eddy_vr01_bootstrap.inicializar_piloto_local") as bootstrap, \
         patch("ednna.eddy_vr01_integrated_scheduler.ciclo_piloto") as pilot, \
         patch("ednna.eddy_vr01_portfolio_cycle.executar_carteira_vr01",
               return_value={"estado": "CARTEIRA_VR01_PROCESSADA", "avaliados": 10}) as portfolio:
        assert scheduler.executar_uma_vez()["estado"] == "OK"
    bootstrap.assert_not_called()
    pilot.assert_not_called()
    portfolio.assert_called_once_with(execute=False)
