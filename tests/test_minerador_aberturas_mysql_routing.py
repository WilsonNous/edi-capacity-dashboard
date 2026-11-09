"""Prevent SQLite regression in opening mining when MySQL is selected."""
from ednna import minerador_aberturas as m
from ednna import motores_mysql_repository as db

def test_mysql_opening_mining_routes(monkeypatch):
    monkeypatch.setenv("EDDY_DB_ENGINE","mysql")
    monkeypatch.setattr(m,"conectar",lambda: (_ for _ in ()).throw(AssertionError("SQLite accessed")))
    monkeypatch.setattr(db,"preparar_modelo",lambda:None)
    captured=[]
    monkeypatch.setattr(db,"salvar_mineracao_abertura",lambda r,now:captured.append(("mining",r["chamado_id"])))
    monkeypatch.setattr(db,"salvar_proposta_abertura",lambda p,now:captured.append(("proposal",p["regra_id"])))
    monkeypatch.setattr(db,"listar_propostas",lambda:[{"regra_id":"ABERTURA-CIELO-001"}])
    monkeypatch.setattr(db,"listar_mineracoes_player",lambda player:[{"chamado_id":123,"etapas":[]}])
    m.salvar_mineracao({"chamado_id":123})
    assert captured==[("mining",123)]
    assert m.listar_propostas()[0]["regra_id"]=="ABERTURA-CIELO-001"
    assert m._simular_ids({"player":"CIELO","etapas":[]},[123])["completa"]
