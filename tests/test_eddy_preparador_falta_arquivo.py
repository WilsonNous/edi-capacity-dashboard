from ednna.preparador_falta_arquivo import preparar_solicitacao_falta_arquivo


def test_47851_consolida_nsa_e_preserva_pendencia_355():
    resultado = preparar_solicitacao_falta_arquivo({
        "player": "VR Benefício", "cliente": "Supermercados Mambo",
        "convenio": "38722", "chamados": [47851, 47812],
        "historico_sem_solicitacao": True,
        "arquivos": [
            {"nsa": "339", "data": "2026-08-16", "ausencia_confirmada": True},
            {"nsa": "355", "data": "2026-08-30", "ausencia_confirmada": False},
        ],
    })
    assert resultado["corpo"].count("NSA 339") == 1
    assert resultado["corpo"].count("NSA 355") == 1
    assert "TEIACARD" not in resultado["corpo"]
    assert "Equipe EDI | Netunna" in resultado["corpo"]
    assert "preparada pelo EDDY" in resultado["corpo"]
    assert "#47851" in resultado["corpo"]
    assert "destinatario_oficial" in resultado["pendencias"]
    assert "confirmacao_ausencia_de_todos_os_arquivos" in resultado["pendencias"]
    assert resultado["pronto_para_aprovacao"] is False
    assert resultado["envio_realizado"] is False
    assert resultado["redmine_atualizado"] is False


def test_deduplicacao_e_controle_aprovacao():
    resultado = preparar_solicitacao_falta_arquivo({
        "player": "VR Benefício", "cliente": "Mambo", "convenio": "38722",
        "destinatario_oficial": "canal@example.org", "historico_sem_solicitacao": True,
        "arquivos": [
            {"nsa": "339", "data": "2026-08-16", "ausencia_confirmada": True},
            {"nsa": "339", "data": "2026-08-16", "ausencia_confirmada": True},
        ],
    })
    assert len(resultado["arquivos"]) == 1
    assert resultado["pronto_para_aprovacao"] is True
    assert resultado["aprovacao_humana_necessaria"] is True
    assert resultado["envio_realizado"] is False
