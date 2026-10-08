from __future__ import annotations

"""Motor de continuidade da EDNNA — follow-up elegante e controlado."""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ednna.acompanhamento_acoes import listar_acoes_aguardando_resposta, marcar_redmine_atualizado, marcar_status_redmine
from ednna.email_sender import responder_todos_email_graph
from ednna.email_identity import finalizar_email
from ednna.redmine_outbox import registrar_ou_enfileirar
from ednna.aprendizado_operacional import obter_autorizacao_motor

TZ = ZoneInfo("America/Sao_Paulo")


def _agora(): return datetime.now(TZ)

def _parse(v):
    try:
        d = datetime.fromisoformat(str(v or "").replace("Z", "+00:00"))
        if d.tzinfo is None: d = d.replace(tzinfo=TZ)
        return d.astimezone(TZ)
    except Exception: return None


def _texto_followup(acao: dict, numero: int) -> str:
    chamado = int(acao.get("chamado_id") or 0)
    regra_id = str(acao.get("regra_id") or "").upper()
    if "VR-BENEFICIOS" in regra_id:
        if numero <= 1:
            return finalizar_email(
                "Olá, tudo bem?\n\n"
                "Passando para verificar se conseguiram realizar a habilitação da NETUNNA no Portal VR para o(s) CNPJ(s) informado(s).\n\n"
                "Quando possível, pedimos, por gentileza, que nos confirmem o retorno para que possamos dar continuidade ao acompanhamento da recepção dos arquivos.\n\n"
                "Caso tenham encontrado alguma dificuldade no procedimento, permanecemos à disposição."
            )
        return finalizar_email(
            "Olá, tudo bem?\n\n"
            "Retomando o acompanhamento da habilitação da NETUNNA no Portal VR, ainda não identificamos a confirmação na conversa.\n\n"
            "Poderiam, por gentileza, nos atualizar sobre o andamento ou informar se há alguma dificuldade para concluir a habilitação?\n\n"
            "Permanecemos à disposição."
        )
    if numero <= 1:
        return finalizar_email(
            "Olá, tudo bem?\n\n"
            "Retomando nossa solicitação encaminhada anteriormente, "
            f"referente ao atendimento #{chamado}.\n\n"
            "Poderiam, por gentileza, nos informar se a solicitação já está em análise "
            "ou se há alguma informação adicional necessária para continuidade?\n\n"
            "Permanecemos à disposição."
        )
    return finalizar_email(
        "Olá, tudo bem?\n\n"
        f"Gostaríamos de acompanhar novamente a solicitação referente ao atendimento #{chamado}. "
        "Até o momento não identificamos retorno na conversa.\n\n"
        "Quando possível, pedimos a gentileza de nos atualizar sobre o andamento ou indicar "
        "eventual pendência para que possamos dar continuidade.\n\n"
        "Agradecemos desde já."
    )


def _regra_catalogo_automatica(regra_id: str) -> bool:
    """Regras do catálogo clássico (ex.: SIM REDE) podem ser automáticas sem
    passar pela autorização das inclusões. Mantemos as duas fontes compatíveis.
    """
    try:
        import json
        from pathlib import Path
        arq = Path(__file__).with_name("catalogo_operacional.json")
        payload = json.loads(arq.read_text(encoding="utf-8"))
        for regra in payload.get("regras", []) or []:
            if str(regra.get("id") or "") == str(regra_id or ""):
                return bool(regra.get("executavel", False) and regra.get("auto_executar", False))
    except Exception:
        pass
    return False


def modo_followup_regra(regra_id: str) -> str:
    """AUTOMATICO somente quando a própria regra foi entregue à EDNNA.
    Regra assistida continua exigindo decisão humana também nos follow-ups.
    """
    rid = str(regra_id or "").strip()
    if _regra_catalogo_automatica(rid):
        return "AUTOMATICO"
    try:
        modo = str((obter_autorizacao_motor(rid) or {}).get("modo") or "").upper().strip()
        if modo == "AUTOMATICA":
            return "AUTOMATICO"
        if modo == "ASSISTIDA":
            return "ASSISTIDO"
    except Exception:
        pass
    return "ASSISTIDO"


def followup_automatico(item: dict) -> bool:
    return str(item.get("modo_followup") or modo_followup_regra(str(item.get("regra_id") or ""))).upper() == "AUTOMATICO"

def avaliar_followups() -> dict:
    acoes = listar_acoes_aguardando_resposta()
    agora = _agora()
    itens=[]
    for a in acoes:
        prazo=_parse(a.get("prazo_resposta_em"))
        n=int(a.get("followup_count") or 0)
        ultimo=_parse(a.get("followup_ultimo_em"))
        maximo=int(os.getenv("EDNNA_FOLLOWUP_MAX", "2") or 2)
        if n >= maximo:
            estado="LIMITE_FOLLOWUP"
        elif not prazo or agora <= prazo:
            estado="AGUARDANDO_PRAZO"
        elif ultimo and agora < ultimo + timedelta(hours=int(os.getenv("EDNNA_FOLLOWUP_MIN_HOURS", "24") or 24)):
            estado="AGUARDANDO_INTERVALO"
        elif not str(a.get("graph_message_id") or "").strip():
            estado="SEM_THREAD"
        else:
            estado="FOLLOWUP_PRONTO"
        itens.append({**a,"estado_followup":estado,"proximo_followup":n+1,"texto_followup":_texto_followup(a,n+1),"modo_followup":modo_followup_regra(str(a.get("regra_id") or ""))})
    # Prioridade operacional: prazo original mais antigo primeiro. Sem prazo,
    # a tarefa permanece visível, mas não recebe vencimento inventado.
    itens.sort(key=lambda x: (
        0 if x.get("estado_followup") == "FOLLOWUP_PRONTO" else 1,
        0 if followup_automatico(x) else 1,
        _parse(x.get("prazo_resposta_em")) or datetime.max.replace(tzinfo=TZ),
        int(x.get("chamado_id") or 0),
    ))
    prontos=sum(x["estado_followup"]=="FOLLOWUP_PRONTO" for x in itens)
    automaticos=sum(x["estado_followup"]=="FOLLOWUP_PRONTO" and followup_automatico(x) for x in itens)
    assistidos=prontos-automaticos
    return {"total":len(itens),"prontos":prontos,"automaticos_prontos":automaticos,"assistidos_prontos":assistidos,"itens":itens}


def registrar_followup(chamado_id:int, regra_id:str) -> None:
    # import local evita acoplamento circular
    from ednna.acompanhamento_acoes import _conectar, _iso, _agora
    with _conectar() as conn:
        conn.execute("""UPDATE acoes_operacionais SET followup_count=COALESCE(followup_count,0)+1,
            followup_ultimo_em=?, atualizado_em=? WHERE chamado_id=? AND regra_id=?""",
            (_iso(_agora()),_iso(_agora()),int(chamado_id),str(regra_id)))


def _chave_followup(chamado_id: int, regra_id: str, numero: int) -> str:
    import hashlib
    digest = hashlib.sha256(str(regra_id).encode("utf-8")).hexdigest()[:16]
    return f"eddy_followup:{int(chamado_id)}:{digest}:{int(numero)}"


def _reservar_followup(chave: str) -> str | None:
    """Uma tentativa por etapa; em falha ambígua, preservar bloqueio para revisão."""
    import uuid
    from painel_cache import adquirir_lock
    dono = uuid.uuid4().hex
    return dono if adquirir_lock(chave, dono, ttl_seconds=86400) else None


def executar_followup(item:dict) -> dict:
    if item.get("estado_followup") != "FOLLOWUP_PRONTO":
        return {"ok":False,"estado":item.get("estado_followup"),"motivo":"Follow-up ainda não está elegível."}
    remetente=str(os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br") or "").strip()
    chamado_id=int(item["chamado_id"]); regra_id=str(item["regra_id"]); numero=int(item["proximo_followup"])
    from ednna.status_guard import preflight_chamado_ativo, encerrar_acompanhamento_terminal
    preflight=preflight_chamado_ativo(chamado_id)
    if preflight.get("bloquear"):
        if preflight.get("motivo") in {"ESTADO_TERMINAL", "ESTADO_TERMINAL_QUARENTENA"}:
            encerrar_acompanhamento_terminal(chamado_id, preflight.get("estado") or "")
        print(f"[EDNNA] Follow-up BLOQUEADO pre-flight | chamado={chamado_id} | regra={regra_id} | motivo={preflight.get('motivo')} | estado={preflight.get('estado') or '-'}", flush=True)
        from ednna.observabilidade import log_event
        log_event("FOLLOWUP", "Follow-up bloqueado pelo pre-flight", nivel="BLOCKED", chamado_id=chamado_id, regra_id=regra_id, detalhe=f"motivo={preflight.get('motivo')} | estado={preflight.get('estado') or '-'}")
        return {"ok":False,"estado":"IGNORADO_ESTADO_TERMINAL" if preflight.get("motivo") in {"ESTADO_TERMINAL", "ESTADO_TERMINAL_QUARENTENA"} else "PREFLIGHT_INDISPONIVEL",
                "motivo":"Follow-up bloqueado pelo estado atual do Redmine.","preflight":preflight}
    # O pre-flight não substitui a idempotência: duas instâncias podem ler o
    # mesmo item elegível. O lock evita concorrência; falha ambígua é retida.
    from painel_cache import liberar_lock
    chave = _chave_followup(chamado_id, regra_id, numero)
    dono = _reservar_followup(chave)
    if dono is None:
        return {"ok": False, "estado": "FOLLOWUP_EM_EXECUCAO_OU_RECONCILIACAO",
                "motivo": "Outra tentativa ou reconciliação já reservou este follow-up.",
                "chamado_id": chamado_id, "regra_id": regra_id}
    texto=str(item.get("texto_followup") or "")
    try:
        resultado=responder_todos_email_graph(
            remetente=remetente, message_id=str(item.get("graph_message_id") or ""), comentario=texto, chamado_id=chamado_id
        )
    except Exception as exc:
        from ednna.observabilidade import log_event
        log_event("FOLLOWUP", "Envio de resultado ambíguo; reconciliação necessária",
                  nivel="BLOCKED", chamado_id=chamado_id, regra_id=regra_id,
                  detalhe=f"numero={numero} | tipo={type(exc).__name__}")
        # Não liberar o lease após erro: um timeout pode ocorrer após o Graph
        # aceitar o envio. A reconciliação deve ocorrer antes de qualquer retry.
        return {"ok": False, "estado": "ENVIO_INCERTO_RECONCILIAR",
                "motivo": "Falha ou timeout Graph; verificar Sent Items/thread antes de repetir.",
                "chamado_id": chamado_id, "regra_id": regra_id}
    if isinstance(resultado, dict) and resultado.get("ok") is True:
        liberar_lock(chave, dono, detalhes="GRAPH_ACEITO")
    # Resultado não confirmado permanece reservado para reconciliação.
    # Nunca contabilizar um follow-up como enviado quando o Graph não confirmou
    # o resultado. Falhas ambíguas exigem reconciliação da thread antes de retry.
    if not isinstance(resultado, dict) or resultado.get("ok") is not True:
        from ednna.observabilidade import log_event
        log_event("FOLLOWUP", "Envio sem confirmação; reconciliar antes de tentar novamente",
                  nivel="BLOCKED", chamado_id=chamado_id, regra_id=regra_id,
                  detalhe=f"numero={numero} | resultado={str(resultado)[:300]}")
        return {"ok": False, "estado": "ENVIO_NAO_CONFIRMADO",
                "motivo": "Graph não confirmou o envio; verificar a thread antes de repetir.",
                "chamado_id": chamado_id, "regra_id": regra_id, "resultado": resultado}
    registrar_followup(chamado_id,regra_id)

    # Follow-up também é atuação operacional: sempre gera journal no Redmine e
    # mantém o chamado no estado de espera correspondente. Se o Redmine falhar,
    # a atualização entra na outbox sem repetir o e-mail.
    status_nome=str(item.get("redmine_status_nome") or item.get("redmine_pendente_status") or "").strip()
    if not status_nome:
        status_nome = "Aguardando Retorno Cliente" if "VR-BENEFICIOS" in regra_id.upper() else "Aguardando Retorno Adquirente"
    nota=(
        f"*EDNNA — Follow-up {numero} enviado*\n\n"
        f"{texto.strip()}\n\n----\n\n"
        "*Acompanhamento EDNNA:* aguardando retorno após nova cobrança."
    )
    redmine=registrar_ou_enfileirar(
        chamado_id=chamado_id, regra_id=regra_id, nota=nota, status_nome=status_nome
    )
    if redmine.get("ok"):
        marcar_redmine_atualizado(chamado_id,regra_id)
        marcar_status_redmine(chamado_id,regra_id,status_nome)
    print(
        f"[EDNNA] Follow-up enviado | chamado={chamado_id} | regra={regra_id} | numero={numero} | redmine={'OK' if redmine.get('ok') else 'PENDENTE'}",
        flush=True,
    )
    from ednna.observabilidade import log_event
    log_event("FOLLOWUP", "Follow-up enviado", chamado_id=chamado_id, regra_id=regra_id, detalhe=f"numero={numero} | redmine={'OK' if redmine.get('ok') else 'PENDENTE'}")
    return {**resultado,"chamado_id":chamado_id,"regra_id":regra_id,"numero":numero,"redmine":redmine}
