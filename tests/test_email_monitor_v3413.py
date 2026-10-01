from ednna.email_sender import _assunto_referencia_chamado


def test_referencia_chamado_formatos_operacionais():
    assert _assunto_referencia_chamado('RE: Processo #49226', 49226)
    assert _assunto_referencia_chamado('RE: SAFRAPAY - CN: 49226', 49226)
    assert _assunto_referencia_chamado('[49226] retorno cliente', 49226)
    assert not _assunto_referencia_chamado('RE: SAFRAPAY - CN: 49227', 49226)
