from __future__ import annotations

"""Fila operacional assistida de inclusões — v3.28.37.

Transforma inclusões ativas do snapshot em planos acionáveis usando somente
regras homologadas + autorização explícita do motor. Esta camada NÃO envia
e-mail, NÃO chama APIs e NÃO altera Redmine. Ela prepara o braço operacional.
"""

from typing import Any
import os
from ednna.email_identity import finalizar_email
import pandas as pd

from ednna.aprendizado_operacional import obter_regra_homologada, obter_autorizacao_motor
from ednna.planejador_inclusoes import descobrir_candidatos_inclusao, preparar_operacao_inclusao, _extrair_dados, _identificar_cnpj_matriz
from ednna.workflows_inclusao import obter_workflow


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
    return {
        **extraidos,
        "estabelecimento": list(extraidos.get("ecs") or []),
        "cnpj_matriz": _identificar_cnpj_matriz(extraidos.get("cnpjs") or []),
        "cliente": str(row.get("Clientes", "") or ""),
        "assunto": str(row.get("Assunto", "") or ""),
        "estado_redmine": str(row.get("Estado", "") or ""),
        "fonte": "SNAPSHOT_ATIVO",
    }


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
    }

    for candidato in inventario.get("candidatos", []) or []:
        players = candidato.get("players") or []
        if len(players) != 1:
            itens.append({**candidato, "estado_motor": "PLAYER_AMBIGUO", "acao_sugerida": "Revisar player"})
            continue
        player = str(players[0])
        regra = obter_regra_homologada(player)
        if not regra:
            contadores["nao_homologadas"] += 1
            itens.append({**candidato, "player": player, "estado_motor": "REGRA_NAO_HOMOLOGADA", "acao_sugerida": "Homologar regra"})
            continue
        contadores["homologadas"] += 1
        aut = obter_autorizacao_motor(str(regra.get("regra_id") or ""))
        if str(aut.get("modo") or "BLOQUEADA") != "ASSISTIDA":
            contadores["nao_autorizadas"] += 1
            itens.append({**candidato, "player": player, "regra_id": regra.get("regra_id"), "estado_motor": "REGRA_HOMOLOGADA_NAO_AUTORIZADA", "acao_sugerida": "Autorizar motor"})
            continue
        contadores["autorizadas"] += 1
        row = _row_por_id(snapshot, int(candidato["id"]))
        dados = _dados_snapshot(row)
        plano = preparar_operacao_inclusao(int(candidato["id"]), player, dados=dados)
        estado = str(plano.get("estado") or "")
        wf = plano.get("workflow") or obter_workflow(player)

        # E-mail assistido exige destinatário humano confirmado na homologação.
        destinatario = str(regra.get("destinatario_confirmado") or "").strip()
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
    if canal != "EMAIL":
        return {"ok": False, "motivo": f"Executor direto ainda não disponível para canal {canal}."}
    destinatario = str(pacote.get("destinatario") or "").strip()
    if not destinatario:
        return {"ok": False, "motivo": "Destinatário não confirmado."}
    player=str(pacote.get("player") or "")
    cliente=str(pacote.get("cliente") or "Cliente")
    cid=int(pacote.get("chamado_id") or 0)
    ecs=[str(x) for x in (pacote.get("estabelecimentos") or []) if str(x).strip()]
    matriz=str(pacote.get("cnpj_matriz") or "").strip()
    assunto=f"[{player} - Inclusão de Estabelecimento - {cliente} - CN: {cid}]"
    linhas=[f"Olá, time {player}, tudo bem?","","Por gentileza, solicitamos a inclusão no tráfego atual de arquivos para nosso cliente comum " + cliente + ".","",]
    if matriz: linhas += [f"CNPJ Matriz: {matriz}"]
    if ecs: linhas += ["Estabelecimento(s): " + ", ".join(ecs)]
    linhas += ["", "Estamos à disposição para quaisquer esclarecimentos."]
    corpo = finalizar_email("\n".join(linhas))
    return {"ok":True,"remetente":os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br"),"para":[destinatario],"cc":[],"assunto":assunto,"corpo":corpo,"prazo_resposta_dias_uteis":2}


def executar_atuacao_assistida_email(pacote: dict) -> dict:
    """Executa somente pacote EMAIL previamente preparado e confirmado na UI."""
    from ednna.acompanhamento_acoes import adquirir_envio, confirmar_envio_real, registrar_falha_envio
    from ednna.email_sender import enviar_email_graph
    r=gerar_rascunho_inclusao(pacote)
    if not r.get("ok"): return r
    cid=int(pacote.get("chamado_id") or 0); rid=str(pacote.get("regra_id") or "")
    adquirido, estado=adquirir_envio(cid,rid)
    if not adquirido:
        return {"ok":False,"motivo":"Ação já iniciada ou enviada.","acompanhamento":estado}
    try:
        mail=enviar_email_graph(remetente=r["remetente"],para=r["para"],cc=r["cc"],assunto=r["assunto"],corpo=r["corpo"])
        acomp=confirmar_envio_real(cid,rid,prazo_dias_uteis=r["prazo_resposta_dias_uteis"],email_assunto=r["assunto"],graph_message_id=mail.get("message_id",""),graph_conversation_id=mail.get("conversation_id",""),graph_internet_message_id=mail.get("internet_message_id",""))
        print(f"[EDNNA] Operação assistida EXECUTADA | chamado={cid} | player={pacote.get('player')} | regra={rid} | canal=EMAIL",flush=True)
        return {"ok":True,"estado":"AGUARDANDO_RESPOSTA","email":mail,"acompanhamento":acomp}
    except Exception as exc:
        registrar_falha_envio(cid,rid,str(exc)); raise
