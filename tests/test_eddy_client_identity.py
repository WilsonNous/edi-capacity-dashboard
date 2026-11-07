from ednna.eddy_client_identity import _cnpj_values, cnpjs_blueprint


def test_cnpj_masked_and_plain():
    assert _cnpj_values("12.345.678/0001-90") == {"12345678000190"}
    assert _cnpj_values("12345678000190") == {"12345678000190"}


def test_cnpj_from_bp_custom_field_not_operational_issue():
    bp = {"custom_fields": [{"name": "CNPJ Matriz", "value": "12.345.678/0001-90"}]}
    assert cnpjs_blueprint(bp) == {"12345678000190"}


def test_identificacao_sheet_and_legacy_sheet():
    abas = {"Identificação": [["CNPJ:", "12.345.678/0001-90"]],
            "ID PROJETO": [["CNPJ:", "98.765.432/0001-10"]],
            "Participantes": [["CNPJ", "11.111.111/0001-11"]]}
    assert cnpjs_blueprint({}, abas) == {"12345678000190", "98765432000110"}


def test_no_arbitrary_cnpj_from_multiple_entities():
    bp = {"custom_fields": [{"name": "CNPJ", "value": [
        "12.345.678/0001-90", "98.765.432/0001-10"]}]}
    assert len(cnpjs_blueprint(bp)) == 2
