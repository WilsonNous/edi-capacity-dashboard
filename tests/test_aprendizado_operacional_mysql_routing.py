"""MySQL routing regression for EDDY operational learning."""
from ednna import aprendizado_operacional as a
from ednna import motores_mysql_repository as db

def test_mysql_learning_crud_does_not_open_sqlite(monkeypatch):
    monkeypatch.setenv("EDDY_DB_ENGINE","mysql")
    monkeypatch.setattr(a,"conectar",lambda: (_ for _ in ()).throw(AssertionError("SQLite accessed")))
    seen=[]
    monkeypatch.setattr(db,"salvar_aprendizado_operacional",lambda result:seen.append(result["regra_id"]))
    monkeypatch.setattr(db,"obter_aprendizado_operacional",lambda rid:{"regra_id":rid,"player":"CIELO"})
    monkeypatch.setattr(db,"obter_revisao_operacional",lambda rid:{"regra_id":rid,"estado":"PENDENTE_REVISAO"})
    monkeypatch.setattr(db,"obter_autorizacao",lambda rid:{"regra_id":rid,"modo":"BLOQUEADA"})
    monkeypatch.setattr(db,"preparar_modelo",lambda:None)
    a.salvar_aprendizado({"regra_id":"INCLUSAO-CIELO-001"})
    assert seen==["INCLUSAO-CIELO-001"]
    assert a.obter_aprendizado("INCLUSAO-CIELO-001")["player"]=="CIELO"
    assert a.obter_revisao("INCLUSAO-CIELO-001")["estado"]=="PENDENTE_REVISAO"
    assert a.obter_autorizacao_motor("INCLUSAO-CIELO-001")["modo"]=="BLOQUEADA"
    a._garantir_tabela_revisoes()
    a._garantir_tabela_autorizacoes_motor()

def test_mysql_learning_inventory(monkeypatch):
    monkeypatch.setenv("EDDY_DB_ENGINE","mysql")
    monkeypatch.setattr(a,"conectar",lambda: (_ for _ in ()).throw(AssertionError("SQLite accessed")))
    monkeypatch.setattr(db,"listar_regras_operacionais",lambda:[{"regra_id":"INCLUSAO-CIELO-001","player":"CIELO","operacao":"INCLUSAO","estado":"APRENDIDO","estado_revisao":None,"payload_json":"{}"}])
    monkeypatch.setattr(a,"obter_autorizacao_motor",lambda rid:{"modo":"BLOQUEADA"})
    assert a.listar_regras_operacionais()[0]["modo_motor"]=="BLOQUEADA"
