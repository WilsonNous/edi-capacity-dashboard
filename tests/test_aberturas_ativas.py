from ednna.aberturas_ativas import (
    DESTINO_EDNNA,
    DESTINO_EXTERNO,
    DESTINO_HUMANO,
    decidir_destino_retorno,
    plano_assistido,
)


def test_retorno_prioriza_checkpoint_humano():
    assert decidir_destino_retorno(
        exige_acao_humana=True,
        depende_evento_externo=True,
        ednna_pode_continuar=True,
    ) == DESTINO_HUMANO


def test_retorno_pode_aguardar_condicao_externa():
    assert decidir_destino_retorno(depende_evento_externo=True) == DESTINO_EXTERNO


def test_retorno_continua_com_ednna_quando_seguro():
    assert decidir_destino_retorno(ednna_pode_continuar=True) == DESTINO_EDNNA


def test_regra_nao_homologada_nao_executa(monkeypatch):
    monkeypatch.setattr("ednna.aberturas_ativas.estado_regra", lambda _rid: None)
    regra = {
        "regra_id": "ABERTURA-GREENCARD-001",
        "player": "GREENCARD",
        "etapas": [
            {"codigo": "PREPARAR_SOLICITACAO", "responsavel": "EDNNA"},
            {"codigo": "ASSINATURA_DOCUMENTO", "responsavel": "CHECKPOINT_HUMANO"},
        ],
    }
    plano = plano_assistido(regra)
    assert plano["autorizada"] is False
    assert plano["modo"] == "SOMENTE_APRENDIZADO"
    assert plano["etapas"][0]["destino_operacional"] == DESTINO_EDNNA
    assert plano["etapas"][1]["destino_operacional"] == DESTINO_HUMANO


def test_regra_em_observacao_pratica_assistida(monkeypatch):
    monkeypatch.setattr(
        "ednna.aberturas_ativas.estado_regra",
        lambda _rid: {"estado": "EM_OBSERVACAO"},
    )
    plano = plano_assistido({"regra_id": "ABERTURA-TICKET-001", "player": "TICKET"})
    assert plano["autorizada"] is True
    assert plano["modo"] == "ATIVO_ASSISTIDO"
