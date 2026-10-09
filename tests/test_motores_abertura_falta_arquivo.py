from ednna.motor_falta_arquivo import avaliar_falta_arquivo
from ednna.motor_aberturas import avaliar_abertura


def _demanda(**updates):
    base = dict(player="REDE", cliente="CLIENTE TESTE", arquivo_esperado="extrato",
                janela_vencida=True, dia_util_confirmado=True,
                entrega_esperada_confirmada=True, recepcao_verificada=True,
                arquivo_recebido=False)
    base.update(updates)
    return base


def test_falta_confirmada_nao_dispara_acao_externa():
    resultado = avaliar_falta_arquivo(_demanda())
    assert resultado["estado"] == "FALTA_CONFIRMADA"
    assert resultado["executavel"] is False
    assert resultado["envio_externo_autorizado"] is False


def test_feriado_ou_fora_calendario_nao_e_falta():
    assert avaliar_falta_arquivo(_demanda(dia_util_confirmado=False))["estado"] == "FORA_CALENDARIO"


def test_janela_nao_vencida_nao_e_falta():
    assert avaliar_falta_arquivo(_demanda(janela_vencida=False))["estado"] == "DENTRO_DA_JANELA"


def test_ausencia_sem_conferencia_nao_e_confirmada():
    assert avaliar_falta_arquivo(_demanda(recepcao_verificada=False))["estado"] == "AGUARDANDO_CONFERENCIA_RECEPCAO"


def test_abertura_nao_aceita_regra_de_inclusao():
    resultado = avaliar_abertura("INCLUSAO-REDE-001")
    assert resultado["estado"] == "OPERACAO_INCOMPATIVEL"
    assert resultado["executavel"] is False
