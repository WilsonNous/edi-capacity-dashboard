"""No-network contract tests for assisted VR01 capture and return."""
from unittest.mock import patch
import pytest

from ednna.eddy_ownership import Ownership, OwnershipError, OwnershipState
from ednna import eddy_vr01_assisted_pilot as pilot

ISSUE = {"id": 49227, "updated_on": "2026-10-28T10:00:00Z",
         "assigned_to": {"id": 42, "name": "Responsavel"}}


def test_capture_persists_verified_original_owner():
    with patch.object(pilot, "load_ownership", return_value=None), patch.object(
        pilot, "save_transition", return_value=1
    ) as save:
        result = pilot.capturar_piloto_assistido(ISSUE, automation_user_id=99)
    item = save.call_args.args[0]
    assert item.original_assignee_id == 42
    assert item.state == OwnershipState.CAPTURED
    assert save.call_args.kwargs == {"expected_revision": None}
    assert result["efeitos_externos"] == 0


@pytest.mark.parametrize("issue", [
    {**ISSUE, "id": 49228},
    {**ISSUE, "assigned_to": {"id": 99}},
    {**ISSUE, "assigned_to": {}},
    {**ISSUE, "updated_on": ""},
])
def test_invalid_capture_never_writes(issue):
    with patch.object(pilot, "save_transition") as save:
        with pytest.raises((OwnershipError, ValueError)):
            pilot.capturar_piloto_assistido(issue, automation_user_id=99)
    save.assert_not_called()


def test_existing_capture_is_not_overwritten():
    with patch.object(pilot, "load_ownership", return_value=(object(), 1)), patch.object(
        pilot, "save_transition"
    ) as save:
        with pytest.raises(OwnershipError, match="JA_CAPTURADO"):
            pilot.capturar_piloto_assistido(ISSUE, automation_user_id=99)
    save.assert_not_called()


def test_return_requires_persisted_audited_state():
    with patch.object(pilot, "load_ownership", return_value=None):
        assert not pilot.avaliar_devolucao_assistida(ISSUE)["confirmado"]
    captured = Ownership(49227, 42, 99, ISSUE["updated_on"])
    with patch.object(pilot, "load_ownership", return_value=(captured, 1)):
        assert pilot.avaliar_devolucao_assistida(ISSUE)["motivo"] == "DEVOLUCAO_NAO_AUDITADA"
    returned = Ownership(49227, 42, 99, ISSUE["updated_on"],
                         OwnershipState.RETURNED, "redmine-confirmed")
    with patch.object(pilot, "load_ownership", return_value=(returned, 5)):
        assert pilot.avaliar_devolucao_assistida(ISSUE)["confirmado"]
        assert not pilot.avaliar_devolucao_assistida(
            {**ISSUE, "assigned_to": {"id": 99}}
        )["confirmado"]
        assert pilot.avaliar_devolucao_assistida(
            {**ISSUE, "updated_on": "changed"}
        )["motivo"] == "VERSAO_REDMINE_DIVERGENTE"
