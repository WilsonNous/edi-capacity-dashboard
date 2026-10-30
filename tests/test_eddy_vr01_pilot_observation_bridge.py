"""Existing VR01 scheduler must never execute integrated pilot actions."""
from unittest.mock import patch
from scripts.eddy_vr01_mysql_scheduler import executar_uma_vez


def test_observation_opt_in_calls_integrated_dry_run_only():
    with patch.dict("os.environ", {"EDDY_VR01_PILOT_OBSERVE": "true"}), \
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
