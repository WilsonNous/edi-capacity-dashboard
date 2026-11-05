"""Four-stage VR01 diagnostics never authorize or execute external actions."""
from unittest.mock import patch

from ednna.eddy_vr01_stage_readiness import diagnosticar_etapas_vr01

MOD = "ednna.eddy_vr01_stage_readiness"


def _run(row, ready=False):
    with patch(f"{MOD}._load", return_value=row), \
         patch(f"{MOD}._identity", return_value=999), \
         patch(f"{MOD}.verificar_prontidao_vr01",
               return_value={"pronto": ready, "bloqueios": [] if ready else ["EXECUCAO_EXTERNA_DESABILITADA"]}), \
         patch(f"{MOD}.verificar_prontidao_operacao_vr01",
               return_value={"pronto": ready, "bloqueios": [] if ready else ["EXECUCAO_EXTERNA_DESABILITADA"]}), \
         patch("ednna.eddy_vr01_integrated._redmine_update") as redmine:
        result = diagnosticar_etapas_vr01()
        redmine.assert_not_called()
        return result


def test_missing_ledger_blocks_all_four_stages():
    result = _run(None)
    assert result["estado"] == "AGUARDA_INICIALIZACAO_MYSQL"
    assert len(result["etapas"]) == 4
    assert all(s["estado"] == "BLOQUEADA_LEDGER" for s in result["etapas"])


def test_initialized_pilot_shows_real_readiness_blockers():
    result = _run({"fase": "PRONTO_PARA_ASSUMIR",
                   "original_owner_id": 97, "eddy_owner_id": 999})
    assert result["etapas"][0]["estado"] == "AGUARDA_HOMOLOGACAO"
    assert result["etapas"][1]["estado"] == "AGUARDA_ETAPA_ANTERIOR"
    assert result["execucao_externa"] is False


def test_ready_does_not_mean_approved_or_executed():
    result = _run({"fase": "PRONTO_PARA_ASSUMIR",
                   "original_owner_id": 97, "eddy_owner_id": 999}, ready=True)
    assert result["etapas"][0]["estado"] == "AGUARDA_APROVACAO_E_EVIDENCIAS"
    assert result["estado"] == "PENDENTE_EXECUCAO_HOMOLOGADA"


def test_identity_mismatch_blocks_all_stages():
    result = _run({"fase": "PRONTO_PARA_ASSUMIR",
                   "original_owner_id": 97, "eddy_owner_id": 888}, ready=True)
    assert result["estado"] == "BLOQUEADO_IDENTIDADE_OU_FASE"


def test_pending_operation_requires_manual_reconciliation():
    result = _run({"fase": "ASSUMIDO_EDDY", "original_owner_id": 97,
                   "eddy_owner_id": 999, "operacao_pendente": "ASSUMIR_REDMINE"})
    assert result["estado"] == "AGUARDA_RECONCILIACAO_MANUAL"


def test_final_state_requires_notification_evidence():
    row = {"fase": "NOTIFICACAO_INTERNA_CONFIRMADA",
           "original_owner_id": 97, "eddy_owner_id": 999, "notificado": 0}
    assert _run(row, ready=True)["estado"] == "PENDENTE_EXECUCAO_HOMOLOGADA"
    row["notificado"] = 1
    assert _run(row, ready=True)["estado"] == "CONCLUIDO_NO_LEDGER"
