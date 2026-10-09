"""Caso 48311: sequência documental não equivale a envio Graph."""
from ednna.correlacao_historico import correlacionar_historico, mascarar_segredos


def _issue():
    return {
        "id": 48311,
        "status": {"name": "AGUARDANDO RETORNO ADQUIRENTE"},
        "journals": [
            {"id": 3, "created_on": "2026-09-11T15:47:00Z",
             "notes": "De: Wilson Martins <wilson.martins@netunna.com.br>\nAssunto: CN: 48311\nSolicitamos inclusão."},
            {"id": 4, "created_on": "2026-09-14T08:03:00Z",
             "notes": "De: Marina <marina@truckpag.com.br>\nAssunto: RE: CN: 48311\nSolicito dados FTP."},
            {"id": 5, "created_on": "2026-10-09T15:03:00Z",
             "notes": "De: Wilson Martins <wilson.martins@netunna.com.br>\nAssunto: RE: CN: 48311\nSenha: segredo-real\nDados encaminhados."},
        ],
    }


def test_journals_provam_historico_nao_envio():
    r = correlacionar_historico(_issue())
    assert r["total_journals_com_email"] == 3
    assert r["mensagens_graph_verificadas"] == 0
    assert r["envio_confirmado_graph"] is False
    assert r["estado"] == "HISTORICO_DOCUMENTAL_SEM_CONFIRMACAO_GRAPH"
    assert r["proxima_acao"].startswith("Acompanhar retorno")
    assert r["transferencia_automatica"] is False
    assert "segredo-real" not in str(r)


def test_graph_confirma_apenas_mensagem_correlacionada():
    mensagens = [
        {"id": "id1", "subject": "RE: CN: 48311", "sentDateTime": "2026-10-09T15:03:00Z", "_fonte_verificada": "MICROSOFT_GRAPH", "_pasta_origem": "sentitems"},
        {"id": "id2", "subject": "CN: 99999", "sentDateTime": "2026-10-09T15:03:00Z"},
    ]
    r = correlacionar_historico(_issue(), mensagens, caixas_consultadas=["wilson.martins@netunna.com.br"])
    assert r["mensagens_graph_verificadas"] == 1
    assert r["envio_confirmado_graph"] is True


def test_senha_mascarada():
    assert "abc123" not in mascarar_segredos("Senha: abc123")


def test_graph_nao_autenticado_nao_confirma_envio():
    r = correlacionar_historico(_issue(), [
        {"id": "forjado", "subject": "CN: 48311", "sentDateTime": "2026-10-09T15:03:00Z"}
    ])
    assert r["mensagens_graph_verificadas"] == 0
    assert r["envio_confirmado_graph"] is False


def test_graph_recebido_nao_comprova_envio():
    r = correlacionar_historico(_issue(), [
        {"id": "recebido", "subject": "CN: 48311", "receivedDateTime": "2026-10-09T15:03:00Z",
         "_fonte_verificada": "MICROSOFT_GRAPH", "_pasta_origem": "inbox"}
    ])
    assert r["mensagens_graph_verificadas"] == 1
    assert r["envio_confirmado_graph"] is False


def test_redacao_nao_remove_linha_seguinte():
    assert mascarar_segredos("Senha: segredo\nPasta: /RedeJP") == "Senha: [REDACTED]\nPasta: /RedeJP"
