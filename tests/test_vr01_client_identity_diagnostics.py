"""VR01 identity diagnostics: no guesses, no sensitive values in results."""
from ednna.eddy_vr01_portfolio_cycle import diagnosticar_identificacao_cliente


def issue(clientes=None, cnpjs=None):
    fields = []
    if clientes is not None:
        fields.append({"id": 1, "name": "Clientes", "value": clientes})
    if cnpjs is not None:
        fields.append({"id": 25, "name": "CNPJ", "value": cnpjs})
    return {"custom_fields": fields}


def test_identificacao_valida():
    assert diagnosticar_identificacao_cliente(issue(["Cliente A"], "12.345.678/0001-90"))["motivos"] == []


def test_cliente_ausente():
    assert diagnosticar_identificacao_cliente(issue(cnpjs="12345678000190"))["motivos"] == ["CLIENTE_AUSENTE"]


def test_cliente_ambiguo():
    assert diagnosticar_identificacao_cliente(issue(["A", "B"], "12345678000190"))["motivos"] == ["CLIENTE_AMBIGUO"]


def test_cnpj_ausente():
    assert diagnosticar_identificacao_cliente(issue(["A"]))["motivos"] == []


def test_cnpj_invalido():
    assert diagnosticar_identificacao_cliente(issue(["A"], "123"))["motivos"] == []


def test_cnpj_ambiguo():
    assert diagnosticar_identificacao_cliente(issue(["A"], ["12345678000190", "98765432000199"]))["motivos"] == []


def test_nao_expoe_dados_sensiveis():
    result = str(diagnosticar_identificacao_cliente(issue(["Cliente Confidencial"], "12345678000190")))
    assert "Confidencial" not in result
    assert "12345678000190" not in result


def test_ausencia_simultanea():
    assert diagnosticar_identificacao_cliente(issue())["motivos"] == ["CLIENTE_AUSENTE", "CNPJ_AUSENTE"]
