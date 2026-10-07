from ednna.continuidade_responsabilidade import classificar_proxima_responsabilidade

def test_envio_confirmado_fica_com_eddy(monkeypatch):
    monkeypatch.setattr("ednna.continuidade_responsabilidade.obter_responsavel_origem", lambda _: {})
    d=classificar_proxima_responsabilidade({"#":10,"Estado":"Aguardando Retorno Adquirente"},"CONTINUIDADE_ESTADO_REDMINE",{"estado":"AGUARDANDO_RESPOSTA","envio_confirmado":1})
    assert d["decisao"]=="AGUARDAR_TERCEIRO"

def test_cliente_com_origem_preservada_devolve(monkeypatch):
    monkeypatch.setattr("ednna.continuidade_responsabilidade.obter_responsavel_origem", lambda _: {"id":77,"fonte":"MEMORIA_TRANSACIONAL"})
    d=classificar_proxima_responsabilidade({"#":47543,"Estado":"AGUARDANDO RETORNO CLIENTE"},"CONTINUIDADE_ESTADO_REDMINE",{})
    assert d["decisao"]=="DEVOLVER_ORIGEM"
    assert d["responsavel_origem"]["id"]==77

def test_cliente_sem_origem_nao_adivinha(monkeypatch):
    monkeypatch.setattr("ednna.continuidade_responsabilidade.obter_responsavel_origem", lambda _: {})
    d=classificar_proxima_responsabilidade({"#":20,"Estado":"AGUARDANDO RETORNO CLIENTE"},"CONTINUIDADE_ESTADO_REDMINE",{})
    assert d["decisao"]=="DECISAO_HUMANA"

def test_resposta_recebida_volta_para_eddy(monkeypatch):
    monkeypatch.setattr("ednna.continuidade_responsabilidade.obter_responsavel_origem", lambda _: {})
    d=classificar_proxima_responsabilidade({"#":30,"Estado":"Em andamento"},"CONTINUIDADE_ESTADO_REDMINE",{"estado":"RESPOSTA_RECEBIDA"})
    assert d["decisao"]=="ACAO_EDDY_DUE"
