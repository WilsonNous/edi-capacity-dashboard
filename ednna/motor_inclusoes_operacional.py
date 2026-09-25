from __future__ import annotations
import re

"""Fila operacional assistida de inclusões — v3.28.37.

Transforma inclusões ativas do snapshot em planos acionáveis usando somente
regras homologadas + autorização explícita do motor. Esta camada NÃO envia
e-mail, NÃO chama APIs e NÃO altera Redmine. Ela prepara o braço operacional.
"""

from typing import Any
import os
from ednna.email_identity import finalizar_email
from ednna.email_policy import aplicar_cc_padrao, aplicar_cc_cliente
from ednna.blueprint_knowledge import emails_cliente_blueprint, localizar_contato_bancario
import pandas as pd

from ednna.aprendizado_operacional import obter_regra_homologada, obter_autorizacao_motor
from ednna.planejador_inclusoes import descobrir_candidatos_inclusao, preparar_operacao_inclusao, _extrair_dados, _identificar_cnpj_matriz
from ednna.workflows_inclusao import obter_workflow
from ednna.armazenamento import obter_analise_primeiro_combate, listar_journals
from ednna.sincronizador import normalizar_marca_alteracao
from ednna.acompanhamento_acoes import listar_redmine_pendentes, listar_acoes_aguardando_resposta


def _row_por_id(snapshot: pd.DataFrame, chamado_id: int) -> dict:
    if snapshot is None or not isinstance(snapshot, pd.DataFrame) or snapshot.empty:
        return {}
    for _, row in snapshot.iterrows():
        try:
            cid = int(float(row.get("#", 0)))
        except Exception:
            continue
        if cid == int(chamado_id):
            return row.to_dict()
    return {}


def _dados_snapshot(row: dict) -> dict:
    issue_fake = {
        "subject": str(row.get("Assunto", "") or ""),
        "description": str(row.get("Descrição", "") or ""),
        "journals": [],
    }
    extraidos = _extrair_dados(issue_fake)
    texto_banco = "\n".join([str(row.get("Assunto", "") or ""), str(row.get("Descrição", "") or "")])
    contas_bancarias = []
    for m in re.finditer(r"(?i)\bconta\s*[:#-]?\s*([0-9][0-9.\- ]{2,20})", texto_banco):
        conta = re.sub(r"\s+", "", m.group(1)).strip(".-")
        if conta and conta not in contas_bancarias: contas_bancarias.append(conta)
    adquirentes_contas = []
    for linha in texto_banco.splitlines():
        if re.search(r"(?i)adquirentes?\s*:", linha):
            adquirentes_contas.extend([x.strip() for x in re.split(r"[,;]", linha.split(":",1)[1]) if x.strip()])
    return {
        **extraidos,
        "estabelecimento": list(extraidos.get("ecs") or []),
        "cnpj_matriz": _identificar_cnpj_matriz(extraidos.get("cnpjs") or []),
        "cnpjs": list(extraidos.get("cnpjs") or []),
        "emails": list(extraidos.get("emails") or []),
        "cliente": str(row.get("Clientes", "") or ""),
        "assunto": str(row.get("Assunto", "") or ""),
        "descricao": str(row.get("Descrição", "") or ""),
        "tipo_demanda": str(row.get("Tipo", "") or ""),
        "estado_redmine": str(row.get("Estado", "") or ""),
        "contas_bancarias": contas_bancarias,
        "adquirentes_bancarios": list(dict.fromkeys(adquirentes_contas)),
        "fonte": "SNAPSHOT_ATIVO",
    }



def _historico_operacional(chamado_id: int, alterado_em: str = "") -> dict:
    """Retorna uma trava conservadora contra primeira atuação duplicada.

    A fonte primária é a análise de primeiro combate. Como defesa adicional,
    journals já persistidos com notas operacionais também bloqueiam uma nova
    primeira solicitação até que a continuidade seja classificada.
    """
    analise = obter_analise_primeiro_combate(int(chamado_id)) or {}
    journals = listar_journals(int(chamado_id)) or []
    # Segurança operacional: um chamado só pode entrar em "Posso agir" depois
    # que os journals correspondentes à versão atual do chamado forem analisados.
    # Sem isso, uma atuação humana anterior pode ser ignorada e a EDNNA duplicar
    # uma solicitação já enviada.
    marca_analise = normalizar_marca_alteracao(analise.get("alterado_em_redmine"))
    marca_snapshot = normalizar_marca_alteracao(alterado_em)
    if not analise:
        return {"tem_atuacao": False, "historico_pendente": True, "fonte": "ANALISE_AUSENTE", "analise": {}, "journals": len(journals)}
    if marca_snapshot and marca_analise and marca_snapshot != marca_analise:
        return {"tem_atuacao": False, "historico_pendente": True, "fonte": "ANALISE_DESATUALIZADA", "analise": analise, "journals": len(journals)}
    teve = bool(int(analise.get("teve_atuacao") or 0))
    notas = [j for j in journals if str(j.get("notas") or "").strip()]
    if teve:
        return {"tem_atuacao": True, "fonte": "ANALISE_PRIMEIRO_COMBATE", "analise": analise, "journals": len(journals)}
    # Não tratamos qualquer comentário como atuação automaticamente. Porém,
    # quando há histórico de e-mail/solicitação/retorno já salvo, é mais seguro
    # bloquear nova primeira ação e mandar para continuidade/revisão.
    sinais = ("de:", "enviado:", "enviadas:", "assunto:", "solicit", "aguardando retorno", "atenciosamente")
    for j in notas:
        txt = str(j.get("notas") or "").lower()
        if any(x in txt for x in sinais):
            return {"tem_atuacao": True, "fonte": "JOURNAL_OPERACIONAL", "analise": analise, "journals": len(journals)}
    return {"tem_atuacao": False, "fonte": "SEM_EVIDENCIA", "analise": analise, "journals": len(journals)}


def _elegibilidade_primeira_atuacao(row: dict) -> dict:
    """Barreira global: a fila principal só aceita chamado realmente inicial.

    Estados de continuidade (aguardando retorno, em andamento etc.) nunca podem
    oferecer uma nova primeira solicitação, mesmo que outra camada falhe.
    """
    estado = str(row.get("Estado", "") or "").strip()
    estado_norm = estado.upper().replace("Á", "A").replace("Ã", "A").replace("Ç", "C").replace("Ê", "E")
    # Regra conservadora: somente ABERTO pode disputar a fila de primeira atuação.
    # Todo outro estado ativo permanece consultável/continuidade.
    if estado_norm != "ABERTO":
        return {"elegivel": False, "motivo": f"Estado Redmine '{estado or 'não informado'}' indica continuidade", "estado_redmine": estado}
    # Se o snapshot trouxer percentual > 0, há evidência adicional de andamento.
    for chave in ("% Completo", "% completo", "Completo", "done_ratio"):
        if chave in row and row.get(chave) not in (None, ""):
            try:
                pct = float(str(row.get(chave)).replace("%", "").replace(",", "."))
                if pct > 0:
                    return {"elegivel": False, "motivo": f"Chamado já possui {pct:g}% de progresso", "estado_redmine": estado}
            except Exception:
                pass
    return {"elegivel": True, "motivo": "Chamado em estado inicial", "estado_redmine": estado}


def avaliar_fila_inclusoes(snapshot: pd.DataFrame) -> dict:
    inventario = descobrir_candidatos_inclusao(snapshot)
    itens: list[dict[str, Any]] = []
    contadores = {
        "descobertas": int(inventario.get("total", 0) or 0),
        "homologadas": 0,
        "autorizadas": 0,
        "prontas": 0,
        "aguardando_dados": 0,
        "aguardando_destinatario": 0,
        "aguardando_executor": 0,
        "nao_homologadas": 0,
        "nao_autorizadas": 0,
        "continuidade": 0,
        "historico_pendente": 0,
    }

    # Estado transacional tem precedência sobre a descoberta do motor.
    # Um chamado com e-mail já enviado não pode voltar para "Posso agir" só
    # porque o snapshot do Redmine ainda está como Aberto (ex.: PUT pendente).
    try:
        pendentes_redmine_ids = {int(x.get("chamado_id") or 0) for x in listar_redmine_pendentes()}
    except Exception as exc:
        pendentes_redmine_ids = set()
        print(f"[EDNNA] Motor inclusões | aviso ao ler Redmine pendente | {type(exc).__name__}: {exc}", flush=True)
    try:
        aguardando_resposta_ids = {int(x.get("chamado_id") or 0) for x in listar_acoes_aguardando_resposta()}
    except Exception as exc:
        aguardando_resposta_ids = set()
        print(f"[EDNNA] Motor inclusões | aviso ao ler acompanhamentos | {type(exc).__name__}: {exc}", flush=True)

    for candidato in inventario.get("candidatos", []) or []:
        cid_candidato = int(candidato["id"])
        players = candidato.get("players") or []
        if len(players) != 1:
            itens.append({**candidato, "estado_motor": "PLAYER_AMBIGUO", "acao_sugerida": "Revisar player"})
            continue
        player = str(players[0])
        row = _row_por_id(snapshot, cid_candidato)

        # Precedência operacional única:
        # REDMINE_PENDENTE > AGUARDANDO_RESPOSTA > primeira atuação.
        # Isso também corrige a interface: o botão Preparar atuação deixa de
        # existir para chamados que já tiveram envio confirmado.
        if cid_candidato in pendentes_redmine_ids:
            contadores["continuidade"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "REDMINE_PENDENTE", "acao_sugerida": "Reconciliar Redmine"})
            continue
        if cid_candidato in aguardando_resposta_ids:
            contadores["continuidade"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "AGUARDANDO_RESPOSTA", "acao_sugerida": "Acompanhar retorno"})
            continue

        elegibilidade = _elegibilidade_primeira_atuacao(row)
        if not elegibilidade.get("elegivel"):
            contadores["continuidade"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "CONTINUIDADE_ESTADO_REDMINE", "acao_sugerida": "Consultar / continuar acompanhamento", "elegibilidade": elegibilidade})
            continue
        historico = _historico_operacional(int(candidato["id"]), str(row.get("Alterado", "") or ""))
        if historico.get("historico_pendente"):
            contadores["historico_pendente"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "AGUARDANDO_VERIFICACAO_HISTORICO", "acao_sugerida": "Sincronizar histórico", "historico_operacional": historico})
            continue
        if historico.get("tem_atuacao"):
            contadores["continuidade"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "CONTINUIDADE_ATUACAO_PREVIA", "acao_sugerida": "Continuar acompanhamento", "historico_operacional": historico})
            continue
        regra = obter_regra_homologada(player)
        if not regra:
            contadores["nao_homologadas"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "REGRA_NAO_HOMOLOGADA", "acao_sugerida": "Homologar regra"})
            continue
        contadores["homologadas"] += 1
        aut = obter_autorizacao_motor(str(regra.get("regra_id") or ""))
        modo_motor = str(aut.get("modo") or "BLOQUEADA").upper()
        if modo_motor not in {"ASSISTIDA", "AUTOMATICA"}:
            contadores["nao_autorizadas"] += 1
            itens.append({**candidato, "player": player, "regra_id": regra.get("regra_id"), "estado_motor": "REGRA_HOMOLOGADA_NAO_AUTORIZADA", "acao_sugerida": "Autorizar motor"})
            continue
        contadores["autorizadas"] += 1
        dados = _dados_snapshot(row)
        # v3.29.2 — a Base de Conhecimento passa a enriquecer as regras sem
        # depender de nova consulta ao Redmine. Blueprint é fonte confiável local.
        cliente_bp = str(dados.get("cliente") or "").strip()
        contatos_bp = emails_cliente_blueprint(cliente_bp, limite=10) if cliente_bp else []
        dados["emails_blueprint"] = contatos_bp
        dados["contato_cliente_principal"] = contatos_bp[0] if contatos_bp else ""
        if player == "SICREDI" and cliente_bp:
            banco_bp = localizar_contato_bancario(cliente_bp, banco="SICREDI", codigo_banco="167", contas=dados.get("contas_bancarias") or [])
            contato_bp = banco_bp.get("contato") or {}
            emails_banco = list(contato_bp.get("emails") or [])
            dados["contato_gerente"] = emails_banco[0] if emails_banco else ""
            dados["gerente_banco"] = contato_bp.get("gerente") or ""
            dados["evidencia_bancaria_bp"] = contato_bp
        plano = preparar_operacao_inclusao(int(candidato["id"]), player, dados=dados)
        estado = str(plano.get("estado") or "")
        wf = plano.get("workflow") or obter_workflow(player)

        # v3.28.58 — uma regra HOMOLOGADA deve reaproveitar o destinatário que
        # sustentou a própria homologação. Prioridade: confirmação humana ->
        # padrão declarativo do workflow -> evidência operacional aprendida.
        # O aprendizado continua enriquecendo a regra, mas não volta a bloquear
        # uma regra que já foi homologada com evidência suficiente.
        payload_regra = regra.get("payload") or {}
        destinos_aprendidos = list(payload_regra.get("destinatarios_operacionais") or [])
        if not destinos_aprendidos:
            destinos_aprendidos = list(payload_regra.get("destinatarios_recorrentes") or [])
        destinatario = str(
            regra.get("destinatario_confirmado")
            or wf.get("destinatario_padrao")
            or (destinos_aprendidos[0] if destinos_aprendidos else "")
            or ""
        ).strip()
        if player == "VR BENEFICIOS":
            # VR: a ação é dirigida ao CLIENTE, nunca à VR. Preferimos contatos
            # externos encontrados no chamado e rejeitamos domínios Netunna/VR.
            candidatos_cliente = [
                str(e).strip() for e in ([*(dados.get("emails_blueprint") or []), *(dados.get("emails") or [])])
                if str(e).strip() and not str(e).lower().endswith("@netunna.com.br")
                and not str(e).lower().endswith("@vr.com.br")
            ]
            if candidatos_cliente:
                destinatario = candidatos_cliente[0]
            elif destinatario.lower().endswith("@vr.com.br") or destinatario.lower().endswith("@netunna.com.br"):
                destinatario = ""
        elif player == "VEROCHEQUE":
            destinatario = "conciliacao@verocard.com.br"
        elif player == "VALECARD":
            destinatario = "atendimentograndesredes@valecard.com.br"
        elif player == "POLICARD":
            destinatario = "grandesredesup@upbrasil.com"
        elif player == "SICREDI" and dados.get("contato_gerente"):
            destinatario = str(dados.get("contato_gerente") or "").strip()
        if estado == "PRONTO_OPERACAO_ASSISTIDA" and "EMAIL" in str(wf.get("canal") or "") and not destinatario:
            estado = "AGUARDANDO_DESTINATARIO"

        if estado == "PRONTO_OPERACAO_ASSISTIDA":
            contadores["prontas"] += 1
            acao = "Preparar atuação"
        elif estado == "AGUARDANDO_DADOS":
            contadores["aguardando_dados"] += 1
            acao = "Completar dados"
        elif estado == "AGUARDANDO_DESTINATARIO":
            contadores["aguardando_destinatario"] += 1
            acao = "Confirmar destinatário"
        elif estado == "AGUARDANDO_EXECUTOR":
            contadores["aguardando_executor"] += 1
            acao = "Implementar executor"
        else:
            acao = "Revisar"

        itens.append({
            **candidato,
            "player": player,
            "regra_id": regra.get("regra_id"),
            "estado_motor": estado,
            "acao_sugerida": acao,
            "destinatario": destinatario,
            "dados_motor": dados,
            "plano": plano,
        })

    print(
        "[EDNNA] Motor inclusões | "
        + " | ".join(f"{k}={v}" for k, v in contadores.items()),
        flush=True,
    )
    return {"resumo": contadores, "itens": itens}



def diagnosticar_regras_operacionais(snapshot: pd.DataFrame) -> dict:
    """Traduz o estado técnico do motor para uma visão operacional por regra.

    A pergunta respondida aqui é simples: a regra tem demanda agora? Se tem,
    quais chamados estão associados e o que impede (ou permite) a atuação?
    Esta função não executa nenhuma ação externa.
    """
    from ednna.aprendizado_operacional import listar_regras_operacionais

    fila = avaliar_fila_inclusoes(snapshot) if isinstance(snapshot, pd.DataFrame) and not snapshot.empty else {"resumo": {}, "itens": []}
    itens = list(fila.get("itens") or [])
    regras = [r for r in (listar_regras_operacionais() or []) if str(r.get("estado_revisao") or "") == "HOMOLOGADA"]
    diagnosticos = []

    rotulos = {
        "PRONTO_OPERACAO_ASSISTIDA": ("PRONTA", "Chamado pronto para atuação"),
        "AGUARDANDO_DADOS": ("PRECISA_DE_VOCE", "Faltam dados obrigatórios no chamado"),
        "AGUARDANDO_DESTINATARIO": ("PRECISA_DE_VOCE", "Falta destinatário confiável"),
        "AGUARDANDO_EXECUTOR": ("ERRO_TECNICO", "Executor técnico ainda não disponível"),
        "REGRA_HOMOLOGADA_NAO_AUTORIZADA": ("PRECISA_DE_VOCE", "Regra homologada, mas ainda não autorizada no motor"),
        "REGRA_NAO_HOMOLOGADA": ("IDENTIFICACAO", "Demanda identificada, regra ainda não homologada"),
        "PLAYER_AMBIGUO": ("IDENTIFICACAO", "Player/adquirente ambíguo"),
        "AGUARDANDO_VERIFICACAO_HISTORICO": ("PRECISA_DE_VOCE", "Histórico precisa ser sincronizado antes de agir"),
        "REDMINE_PENDENTE": ("REDMINE_PENDENTE", "E-mail/ação já ocorreu; falta reconciliar Redmine"),
        "AGUARDANDO_RESPOSTA": ("AGUARDANDO_RESPOSTA", "EDNNA já atuou e aguarda retorno"),
        "CONTINUIDADE_ESTADO_REDMINE": ("CONTINUIDADE", "Chamado já está em continuidade no Redmine"),
        "CONTINUIDADE_ATUACAO_PREVIA": ("CONTINUIDADE", "Há evidência de atuação anterior"),
    }

    for regra in regras:
        player = str(regra.get("player") or "").strip()
        rid = str(regra.get("regra_id") or "").strip()
        aut = obter_autorizacao_motor(rid)
        modo = str(aut.get("modo") or "BLOQUEADA").upper()
        wf = regra.get("workflow") or obter_workflow(player)
        relacionados = [x for x in itens if str(x.get("player") or "").strip().upper() == player.upper() or str(x.get("regra_id") or "") == rid]
        estados = {}
        chamados = []
        for item in relacionados:
            est = str(item.get("estado_motor") or "DESCONHECIDO")
            estados[est] = estados.get(est, 0) + 1
            categoria, motivo = rotulos.get(est, ("REVISAO", "Revisar diagnóstico do motor"))
            chamados.append({
                "id": int(item.get("id") or 0), "cliente": item.get("cliente") or "",
                "estado_motor": est, "categoria": categoria, "motivo": motivo,
                "acao_sugerida": item.get("acao_sugerida") or "Revisar",
            })
        if not relacionados:
            situacao, motivo = "SEM_DEMANDA", "Regra pronta, mas não há chamado ativo compatível neste snapshot"
        elif estados.get("PRONTO_OPERACAO_ASSISTIDA"):
            situacao, motivo = "PRONTA", f"{estados['PRONTO_OPERACAO_ASSISTIDA']} chamado(s) pronto(s) para atuação"
        elif any(k in estados for k in ("AGUARDANDO_DADOS","AGUARDANDO_DESTINATARIO","REGRA_HOMOLOGADA_NAO_AUTORIZADA","AGUARDANDO_VERIFICACAO_HISTORICO")):
            situacao, motivo = "PRECISA_DE_VOCE", "Existe demanda, mas há uma pendência operacional antes da atuação"
        elif estados.get("AGUARDANDO_EXECUTOR"):
            situacao, motivo = "ERRO_TECNICO", "Existe demanda, mas falta executor técnico"
        elif any(k in estados for k in ("PLAYER_AMBIGUO","REGRA_NAO_HOMOLOGADA")):
            situacao, motivo = "IDENTIFICACAO", "Existe demanda com problema de identificação/classificação"
        elif any(k in estados for k in ("AGUARDANDO_RESPOSTA","REDMINE_PENDENTE","CONTINUIDADE_ESTADO_REDMINE","CONTINUIDADE_ATUACAO_PREVIA")):
            situacao, motivo = "EM_ACOMPANHAMENTO", "A demanda já passou da primeira atuação e está em continuidade"
        else:
            situacao, motivo = "REVISAO", "Há demanda, mas o estado precisa de revisão"
        diagnosticos.append({
            "player": player, "regra_id": rid, "modo": modo, "workflow": wf.get("workflow") or "NAO_CLASSIFICADO",
            "canal": wf.get("canal") or "NAO_IDENTIFICADO", "prontidao_executor": wf.get("prontidao") or "SEM_WORKFLOW",
            "situacao": situacao, "motivo": motivo, "total_chamados": len(relacionados),
            "estados": estados, "chamados": chamados,
            "pode_automatizar": bool(wf.get("prontidao") == "ASSISTIDA_DISPONIVEL" and modo in {"ASSISTIDA","AUTOMATICA"}),
        })
    return {"regras": diagnosticos, "fila": fila}

def preparar_atuacao_assistida(item: dict) -> dict:
    """Gera um pacote de atuação para confirmação humana, sem ação externa."""
    estado = str(item.get("estado_motor") or "")
    if estado != "PRONTO_OPERACAO_ASSISTIDA":
        return {"ok": False, "estado": estado, "motivo": "Chamado ainda não está pronto para atuação assistida."}
    plano = item.get("plano") or {}
    wf = plano.get("workflow") or {}
    dados = item.get("dados_motor") or {}
    pacote = {
        "ok": True,
        "estado": "AGUARDANDO_CONFIRMACAO_HUMANA",
        "chamado_id": int(item.get("id") or 0),
        "player": item.get("player"),
        "regra_id": item.get("regra_id"),
        "canal": wf.get("canal"),
        "workflow": wf.get("workflow"),
        "destinatario": item.get("destinatario") or "",
        "cliente": dados.get("cliente") or "",
        "cnpj_matriz": dados.get("cnpj_matriz") or "",
        "estabelecimentos": dados.get("estabelecimento") or [],
        "cnpjs": dados.get("cnpjs") or [],
        "emails": dados.get("emails") or [],
        "emails_blueprint": dados.get("emails_blueprint") or [],
        "contato_cliente_principal": dados.get("contato_cliente_principal") or "",
        "contas_bancarias": dados.get("contas_bancarias") or [],
        "adquirentes_bancarios": dados.get("adquirentes_bancarios") or [],
        "contato_gerente": dados.get("contato_gerente") or "",
        "gerente_banco": dados.get("gerente_banco") or "",
        "blueprint_id": (item.get("plano") or {}).get("blueprint_id") or dados.get("blueprint_id"),
        "assunto": dados.get("assunto") or "",
        "descricao": dados.get("descricao") or "",
        "tipo_demanda": dados.get("tipo_demanda") or "",
        "etapas": wf.get("etapas") or [],
        "confirmacao_obrigatoria": True,
        "executou_acao_externa": False,
    }
    print(f"[EDNNA] Operação assistida preparada | chamado={pacote['chamado_id']} | player={pacote['player']} | regra={pacote['regra_id']} | estado=AGUARDANDO_CONFIRMACAO_HUMANA", flush=True)
    return pacote


def gerar_rascunho_inclusao(pacote: dict) -> dict:
    """Transforma pacote validado de inclusão EMAIL em rascunho visível ao operador."""
    if not pacote.get("ok"):
        return {"ok": False, "motivo": "Pacote operacional inválido."}
    canal = str(pacote.get("canal") or "")
    player=str(pacote.get("player") or "")
    if player in {"GREENCARD", "ROTACARD"} and canal == "DOCUMENTO+EMAIL":
        from ednna.greencard_workflow import preparar_primeira_etapa
        r = preparar_primeira_etapa(pacote)
        if r.get("ok"):
            r["remetente"] = os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br")
            r["cc"] = aplicar_cc_padrao(r.get("para") or [])
        return r
    if canal != "EMAIL":
        return {"ok": False, "motivo": f"Executor direto ainda não disponível para canal {canal}."}
    destinatario = str(pacote.get("destinatario") or "").strip()
    if player == "VEROCHEQUE" and not destinatario:
        destinatario = "conciliacao@verocard.com.br"
    if player == "VALECARD" and not destinatario:
        destinatario = "atendimentograndesredes@valecard.com.br"
    if player == "POLICARD" and not destinatario:
        destinatario = "grandesredesup@upbrasil.com"
    if not destinatario:
        return {"ok": False, "motivo": "Destinatário não confirmado."}
    cliente=str(pacote.get("cliente") or "Cliente")
    cid=int(pacote.get("chamado_id") or 0)
    ecs=[str(x) for x in (pacote.get("estabelecimentos") or []) if str(x).strip()]
    cnpjs=[str(x) for x in (pacote.get("cnpjs") or []) if str(x).strip()]
    matriz=str(pacote.get("cnpj_matriz") or "").strip()

    if player == "VR BENEFICIOS":
        # O cliente é quem realiza a habilitação no Portal VR. A EDNNA somente
        # orienta e acompanha; não envia solicitação de inclusão para a VR.
        assunto=f"[VR - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
        linhas=[
            "Olá, tudo bem?", "",
            "Para darmos continuidade à recepção dos arquivos da VR Benefícios, é necessário habilitar a NETUNNA como conciliadora no Portal VR para o(s) CNPJ(s) abaixo.", "",
            "1 - Acesse o Portal VR.",
            "2 - No menu principal, clique em Financeiro.",
            "3 - Selecione Conciliação.",
            "4 - Selecione NETUNNA como conciliadora responsável pelo recebimento dos arquivos EDI.",
            "5 - Confirme e finalize a habilitação.", "",
        ]
        if cnpjs:
            linhas += ["CNPJ(s) solicitado(s):"] + [f"- {x}" for x in cnpjs] + [""]
        linhas += [
            "Após concluir a habilitação, pedimos a gentileza de nos confirmar o retorno para que possamos acompanhar a recepção dos arquivos.", "",
            "Caso o estabelecimento ainda não esteja em operação, informe também a previsão de inauguração/início das vendas.",
        ]
        corpo=finalizar_email("\n".join(linhas))
        return {
            "ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),
            "para":([str(e) for e in (pacote.get("emails_blueprint") or []) if str(e).strip()] or [destinatario]),"cc":aplicar_cc_padrao(([str(e) for e in (pacote.get("emails_blueprint") or []) if str(e).strip()] or [destinatario])),"assunto":assunto,"corpo":corpo,
            "prazo_resposta_dias_uteis":2,"tipo_acao":"ORIENTAR_CLIENTE_PORTAL_VR",
            "status_pos_envio":"Aguardando Retorno Cliente",
        }

    if player == "SICREDI":
        contas=[str(x) for x in (pacote.get("contas_bancarias") or []) if str(x).strip()]
        if not destinatario or not contas:
            faltam=[]
            if not destinatario: faltam.append("contato/e-mail do gerente no Blueprint")
            if not contas: faltam.append("conta(s) bancária(s) no chamado")
            return {"ok":False,"motivo":"SICREDI: faltam dados para abertura: " + ", ".join(faltam) + ".","estado":"AGUARDANDO_DADOS"}
        assunto=f"[SICREDI - Abertura de Relacionamento - {cliente} - CN: {cid}]"
        linhas=["Olá, tudo bem?", "", f"Solicitamos a abertura de relacionamento bancário para nosso cliente {cliente}, para viabilizar o recebimento dos arquivos EDI referentes aos domicílios bancários abaixo:", ""]
        desc=str(pacote.get("descricao") or "")
        blocos=[x.strip() for x in desc.splitlines() if x.strip() and ("Conta" in x or "Adquirente" in x)]
        if blocos: linhas += blocos
        else: linhas += [f"- Conta {x}" for x in contas]
        linhas += ["", "Os dados acima correspondem aos domicílios bancários das adquirentes informadas no chamado.", "", "Por gentileza, pedimos a confirmação da abertura do relacionamento e das orientações necessárias para o tráfego dos arquivos."]
        corpo=finalizar_email("\n".join(linhas))
        return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":[destinatario],"cc":aplicar_cc_cliente([destinatario], [], cliente),"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2,"tipo_acao":"ABRIR_RELACIONAMENTO_BANCARIO_SICREDI","status_pos_envio":"Aguardando Retorno Banco"}

    if player == "TICKET":
        if not cnpjs or not ecs:
            faltam=[]
            if not cnpjs: faltam.append("CNPJ")
            if not ecs: faltam.append("EC/Estabelecimento")
            return {"ok":False,"motivo":"TICKET: faltam dados obrigatórios antes do envio: " + ", ".join(faltam) + ".","estado":"AGUARDANDO_DADOS"}
        assunto=f"[TICKET - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
        linhas=[
            "Olá, time Ticket, tudo bem?", "",
            f"Por gentileza, solicitamos a inclusão no tráfego atual de arquivos para nosso cliente comum {cliente}, conforme dados abaixo:", "",
            f"CNPJ: {cnpjs[0]}",
            "Estabelecimentos/ECs:",
        ]
        linhas += [f"- {ec}" for ec in ecs]
        linhas += ["", "Estamos à disposição para quaisquer esclarecimentos."]
        corpo=finalizar_email("\n".join(linhas))
        return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":[destinatario],"cc":aplicar_cc_cliente([destinatario], [], cliente),"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2,"tipo_acao":"SOLICITAR_INCLUSAO_TICKET","status_pos_envio":"Aguardando Retorno Adquirente"}

    if player == "VALECARD":
        if not cnpjs or not ecs:
            faltam=[]
            if not cnpjs: faltam.append("CNPJ")
            if not ecs: faltam.append("EC")
            return {"ok":False,"motivo":"VALECARD: faltam dados obrigatórios antes do envio: " + ", ".join(faltam) + ".","estado":"AGUARDANDO_DADOS"}
        assunto=f"[VALECARD - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
        linhas=[
            "Olá, time Valecard, tudo bem?", "",
            f"Por gentileza, solicitamos a inclusão no tráfego atual de arquivos para nosso cliente comum {cliente}, conforme dados abaixo:", "",
            f"CNPJ: {cnpjs[0]}",
            f"EC: {ecs[0]}", "",
            "Estamos à disposição para quaisquer esclarecimentos.",
        ]
        corpo=finalizar_email("\n".join(linhas))
        return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":["atendimentograndesredes@valecard.com.br"],"cc":aplicar_cc_cliente(["atendimentograndesredes@valecard.com.br"], [], cliente),"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":3,"tipo_acao":"SOLICITAR_INCLUSAO_VALECARD","status_pos_envio":"Aguardando Retorno Adquirente"}

    if player == "POLICARD":
        if not cnpjs or not ecs:
            faltam=[]
            if not cnpjs: faltam.append("CNPJ")
            if not ecs: faltam.append("EC")
            return {"ok":False,"motivo":"POLICARD: faltam dados obrigatórios antes do envio: " + ", ".join(faltam) + ".","estado":"AGUARDANDO_DADOS"}
        assunto=f"[POLICARD - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
        linhas=[
            "Olá, time Policard, tudo bem?", "",
            f"Por gentileza, solicitamos a inclusão no tráfego atual de arquivos para nosso cliente comum {cliente}, conforme dados abaixo:", "",
            f"CNPJ: {cnpjs[0]}",
            f"EC: {ecs[0]}", "",
            "Estamos à disposição para quaisquer esclarecimentos.",
        ]
        corpo=finalizar_email("\n".join(linhas))
        return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":["grandesredesup@upbrasil.com"],"cc":aplicar_cc_cliente(["grandesredesup@upbrasil.com"], [], cliente),"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2,"tipo_acao":"SOLICITAR_INCLUSAO_POLICARD","status_pos_envio":"Aguardando Retorno Adquirente"}

    if player == "VEROCHEQUE":
        # Procedimento operacional confirmado pela Verocheque: modelo fixo de
        # conciliação + autorização do responsável do estabelecimento.
        externos=[e for e in ([*(pacote.get("emails_blueprint") or []), *(pacote.get("emails") or [])]) if str(e).strip() and not str(e).lower().endswith("@netunna.com.br") and not str(e).lower().endswith("@verocard.com.br")]
        responsavel = externos[0] if externos else "[PENDENTE: e-mail do responsável do estabelecimento]"
        cnpj = cnpjs[0] if cnpjs else (ecs[0] if ecs else "[PENDENTE: CNPJ]")
        assunto=f"[VEROCHEQUE - Inclusão de estabelecimento - {cliente} - CN: {cid}]"
        linhas=[
            "Olá, time VEROCHEQUE, tudo bem?", "",
            "Segue os dados para inclusão do estabelecimento no tráfego de arquivos de conciliação:", "",
            f"Razão Social do Estabelecimento: {cliente}",
            f"CNPJ: {cnpj}",
            "Layout do arquivo: 1.7D",
            "Periodicidade: Diário",
            "Diretório de exportação: Servidor SFTP Verocard (Host: sftp.verocard.com.br / Porta: 20022), na pasta vinculada ao usuário netunna.",
            f"E-mail do responsável do estabelecimento: {responsavel}",
            "E-mail do responsável da conciliadora: edi@netunna.com.br", "",
            "É necessária a autorização do responsável pelo estabelecimento, por carta assinada ou resposta por e-mail, autorizando a NETUNNA a receber os arquivos.",
        ]
        if responsavel.startswith("[PENDENTE"):
            return {"ok":False,"motivo":"VEROCHEQUE: falta identificar o e-mail do responsável do estabelecimento antes do envio.","estado":"AGUARDANDO_DADOS"}
        corpo=finalizar_email("\n".join(linhas))
        return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":["conciliacao@verocard.com.br"],"cc":aplicar_cc_cliente(["conciliacao@verocard.com.br"], [responsavel], cliente),"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2,"tipo_acao":"SOLICITAR_INCLUSAO_VEROCHEQUE","status_pos_envio":"Aguardando Retorno Adquirente"}

    assunto=f"[{player} - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
    linhas=[f"Olá, time {player}, tudo bem?","","Por gentileza, solicitamos a inclusão no tráfego atual de arquivos para nosso cliente comum " + cliente + ".","",]
    if matriz: linhas += [f"CNPJ Matriz: {matriz}"]
    elif cnpjs: linhas += ["CNPJ(s): " + ", ".join(cnpjs)]
    if ecs: linhas += ["Estabelecimento(s)/EC(s): " + ", ".join(ecs)]
    linhas += ["", "Estamos à disposição para quaisquer esclarecimentos."]
    corpo = finalizar_email("\n".join(linhas))
    return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":[destinatario],"cc":aplicar_cc_cliente([destinatario], [], cliente),"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2,"tipo_acao":"SOLICITAR_INCLUSAO","status_pos_envio":"Aguardando Retorno Adquirente"}

def executar_atuacao_assistida_email(pacote: dict) -> dict:
    """Executa somente pacote EMAIL previamente preparado e confirmado na UI."""
    from ednna.acompanhamento_acoes import adquirir_envio, confirmar_envio_real, registrar_falha_envio
    from ednna.email_sender import enviar_email_graph
    r=gerar_rascunho_inclusao(pacote)
    if not r.get("ok"): return r
    # Permite ajuste humano do rascunho na operação assistida sem alterar a regra
    # homologada. A execução automática continua usando o template oficial.
    override = pacote.get("email_override") or {}
    if isinstance(override, dict):
        for campo in ("para", "cc", "assunto", "corpo"):
            if campo in override and override.get(campo) not in (None, ""):
                r[campo] = override.get(campo)
    cid=int(pacote.get("chamado_id") or 0); rid=str(pacote.get("regra_id") or "")
    print(f"[EDNNA] Execução solicitada | chamado={cid} | player={pacote.get('player')} | regra={rid}", flush=True)
    adquirido, estado=adquirir_envio(cid,rid)
    if not adquirido:
        estado_atual = str((estado or {}).get("estado") or "DESCONHECIDO")
        enviado = bool(str((estado or {}).get("enviado_em") or "").strip())
        motivo = "E-mail já enviado; chamado está em acompanhamento." if enviado else "Execução já está em andamento. Aguarde alguns instantes e atualize a tela."
        print(f"[EDNNA] Execução não adquirida | chamado={cid} | regra={rid} | estado={estado_atual} | enviado={enviado}", flush=True)
        return {"ok":False,"motivo":motivo,"estado":estado_atual,"acompanhamento":estado}
    print(f"[EDNNA] Executor adquirido | chamado={cid} | regra={rid} | estado=EXECUTANDO", flush=True)
    try:
        print(f"[EDNNA] Graph | iniciando envio | chamado={cid} | para={','.join(r.get('para') or [])}", flush=True)
        mail=enviar_email_graph(remetente=r["remetente"],para=r["para"],cc=r["cc"],assunto=r["assunto"],corpo=r["corpo"],anexos=r.get("anexos") or [])
        print(f"[EDNNA] Graph | HTTP 202 aceito | chamado={cid}", flush=True)
        # v3.28.53: além do HTTP 202, procurar a cópia real em Sent Items.
        # Falha desta leitura NÃO reenvia o e-mail: o HTTP 202 continua sendo prova de aceitação.
        try:
            from ednna.email_sender import confirmar_email_em_sent_items
            evidencia=confirmar_email_em_sent_items(remetente=r["remetente"], chamado_id=cid, assunto=r["assunto"])
            if evidencia.get("confirmado"):
                mail["message_id"]=evidencia.get("message_id","") or mail.get("message_id","")
                mail["conversation_id"]=evidencia.get("conversation_id","") or mail.get("conversation_id","")
                mail["internet_message_id"]=evidencia.get("internet_message_id","") or mail.get("internet_message_id","")
                mail["sent_datetime"]=evidencia.get("sent_datetime","")
                mail["sent_items_confirmed"]=True
                print(f"[EDNNA] Graph | SENT_ITEMS_CONFIRMED | chamado={cid} | message_id={mail.get('message_id') or 'n/d'} | enviado_em={mail.get('sent_datetime') or 'n/d'}", flush=True)
            else:
                mail["sent_items_confirmed"]=False
                print(f"[EDNNA] Graph | SENT_ITEMS_PENDING | chamado={cid} | HTTP202=confirmado", flush=True)
        except Exception as sent_exc:
            mail["sent_items_confirmed"]=False
            mail["sent_items_warning"]=f"{type(sent_exc).__name__}: {sent_exc}"
            print(f"[EDNNA] Graph | SENT_ITEMS_CHECK_ERROR | chamado={cid} | {type(sent_exc).__name__}: {sent_exc}", flush=True)
        acomp=confirmar_envio_real(cid,rid,prazo_dias_uteis=r["prazo_resposta_dias_uteis"],email_assunto=r["assunto"],graph_message_id=mail.get("message_id",""),graph_conversation_id=mail.get("conversation_id",""),graph_internet_message_id=mail.get("internet_message_id",""),enviado_em_real=mail.get("sent_datetime",""))
        print(f"[EDNNA] Acompanhamento | chamado={cid} | estado=AGUARDANDO_RESPOSTA", flush=True)
        if pacote.get("player") in {"GREENCARD", "ROTACARD"}:
            try:
                from ednna.greencard_workflow import registrar_estado, registrar_movimentacao_bp
                registrar_estado(pacote, "AGUARDANDO_CLIENTE", formulario_nome=((r.get("formulario") or {}).get("filename") or ""), assunto=r.get("assunto"))
                bp_res=registrar_movimentacao_bp(pacote, f"Chamado #{cid}: formulário {pacote.get('player')} pré-preenchido e enviado ao cliente para revisão, complemento e assinatura. Estado EDNNA: AGUARDANDO_CLIENTE.")
                print(f"[EDNNA] {pacote.get('player')} | BP movimentado | chamado={cid} | ok={bp_res.get('ok')}", flush=True)
            except Exception as gc_exc:
                print(f"[EDNNA] {pacote.get('player')} | persistência/BP pendente | chamado={cid} | {type(gc_exc).__name__}: {gc_exc}", flush=True)
        if pacote.get("player") == "SICREDI" and int(pacote.get("blueprint_id") or 0):
            try:
                from ednna.redmine_writer import adicionar_nota_chamado
                bp=int(pacote.get("blueprint_id") or 0)
                contas=", ".join(str(x) for x in (pacote.get("contas_bancarias") or []))
                nota_bp=f"*EDNNA · Movimentação bancária SICREDI*\n\nChamado #{cid}: solicitação de abertura de relacionamento enviada ao contato bancário obtido do Blueprint.\nContas: {contas or 'não informadas'}\nEstado EDNNA: AGUARDANDO_RETORNO_BANCO.\n\nMarcador: EDNNA-SICREDI:{cid}"
                adicionar_nota_chamado(chamado_id=bp, nota=nota_bp)
                print(f"[EDNNA] SICREDI | BP movimentado | chamado={cid} | bp={bp}", flush=True)
            except Exception as bank_exc:
                print(f"[EDNNA] SICREDI | BP pendente | chamado={cid} | {type(bank_exc).__name__}: {bank_exc}", flush=True)
        # Pós-envio obrigatório: o e-mail já saiu, portanto qualquer falha no Redmine
        # vira outbox pendente e nunca provoca reenvio da mensagem.
        from ednna.redmine_outbox import registrar_ou_enfileirar
        status_pos = str(r.get("status_pos_envio") or "Aguardando Retorno Cliente")
        # O journal é evidência operacional: registra a mensagem integral que
        # acabou de ser enviada, e não apenas um resumo. Isso mantém Redmine e
        # Graph auditáveis com o mesmo conteúdo.
        from ednna.redmine_writer import montar_nota_email_enviado
        nota = montar_nota_email_enviado(
            remetente=r.get("remetente", "edi@netunna.com.br"),
            para=list(r.get("para") or []),
            cc=list(r.get("cc") or []),
            assunto=str(r.get("assunto") or ""),
            corpo=str(r.get("corpo") or ""),
            enviado_em=str(mail.get("sent_datetime") or acomp.get("enviado_em") or ""),
            prazo_resposta_em=str(acomp.get("prazo_resposta_em") or ""),
        )
        print(f"[EDNNA] Redmine | atualização iniciada | chamado={cid} | status={status_pos}", flush=True)
        redmine_result = registrar_ou_enfileirar(
            chamado_id=cid, regra_id=rid, nota=nota, status_nome=status_pos,
            assigned_to_id=int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166),
        )
        print(f"[EDNNA] Redmine | atualização concluída | chamado={cid} | pendente={bool((redmine_result or {}).get('pendente'))}", flush=True)
        print(f"[EDNNA] Operação assistida EXECUTADA | chamado={cid} | player={pacote.get('player')} | regra={rid} | canal=EMAIL | tipo={r.get('tipo_acao')}",flush=True)
        return {"ok":True,"estado":"AGUARDANDO_RETORNO_CLIENTE" if pacote.get("player") == "VR BENEFICIOS" else "AGUARDANDO_RESPOSTA","email":mail,"acompanhamento":acomp,"redmine":redmine_result,"tipo_acao":r.get("tipo_acao")}
    except Exception as exc:
        print(f"[EDNNA] Operação assistida ERRO | chamado={cid} | regra={rid} | erro={type(exc).__name__}: {exc}", flush=True)
        registrar_falha_envio(cid,rid,str(exc)); raise


def executar_inclusoes_automaticas(snapshot: pd.DataFrame) -> dict:
    """Executa inclusões já comprovadas anteriormente pela mesma regra.

    Critério de confiança: a regra precisa estar homologada/autorizada, o chamado
    precisa estar realmente em primeira atuação e a mesma regra precisa possuir
    ao menos um envio confirmado pelo Graph no histórico operacional.
    """
    from ednna.acompanhamento_acoes import regra_possui_envio_confirmado
    habilitado = str(os.getenv("EDNNA_INCLUSOES_AUTO", "true") or "true").strip().casefold() in {"1","true","sim","yes","on"}
    resumo={"habilitado":habilitado,"avaliados":0,"elegiveis":0,"executados":0,"ignorados":0,"erros":0,"detalhes":[]}
    if not habilitado or snapshot is None or not isinstance(snapshot,pd.DataFrame) or snapshot.empty:
        return resumo
    fila=avaliar_fila_inclusoes(snapshot)
    # v3.29.2 — worker pode enriquecer a Base de Conhecimento em background.
    # A UI continua rápida; somente o worker consulta relações/anexos quando um
    # cliente ainda não possui contatos locais e a regra pode precisar deles.
    try:
        from ednna.blueprint_knowledge import emails_cliente_blueprint, localizar_contato_bancario
        from ednna.contexto_relacionamentos import sincronizar_conhecimento_blueprint
        sincronizados=0
        for _item in fila.get("itens", []):
            if sincronizados >= 3:
                break
            _estado=str(_item.get("estado_motor") or "")
            if _estado not in {"PRONTO_OPERACAO_ASSISTIDA","AGUARDANDO_DESTINATARIO","AGUARDANDO_DADOS"}:
                continue
            _dados=_item.get("dados_motor") or {}
            _cliente=str(_dados.get("cliente") or "").strip()
            _cid=int(_item.get("id") or 0)
            if not _cliente or not _cid or emails_cliente_blueprint(_cliente, limite=1):
                continue
            try:
                sincronizar_conhecimento_blueprint(_cid, force_contexto=False)
                sincronizados += 1
                print(f"[EDNNA] Blueprint background | chamado={_cid} | cliente={_cliente} | sincronizado", flush=True)
            except Exception as _exc:
                print(f"[EDNNA] Blueprint background | chamado={_cid} | cliente={_cliente} | falha={type(_exc).__name__}: {_exc}", flush=True)
        if sincronizados:
            fila=avaliar_fila_inclusoes(snapshot)
    except Exception as _exc:
        print(f"[EDNNA] Blueprint background | enriquecimento indisponivel | {type(_exc).__name__}: {_exc}", flush=True)
    limite=max(1,int(os.getenv("EDNNA_INCLUSOES_AUTO_MAX_PER_CYCLE","5") or 5))
    for item in fila.get("itens",[]):
        if resumo["executados"] >= limite: break
        resumo["avaliados"] += 1
        if str(item.get("estado_motor") or "") != "PRONTO_OPERACAO_ASSISTIDA":
            resumo["ignorados"] += 1; continue
        rid=str(item.get("regra_id") or "")
        aut = obter_autorizacao_motor(rid)
        modo_motor = str(aut.get("modo") or "BLOQUEADA").upper()
        # AUTOMATICA é autorização humana explícita. Para compatibilidade, uma
        # regra ASSISTIDA que já possua envio confirmado também pode ser promovida
        # pelo histórico, como nas versões anteriores.
        confianca_historica = regra_possui_envio_confirmado(rid)
        # Workflows documentais (Greencard) só entram no worker quando o operador
        # marcou explicitamente AUTOMATICA. Um envio assistido anterior não promove
        # sozinho um processo que envolve documento/assinatura.
        player_item = str(item.get("player") or "").upper()
        if player_item in {"GREENCARD", "ROTACARD"}:
            autorizado_auto = (modo_motor == "AUTOMATICA")
        else:
            autorizado_auto = modo_motor == "AUTOMATICA" or (modo_motor == "ASSISTIDA" and confianca_historica)
        if not autorizado_auto:
            resumo["ignorados"] += 1; continue
        resumo["elegiveis"] += 1
        pacote=preparar_atuacao_assistida(item)
        if not pacote.get("ok"):
            resumo["ignorados"] += 1; continue
        try:
            origem_auto = "AUTORIZACAO_EXPLICITA" if modo_motor == "AUTOMATICA" else "HISTORICO_CONFIRMADO"
            print(f"[EDNNA] Inclusão automática | chamado={pacote.get('chamado_id')} | regra={rid} | origem={origem_auto}",flush=True)
            resultado=executar_atuacao_assistida_email(pacote)
            if resultado.get("ok"):
                resumo["executados"] += 1
            else:
                resumo["ignorados"] += 1
            resumo["detalhes"].append({"chamado":pacote.get("chamado_id"),"regra":rid,"resultado":resultado.get("estado") or resultado.get("motivo")})
        except Exception as exc:
            resumo["erros"] += 1
            resumo["detalhes"].append({"chamado":pacote.get("chamado_id"),"regra":rid,"erro":f"{type(exc).__name__}: {exc}"})
            print(f"[EDNNA] Inclusão automática | ERRO | chamado={pacote.get('chamado_id')} | regra={rid} | {type(exc).__name__}: {exc}",flush=True)
    if resumo["elegiveis"] or resumo["executados"] or resumo["erros"]:
        print(f"[EDNNA] Inclusões automáticas | elegiveis={resumo['elegiveis']} | executados={resumo['executados']} | erros={resumo['erros']}",flush=True)
    return resumo
