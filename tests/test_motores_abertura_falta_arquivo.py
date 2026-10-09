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


def test_abertura_homologada_nao_usa_workflow_de_inclusao(monkeypatch):
    import ednna.motor_aberturas as motor
    monkeypatch.setattr(motor, "estado_regra", lambda rid: {"estado": "ATIVA", "player": "BANRISUL"})
    monkeypatch.setattr(motor, "obter_autorizacao_motor", lambda rid: {"modo": "ASSISTIDA"})
    monkeypatch.setattr(motor, "listar_propostas", lambda: [{
        "regra_id": "ABERTURA-BANRISUL-001", "etapas": [
            {"responsavel": "CHECKPOINT_HUMANO", "titulo": "Acessar portal", "confianca": "ALTA"}],
        "evidencias": 3}])
    result = motor.avaliar_abertura("ABERTURA-BANRISUL-001")
    assert result["estado"] == "PREPARACAO_ASSISTIDA_SEM_ENVIO"
    assert result["executavel"] is False
    assert len(result["checkpoints_humanos"]) == 1


def test_falta_aprendida_sem_executor_externo(monkeypatch):
    import ednna.motor_falta_arquivo as motor
    monkeypatch.setattr(motor, "listar_regras_aprendidas", lambda: [{
        "regra_id": "FALTA-ARQUIVO-REDE-001", "estado": "ATIVA"}])
    result = motor.avaliar_regra_aprendida("FALTA-ARQUIVO-REDE-001", _demanda())
    assert result["estado"] == "TRATATIVA_APRENDIDA_AGUARDANDO_EXECUTOR"
    assert result["executavel"] is False


def test_abertura_sem_etapa_validada_nao_prepara(monkeypatch):
    import ednna.motor_aberturas as motor
    monkeypatch.setattr(motor, "estado_regra", lambda rid: {"estado": "ATIVA", "player": "SICREDI"})
    monkeypatch.setattr(motor, "obter_autorizacao_motor", lambda rid: {"modo": "ASSISTIDA"})
    monkeypatch.setattr(motor, "listar_propostas", lambda: [{
        "regra_id": "ABERTURA-SICREDI-001",
        "etapas": [{"codigo": "ENVIAR_EMAIL", "confianca": "A_VALIDAR"}]}])
    result = motor.avaliar_abertura("ABERTURA-SICREDI-001")
    assert result["estado"] == "AGUARDANDO_PROCEDIMENTO_APRENDIDO"
    assert result["executavel"] is False


def test_falta_arquivo_sem_confirmacao_nao_cobra(monkeypatch):
    import ednna.motor_falta_arquivo as motor
    monkeypatch.setattr(motor, "listar_regras_aprendidas", lambda: [{
        "regra_id": "FALTA-ARQUIVO-REDE-001", "estado": "ATIVA"}])
    result = motor.avaliar_regra_aprendida(
        "FALTA-ARQUIVO-REDE-001", _demanda(arquivo_recebido=None))
    assert result["estado"] == "AGUARDANDO_CONFIRMACAO_AUSENCIA"
    assert result["envio_externo_autorizado"] is False


def test_abertura_autorizada_automatica_nao_e_liberada(monkeypatch):
    import ednna.motor_aberturas as motor
    monkeypatch.setattr(motor, "estado_regra", lambda rid: {"estado": "ATIVA", "player": "SICREDI"})
    monkeypatch.setattr(motor, "obter_autorizacao_motor", lambda rid: {"modo": "AUTOMATICA"})
    monkeypatch.setattr(motor, "listar_propostas", lambda: [{
        "regra_id": "ABERTURA-SICREDI-001",
        "etapas": [{"codigo": "PREPARAR_SOLICITACAO", "confianca": "ALTA"}]}])
    result = motor.avaliar_abertura("ABERTURA-SICREDI-001")
    assert result["estado"] == "AUTOMATICA_NAO_SUPORTADA_ABERTURA"
    assert result["executavel"] is False
