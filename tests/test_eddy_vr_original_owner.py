import pytest
from ednna.eddy_vr_original_owner import capturar_responsavel_original, verificar_devolucao


ISSUE = {"id": 49227, "updated_on": "2026-10-27T10:00:00Z",
         "assigned_to": {"id": 42, "name": "Wilson"}}


def test_capture_before_takeover_and_verify_return():
    owner = capturar_responsavel_original(ISSUE, automation_user_id=99)
    assert owner["original_owner_id"] == 42
    taken = {**ISSUE, "assigned_to": {"id": 99, "name": "ednna.ia"}}
    assert not verificar_devolucao(taken, owner)["confirmado"]
    assert verificar_devolucao(ISSUE, owner)["confirmado"]


@pytest.mark.parametrize("issue", [
    {"id": 49227, "updated_on": "v1", "assigned_to": {"id": 99}},
    {"id": 49227, "updated_on": "v1"},
    {"id": 49227, "assigned_to": {"id": 42}},
])
def test_capture_blocks_unverifiable_owner(issue):
    with pytest.raises(ValueError):
        capturar_responsavel_original(issue, automation_user_id=99)


def test_different_ticket_never_confirms_return():
    owner = capturar_responsavel_original(ISSUE, automation_user_id=99)
    assert not verificar_devolucao({**ISSUE, "id": 123}, owner)["confirmado"]
