"""Pending assignment reconciliation uses the current issue context and never PUTs."""
from unittest.mock import patch
from ednna import eddy_vr01_integrated as vr


def _row():
    return {"fase": "PRONTO_PARA_ASSUMIR", "operacao_pendente": "ASSUMIR_REDMINE",
            "original_owner_id": 97, "eddy_owner_id": 166}


def test_assuncao_confirmada_sem_put():
    with vr.escopo_vr01(47851, 97, "Cliente A", "12345678000190"):
        with patch.object(vr, "_load", return_value=_row()), patch.object(vr, "_identity", return_value=166), \\
             patch.object(vr, "_advance") as advance, patch.object(vr, "_event") as event, \\
             patch.object(vr, "_redmine_update") as put:
            result = vr.reconciliar_assuncao_pendente(issue={"id": 47851, "assigned_to": {"id": 166}})
    assert result["estado"] == "ASSUNCAO_RECONCILIADA"
    advance.assert_called_once_with("PRONTO_PARA_ASSUMIR", "ASSUMIR_REDMINE", "ASSUMIDO_EDDY")
    event.assert_called_once_with("ASSUNCAO_EDDY", "166")
    put.assert_not_called()


def test_responsavel_divergente_preserva_reserva():
    with vr.escopo_vr01(47851, 97, "Cliente A", "12345678000190"):
        with patch.object(vr, "_load", return_value=_row()), patch.object(vr, "_identity", return_value=166), \\
             patch.object(vr, "_advance") as advance, patch.object(vr, "_event") as event:
            result = vr.reconciliar_assuncao_pendente(issue={"id": 47851, "assigned_to": {"id": 97}})
    assert result["estado"] == "AGUARDA_CONFIRMACAO_REDMINE"
    advance.assert_not_called()
    event.assert_not_called()


def test_chamado_divergente_nao_reconcilia():
    with vr.escopo_vr01(47851, 97, "Cliente A", "12345678000190"):
        with patch.object(vr, "_load", return_value=_row()), patch.object(vr, "_identity", return_value=166), \\
             patch.object(vr, "_advance") as advance:
            result = vr.reconciliar_assuncao_pendente(issue={"id": 50318, "assigned_to": {"id": 166}})
    assert result["estado"] == "RECONCILIACAO_ADIADA"
    advance.assert_not_called()


def test_erro_leitura_nao_reconcilia():
    with vr.escopo_vr01(47851, 97, "Cliente A", "12345678000190"):
        with patch.object(vr, "_load", return_value=_row()), patch.object(vr, "_identity", return_value=166), \\
             patch.object(vr, "_read_issue", side_effect=TimeoutError), patch.object(vr, "_advance") as advance:
            result = vr.reconciliar_assuncao_pendente()
    assert result["estado"] == "RECONCILIACAO_ADIADA"
    advance.assert_not_called()


def test_sem_reserva_nao_altera_estado():
    with patch.object(vr, "_load", return_value=None), patch.object(vr, "_advance") as advance:
        assert vr.reconciliar_assuncao_pendente()["estado"] == "SEM_ASSUNCAO_PENDENTE"
    advance.assert_not_called()
