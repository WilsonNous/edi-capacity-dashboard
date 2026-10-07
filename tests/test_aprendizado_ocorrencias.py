from ednna.aprendizado_ocorrencias import classificar_ocorrencias

def test_falta_arquivo():
    row={"Assunto":"Cliente sem arquivo","Descrição":"Não recebemos o arquivo de movimento hoje"}
    assert "FALTA_ARQUIVO" in classificar_ocorrencias(row)

def test_falta_registro():
    row={"Assunto":"Venda não localizada","Descrição":"A transação não consta no arquivo"}
    assert "FALTA_REGISTRO" in classificar_ocorrencias(row)

def test_reprocessamento():
    row={"Assunto":"Solicitação de reprocessamento","Descrição":"Favor reprocessar o arquivo"}
    assert "REPROCESSAMENTO" in classificar_ocorrencias(row)

def test_sem_falso_positivo_basico():
    row={"Assunto":"Inclusão de EC","Descrição":"Solicito habilitação do estabelecimento"}
    assert classificar_ocorrencias(row) == []
