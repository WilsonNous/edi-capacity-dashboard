"""MySQL routing regression: no legacy SQLite access in homologation lifecycle."""
import pytest
from ednna import homologacao

def test_mysql_homologacao_reads_without_sqlite(monkeypatch):
    monkeypatch.setenv("EDDY_DB_ENGINE","mysql")
    from ednna import motores_mysql_repository as repo
    monkeypatch.setattr(homologacao,"conectar",lambda: (_ for _ in ()).throw(AssertionError("SQLite accessed")))
    monkeypatch.setattr(repo,"estado_regra",lambda rid: {"regra_id":rid,"estado":"SUSPENSA"})
    monkeypatch.setattr(repo,"listar_homologacoes",lambda: [{"regra_id":"ABERTURA-X-001","estado":"SUSPENSA"}])
    assert homologacao.estado_regra("ABERTURA-X-001")["estado"]=="SUSPENSA"
    assert len(homologacao.listar_homologacoes_mais_recentes())==1
    assert not homologacao.regra_pode_executar("ABERTURA-X-001")

def test_mysql_homologacao_writes_without_sqlite(monkeypatch):
    monkeypatch.setenv("EDDY_DB_ENGINE","mysql")
    from ednna import motores_mysql_repository as repo
    monkeypatch.setattr(homologacao,"conectar",lambda: (_ for _ in ()).throw(AssertionError("SQLite accessed")))
    monkeypatch.setattr(repo,"preparar_modelo",lambda:None)
    monkeypatch.setattr(repo,"homologar",lambda rid,player,estado,professor,nota,raw,sha,motivo,agora: {
        "regra_id":rid,"versao":1,"estado":estado,"nota":nota,
        "homologado_por":professor,"homologado_em":agora,"snapshot_sha256":sha})
    monkeypatch.setattr(repo,"alterar_estado",lambda rid,estado,professor,motivo,agora: {"regra_id":rid,"estado":estado})
    result=homologacao.homologar_e_ativar({"regra_id":"ABERTURA-X-001","player":"X"},
        {"nota_ponderada_pct":95,"criticas_recentes":[]}, "Professor")
    assert result["estado"]=="ATIVA"
    assert homologacao.alterar_estado("ABERTURA-X-001","SUSPENSA","Professor")["estado"]=="SUSPENSA"
    with pytest.raises(ValueError):
        homologacao.homologar_e_ativar({"regra_id":"X"},{"nota_ponderada_pct":84},"Professor")
