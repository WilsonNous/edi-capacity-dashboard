from ednna.eddy_vr01_email_templates import (
    assunto_vr01, mensagem_autorizacao, mensagem_followup,
)
from ednna.eddy_vr01_operation_readiness import OPERATION_REQUIREMENTS


def test_assunto_rastreavel():
    assert assunto_vr01(50318) == (
        "[VR | Inclusão de Estabelecimento | SUPERMERCADOS MAMBO | CN: 50318]"
    )


def test_template_autorizacao_html():
    html = mensagem_autorizacao(50318)
    for trecho in ("Financeiro", "Conciliação", "NETUNNA",
                   "71.676.316/0033-23", "#50318", "Equipe EDI | NETUNNA"):
        assert trecho in html
    assert html.startswith("<!doctype html>")


def test_followup_cobranca_e_assinatura():
    html = mensagem_followup(50318)
    assert "autorização já foi realizada" in html
    assert "Equipe EDI | NETUNNA" in html
    assert "#50318" in html


def test_escape_dados_externos():
    assert "&lt;script&gt;" in mensagem_autorizacao(50318, cliente="<script>")
    assert "<script>" not in mensagem_autorizacao(50318, cliente="<script>")


def test_monitoramento_nao_confunde_transicao_com_homologacao():
    assert OPERATION_REQUIREMENTS["MONITORAR_CLIENTE"] == ()
    assert "EDDY_VR01_REPLY_RECONCILIATION_READY" in OPERATION_REQUIREMENTS["CONFIRMACAO_VALIDADA"]
    assert "EDDY_VR01_REPLY_RECONCILIATION_READY" in OPERATION_REQUIREMENTS["FOLLOWUP_CLIENTE"]
