from ednna.simrede_francimar import classificar_ocorrencias_simrede

def msg(texto, remetente="francimar.tondello@grupoargenta.com.br"):
    return {"from":{"emailAddress":{"address":remetente}},"subject":"Logs arquivos adquirentes produção Rede Sim","body":{"contentType":"text","content":texto},"id":"m1","internetMessageId":"i1"}

def test_francimar_senff_lote():
    out=classificar_ocorrencias_simrede(msg("faltam vendas SENFF em 03/06/2026 SIM A 07.473.735/0039-54 SIM B 07.473.735/0059-06"))
    assert len(out)==2
    assert {x["tipo"] for x in out}=={"FALTA_VENDAS"}
    assert {x["player"] for x in out}=={"SENFF"}

def test_ignora_remetente_nao_confiavel():
    assert classificar_ocorrencias_simrede(msg("faltam vendas SENFF 07.473.735/0039-54","outro@example.com"))==[]

def test_nao_mistura_historico_citado():
    texto="faltam vendas SENFF 07.473.735/0039-54 Em sex., 25 de set. de 2026 escreveu: faltam vendas STONE 07.473.735/0244-47"
    out=classificar_ocorrencias_simrede(msg(texto))
    assert len(out)==1
    assert out[0]["player"]=="SENFF"
    assert out[0]["cnpj"]=="07.473.735/0039-54"
