from ednna.aprovacao_envio_edi import avaliar_autorizacao_envio
from ednna.executor_envio_eddy import executar_envio_assistido
from ednna.preparador_falta_arquivo import preparar_solicitacao_falta_arquivo


def _dados():
    minuta = preparar_solicitacao_falta_arquivo({
        "player": "VR Benefício", "cliente": "Mambo", "convenio": "38722",
        "destinatario_oficial": "edi@example.org", "historico_sem_solicitacao": True,
        "arquivos": [{"nsa": "339", "data": "2026-08-16", "ausencia_confirmada": True}],
    })
    digest = avaliar_autorizacao_envio(minuta)["digest_minuta"]
    return minuta, {"aprovado": True, "digest": digest, "aprovador": "Operador EDI"}


def test_padrao_simulacao_nao_chama_graph(tmp_path):
    minuta, aprovacao = _dados()
    def proibido(**kwargs):
        raise AssertionError("Graph não deveria ser chamado")
    resultado = executar_envio_assistido(chamado_id=47851, minuta=minuta, aprovacao=aprovacao,
        remetente="edi@example.org", db_path=str(tmp_path / "envios.db"), enviar=proibido)
    assert resultado["estado"] == "SIMULACAO"
    assert not (tmp_path / "envios.db").exists()


def test_aprovacao_invalida_bloqueia(tmp_path):
    minuta, aprovacao = _dados()
    aprovacao["digest"] = "invalido"
    resultado = executar_envio_assistido(chamado_id=47851, minuta=minuta, aprovacao=aprovacao,
        remetente="edi@example.org", db_path=str(tmp_path / "envios.db"))
    assert resultado["estado"] == "BLOQUEADO"


def test_graph_202_e_repeticao_nao_duplica(tmp_path, monkeypatch):
    monkeypatch.setenv("EDDY_GRAPH_SEND_ENABLED", "true")
    minuta, aprovacao = _dados()
    chamadas = []
    def fake_send(**kwargs):
        chamadas.append(kwargs)
        return {"ok": True, "status_code": 202, "message_id": "graph-id"}
    args = dict(chamado_id=47851, minuta=minuta, aprovacao=aprovacao,
                remetente="edi@example.org", db_path=str(tmp_path / "envios.db"),
                habilitar_envio=True, enviar=fake_send)
    primeiro = executar_envio_assistido(**args)
    segundo = executar_envio_assistido(**args)
    assert primeiro["estado"] == "ACEITO_GRAPH"
    assert segundo["estado"] == "JA_REGISTRADO"
    assert len(chamadas) == 1


def test_erro_ambíguo_nao_gera_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("EDDY_GRAPH_SEND_ENABLED", "true")
    minuta, aprovacao = _dados()
    chamadas = []
    def fake_send(**kwargs):
        chamadas.append(1)
        raise TimeoutError("resposta perdida")
    args = dict(chamado_id=47851, minuta=minuta, aprovacao=aprovacao,
                remetente="edi@example.org", db_path=str(tmp_path / "envios.db"),
                habilitar_envio=True, enviar=fake_send)
    primeiro = executar_envio_assistido(**args)
    segundo = executar_envio_assistido(**args)
    assert primeiro["estado"] == "INDETERMINADO"
    assert primeiro["requer_conciliacao"] is True
    assert segundo["estado"] == "JA_REGISTRADO"
    assert len(chamadas) == 1


def test_alterar_minuta_nao_permite_segundo_envio(tmp_path, monkeypatch):
    monkeypatch.setenv("EDDY_GRAPH_SEND_ENABLED", "true")
    minuta, aprovacao = _dados()
    chamadas = []
    def fake_send(**kwargs):
        chamadas.append(1)
        return {"ok": True, "status_code": 202, "message_id": "id"}
    args = dict(chamado_id=47851, remetente="edi@example.org",
                db_path=str(tmp_path / "envios.db"), habilitar_envio=True, enviar=fake_send)
    primeiro = executar_envio_assistido(minuta=minuta, aprovacao=aprovacao, **args)
    assert primeiro["estado"] == "ACEITO_GRAPH"
    alterada = dict(minuta, corpo=minuta["corpo"] + " Ajuste posterior")
    novo_digest = avaliar_autorizacao_envio(alterada)["digest_minuta"]
    segunda = executar_envio_assistido(minuta=alterada, aprovacao={
        "aprovado": True, "digest": novo_digest, "aprovador": "Operador EDI"
    }, **args)
    assert segunda["estado"] == "JA_REGISTRADO"
    assert segunda["minuta_alterada"] is True
    assert len(chamadas) == 1
