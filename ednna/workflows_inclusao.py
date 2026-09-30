from __future__ import annotations

"""Workflows declarativos de inclusão da EDNNA.

v3.28.33 — o workflow deixa de ser apenas uma descrição e passa a declarar
pré-requisitos, estados e artefatos necessários para o motor operacional.
Nenhuma função deste módulo executa chamadas externas.
"""

from pathlib import Path
from typing import Any
import json

from ednna.armazenamento import conectar, agora_brasil_iso

WORKFLOW_EMAIL_ESTABELECIMENTO = "INCLUSAO_EMAIL_ESTABELECIMENTO"
WORKFLOW_VR_PORTAL_CLIENTE = "INCLUSAO_VR_PORTAL_CLIENTE"
GREEN_TEMPLATE = "docs/templates/TERMO_GREEN_BENEFICIOS.docx"

WORKFLOWS = {
    "VALECARD": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_VALECARD_CNPJ_EC","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"destinatario_padrao":"atendimentograndesredes@valecard.com.br","regra_dados":"Enviar obrigatoriamente CNPJ e EC do estabelecimento. Após protocolo, acompanhar o prazo informado; após confirmação de inclusão, aguardar os próximos arquivos e validar a presença da filial.","etapas":["EXTRAIR_CNPJ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","INTERPRETAR_PROTOCOLO","INTERPRETAR_CONFIRMACAO_INCLUSAO","AGUARDAR_ARQUIVOS","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ALELO": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ALELO_EMAIL_MATRIZ_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpj_matriz","estabelecimento"],"regra_dados":"Enviar obrigatoriamente CNPJ Matriz e estabelecimento/EC solicitado.","etapas":["EXTRAIR_CNPJ_MATRIZ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKET": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_TICKET_MULTI_EC","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"regra_dados":"Enviar todos os ECs/estabelecimentos encontrados no chamado, nunca apenas o primeiro. Incluir também CNPJ e cliente/razão social quando disponíveis.","etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "ONECARD": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "POLICARD": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_POLICARD_CNPJ_EC","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"destinatario_padrao":"conciliacao@upbrasil.com","politica_destinatarios":"POLICARD_CONCILIACAO_UPBRASIL_2026_09_14","regra_dados":"Demandas de conciliação devem ser enviadas exclusivamente para conciliacao@upbrasil.com; não copiar grandesredesup@upbrasil.com nem outros endereços @upbrasil.com. Enviar obrigatoriamente CNPJ e EC do estabelecimento. Após o envio, acompanhar retorno da adquirente e não repetir a primeira solicitação se o chamado já estiver em andamento/aguardando retorno ou possuir atuação anterior.","etapas":["EXTRAIR_CNPJ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TRUCKPAG": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_EMAIL_ESTABELECIMENTO,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VEROCHEQUE": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_VEROCHEQUE_PADRAO_CONCILIACAO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs"],"destinatario_padrao":"conciliacao@verocard.com.br","layout_padrao":"1.7D","periodicidade_padrao":"Diário","diretorio_exportacao_padrao":"Servidor SFTP Verocard (Host: sftp.verocard.com.br / Porta: 20022), na pasta vinculada ao usuário netunna","responsavel_conciliadora_padrao":"edi@netunna.com.br","exige_autorizacao_estabelecimento":True,"regra_dados":"Enviar Razão Social, CNPJ, layout, periodicidade, diretório de exportação, e-mail do responsável do estabelecimento e e-mail da conciliadora. É obrigatória carta assinada ou resposta por e-mail do responsável do estabelecimento autorizando a NETUNNA a receber os arquivos.","etapas":["EXTRAIR_RAZAO_SOCIAL","EXTRAIR_CNPJ","IDENTIFICAR_RESPONSAVEL_ESTABELECIMENTO","VALIDAR_AUTORIZACAO_CLIENTE","PREPARAR_EMAIL_PADRAO_VEROCHEQUE","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","INTERPRETAR_DSNAME","AGUARDAR_ARQUIVOS","REGISTRAR_EVIDENCIA_REDMINE"]},
    "VR BENEFICIOS": {"tipo_player":"BENEFICIO","workflow":WORKFLOW_VR_PORTAL_CLIENTE,"canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs"],"responsavel_habilitacao":"CLIENTE","destinatario_tipo":"CLIENTE","retorno_esperado_de":"CLIENTE","status_pos_envio":"Aguardando Retorno Cliente","sla_primeiro_followup_horas":48,"regra_dados":"O cliente habilita a NETUNNA no Portal VR em Financeiro > Conciliação. A EDNNA apenas orienta, acompanha o retorno e monitora a chegada dos primeiros arquivos.","etapas":["EXTRAIR_CNPJS","IDENTIFICAR_CONTATOS_CLIENTE","PREPARAR_ORIENTACAO_PORTAL_VR","ENVIAR_ORIENTACAO_CLIENTE","AGUARDAR_RETORNO_CLIENTE","FOLLOWUP_CLIENTE_SE_NECESSARIO","INTERPRETAR_RETORNO_CLIENTE","VALIDAR_INICIO_OPERACAO","AGUARDAR_PRIMEIROS_ARQUIVOS","VALIDAR_ARQUIVOS_RECEBIDOS","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SENFF": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_EMAIL_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"regra_dados":"Solicitar inclusão do(s) estabelecimento(s)/EC(s) usando o destinatário confirmado na homologação. Nunca agir novamente se houver atuação anterior; após envio, registrar evidência no Redmine e acompanhar o retorno.","etapas":["EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SODEXO/PLUXEE": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_EMAIL_REUSA_FALTA_ARQUIVO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","fonte_procedimento":"FALTA_ARQUIVO_SODEXO_PLUXEE","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","RECUPERAR_CONTATOS_FALTA_ARQUIVO","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "CIELO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_API","canal":"API","fonte_dados":"CHAMADO_ATUAL","executor":"CIELO_API","etapas":["EXTRAIR_DADOS","VALIDAR_DADOS","EXECUTAR_API","VALIDAR_RETORNO_API","REGISTRAR_EVIDENCIA_REDMINE"]},
    "TICKETLOG": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_ABERTURA_CHAMADO","canal":"CHAMADO","fonte_dados":"CHAMADO_ATUAL","executor":"TICKETLOG_CHAMADO","campos_obrigatorios":["estabelecimento"],"etapas":["EXTRAIR_ESTABELECIMENTO","ABRIR_CHAMADO_FORNECEDOR","REGISTRAR_PROTOCOLO","ACOMPANHAR_CHAMADO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "REDECARD": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_OPTIN_DEPOIS_AUTORIZACAO_CLIENTE","canal":"API+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"REDECARD_OPTIN_API+EMAIL_GRAPH","etapas":["VALIDAR_DADOS","EXECUTAR_OPTIN_API","VALIDAR_RETORNO_OPTIN","SOLICITAR_AUTORIZACAO_CLIENTE_EMAIL","AGUARDAR_AUTORIZACAO_CLIENTE","REGISTRAR_AUTORIZACAO_REDMINE","VALIDAR_CONCLUSAO"]},
    # v3.32.4 — inclusão simples GREENCARD homologada pelo caso histórico #46968.
    # Para INCLUSAO de EC não há formulário prévio: a solicitação vai diretamente
    # ao Suporte Credenciado. O Blueprint fornece os contatos do cliente apenas
    # para CC. Abertura de relacionamento continua sendo um fluxo distinto e não
    # deve herdar automaticamente este procedimento.
    "GREENCARD": {"tipo_player":"BENEFICIO","workflow":"INCLUSAO_GREENCARD_EMAIL_DIRETO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["cnpjs","estabelecimento"],"destinatario_padrao":"suporte.credenciado@grupogreencard.com.br","status_pos_envio":"Aguardando Retorno Adquirente","sla_primeiro_followup_horas":48,"regra_dados":"Na inclusão de estabelecimento, enviar diretamente ao Suporte Credenciado Greencard solicitando inclusão no tráfego EDI e disponibilidade dos arquivos na CAIXA POSTAL NETUNNA junto à Greencard. Informar cliente, CNPJ e EC solicitado. Contatos do cliente vindos do Blueprint entram em CC. Preservar separadamente o EC solicitado e eventual EC Greencard confirmado no retorno.","estados":["PRONTO_ENVIO_GREENCARD","AGUARDANDO_GREENCARD","AGUARDANDO_ARQUIVOS","VALIDAR_ARQUIVOS","CONCLUIDO"],"etapas":["EXTRAIR_CNPJ","EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","IDENTIFICAR_CONTATOS_CLIENTE_CC","ENVIAR_GREENCARD","AGUARDAR_RETORNO_ADQUIRENTE","INTERPRETAR_EC_GREENCARD_CONFIRMADO","AGUARDAR_ARQUIVOS","VALIDAR_MOVIMENTACAO_OU_AUSENCIA_VENDAS","REGISTRAR_MOVIMENTACAO_BP","CONCLUIR"]},
    "ROTACARD": {"tipo_player":"BENEFICIO","workflow":"ABERTURA_OU_INCLUSAO_FORMULARIO_ROTACARD","canal":"DOCUMENTO+EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"FORMULARIO_ROTACARD+EMAIL_GRAPH","artefato_template":GREEN_TEMPLATE,"campos_formulario":["razao_social","nome_fantasia","cnpj_matriz","endereco","bairro","cidade","estado","cep","representante_legal","rg","fone","email","relacao_cnpjs"],"documentos_retorno_obrigatorios":["termo_assinado","documento_identidade_representante"],"estados":["PREPARAR_TERMO","AGUARDANDO_CLIENTE","VALIDAR_DOCUMENTACAO","AGUARDANDO_ROTACARD","AGUARDANDO_ARQUIVOS","VALIDAR_ARQUIVOS","ABRIR_IMPLANTACAO","CONCLUIDO"],"etapas":["COLETAR_DADOS_BLUEPRINT","PREENCHER_TERMO_ROTACARD","ENVIAR_TERMO_CLIENTE","AGUARDAR_ASSINATURA_CLIENTE","VALIDAR_TERMO_ASSINADO","VALIDAR_DOCUMENTO_IDENTIDADE","ENVIAR_ROTACARD","MONITORAR_RETORNO","AGUARDAR_ARQUIVOS_FTP","VALIDAR_ECS_RECEBIDOS","ABRIR_IMPLANTACAO_SE_ABERTURA","REGISTRAR_MOVIMENTACAO_BP","CONCLUIR"]},
    "VERO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_EMAIL_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"regra_dados":"Procedimento homologado por e-mail. Usar o destinatário confirmado na homologação, informar cliente e estabelecimento/EC do chamado, registrar o e-mail integral no Redmine e acompanhar o retorno.","etapas":["EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "WIZEO": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_EMAIL_ESTABELECIMENTO","canal":"EMAIL","fonte_dados":"CHAMADO_ATUAL","executor":"EMAIL_GRAPH","campos_obrigatorios":["estabelecimento"],"regra_dados":"Procedimento homologado por e-mail. Usar o destinatário confirmado na homologação, informar cliente e estabelecimento/EC do chamado, registrar o e-mail integral no Redmine e acompanhar o retorno.","etapas":["EXTRAIR_ESTABELECIMENTO","VALIDAR_DADOS","PREPARAR_EMAIL_INCLUSAO","ENVIAR_EMAIL","AGUARDAR_RETORNO_ADQUIRENTE","MONITORAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
    "SAFRAPAY": {"tipo_player":"ADQUIRENTE","workflow":"INCLUSAO_SAFRAPAY_SUPPLY_MIDIA","canal":"DOCUMENTO+EMAIL+CHECKPOINT_HUMANO","fonte_dados":"CHAMADO_ATUAL+BLUEPRINT","executor":"EMAIL_GRAPH+INTERVENCAO_HUMANA","campos_obrigatorios":["cnpjs","estabelecimento"],"destinatario_padrao":"conciliador.safrapay@safra.com.br","van_padrao":"SUPPLY MIDIA","custo_van":"NETUNNA","layout_padrao":"Padrão V2.0 Ed.13","produto_formulario":"090 - Extrato EDI Safrapay","status_pos_envio":"Aguardando Retorno Adquirente","sla_primeiro_followup_horas":48,"regra_dados":"Inclusão SAFRAPAY: o cliente valida, carimba e assina o Termo SAFRAPAY; após retorno do termo assinado, enviar ao conciliador.safrapay@safra.com.br informando cliente, CNPJ, EC, VAN Supply Mídia e padrão V2.0 Ed.13. Para Supply Mídia, o custo é integralmente Netunna. A atualização da planilha Supply Mídia e a validação final da recepção física dos arquivos são checkpoints humanos; a EDNNA continua dona do workflow antes e depois desses checkpoints.","checkpoints_humanos":[{"codigo":"TERMO_SAFRAPAY","titulo":"Preparar/validar Termo SAFRAPAY com o cliente","momento":"ANTES_ENVIO_SAFRAPAY"},{"codigo":"PLANILHA_SUPPLY","titulo":"Atualizar planilha Supply Mídia","momento":"APOS_RETORNO_SAFRAPAY"},{"codigo":"VALIDAR_ARQUIVOS","titulo":"Validar recepção dos arquivos SAFRAPAY","momento":"APOS_CONFIGURACAO_VAN"}],"estados":["AGUARDANDO_TERMO_CLIENTE","AGUARDANDO_SAFRAPAY","PRECISO_DE_VOCE_PLANILHA_SUPPLY","AGUARDANDO_SUPPLY_MIDIA","PRECISO_DE_VOCE_VALIDAR_ARQUIVOS","CONCLUIDO"],"etapas":["EXTRAIR_CNPJ","EXTRAIR_ESTABELECIMENTO","IDENTIFICAR_CONTATOS_CLIENTE","CHECKPOINT_TERMO_SAFRAPAY","AGUARDAR_TERMO_ASSINADO","ENVIAR_SAFRAPAY","AGUARDAR_RETORNO_SAFRAPAY","INTERPRETAR_RETORNO_SAFRAPAY","CHECKPOINT_PLANILHA_SUPPLY","AGUARDAR_SUPPLY_MIDIA","REGISTRAR_CAIXA_POSTAL","CHECKPOINT_VALIDAR_ARQUIVOS","REGISTRAR_EVIDENCIA_REDMINE","CONCLUIR"]},
    "SICREDI": {"tipo_player":"BANCO","workflow":"ABERTURA_SICREDI_BANCO","canal":"EMAIL","fonte_dados":"BLUEPRINT_DOMICILIOS_BANCARIOS","executor":"EMAIL_GRAPH","campos_obrigatorios":["contas_bancarias","contato_gerente"],"van_solicitada":"SUPPLY MIDIA","layout_extrato":"CNAB 240 padrão Febraban 5.0 Aberto","periodicidade":"Diário","status_pos_envio":"Aguardando Retorno Banco","sla_primeiro_followup_horas":48,"regra_dados":"Abertura de relacionamento SICREDI para Extrato de Conciliação Bancária. Resolver gerente pelo Blueprint, enviar CNPJ e todos os domicílios agência/conta, solicitar VAN Supply Mídia e CNAB 240 Febraban 5.0 Aberto diário. Interpretar dúvidas, prazos, assinatura/documentação e divergência de VAN. Após banco, acompanhar VAN, caixa postal, virada de chave/transmissão e validar arquivo por domicílio. Só concluir quando todos os domicílios esperados tiverem evidência de arquivo recebido.","estados":["AGUARDANDO_BANCO","AGUARDANDO_CLIENTE","DIVERGENCIA_VAN","AGUARDANDO_VAN","AGUARDANDO_TRANSMISSAO","AGUARDANDO_ARQUIVOS","VALIDACAO_PARCIAL","CONCLUIDO"],"etapas":["LOCALIZAR_BLUEPRINT","EXTRAIR_DOMICILIOS_BANCARIOS","EXTRAIR_GERENTE_CONTA","VALIDAR_CONTAS_SOLICITADAS","PREPARAR_EMAIL_ABERTURA","ENVIAR_EMAIL","AGUARDAR_RETORNO_BANCO","INTERPRETAR_RETORNO_BANCO","TRATAR_ASSINATURA_SE_SOLICITADA","VALIDAR_VAN_RETORNADA","AGUARDAR_RETORNO_VAN","VALIDAR_CAIXA_POSTAL","VALIDAR_VIRADA_CHAVE_TRANSMISSAO","AGUARDAR_ARQUIVOS","VALIDAR_ARQUIVOS_POR_DOMICILIO","COBRAR_DOMICILIOS_PENDENTES","REGISTRAR_MOVIMENTACAO_BP","REGISTRAR_EVIDENCIA_REDMINE","CONCLUIR_SOMENTE_COM_TODOS_DOMICILIOS"]},
    "BANRISUL": {"tipo_player":"BANCO","workflow":"INCLUSAO_BANCO_VIA_AR","canal":"RELACIONAMENTO_BANCARIO","fonte_dados":"ABERTURA_RELACIONAMENTO","executor":"ASSISTIDO_BANCO","etapas":["LOCALIZAR_ABERTURA_RELACIONAMENTO","EXTRAIR_DADOS_BANCARIOS","EXTRAIR_GERENTE_CONTA","PREPARAR_SOLICITACAO","EXECUTAR_CANAL_HOMOLOGADO","ACOMPANHAR_RETORNO","REGISTRAR_EVIDENCIA_REDMINE"]},
}



def _garantir_tabela_configuracoes() -> None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS configuracoes_regras (
            player TEXT PRIMARY KEY, ativa INTEGER NOT NULL DEFAULT 1, override_json TEXT NOT NULL DEFAULT '{}',
            atualizado_por TEXT, atualizado_em TEXT NOT NULL
        )""")
        conn.commit()

def obter_configuracao_regra(player: str) -> dict:
    _garantir_tabela_configuracoes()
    p=str(player or '').strip().upper()
    with conectar() as conn:
        row=conn.execute("SELECT * FROM configuracoes_regras WHERE player=?",(p,)).fetchone()
    if not row: return {"player":p,"ativa":True,"override":{}}
    d=dict(row)
    try: ov=json.loads(d.get('override_json') or '{}')
    except Exception: ov={}
    return {"player":p,"ativa":bool(d.get('ativa',1)),"override":ov,"atualizado_por":d.get('atualizado_por'),"atualizado_em":d.get('atualizado_em')}

def salvar_configuracao_regra(player: str, *, ativa: bool=True, override: dict|None=None, atualizado_por: str='OPERADOR_EDNNA') -> dict:
    _garantir_tabela_configuracoes()
    p=str(player or '').strip().upper()
    if p not in WORKFLOWS:
        raise ValueError('A configuração persistente só pode alterar uma regra declarativa conhecida.')
    now=agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""INSERT INTO configuracoes_regras(player,ativa,override_json,atualizado_por,atualizado_em) VALUES(?,?,?,?,?)
        ON CONFLICT(player) DO UPDATE SET ativa=excluded.ativa,override_json=excluded.override_json,atualizado_por=excluded.atualizado_por,atualizado_em=excluded.atualizado_em""",
        (p,1 if ativa else 0,json.dumps(override or {},ensure_ascii=False),atualizado_por,now))
        conn.commit()
    return obter_configuracao_regra(p)

def listar_catalogo_workflows() -> list[dict]:
    itens=[]
    for player in sorted(WORKFLOWS):
        cfg=obter_workflow(player)
        itens.append(cfg)
    return itens

# Infraestrutura realmente disponível hoje. Executores compostos só ficam
# prontos quando TODOS os seus componentes estiverem implementados.
EXECUTORES_IMPLEMENTADOS = {"EMAIL_GRAPH", "MONITOR_EMAIL", "REDMINE", "FORMULARIO_GREENCARD", "FORMULARIO_ROTACARD", "INTERVENCAO_HUMANA"}


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
        # v3.31.0 — regras ensinadas e homologadas podem fornecer um workflow
        # declarativo sem exigir alteração do código-fonte. A autorização de
        # execução continua separada e explícita na Central de Regras.
        try:
            from ednna.construtor_regras import obter_workflow_treinavel
            cfg = dict(obter_workflow_treinavel(p) or {})
        except Exception:
            cfg = {}
    if not cfg:
        return {"player": p, "workflow":"NAO_CLASSIFICADO", "canal":"NAO_IDENTIFICADO", "executor":"NAO_IMPLEMENTADO", "etapas":[], "prontidao":"SEM_WORKFLOW"}
    cfg["player"] = p
    if p in WORKFLOWS:
        persistida=obter_configuracao_regra(p)
        cfg.update(dict(persistida.get("override") or {}))
        cfg["ativa"] = bool(persistida.get("ativa", True))
        cfg["configuracao_atualizada_em"] = persistida.get("atualizado_em") or ""
    else:
        cfg.setdefault("ativa", True)
    # v3.28.35 — workflows definidos pela operação têm autoridade humana confirmada.
    # O histórico enriquece a regra, mas não bloqueia sua revisão/homologação.
    cfg.setdefault("fonte_autoridade", "ORIENTACAO_OPERACIONAL")
    cfg.setdefault("procedimento_confirmado", True)
    executores = [x for x in str(cfg.get("executor") or "").split("+") if x]
    faltantes = [x for x in executores if x not in EXECUTORES_IMPLEMENTADOS]
    cfg["executores_faltantes"] = faltantes
    cfg["prontidao"] = ("INATIVA" if not cfg.get("ativa", True) else ("ASSISTIDA_DISPONIVEL" if not faltantes else "AGUARDANDO_EXECUTOR"))
    return cfg


def planejar_workflow(player: str, dados: dict | None = None) -> dict:
    cfg = obter_workflow(player)
    validacao = validar_dados_workflow(player, dados)
    pode_assistido = cfg.get("prontidao") == "ASSISTIDA_DISPONIVEL" and validacao["valido"]
    if not validacao["valido"]:
        estado = "AGUARDANDO_DADOS"
    elif cfg.get("prontidao") != "ASSISTIDA_DISPONIVEL":
        estado = "AGUARDANDO_EXECUTOR"
    elif str(cfg.get("player") or "").upper() == "SAFRAPAY":
        # SAFRAPAY começa com um checkpoint humano deliberado: o termo deve ser
        # validado/carimbado/assinado pelo cliente. A regra pode ser automática
        # sem permitir que o worker pule essa etapa.
        estado = "CHECKPOINT_HUMANO"
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
