"""Legacy per-player bootstraps must not access SQLite or auto-authorize on MySQL."""
import pytest
from ednna import aprendizado_operacional as a
from ednna import motores_mysql_repository as db

@pytest.mark.parametrize("func",[
    "garantir_greencard_pronta","garantir_safrapay_pronta","garantir_itau_pronto"])
def test_mysql_bootstrap_requires_historical_reconciliation(monkeypatch,func):
    monkeypatch.setenv("EDDY_DB_ENGINE","mysql")
    monkeypatch.setattr(a,"conectar",lambda: (_ for _ in ()).throw(AssertionError("SQLite accessed")))
    monkeypatch.setattr(a,"autorizar_regra_motor",lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("Unexpected authorization")))
    monkeypatch.setattr(db,"obter_autorizacao",lambda rid:{"regra_id":rid,"modo":"BLOQUEADA"})
    result=getattr(a,func)()
    if func=="garantir_itau_pronto":
        assert all(x["estado"]=="MIGRACAO_HISTORICA_PENDENTE" for x in result.values())
    else:
        assert result["estado"]=="MIGRACAO_HISTORICA_PENDENTE"
        assert result["autorizacao"]["modo"]=="BLOQUEADA"
