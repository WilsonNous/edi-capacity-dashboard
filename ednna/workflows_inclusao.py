from __future__ import annotations

"""Workflows declarativos de inclusão da EDNNA.

v3.28.33 — o workflow deixa de ser apenas uma descrição e passa a declarar
pré-requisitos, estados e artefatos necessários para o motor operacional.
Nenhuma função deste módulo executa chamadas externas.
"""

from pathlib import Path
from typing import Any

WORKFLOW_EMAIL_ESTABELECIMENTO = "INCLUSAO_EMAIL_ESTABELECIMENTO"
GREEN_TEMPLATE = "docs/templates/TERMO_GREEN_BENEFICIOS.docx"

WORKFLOWS = {
    "VALECARD": {"tipo_player":"ADQUIRENTE","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ALELO": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ALELO_EMAIL_MATRIZ_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpj_matriz","estabelecimento"],"regra_dados":"Enviar obrigatoriamente CNPJ Matriz e estabelecimento/EC solicitado.","etapas":["EXTRAIR_CNPJ_MATRIZ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKET": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ONECARD": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "POLICARD": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TRUCKPAG": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VEROCHEQUE": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VR BENEFICIOS": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SODEXO/PLUXEE": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_EMAIL_REUSA_FALTA_ARQUIVO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","fonte_procedimento":"FALTA_ARQUIVO_SODEXO_PLUXEE","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","RECUPERAR_CONTATOS_FALTA_ARQUIVO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "CIELO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_API","canal":"API","fonte_dados":"CHAMADO_ATUAL","executor":"CIELO_API","etapas":["EXTRAIR_DADOS","VALIDAR_DADOS","EXECUTAR_API","VALIDAR_RETORNO_API","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKETLOG": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ABERTURA_CHAMADO","canal":"CHAMADO","fonte_dados":"CHAMADO_ATUAL","executor":"TICKETLOG_CHAMADO","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","ABRIR_CHAMADO_FORNECEDOR","REGISTRAR_PROTOCOLO","ACOMPANHAR_CHAMADO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "REDECARD": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_OPTIN_DEPOIS_AUTORIZACAO_CLIENTE","canal":"API+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"REDECARD_OPTIN_API+EMAIL_GRAPH","etapas":["VALIDAR_DADOS","EXECUTAR_OPTIN_API","VALIDAR_RETORNO_OPTIN","SOLICITAR_AUTORIZACAO_CLIENTE_EMAIL","AGUARDAR_AUTORIZACAO_CLIENTE","REGISTRAR_AUTORIZACAO_REDMINE","VALIDAR_CONCLUSAO"]},
    "GREENCARD": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_FORMULARIO_ASSINATURA_CLIENTE","canal":"DOCUMENTO+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"FORMULARIO_GREENCARD+EMAIL_GRAPH","artefato_template":GREEN_TEMPLATE,"campos_formulario":["razao_social","nome_fantasia","cnpj_matriz","endereco","bairro","cidade","estado","cep","representante_legal","rg","fone","email","relacao_cnpjs"],"documentos_retorno_obrigatorios":["termo_assinado","documento_identidade_representante"],"estados":["PREPARAR_TERMO","AGUARDANDO_CLIENTE","VALIDAR_DOCUMENTACAO","AGUARDANDO_GREENCARD","CONCLUIDO"],"etapas":["COLETAR_DADOS","PREENCHER_TERMO_GREENCARD","ENVIAR_TERMO_CLIENTE","AGUARDAR_ASSINATURA_CLIENTE","VALIDAR_TERMO_ASSINADO","VALIDAR_DOCUMENTO_IDENTIDADE","ENVIAR_GREENCARD","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "BANRISUL": {"tipo_player":"BANCO","workflow":"INCLUSAO_BANCO_VIA_AR","canal":"RELACIONAMENTO_BANCARIO","fonte_dados":"ABERTURA_RELACIONAMENTO","executor":"ASSISTIDO_BANCO","etapas":["LOCALIZAR_ABERTURA_RELACIONAMENTO","EXTRAIR_DADOS_BANCARIOS","EXTRAIR_GERENTE_CONTA","PREPARAR_SOLICITACAO","EXECUTAR_CANAL_HOMOLOGADO","ACOMPANHAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
}

# Infraestrutura realmente disponível hoje. Executores compostos só ficam
# prontos quando TODOS os seus componentes estiverem implementados.
EXECUTORES_IMPLEMENTADOS = {"EMAIL_GRAPH", "MONITOR_EMAIL", "REDMINE"}


def _valor_presente(dados: dict, campo: str) -> bool:
    aliases = {
        "estabelecimento": ("estabelecimento", "ec", "ecs", "convenio", "convenios"),
        "cnpj_matriz": ("cnpj_matriz", "matriz_cnpj"),
    }
    for chave in aliases.get(campo, (campo,)):
        valor = dados.get(chave)
        if isinstance(valor, (list, tuple, set)) and any(str(x or "").strip() for x in valor):
            return True
        if valor is not None and str(valor).strip():
            return True
    return False


def validar_dados_workflow(player: str, dados: dict | None = None) -> dict:
    """Valida apenas pré-requisitos declarativos, sem executar nada."""
    cfg = obter_workflow(player)
    dados = dict(dados or {})
    faltantes = [c for c in cfg.get("campos_obrigatorios", []) if not _valor_presente(dados, c)]
    artefato = cfg.get("artefato_template")
    artefato_ok = True
    if artefato:
        artefato_ok = (Path(__file__).resolve().parents[1] / artefato).exists()
    return {
        "valido": not faltantes and artefato_ok,
        "campos_faltantes": faltantes,
        "artefato_ok": artefato_ok,
        "artefato_template": artefato or "",
    }


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
    validacao = validar_dados_workflow(player, dados)
    pode_assistido = cfg.get("prontidao") == "ASSISTIDA_DISPONIVEL" and validacao["valido"]
    if not validacao["valido"]:
        estado = "AGUARDANDO_DADOS"
    elif cfg.get("prontidao") != "ASSISTIDA_DISPONIVEL":
        estado = "AGUARDANDO_EXECUTOR"
    else:
        estado = "PRONTO_OPERACAO_ASSISTIDA"
    return {
        **cfg,
        "dados_contexto": dados or {},
        "validacao": validacao,
        "estado_planejamento": estado,
        "pode_executar_automatico": False,
        "pode_operar_assistido": pode_assistido,
    }
