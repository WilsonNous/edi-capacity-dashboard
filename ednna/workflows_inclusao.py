from __future__ import annotations

"""Workflows declarativos de inclusão da EDNNA.

v3.28.33 — o workflow deixa de ser apenas uma descrição e passa a declarar
pré-requisitos, estados e artefatos necessários para o motor operacional.
Nenhuma função deste módulo executa chamadas externas.
"""

from pathlib import Path
from typing import Any

WORKFLOW_EMAIL_ESTABELECIMENTO = "INCLUSAO_EMAIL_ESTABELECIMENTO"
WORKFLOW_VR_PORTAL_CLIENTE = "INCLUSAO_VR_PORTAL_CLIENTE"
GREEN_TEMPLATE = "docs/templates/TERMO_GREEN_BENEFICIOS.docx"

WORKFLOWS = {
    "VALECARD": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_VALECARD_CNPJ_EC","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"destinatario_padrao":"atendimentograndesredes@valecard.com.br","regra_dados":"Enviar obrigatoriamente CNPJ e EC do estabelecimento. Após protocolo, acompanhar o prazo informado; após confirmação de inclusão, aguardar os próximos arquivos e validar a presença da filial.","etapas":["EXTRAIR_CNPJ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","INTERPRETAR_PROTOCOLO","INTERPRETAR_CONFIRMACAO_INCLUSAO","AGUARDAR_ARQUIVOS","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ALELO": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ALELO_EMAIL_MATRIZ_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpj_matriz","estabelecimento"],"regra_dados":"Enviar obrigatoriamente CNPJ Matriz e estabelecimento/EC solicitado.","etapas":["EXTRAIR_CNPJ_MATRIZ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKET": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_TICKET_MULTI_EC","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"regra_dados":"Enviar todos os ECs/estabelecimentos encontrados no chamado, nunca apenas o primeiro. Incluir também CNPJ e cliente/razão social quando disponíveis.","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ONECARD": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "POLICARD": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_POLICARD_CNPJ_EC","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"destinatario_padrao":"grandesredesup@upbrasil.com","regra_dados":"Enviar obrigatoriamente CNPJ e EC do estabelecimento. Após o envio, acompanhar retorno da adquirente e não repetir a primeira solicitação se o chamado já estiver em andamento/aguardando retorno ou possuir atuação anterior.","etapas":["EXTRAIR_CNPJ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TRUCKPAG": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VEROCHEQUE": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_VEROCHEQUE_PADRAO_CONCILIACAO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs"],"destinatario_padrao":"conciliacao@verocard.com.br","layout_padrao":"1.7D","periodicidade_padrao":"Diário","diretorio_exportacao_padrao":"Servidor SFTP Verocard (Host: sftp.verocard.com.br / Porta: 20022), na pasta vinculada ao usuário netunna","responsavel_conciliadora_padrao":"edi@netunna.com.br","exige_autorizacao_estabelecimento":True,"regra_dados":"Enviar Razão Social, CNPJ, layout, periodicidade, diretório de exportação, e-mail do responsável do estabelecimento e e-mail da conciliadora. É obrigatória carta assinada ou resposta por e-mail do responsável do estabelecimento autorizando a NETUNNA a receber os arquivos.","etapas":["EXTRAIR_RAZAO_SOCIAL","EXTRAIR_CNPJ","IDENTIFICAR_RESPONSAVEL_ESTABELECIMENTO","VALIDAR_AUTORIZACAO_CLIENTE","PREPARAR_EMAIL_PADRAO_VEROCHEQUE","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","INTERPRETAR_DSNAME","AGUARDAR_ARQUIVOS","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VR BENEFICIOS": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_VR_PORTAL_CLIENTE,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs"],"responsavel_habilitacao":"CLIENTE","destinatario_tipo":"CLIENTE","retorno_esperado_de":"CLIENTE","status_pos_envio":"Aguardando Retorno Cliente","sla_primeiro_followup_horas":48,"regra_dados":"O cliente habilita a NETUNNA no Portal VR em Financeiro > Conciliação. A EDNNA apenas orienta, acompanha o retorno e monitora a chegada dos primeiros arquivos.","etapas":["EXTRAIR_CNPJS","IDENTIFICAR_CONTATOS_CLIENTE","PREPARAR_ORIENTACAO_PORTAL_VR","ENVIAR_ORIENTACAO_CLIENTE","AGUARDAR_RETORNO_CLIENTE","FOLLOWUP_CLIENTE_SE_NECESSARIO","INTERPRETAR_RETORNO_CLIENTE","VALIDAR_INICIO_OPERACAO","AGUARDAR_PRIMEIROS_ARQUIVOS","VALIDAR_ARQUIVOS_RECEBIDOS","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SENFF": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_EMAIL_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"regra_dados":"Solicitar inclusão do(s) estabelecimento(s)/EC(s) usando o destinatário confirmado na homologação. Nunca agir novamente se houver atuação anterior; após envio, registrar evidência no Redmine e acompanhar o retorno.","etapas":["EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SODEXO/PLUXEE": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_EMAIL_REUSA_FALTA_ARQUIVO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","fonte_procedimento":"FALTA_ARQUIVO_SODEXO_PLUXEE","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","RECUPERAR_CONTATOS_FALTA_ARQUIVO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "CIELO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_API","canal":"API","fonte_dados":"CHAMADO_ATUAL","executor":"CIELO_API","etapas":["EXTRAIR_DADOS","VALIDAR_DADOS","EXECUTAR_API","VALIDAR_RETORNO_API","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKETLOG": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ABERTURA_CHAMADO","canal":"CHAMADO","fonte_dados":"CHAMADO_ATUAL","executor":"TICKETLOG_CHAMADO","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","ABRIR_CHAMADO_FORNECEDOR","REGISTRAR_PROTOCOLO","ACOMPANHAR_CHAMADO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "REDECARD": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_OPTIN_DEPOIS_AUTORIZACAO_CLIENTE","canal":"API+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"REDECARD_OPTIN_API+EMAIL_GRAPH","etapas":["VALIDAR_DADOS","EXECUTAR_OPTIN_API","VALIDAR_RETORNO_OPTIN","SOLICITAR_AUTORIZACAO_CLIENTE_EMAIL","AGUARDAR_AUTORIZACAO_CLIENTE","REGISTRAR_AUTORIZACAO_REDMINE","VALIDAR_CONCLUSAO"]},
    "GREENCARD": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_FORMULARIO_ASSINATURA_CLIENTE","canal":"DOCUMENTO+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"FORMULARIO_GREENCARD+EMAIL_GRAPH","artefato_template":GREEN_TEMPLATE,"campos_formulario":["razao_social","nome_fantasia","cnpj_matriz","endereco","bairro","cidade","estado","cep","representante_legal","rg","fone","email","relacao_cnpjs"],"documentos_retorno_obrigatorios":["termo_assinado","documento_identidade_representante"],"estados":["PREPARAR_TERMO","AGUARDANDO_CLIENTE","VALIDAR_DOCUMENTACAO","AGUARDANDO_GREENCARD","CONCLUIDO"],"etapas":["COLETAR_DADOS","PREENCHER_TERMO_GREENCARD","ENVIAR_TERMO_CLIENTE","AGUARDAR_ASSINATURA_CLIENTE","VALIDAR_TERMO_ASSINADO","VALIDAR_DOCUMENTO_IDENTIDADE","ENVIAR_GREENCARD","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VERO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_EMAIL_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"regra_dados":"Procedimento homologado por e-mail. Usar o destinatário confirmado na homologação, informar cliente e estabelecimento/EC do chamado, registrar o e-mail integral no Redmine e acompanhar o retorno.","etapas":["EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "WIZEO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_EMAIL_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"regra_dados":"Procedimento homologado por e-mail. Usar o destinatário confirmado na homologação, informar cliente e estabelecimento/EC do chamado, registrar o e-mail integral no Redmine e acompanhar o retorno.","etapas":["EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "BANRISUL": {"tipo_player":"BANCO","workflow":"INCLUSAO_BANCO_VIA_AR","canal":"RELACIONAMENTO_BANCARIO","fonte_dados":"ABERTURA_RELACIONAMENTO","executor":"ASSISTIDO_BANCO","etapas":["LOCALIZAR_ABERTURA_RELACIONAMENTO","EXTRAIR_DADOS_BANCARIOS","EXTRAIR_GERENTE_CONTA","PREPARAR_SOLICITACAO","EXECUTAR_CANAL_HOMOLOGADO","ACOMPANHAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
}

# Infraestrutura realmente disponível hoje. Executores compostos só ficam
# prontos quando TODOS os seus componentes estiverem implementados.
EXECUTORES_IMPLEMENTADOS = {"EMAIL_GRAPH", "MONITOR_EMAIL", "REDMINE"}


def _valor_presente(dados: dict, campo: str) -> bool:
    aliases = {
        "estabelecimento": ("estabelecimento", "ec", "ecs", "convenio", "convenios"),
        "cnpj_matriz": ("cnpj_matriz", "matriz_cnpj"),
        "cnpjs": ("cnpjs", "cnpj", "relacao_cnpjs"),
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
    # v3.28.35 — workflows definidos pela operação têm autoridade humana confirmada.
    # O histórico enriquece a regra, mas não bloqueia sua revisão/homologação.
    cfg.setdefault("fonte_autoridade", "ORIENTACAO_OPERACIONAL")
    cfg.setdefault("procedimento_confirmado", True)
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
