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
    domicilios_bancarios = []
    for m in re.finditer(r"(?i)ag[eê]ncia\s*[:#-]?\s*([0-9]{1,6})\s*(?:[/|;-]|\s)+\s*conta\s*[:#-]?\s*([0-9][0-9.\- ]{2,20})", texto_banco):
        ag=re.sub(r"\s+","",m.group(1)); ct=re.sub(r"\s+","",m.group(2)).strip(".-")
        item={"agencia":ag,"conta":ct}
        if item not in domicilios_bancarios: domicilios_bancarios.append(item)
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
        "domicilios_bancarios": domicilios_bancarios,
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
        print(f"[EDDY] Motor inclusões | aviso ao ler Redmine pendente | {type(exc).__name__}: {exc}", flush=True)
    try:
        aguardando_resposta_ids = {int(x.get("chamado_id") or 0) for x in listar_acoes_aguardando_resposta()}
    except Exception as exc:
        aguardando_resposta_ids = set()
        print(f"[EDDY] Motor inclusões | aviso ao ler acompanhamentos | {type(exc).__name__}: {exc}", flush=True)

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
            destinatario = "conciliacao@upbrasil.com"
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
        elif estado == "CHECKPOINT_HUMANO":
            acao = "Preparar/validar Termo SAFRAPAY com o cliente"
        else:
            acao = "Revisar"

        itens.append({
            **candidato,
            "player": player,
            "regra_id": regra.get("regra_id"),
            "modo_motor": modo_motor,
            "estado_motor": estado,
            "acao_sugerida": acao,
            "destinatario": destinatario,
            "dados_motor": dados,
            "plano": plano,
        })

    print(
        "[EDDY] Motor inclusões | "
        + " | ".join(f"{k}={v}" for k, v in contadores.items()),
        flush=True,
    )
    # EDDY 4.3 — explica por que conhecimento homologado ainda pode não estar
    # executável. O diagnóstico não altera autorização nem executa ação externa.
    try:
        from ednna.prontidao_operacional import resumir_prontidao
        players_fila = [str(x.get("player") or "") for x in itens if x.get("player")]
        prontidao = resumir_prontidao(players_fila)
        estados = prontidao.get("estados") or {}
        if estados:
            print("[EDDY] Prontidão regras | " + " | ".join(f"{k}={v}" for k,v in sorted(estados.items())), flush=True)
        for p in prontidao.get("itens") or []:
            if p.get("conhecimento") == "HOMOLOGADA" and not p.get("pronta"):
                print(
                    "[EDDY] Regra homologada não executável | "
                    f"player={p.get('player')} | regra={p.get('regra_id') or '-'} | "
                    f"workflow={p.get('workflow')} | executor={p.get('executor')} | "
                    f"motor={p.get('modo_motor')} | bloqueios={','.join(p.get('bloqueios') or []) or '-'} | "
                    f"proxima_acao={p.get('proxima_acao')}",
                    flush=True,
                )
    except Exception as exc:
        prontidao = {"erro": f"{type(exc).__name__}: {exc}"}
        print(f"[EDDY] Prontidão regras | falha={type(exc).__name__}: {exc}", flush=True)
    return {"resumo": contadores, "itens": itens, "prontidao_regras": prontidao}



def diagnosticar_continuidade_operacional(snapshot: pd.DataFrame) -> dict:
    """Transforma o balde genérico CONTINUIDADE em uma fila explicável e acionável.

    Não executa ações externas. A execução continua pertencendo ao monitor,
    follow-up engine e outbox. Aqui apenas classificamos cada chamado e deixamos
    explícito por que ele ainda não avançou.
    """
    fila = avaliar_fila_inclusoes(snapshot)
    try:
        from ednna.followup_engine import avaliar_followups
        followups = avaliar_followups()
        followup_por_id = {
            int(x.get("chamado_id") or 0): x
            for x in (followups.get("itens") or [])
            if int(x.get("chamado_id") or 0)
        }
    except Exception as exc:
        followup_por_id = {}
        print(f"[EDDY] Continuidade diagnóstico | follow-up indisponível | {type(exc).__name__}: {exc}", flush=True)

    itens = []
    contadores = {
        "total": 0,
        "aguardando_prazo": 0,
        "followup_automatico": 0,
        "followup_assistido": 0,
        "aguardando_intervalo": 0,
        "limite_followup": 0,
        "sem_thread": 0,
        "redmine_pendente": 0,
        "atuacao_previa_sem_acompanhamento": 0,
        "estado_redmine_sem_acompanhamento": 0,
        "outros": 0,
    }

    for item in fila.get("itens") or []:
        estado = str(item.get("estado_motor") or "")
        if estado not in {
            "REDMINE_PENDENTE", "AGUARDANDO_RESPOSTA",
            "CONTINUIDADE_ESTADO_REDMINE", "CONTINUIDADE_ATUACAO_PREVIA",
        }:
            continue
        cid = int(item.get("id") or 0)
        diagnostico = {
            "chamado_id": cid,
            "cliente": item.get("cliente") or "",
            "player": item.get("player") or "",
            "estado_motor": estado,
            "proxima_acao": item.get("acao_sugerida") or "Revisar continuidade",
            "motivo": "",
            "executavel_agora": False,
        }
        contadores["total"] += 1

        if estado == "REDMINE_PENDENTE":
            contadores["redmine_pendente"] += 1
            diagnostico.update(motivo="Ação já ocorreu; falta reconciliar o efeito no Redmine.", proxima_acao="Reconciliar Redmine")
        elif estado == "AGUARDANDO_RESPOSTA":
            fu = followup_por_id.get(cid)
            if not fu:
                contadores["outros"] += 1
                diagnostico["motivo"] = "Acompanhamento ativo sem diagnóstico de follow-up."
            else:
                est_fu = str(fu.get("estado_followup") or "")
                modo = str(fu.get("modo_followup") or "ASSISTIDO")
                diagnostico["estado_followup"] = est_fu
                diagnostico["modo_followup"] = modo
                diagnostico["prazo_resposta_em"] = fu.get("prazo_resposta_em")
                diagnostico["followup_count"] = int(fu.get("followup_count") or 0)
                if est_fu == "AGUARDANDO_PRAZO":
                    contadores["aguardando_prazo"] += 1
                    diagnostico.update(motivo="Prazo de resposta ainda não venceu.", proxima_acao="Aguardar prazo")
                elif est_fu == "AGUARDANDO_INTERVALO":
                    contadores["aguardando_intervalo"] += 1
                    diagnostico.update(motivo="Follow-up anterior ainda está dentro do intervalo mínimo.", proxima_acao="Aguardar intervalo")
                elif est_fu == "LIMITE_FOLLOWUP":
                    contadores["limite_followup"] += 1
                    diagnostico.update(motivo="Limite automático de follow-ups atingido.", proxima_acao="Decisão humana / escalonamento")
                elif est_fu == "SEM_THREAD":
                    contadores["sem_thread"] += 1
                    diagnostico.update(motivo="Envio existe, mas não há message_id para responder na thread.", proxima_acao="Reconstruir thread")
                elif est_fu == "FOLLOWUP_PRONTO" and modo == "AUTOMATICO":
                    contadores["followup_automatico"] += 1
                    diagnostico.update(motivo="Prazo vencido e regra autoriza continuidade automática.", proxima_acao="Enviar follow-up automático", executavel_agora=True)
                elif est_fu == "FOLLOWUP_PRONTO":
                    contadores["followup_assistido"] += 1
                    diagnostico.update(motivo="Prazo vencido, mas a regra exige decisão humana.", proxima_acao="Aprovar follow-up assistido")
                else:
                    contadores["outros"] += 1
                    diagnostico["motivo"] = f"Estado de follow-up não classificado: {est_fu or 'vazio'}."
        elif estado == "CONTINUIDADE_ATUACAO_PREVIA":
            contadores["atuacao_previa_sem_acompanhamento"] += 1
            diagnostico.update(
                motivo="Há evidência de atuação anterior, mas o chamado não está na fila transacional de acompanhamento.",
                proxima_acao="Reconstruir acompanhamento / classificar última atuação",
            )
        elif estado == "CONTINUIDADE_ESTADO_REDMINE":
            contadores["estado_redmine_sem_acompanhamento"] += 1
            diagnostico.update(
                motivo="O Redmine indica continuidade, mas não existe acompanhamento transacional ativo.",
                proxima_acao="Classificar continuidade pelo histórico",
            )
        itens.append(diagnostico)

    print(
        "[EDDY] Continuidade diagnóstico | "
        + " | ".join(f"{k}={v}" for k, v in contadores.items()),
        flush=True,
    )
    return {"resumo": contadores, "itens": itens}


def reconstruir_continuidades_orfas(snapshot: pd.DataFrame, limite: int = 12) -> dict:
    """Reconstrói histórico dos chamados de continuidade que ficaram fora da máquina transacional.

    Esta etapa é deliberadamente conservadora: sincroniza journals e classifica a
    responsabilidade, mas NÃO envia e-mail nem altera o Redmine. Depois da
    reconstrução, o ciclo seguinte pode decidir follow-up, execução homologada,
    decisão humana ou devolução ao responsável de origem.
    """
    diagnostico = diagnosticar_continuidade_operacional(snapshot)
    orfaos = [
        x for x in diagnostico.get("itens", [])
        if x.get("estado_motor") in {"CONTINUIDADE_ATUACAO_PREVIA", "CONTINUIDADE_ESTADO_REDMINE"}
    ]
    if not orfaos:
        return {"candidatos": 0, "processados": 0, "sucesso": 0, "erros": 0, "itens": []}

    from ednna.sincronizador_journals import processar_chamado
    from ednna.primeiro_combate import autores_edi_do_dataframe
    autores_edi = autores_edi_do_dataframe(snapshot)
    resultados = []
    sucesso = erros = 0

    # Priorizamos os mais antigos/estagnados quando a coluna existir.
    ids = {int(x.get("chamado_id") or 0) for x in orfaos}
    frame = snapshot.copy()
    if "#" in frame.columns:
        frame["_eddy_id"] = pd.to_numeric(frame["#"], errors="coerce")
        frame = frame[frame["_eddy_id"].isin(ids)]
    if "Alterado" in frame.columns:
        frame["_eddy_alterado"] = pd.to_datetime(frame["Alterado"], errors="coerce", utc=True)
        frame = frame.sort_values("_eddy_alterado", ascending=True, na_position="first")

    for _, row in frame.head(max(1, int(limite))).iterrows():
        cid = int(float(row.get("#", 0)))
        try:
            item = processar_chamado(row, autores_edi)
            ok = bool(item.get("ok"))
            sucesso += int(ok)
            erros += int(not ok)
            resultados.append({
                "chamado_id": cid,
                "ok": ok,
                "situacao": item.get("situacao"),
                "teve_atuacao": bool(item.get("teve_atuacao")),
                "autor_primeira_atuacao": item.get("autor") or "",
                "data_primeira_atuacao": item.get("data") or "",
                "journals": int(item.get("journals") or 0),
                "erro": item.get("erro") or "",
            })
        except Exception as exc:
            erros += 1
            resultados.append({"chamado_id": cid, "ok": False, "situacao": "ERRO_RECONSTRUCAO", "erro": f"{type(exc).__name__}: {exc}"})

    print(
        f"[EDNNA] Retomada continuidade | candidatos={len(orfaos)} | "
        f"processados={len(resultados)} | sucesso={sucesso} | erros={erros} | "
        f"ids={[x.get('chamado_id') for x in resultados]}",
        flush=True,
    )
    return {"candidatos": len(orfaos), "processados": len(resultados), "sucesso": sucesso, "erros": erros, "itens": resultados}


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
        "CHECKPOINT_HUMANO": ("PRECISA_DE_VOCE", "Workflow automático aguardando checkpoint humano"),
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
        "domicilios_bancarios": dados.get("domicilios_bancarios") or [],
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
    print(f"[EDDY] Operação assistida preparada | chamado={pacote['chamado_id']} | player={pacote['player']} | regra={pacote['regra_id']} | estado=AGUARDANDO_CONFIRMACAO_HUMANA", flush=True)
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
        destinatario = "conciliacao@upbrasil.com"
    if player == "GREENCARD" and not destinatario:
        destinatario = "suporte.credenciado@grupogreencard.com.br"
    if not destinatario:
        return {"ok": False, "motivo": "Destinatário não confirmado."}
    cliente=str(pacote.get("cliente") or "Cliente")
    cid=int(pacote.get("chamado_id") or 0)
    ecs=[str(x) for x in (pacote.get("estabelecimentos") or []) if str(x).strip()]
    cnpjs=[str(x) for x in (pacote.get("cnpjs") or []) if str(x).strip()]
    matriz=str(pacote.get("cnpj_matriz") or "").strip()

    if player == "GREENCARD":
        destinatario = "suporte.credenciado@grupogreencard.com.br"
        assunto=f"[GREENCARD - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
        linhas=[
            "Olá, Time Greencard!", "",
            "Por gentileza, solicitamos a inclusão de estabelecimento no tráfego de dados EDI para nosso cliente abaixo detalhado.", "",
            f"Cliente: {cliente}",
        ]
        if cnpjs:
            linhas.append("CNPJ(s): " + "; ".join(cnpjs))
        if ecs:
            linhas.append("Estabelecimento(s) / EC(s) solicitado(s): " + "; ".join(ecs))
        linhas += [
            "",
            "Os arquivos deverão ser disponibilizados na CAIXA POSTAL NETUNNA junto à Greencard.", "",
            "Agradecemos e ficamos à disposição para quaisquer esclarecimentos.", "",
            "Atenciosamente,", "Equipe EDI Netunna", "",
            "Mensagem operacional preparada e acompanhada pela EDNNA — Automação EDI Netunna."
        ]
        return {
            "ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),
            "para":[destinatario],"cc":aplicar_cc_cliente([destinatario], [], cliente),
            "assunto":assunto,"corpo":"\n".join(linhas),"prazo_resposta_dias_uteis":2,
            "tipo_acao":"SOLICITAR_INCLUSAO_GREENCARD","status_pos_envio":"Aguardando Retorno Adquirente"
        }

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
        domicilios=list(pacote.get("domicilios_bancarios") or [])
        if not destinatario or not contas:
            faltam=[]
            if not destinatario: faltam.append("contato/e-mail do gerente no Blueprint")
            if not contas: faltam.append("conta(s) bancária(s) no chamado")
            return {"ok":False,"motivo":"SICREDI: faltam dados para abertura: " + ", ".join(faltam) + ".","estado":"AGUARDANDO_DADOS"}
        assunto=f"[SICREDI (BANCO) - Abertura de Relacionamento - {cliente} - CN: {cid}]"
        linhas=["Olá, tudo bem?", "", "Por gentileza, solicitamos a Abertura de Relacionamento para a Habilitação de Tráfego de Arquivos de Extrato de Conciliação Bancária para os seguintes domicílios bancários - via VAN SUPPLY MIDIA:", ""]
        cnpjs=[str(x) for x in (pacote.get("cnpjs") or []) if str(x).strip()]
        if cliente: linhas += [f"Cliente: {cliente}"]
        if cnpjs: linhas += [f"CNPJ: {', '.join(cnpjs)}"]
        if domicilios:
            linhas += [f"Agência: {d.get('agencia','—')} / Conta: {d.get('conta','—')}" for d in domicilios]
        else:
            linhas += [f"Conta: {x}" for x in contas]
        linhas += ["", 'O arquivo de extrato de conciliação bancária deve estar no Layout 240 padrão Febraban 5.0 "Aberto" e Diário.', "", "Ficamos à disposição para quaisquer esclarecimentos."]
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
        from ednna.email_policy import aplicar_politica_destinatarios
        _base_para=["conciliacao@upbrasil.com"]
        _base_cc=aplicar_cc_cliente(_base_para, [], cliente)
        _policard_para, _policard_cc, _policard_policy = aplicar_politica_destinatarios("POLICARD", "CONCILIACAO", _base_para, _base_cc)
        return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":_policard_para,"cc":_policard_cc,"politica_destinatarios":_policard_policy,"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2,"tipo_acao":"SOLICITAR_INCLUSAO_POLICARD","status_pos_envio":"Aguardando Retorno Adquirente"}

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
    # v3.32.5 — barreira global: imediatamente antes de qualquer envio,
    # confirme no Redmine que o chamado continua ativo. Snapshot/cache nunca
    # autoriza envio para Rejeitada/Concluído/Cancelado/Fechado.
    from ednna.status_guard import preflight_chamado_ativo, encerrar_acompanhamento_terminal
    preflight = preflight_chamado_ativo(cid)
    if preflight.get("bloquear"):
        if preflight.get("motivo") == "ESTADO_TERMINAL":
            encerrar_acompanhamento_terminal(cid, preflight.get("estado") or "")
        print(f"[EDDY] Execução BLOQUEADA pre-flight | chamado={cid} | regra={rid} | motivo={preflight.get('motivo')} | estado={preflight.get('estado') or '-'}", flush=True)
        return {"ok":False,"estado":"IGNORADO_ESTADO_TERMINAL" if preflight.get("motivo")=="ESTADO_TERMINAL" else "PREFLIGHT_INDISPONIVEL",
                "motivo":f"Envio bloqueado pelo pre-flight Redmine: {preflight.get('estado') or preflight.get('motivo')}.",
                "preflight":preflight}
    print(f"[EDDY] Execução solicitada | chamado={cid} | player={pacote.get('player')} | regra={rid}", flush=True)
    adquirido, estado=adquirir_envio(cid,rid)
    if not adquirido:
        estado_atual = str((estado or {}).get("estado") or "DESCONHECIDO")
        enviado = bool(str((estado or {}).get("enviado_em") or "").strip())
        motivo = "E-mail já enviado; chamado está em acompanhamento." if enviado else "Execução já está em andamento. Aguarde alguns instantes e atualize a tela."
        print(f"[EDDY] Execução não adquirida | chamado={cid} | regra={rid} | estado={estado_atual} | enviado={enviado}", flush=True)
        return {"ok":False,"motivo":motivo,"estado":estado_atual,"acompanhamento":estado}
    print(f"[EDDY] Executor adquirido | chamado={cid} | regra={rid} | estado=EXECUTANDO", flush=True)
    try:
        print(f"[EDDY] Graph | iniciando envio | chamado={cid} | para={','.join(r.get('para') or [])}", flush=True)
        mail=enviar_email_graph(remetente=r["remetente"],para=r["para"],cc=r["cc"],assunto=r["assunto"],corpo=r["corpo"],anexos=r.get("anexos") or [],chamado_id=cid)
        print(f"[EDDY] Graph | HTTP 202 aceito | chamado={cid}", flush=True)
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
                print(f"[EDDY] Graph | SENT_ITEMS_CONFIRMED | chamado={cid} | message_id={mail.get('message_id') or 'n/d'} | enviado_em={mail.get('sent_datetime') or 'n/d'}", flush=True)
            else:
                mail["sent_items_confirmed"]=False
                print(f"[EDDY] Graph | SENT_ITEMS_PENDING | chamado={cid} | HTTP202=confirmado", flush=True)
        except Exception as sent_exc:
            mail["sent_items_confirmed"]=False
            mail["sent_items_warning"]=f"{type(sent_exc).__name__}: {sent_exc}"
            print(f"[EDDY] Graph | SENT_ITEMS_CHECK_ERROR | chamado={cid} | {type(sent_exc).__name__}: {sent_exc}", flush=True)
        acomp=confirmar_envio_real(cid,rid,prazo_dias_uteis=r["prazo_resposta_dias_uteis"],email_assunto=r["assunto"],graph_message_id=mail.get("message_id",""),graph_conversation_id=mail.get("conversation_id",""),graph_internet_message_id=mail.get("internet_message_id",""),enviado_em_real=mail.get("sent_datetime",""))
        print(f"[EDNNA] Acompanhamento | chamado={cid} | estado=AGUARDANDO_RESPOSTA", flush=True)
        if pacote.get("player") in {"GREENCARD", "ROTACARD"}:
            try:
                from ednna.greencard_workflow import registrar_estado, registrar_movimentacao_bp
                if pacote.get("player") == "GREENCARD":
                    registrar_estado(pacote, "AGUARDANDO_GREENCARD", assunto=r.get("assunto"), ec_solicitado=list(pacote.get("estabelecimentos") or []))
                    bp_msg=(f"Chamado #{cid}: solicitação de inclusão de estabelecimento enviada diretamente ao Suporte Credenciado Greencard. "
                            "Arquivos solicitados para a CAIXA POSTAL NETUNNA. Estado EDNNA: AGUARDANDO_GREENCARD.")
                else:
                    registrar_estado(pacote, "AGUARDANDO_CLIENTE", formulario_nome=((r.get("formulario") or {}).get("filename") or ""), assunto=r.get("assunto"))
                    bp_msg=f"Chamado #{cid}: formulário ROTACARD pré-preenchido e enviado ao cliente para revisão, complemento e assinatura. Estado EDNNA: AGUARDANDO_CLIENTE."
                bp_res=registrar_movimentacao_bp(pacote, bp_msg)
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
