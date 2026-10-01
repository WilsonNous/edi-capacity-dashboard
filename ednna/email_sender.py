from __future__ import annotations

import os
import re
import base64
from typing import Iterable

import requests

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

class EmailConfigError(RuntimeError): pass
class EmailSendError(RuntimeError): pass

def _obrigatoria(nome: str) -> str:
    valor=str(os.getenv(nome,"") or "").strip()
    if not valor: raise EmailConfigError(f"Variável obrigatória ausente: {nome}")
    return valor

def _destinatarios(lista: Iterable[str]) -> list[dict]:
    return [{"emailAddress":{"address":str(e).strip()}} for e in (lista or []) if str(e or "").strip()]

def obter_token_graph() -> str:
    resposta=requests.post(TOKEN_URL_TEMPLATE.format(tenant_id=_obrigatoria("AZURE_TENANT_ID")),data={"client_id":_obrigatoria("AZURE_CLIENT_ID"),"client_secret":_obrigatoria("AZURE_CLIENT_SECRET"),"scope":"https://graph.microsoft.com/.default","grant_type":"client_credentials"},timeout=20)
    if resposta.status_code!=200: raise EmailSendError(f"Falha ao obter token do Microsoft Graph: HTTP {resposta.status_code} - {resposta.text[:500]}")
    token=str(resposta.json().get("access_token","") or "").strip()
    if not token: raise EmailSendError("Microsoft Graph não retornou access_token.")
    return token

def _graph_get(url: str, *, params: dict|None=None, timeout:int=30) -> dict:
    resposta=requests.get(url,headers={"Authorization":f"Bearer {obter_token_graph()}","Accept":"application/json"},params=params or {},timeout=timeout)
    if resposta.status_code!=200: raise EmailSendError(f"Falha ao consultar Microsoft Graph: HTTP {resposta.status_code} - {resposta.text[:800]}")
    return resposta.json()

def enviar_email_graph(*,remetente:str,para:list[str],cc:list[str],assunto:str,corpo:str,anexos:list[dict]|None=None,chamado_id:int|None=None)->dict:
    remetente=str(remetente or os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br") or "").strip()
    if not remetente: raise EmailConfigError("Remetente não configurado.")
    if not para: raise EmailConfigError("Nenhum destinatário informado.")
    if chamado_id is None or int(chamado_id or 0)<=0: raise EmailSendError("Envio bloqueado: chamado_id é obrigatório para o pre-flight Redmine.")
    from ednna.status_guard import validar_efeito_externo
    pf=validar_efeito_externo(int(chamado_id),"EMAIL_GRAPH_SEND")
    if pf.get("bloquear"): raise EmailSendError(f"Envio bloqueado pelo pre-flight Redmine: {pf.get('estado') or pf.get('motivo')}.")
    payload={"message":{"subject":assunto,"body":{"contentType":"Text","content":corpo},"toRecipients":_destinatarios(para),"ccRecipients":_destinatarios(cc)},"saveToSentItems":True}
    if anexos: payload["message"]["attachments"]=[{"@odata.type":"#microsoft.graph.fileAttachment","name":str(a.get("filename") or "anexo.bin"),"contentType":str(a.get("content_type") or "application/octet-stream"),"contentBytes":base64.b64encode(bytes(a.get("conteudo") or b"")).decode("ascii")} for a in anexos if a.get("conteudo")]
    resposta=requests.post(f"{GRAPH_BASE_URL}/users/{remetente}/sendMail",headers={"Authorization":f"Bearer {obter_token_graph()}","Content-Type":"application/json"},json=payload,timeout=30)
    if resposta.status_code!=202: raise EmailSendError(f"Falha ao enviar e-mail pelo Microsoft Graph: HTTP {resposta.status_code} - {resposta.text[:800]}")
    resultado={"ok":True,"status_code":202,"remetente":remetente,"para":list(para),"cc":list(cc),"assunto":assunto,"message_id":"","conversation_id":"","internet_message_id":""}
    try:
        enviado=localizar_email_enviado(remetente=remetente,assunto=assunto); resultado["message_id"]=str(enviado.get("id","") or ""); resultado["conversation_id"]=str(enviado.get("conversationId","") or ""); resultado["internet_message_id"]=str(enviado.get("internetMessageId","") or "")
    except Exception as exc: resultado["metadata_warning"]=str(exc)[:500]
    return resultado

def baixar_mensagem_eml(*,caixa_postal:str,message_id:str)->bytes:
    caixa_postal=str(caixa_postal or "").strip(); message_id=str(message_id or "").strip()
    if not caixa_postal or not message_id: raise EmailConfigError("Caixa postal/message_id ausente para gerar evidência .eml.")
    resposta=requests.get(f"{GRAPH_BASE_URL}/users/{caixa_postal}/messages/{message_id}/$value",headers={"Authorization":f"Bearer {obter_token_graph()}","Accept":"message/rfc822"},timeout=45)
    if resposta.status_code!=200: raise EmailSendError(f"Falha ao baixar e-mail original pelo Microsoft Graph: HTTP {resposta.status_code} - {resposta.text[:500]}")
    return bytes(resposta.content)

def localizar_email_enviado(*,remetente:str,assunto:str)->dict:
    dados=_graph_get(f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",params={"$select":"id,subject,conversationId,internetMessageId,sentDateTime","$orderby":"sentDateTime desc","$top":"25"}); alvo=str(assunto or "").strip().casefold()
    for item in dados.get("value",[]):
        if str(item.get("subject","") or "").strip().casefold()==alvo:return item
    return {}

def listar_mensagens_conversa(*,caixa_postal:str,conversation_id:str,recebidas_apos:str="")->list[dict]:
    dados=_graph_get(f"{GRAPH_BASE_URL}/users/{caixa_postal}/mailFolders/inbox/messages",params={"$select":"id,subject,conversationId,internetMessageId,receivedDateTime,from,body,bodyPreview,isRead","$orderby":"receivedDateTime desc","$top":"500"}); itens=[]; alvo=str(conversation_id or "")
    for item in dados.get("value",[]) or []:
        if str(item.get("conversationId","") or "")!=alvo:continue
        if recebidas_apos and str(item.get("receivedDateTime","") or "")<str(recebidas_apos):continue
        itens.append(item)
    itens.sort(key=lambda x:str(x.get("receivedDateTime","") or "")); return itens

def _assunto_referencia_chamado(assunto:str,chamado_id:int)->bool:
    texto=str(assunto or ""); cid=str(int(chamado_id)); padroes=[rf"#\s*{re.escape(cid)}\b",rf"\bCN\s*[:#-]?\s*{re.escape(cid)}\b",rf"\[\s*{re.escape(cid)}\s*\]"]
    return any(re.search(p,texto,flags=re.IGNORECASE) for p in padroes)

def listar_emails_enviados_por_chamado(*,remetente:str,chamado_id:int,top:int=500)->list[dict]:
    dados=_graph_get(f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",params={"$select":"id,subject,conversationId,internetMessageId,sentDateTime,from,toRecipients,ccRecipients,body,bodyPreview","$orderby":"sentDateTime desc","$top":str(max(25,min(int(top or 500),500)))}); itens=[x for x in dados.get("value",[]) or [] if _assunto_referencia_chamado(str(x.get("subject") or ""),int(chamado_id))]; itens.sort(key=lambda x:str(x.get("sentDateTime") or "")); return itens

def localizar_email_enviado_por_chamado(*,remetente:str,chamado_id:int)->dict:
    dados=_graph_get(f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",params={"$select":"id,subject,conversationId,internetMessageId,sentDateTime,from,toRecipients,ccRecipients","$orderby":"sentDateTime desc","$top":"250"})
    for item in dados.get("value",[]) or []:
        if _assunto_referencia_chamado(str(item.get("subject","") or ""),int(chamado_id)):return item
    return {}

def localizar_resposta_por_chamado(*,caixa_postal:str,chamado_id:int,recebidas_apos:str="")->dict:
    """Fallback por #ID, CN: ID ou [ID]. To e CC funcionam porque a mensagem já está na Inbox da caixa operacional."""
    dados=_graph_get(f"{GRAPH_BASE_URL}/users/{caixa_postal}/mailFolders/inbox/messages",params={"$select":"id,subject,conversationId,internetMessageId,receivedDateTime,from,body,bodyPreview,isRead","$orderby":"receivedDateTime desc","$top":"500"})
    for item in dados.get("value",[]) or []:
        assunto=str(item.get("subject","") or "")
        if not _assunto_referencia_chamado(assunto,int(chamado_id)):continue
        if recebidas_apos and str(item.get("receivedDateTime","") or "")<str(recebidas_apos):continue
        return item
    return {}

def listar_envios_cancelamento_getnet(*,remetente:str,top:int=250)->list[dict]:
    dados=_graph_get(f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",params={"$select":"id,subject,conversationId,internetMessageId,sentDateTime,from,toRecipients,ccRecipients","$orderby":"sentDateTime desc","$top":str(max(25,min(int(top or 250),500)))}); resultado=[]
    for item in dados.get("value",[]) or []:
        assunto=str(item.get("subject","") or ""); baixo=assunto.casefold()
        if "getnet" not in baixo or "cancel" not in baixo:continue
        m=re.search(r"#\s*(\d{3,})\b",assunto)
        if not m:continue
        copia=dict(item); copia["chamado_id"]=int(m.group(1)); resultado.append(copia)
    return resultado

def _texto_para_html(texto:str)->str:
    import html
    bruto=str(texto or "").replace("\r\n","\n").replace("\r","\n").strip(); paragrafos=[p.strip() for p in bruto.split("\n\n") if p.strip()]; return "".join(f"<p>{html.escape(p).replace(chr(10),'<br>')}</p>" for p in paragrafos)

def responder_todos_email_graph(*,remetente:str,message_id:str,comentario:str,chamado_id:int)->dict:
    remetente=str(remetente or os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br") or "").strip(); message_id=str(message_id or "").strip(); comentario=str(comentario or "").strip()
    if not remetente:raise EmailConfigError("Remetente não configurado.")
    if not message_id:raise EmailConfigError("Mensagem original não localizada para follow-up.")
    if not comentario:raise EmailConfigError("Comentário do follow-up está vazio.")
    from ednna.status_guard import validar_efeito_externo
    pf=validar_efeito_externo(int(chamado_id),"EMAIL_GRAPH_REPLY_ALL")
    if pf.get("bloquear"):raise EmailSendError(f"Follow-up bloqueado pelo pre-flight Redmine: {pf.get('estado') or pf.get('motivo')}.")
    resposta=requests.post(f"{GRAPH_BASE_URL}/users/{remetente}/messages/{message_id}/replyAll",headers={"Authorization":f"Bearer {obter_token_graph()}","Content-Type":"application/json"},json={"comment":comentario},timeout=30)
    if resposta.status_code!=202:raise EmailSendError(f"Falha ao responder Reply All pelo Microsoft Graph: HTTP {resposta.status_code} - {resposta.text[:800]}")
    print(f"[EDNNA] Follow-up Graph | REPLY_ALL_ACCEPTED | message_id_origem={message_id}",flush=True); return {"ok":True,"status_code":202,"message_id_origem":message_id,"modo":"replyAll","envio_confirmado":True}

def confirmar_email_em_sent_items(*,remetente:str,chamado_id:int=0,assunto:str="")->dict:
    item={}
    if chamado_id:item=localizar_email_enviado_por_chamado(remetente=remetente,chamado_id=int(chamado_id))
    if not item and assunto:item=localizar_email_enviado(remetente=remetente,assunto=assunto)
    if not item:return {"confirmado":False}
    return {"confirmado":True,"message_id":str(item.get("id") or ""),"conversation_id":str(item.get("conversationId") or ""),"internet_message_id":str(item.get("internetMessageId") or ""),"sent_datetime":str(item.get("sentDateTime") or ""),"subject":str(item.get("subject") or "")}
