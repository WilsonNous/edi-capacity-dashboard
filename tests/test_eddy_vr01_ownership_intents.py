"""Fail-closed intent preparation for pilot #49227."""
from unittest.mock import patch
import pytest
from ednna.eddy_ownership import Ownership, OwnershipError, OwnershipState
from ednna import eddy_vr01_ownership_intents as intents

ISSUE = {"id": 49227, "updated_on": "v1", "assigned_to": {"id": 42}}


def test_claim_preparation_persists_pending_only():
    item = Ownership(49227, 42, 99, "v1")
    with patch.object(intents, "load_ownership", return_value=(item, 3)), patch.object(
        intents, "save_transition", return_value=4
    ) as save:
        result = intents.preparar_intencao_atribuicao(ISSUE, destino="eddy")
    assert save.call_args.args[0].state == OwnershipState.CLAIM_PENDING
    assert save.call_args.kwargs == {"expected_revision": 3}
    assert result["destino_assignee_id"] == 99
    assert result["redmine_escritas"] == 0


def test_return_preparation_targets_original():
    item = Ownership(49227, 42, 99, "v2", OwnershipState.HUMAN_REQUIRED)
    issue = {**ISSUE, "updated_on": "v2", "assigned_to": {"id": 99}}
    with patch.object(intents, "load_ownership", return_value=(item, 4)), patch.object(
        intents, "save_transition", return_value=5
    ) as save:
        result = intents.preparar_intencao_atribuicao(issue, destino="original")
    assert save.call_args.args[0].state == OwnershipState.RETURN_PENDING
    assert result["destino_assignee_id"] == 42


@pytest.mark.parametrize("issue", [
    {**ISSUE, "id": 49228},
    {**ISSUE, "updated_on": "stale"},
    {**ISSUE, "assigned_to": {"id": 99}},
    {**ISSUE, "assigned_to": {}},
])
def test_mismatch_never_persists_intent(issue):
    item = Ownership(49227, 42, 99, "v1")
    with patch.object(intents, "load_ownership", return_value=(item, 1)), patch.object(
        intents, "save_transition"
    ) as save:
        with pytest.raises(OwnershipError):
            intents.preparar_intencao_atribuicao(issue, destino="eddy")
    save.assert_not_called()
