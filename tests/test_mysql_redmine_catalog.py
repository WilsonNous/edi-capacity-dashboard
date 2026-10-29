"""Catalog interpretation safety tests."""
from ednna.mysql_redmine_catalog import traduzir_valores


def test_multi_value_preserves_identifiers_and_labels():
    result = traduzir_valores(["347", "246"], 1,
                             mapa={"347": "MAMBO", "246": "ANDREAZZA"})
    assert result == [
        {"id": "347", "nome": "MAMBO", "resolvido": True},
        {"id": "246", "nome": "ANDREAZZA", "resolvido": True},
    ]


def test_unknown_value_never_becomes_name():
    assert traduzir_valores(["999"], 1, mapa={}) == [
        {"id": "999", "nome": None, "resolvido": False},
    ]
