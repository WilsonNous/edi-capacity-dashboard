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
    return {"total":len(itens),"prontos":sum(x["estado_followup"]=="FOLLOWUP_PRONTO" for x in itens),"itens":itens}


def registrar_followup(chamado_id:int, regra_id:str) -> None:
    # import local evita acoplamento circular
    from ednna.acompanhamento_acoes import _conectar, _iso, _agora
    with _conectar() as conn:
        conn.execute("""UPDATE acoes_operacionais SET followup_count=COALESCE(followup_count,0)+1,
            followup_ultimo_em=?, atualizado_em=? WHERE chamado_id=? AND regra_id=?""",
            (_iso(_agora()),_iso(_agora()),int(chamado_id),str(regra_id)))


def executar_followup(item:dict) -> dict:
    if item.get("estado_followup") != "FOLLOWUP_PRONTO":
        return {"ok":False,"estado":item.get("estado_followup"),"motivo":"Follow-up ainda não está elegível."}
    remetente=str(os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br") or "").strip()
    chamado_id=int(item["chamado_id"]); regra_id=str(item["regra_id"]); numero=int(item["proximo_followup"])
    texto=str(item.get("texto_followup") or "")
    resultado=responder_todos_email_graph(
        remetente=remetente, message_id=str(item.get("graph_message_id") or ""), comentario=texto
    )
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
    return {**resultado,"chamado_id":chamado_id,"regra_id":regra_id,"numero":numero,"redmine":redmine}
