from __future__ import annotations

"""Catálogo declarativo de workflows de inclusão da EDNNA (v3.28.24).

Separa conhecimento homologado, workflow e executor. Nenhuma função deste módulo
faz chamada externa. Os executores são capacidades declaradas e podem estar
pendentes de implementação/validação.
"""

WORKFLOW_EMAIL_ESTABELECIMENTO = "INCLUSAO_EMAIL_ESTABELECIMENTO"

WORKFLOWS = {
    "VALECARD": {"tipo_player":"ADQUIRENTE","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ALELO": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKET": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ONECARD": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "POLICARD": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TRUCKPAG": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VEROCHEQUE": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VR BENEFICIOS": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SODEXO/PLUXEE": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_EMAIL_REUSA_FALTA_ARQUIVO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","fonte_procedimento":"FALTA_ARQUIVO_SODEXO_PLUXEE","executor":"EMAIL_GRAPH","etapas":["EXTRAIR_ESTABELECIMENTO","RECUPERAR_CONTATOS_FALTA_ARQUIVO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "CIELO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_API","canal":"API","fonte_dados":"CHAMADO_ATUAL","executor":"CIELO_API","etapas":["EXTRAIR_DADOS","VALIDAR_DADOS","EXECUTAR_API","VALIDAR_RETORNO_API","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKETLOG": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ABERTURA_CHAMADO","canal":"CHAMADO","fonte_dados":"CHAMADO_ATUAL","executor":"TICKETLOG_CHAMADO","etapas":["EXTRAIR_ESTABELECIMENTO","ABRIR_CHAMADO_FORNECEDOR","REGISTRAR_PROTOCOLO","ACOMPANHAR_CHAMADO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "REDECARD": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_OPTIN_DEPOIS_AUTORIZACAO_CLIENTE","canal":"API+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"REDECARD_OPTIN_API+EMAIL_GRAPH","etapas":["VALIDAR_DADOS","EXECUTAR_OPTIN_API","VALIDAR_RETORNO_OPTIN","SOLICITAR_AUTORIZACAO_CLIENTE_EMAIL","AGUARDAR_AUTORIZACAO_CLIENTE","REGISTRAR_AUTORIZACAO_REDMINE","VALIDAR_CONCLUSAO"]},
    "GREENCARD": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_FORMULARIO_ASSINATURA_CLIENTE","canal":"DOCUMENTO+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"FORMULARIO_GREENCARD+EMAIL_GRAPH","etapas":["COLETAR_DADOS","GERAR_FORMULARIO_GREENCARD","ENVIAR_FORMULARIO_CLIENTE","AGUARDAR_ASSINATURA_CLIENTE","VALIDAR_FORMULARIO_ASSINADO","ENVIAR_GREENCARD","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "BANRISUL": {"tipo_player":"BANCO","workflow":"INCLUSAO_BANCO_VIA_AR","canal":"RELACIONAMENTO_BANCARIO","fonte_dados":"ABERTURA_RELACIONAMENTO","executor":"ASSISTIDO_BANCO","etapas":["LOCALIZAR_ABERTURA_RELACIONAMENTO","EXTRAIR_DADOS_BANCARIOS","EXTRAIR_GERENTE_CONTA","PREPARAR_SOLICITACAO","EXECUTAR_CANAL_HOMOLOGADO","ACOMPANHAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
}

# Capacidades que a aplicação já possui como infraestrutura. Isso NÃO significa
# que um workflow completo esteja liberado para execução automática.
EXECUTORES_IMPLEMENTADOS = {"EMAIL_GRAPH", "MONITOR_EMAIL", "REDMINE"}


def obter_workflow(player: str) -> dict:
    p = str(player or "").strip().upper()
    cfg = dict(WORKFLOWS.get(p) or {})
    if not cfg:
        return {"player": p, "workflow":"NAO_CLASSIFICADO", "canal":"NAO_IDENTIFICADO", "executor":"NAO_IMPLEMENTADO", "etapas":[], "prontidao":"SEM_WORKFLOW"}
    cfg["player"] = p
    executores = [x for x in str(cfg.get("executor") or "").split("+") if x]
    faltantes = [x for x in executores if x not in EXECUTORES_IMPLEMENTADOS]
    cfg["executores_faltantes"] = faltantes
    cfg["prontidao"] = "ASSISTIDA_DISPONIVEL" if not faltantes else "AGUARDANDO_EXECUTOR"
    return cfg


def planejar_workflow(player: str, dados: dict | None = None) -> dict:
    cfg = obter_workflow(player)
    return {**cfg, "dados_contexto": dados or {}, "pode_executar_automatico": False,
            "pode_operar_assistido": cfg.get("prontidao") == "ASSISTIDA_DISPONIVEL"}
