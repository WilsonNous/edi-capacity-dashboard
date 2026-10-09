"""Regressões dos ciclos seguros de abertura e falta de arquivo."""
from unittest.mock import patch

from ednna.observabilidade_motores import executar_ciclo


def test_ciclo_nao_executa_acoes_externas():
    with patch("ednna.motor_aberturas.avaliar_aberturas_homologadas", return_value=[
        {"regra_id": "ABERTURA-SICREDI-001", "estado": "AGUARDANDO_AUTORIZACAO", "executavel": False}
    ]), patch("ednna.motor_falta_arquivo.listar_regras_aprendidas", return_value=[
        {"regra_id": "FALTA-ARQUIVO-EXEMPLO", "estado": "ATIVA", "executavel": False}
    ]):
        resultado = executar_ciclo()
    assert resultado["aberturas"] == 1
    assert resultado["falta_arquivo_regras"] == 1
    assert resultado["falta_arquivo_demandas_confirmadas"] == 0
    assert resultado["envios_externos"] == 0


def test_ciclo_sem_regras():
    with patch("ednna.motor_aberturas.avaliar_aberturas_homologadas", return_value=[]), patch(
        "ednna.motor_falta_arquivo.listar_regras_aprendidas", return_value=[]
    ):
        resultado = executar_ciclo()
    assert resultado["aberturas"] == 0
    assert resultado["falta_arquivo_regras"] == 0
