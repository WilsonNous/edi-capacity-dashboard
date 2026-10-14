from ednna.aprovacao_envio_edi import avaliar_autorizacao_envio
from ednna.preparador_falta_arquivo import preparar_solicitacao_falta_arquivo


def _minuta():
    return preparar_solicitacao_falta_arquivo({
        "player": "VR Benefício", "cliente": "Mambo", "convenio": "38722",
        "destinatario_oficial": "edi@example.org",
        "historico_sem_solicitacao": True,
        "arquivos": [{"nsa": "339", "data": "2026-08-16", "ausencia_confirmada": True}],
    })


def test_sem_aprovacao_nao_libera():
    resultado = avaliar_autorizacao_envio(_minuta())
    assert resultado["autorizacao_valida"] is False
    assert "aprovacao_humana_da_versao_atual" in resultado["pendencias"]
    assert resultado["execucao"] == "NOT_PERFORMED"


def test_aprovacao_exige_hash_exato_e_identidade():
    minuta = _minuta()
    digest = avaliar_autorizacao_envio(minuta)["digest_minuta"]
    assert avaliar_autorizacao_envio(minuta, {"aprovado": True, "digest": digest, "aprovador": "Operador EDI"})["autorizacao_valida"] is True
    alterada = dict(minuta, corpo=minuta["corpo"] + " outro texto")
    assert avaliar_autorizacao_envio(alterada, {"aprovado": True, "digest": digest, "aprovador": "Operador EDI"})["autorizacao_valida"] is False


def test_pendencias_impedem_liberacao_mesmo_com_aprovacao():
    minuta = _minuta()
    minuta["pendencias"] = ["confirmacao_ausencia_de_todos_os_arquivos"]
    digest = avaliar_autorizacao_envio(minuta)["digest_minuta"]
    resultado = avaliar_autorizacao_envio(minuta, {"aprovado": True, "digest": digest, "aprovador": "Operador EDI"})
    assert resultado["autorizacao_valida"] is False
    assert resultado["envio_realizado"] is False
