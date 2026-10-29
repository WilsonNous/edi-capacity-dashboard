"""Read-only VR01 validation must reconcile persisted intent and never mutate."""
from unittest.mock import MagicMock, patch

from scripts import eddy_vr01_validation_report as report


def test_validation_reconciles_observational_proposal_without_writes():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (report.chave_observacional("key"), "2026-10-29", "AGUARDANDO", "COBRAR", "OBSERVACIONAL")
    snapshot = {
        "chamado": {"payload_json": {"id": 50318, "updated_on": "2026-10-29",
                                    "_eddy_journals_completos": True}},
        "journals": [{"notas": "historico", "criado_em": "2026-10-29"}],
    }
    intent = {"situacao": "PENDENTE", "action_key": "key",
              "redmine_updated_on": "2026-10-29",
              "etapa": "AGUARDANDO", "acao": "COBRAR", "destino": "FORNECEDOR"}
    with patch.object(report, "connect", return_value=conn), \
         patch.object(report, "carregar_snapshot", return_value=snapshot), \
         patch.object(report, "criar_intencao", return_value=intent):
        result = report.validar_pilotos(ids=(50318,))
    assert cursor.execute.call_args.args[1] == (50318, report.chave_observacional("key"))
    assert result["conferidos"] == 1
    assert result["chamados"][0]["estado"] == "PROPOSTA_OBSERVACIONAL_CONFERIDA"
    assert result["chamados"][0]["aprovado_para_envio"] is False
    assert result["envios_realizados"] == 0
    assert all(call.args[0].lstrip().upper().startswith("SELECT")
               for call in cursor.execute.call_args_list)


def test_validation_reports_missing_snapshot_without_mutations():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    with patch.object(report, "connect", return_value=conn), \
         patch.object(report, "carregar_snapshot", return_value=None):
        result = report.validar_pilotos(ids=(49119,))
    assert result["conferidos"] == 0
    assert result["chamados"][0]["estado"] == "SNAPSHOT_AUSENTE"
    cursor.execute.assert_not_called()
