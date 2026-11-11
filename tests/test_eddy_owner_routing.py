from ednna.eddy_owner_routing import sugerir_responsavel


def test_special_clients_override_alphabetical():
    for name in ("SIM REDE", "SANTA LÚCIA", "SANDER", "MARTMINAS", "POSTOS ROTA", "MAMBO"):
        assert sugerir_responsavel(name)["responsavel"] == "Wilson"


def test_alphabetical_distribution():
    assert sugerir_responsavel("ACME")["responsavel"] == "Vitória"
    assert sugerir_responsavel("MERCADO")["responsavel"] == "Vitória"
    assert sugerir_responsavel("NOVA REDE")["responsavel"] == "Laura"
    assert sugerir_responsavel("ZETA")["responsavel"] == "Laura"


def test_override_and_invalid_configuration(monkeypatch):
    monkeypatch.setenv("EDDY_OWNER_ROUTING_JSON", '{"excecoes":{"ACME":"Laura"},"alfabetico":{"A_M":"Vitória","N_Z":"Laura"}}')
    assert sugerir_responsavel("ACME")["responsavel"] == "Laura"
    monkeypatch.setenv("EDDY_OWNER_ROUTING_JSON", '{"excecoes":[]}')
    assert sugerir_responsavel("ACME")["criterio"] == "CONFIGURACAO_INVALIDA"
