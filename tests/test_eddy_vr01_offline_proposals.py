"""Offline VR01 proposals cannot enter the dispatchable PENDENTE state."""
from unittest.mock import MagicMock, patch

from ednna import eddy_vr01_offline_proposals as module


def issue(issue_id):
    return {"id": issue_id, "updated_on": "2026-10-29T09:00:00Z",
            "_eddy_journals_completos": True,
            "subject": "VR BENEFICIO - INCLUSÃO DE ESTABELECIMENTO",
            "tracker": {"name": "EDI - Inclusão de EC/Domc"},
            "status": {"name": "Em Andamento"}}


def test_observational_intent_is_persisted_not_dispatchable():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    snapshot = {"chamado": {"payload_json": issue(50318)}, "journals": []}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \
         patch.object(module, "connect", return_value=conn):
        result = module.preparar_intencoes_locais(ids=(50318,))
    assert result["propostas"] == 1
    assert result["acoes_externas_autorizadas"] is False
    sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("'OBSERVACIONAL'" in query for query in sql)
    assert all("UPDATE" not in query for query in sql)


def test_missing_snapshot_is_blocked_without_proposal():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    with patch.object(module, "carregar_snapshot", return_value=None), \
         patch.object(module, "connect", return_value=conn):
        result = module.preparar_intencoes_locais(ids=(49119,))
    assert result["propostas"] == 0
    assert result["bloqueados"][0]["motivo"] == "SNAPSHOT_AUSENTE"


def test_incomplete_history_cannot_generate_intent():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    data = issue(48786)
    data["_eddy_journals_completos"] = False
    with patch.object(module, "carregar_snapshot", return_value={"chamado": {"payload_json": data}, "journals": []}), \
         patch.object(module, "connect", return_value=conn):
        result = module.preparar_intencoes_locais(ids=(48786,))
    assert result["propostas"] == 0
    assert result["bloqueados"][0]["motivo"] == "BLOQUEADO_HISTORICO_INCOMPLETO"


def test_observational_key_is_separate_and_idempotent():
    assert module.chave_observacional("a" * 64) != "a" * 64
    assert module.chave_observacional("a" * 64) == module.chave_observacional("a" * 64)
    assert len(module.chave_observacional("a" * 64)) == 64


def test_insert_ignore_reports_existing_row_without_overwriting():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.rowcount = 0
    snapshot = {"chamado": {"payload_json": issue(50318)}, "journals": []}
    with patch.object(module, "carregar_snapshot", return_value=snapshot), \\
         patch.object(module, "connect", return_value=conn):
        result = module.preparar_intencoes_locais(ids=(50318,))
    assert result["propostas"] == 1
    assert result["inseridas"] == 0
    assert result["ja_existentes"] == 1
    sql_calls = [c for c in cursor.execute.call_args_list if "INSERT IGNORE" in c.args[0]]
    assert len(sql_calls) == 1
    assert sql_calls[0].args[1][0] == module.chave_observacional(
        module.criar_intencao(issue(50318), [])["action_key"]
    )
    assert all("UPDATE" not in c.args[0] for c in cursor.execute.call_args_list)
