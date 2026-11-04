from ednna.redmine_collection_policy import observational_state


def test_missing_lifecycle_is_read_only():
    assert observational_state(50318, None) == {
        "chamado_id": 50318, "estado": "AGUARDA_INICIALIZACAO_MYSQL",
        "externo": False, "fonte": "MYSQL_LOCAL"}


def test_existing_lifecycle_is_read_only():
    result = observational_state(42, {"fase": "AGUARDA_CONTATO_BP",
                                      "operacao_pendente": "BUSCAR_CONTATO_BP"})
    assert result["fase"] == "AGUARDA_CONTATO_BP"
    assert result["operacao_pendente"] == "BUSCAR_CONTATO_BP"
    assert result["externo"] is False
    assert result["fonte"] == "MYSQL_LOCAL"


def test_completed_lifecycle_preserves_contract():
    result = observational_state(50318, {"fase": "CONCLUIDO", "operacao_pendente": None})
    assert result["acao"] == "CONCLUIDO"
    assert result["externo"] is False
