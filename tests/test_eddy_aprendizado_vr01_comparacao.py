from ednna.eddy_aprendizado_vr01_comparacao import comparar_aprendizado_vr01

def test_no_evidence_never_homologates():
    for player in ("GREENCARD","SAFRAPAY","ITAU"):
        result=comparar_aprendizado_vr01(player,None,None,None)
        assert result["estado"]=="APRENDIZADO_A_CONCILIAR"
        assert not result["homologacao_automatica"]
        assert not result["execucao_externa_liberada"]
        assert result["pendencias_execucao_vr01"]

def test_historical_reference_and_human_review_are_required():
    aprendido={"regra_id":"INCLUSAO-SAFRAPAY-001","player":"SAFRAPAY",
               "operacao":"INCLUSAO","fontes":{"chamado_historico":45956}}
    revisao={"estado":"HOMOLOGADA","revisado_por":"OPERADOR","homologado_em":"2026-11-09"}
    result=comparar_aprendizado_vr01("SAFRAPAY",aprendido,revisao,{"modo":"AUTOMATICA"})
    assert result["estado"]=="APTA_A_REVISAO_DOCUMENTAL"
    assert not result["execucao_externa_liberada"]
    assert result["autorizacao_atual"]=="AUTOMATICA"
    aprendido["fontes"]["chamado_historico"]=123
    assert "REFERENCIA_HISTORICA_NAO_CONCILIADA" in comparar_aprendizado_vr01("SAFRAPAY",aprendido,revisao,None)["pendencias_aprendizado"]
