"""Portfolio planning never executes external operations."""
from unittest.mock import patch
from ednna import eddy_vr01_portfolio as portfolio


def _snapshot(issue_id, complete=True):
    return {
        "chamado": {"payload_json": {
            "id": issue_id, "updated_on": "2026-11-06T12:00:00Z",
            "_eddy_journals_completos": complete,
            "subject": "VR BENEFICIO - INCLUSAO DE ESTABELECIMENTO",
            "status": {"name": "Em Andamento", "is_closed": False},
            "assigned_to": {"id": 97},
            "tracker": {"name": "EDI - Inclusão de EC/Domc"},
        }},
        "journals": [],
    }


def test_portfolio_uses_each_issue_own_snapshot():
    ids = (50318, 50671)
    with patch.object(portfolio, "listar_chamados_vr_mysql", return_value=ids), \
         patch.object(portfolio, "carregar_snapshot", side_effect=lambda cid: _snapshot(cid)) as read:
        result = portfolio.planejar_carteira_vr01()
    assert result["avaliados"] == 2
    assert result["execucao_externa"] is False
    assert result["envios_realizados"] == result["redmine_escritas"] == 0
    assert [call.args[0] for call in read.call_args_list] == list(ids)
    assert [item["chamado_id"] for item in result["chamados"]] == list(ids)


def test_portfolio_does_not_plan_incomplete_history():
    with patch.object(portfolio, "carregar_snapshot", return_value=_snapshot(50318, False)):
        result = portfolio.planejar_carteira_vr01(ids=(50318,))
    assert result["chamados"][0]["estado"] == "BLOQUEADO_HISTORICO_INCOMPLETO"


def test_portfolio_does_not_plan_missing_snapshot():
    with patch.object(portfolio, "carregar_snapshot", return_value=None):
        result = portfolio.planejar_carteira_vr01(ids=(50671,))
    assert result["chamados"][0]["estado"] == "BLOQUEADO_SNAPSHOT_AUSENTE"
