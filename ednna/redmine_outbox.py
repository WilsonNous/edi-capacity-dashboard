from __future__ import annotations
"""Outbox resiliente para efeitos pós-envio no Redmine.

Contrato v3.28.55:
- e-mail enviado nunca é reenviado por falha do Redmine;
- start_date/due_date são sempre normalizados pelo writer;
- pendências legadas podem reconstruir a trilha REAL a partir de Sent Items.
"""
import html
import os
import re

from ednna.acompanhamento_acoes import (
    agendar_redmine_pendente,
    concluir_redmine_pendente,
    listar_redmine_pendentes,
    obter_acompanhamento,
)
from ednna.redmine_writer import (
    registrar_email_e_status_chamado,
    nota_marcador_ja_existe,
)


def _datas_acompanhamento(chamado_id: int, regra_id: str) -> tuple[str, str]:
    acao = obter_acompanhamento(int(chamado_id), str(regra_id)) or {}
    return str(acao.get("enviado_em") or ""), str(acao.get("prazo_resposta_em") or "")


def registrar_ou_enfileirar(*, chamado_id:int, regra_id:str, nota:str, status_nome:str, assigned_to_id:int|None=None) -> dict:
    data_inicio, data_fim = _datas_acompanhamento(chamado_id, regra_id)
    try:
        res=registrar_email_e_status_chamado(
            chamado_id=chamado_id, nota=nota, status_nome=status_nome,
            data_inicio=data_inicio, data_fim=data_fim,
            assigned_to_id=assigned_to_id,
        )
        concluir_redmine_pendente(chamado_id, regra_id, status_nome)
        return {"ok":True,"pendente":False,"redmine":res}
    except Exception as exc:
        agendar_redmine_pendente(
            chamado_id, regra_id, nota=nota, status_nome=status_nome,
            assigned_to_id=assigned_to_id, erro=f"{type(exc).__name__}: {exc}"
        )
        print(f"[EDNNA] Redmine pós-envio | PENDENTE chamado={chamado_id} | regra={regra_id} | {type(exc).__name__}: {exc}", flush=True)
        return {"ok":False,"pendente":True,"erro":f"{type(exc).__name__}: {exc}"}


def _emails(lista) -> str:
    saida=[]
    for x in lista or []:
        addr=((x or {}).get("emailAddress") or {}).get("address")
        if addr: saida.append(str(addr))
    return "; ".join(saida)


def _texto_corpo(item: dict) -> str:
    body=(item.get("body") or {})
    conteudo=str(body.get("content") or item.get("bodyPreview") or "")
    if str(body.get("contentType") or "").casefold()=="html":
        conteudo=re.sub(r"(?i)<br\s*/?>", "\n", conteudo)
        conteudo=re.sub(r"(?i)</p\s*>", "\n\n", conteudo)
        conteudo=re.sub(r"<[^>]+>", "", conteudo)
        conteudo=html.unescape(conteudo)
    return "\n".join(x.rstrip() for x in conteudo.replace("\r\n","\n").split("\n")).strip()


def _nota_sent_item(item: dict, indice: int) -> tuple[str,str]:
    mid=str(item.get("internetMessageId") or item.get("id") or "").strip()
    marcador=f"[EDNNA-EVIDENCIA:{mid}]"
    titulo="E-mail inicial" if indice==0 else f"Follow-up {indice}"
    nota=(
        f"*EDNNA — {titulo} recuperado de Itens Enviados*\n\n"
        f"*Enviado em:* {item.get('sentDateTime') or ''}\n"
        f"*Para:* {_emails(item.get('toRecipients'))}\n"
        f"*Cc:* {_emails(item.get('ccRecipients'))}\n"
        f"*Assunto:* {item.get('subject') or ''}\n\n"
        f"{_texto_corpo(item)}\n\n----\n{marcador}"
    ).strip()
    return nota, marcador


def reconstruir_historico_sent_items(*, chamado_id:int, regra_id:str, status_nome:str, assigned_to_id:int|None=None) -> dict:
    """Resgata e-mails já enviados antes/follow-ups e os grava cronologicamente no Redmine.

    Idempotência: cada journal recebe marcador do internetMessageId/message id e é
    ignorado se já existir no histórico do chamado.
    """
    from ednna.email_sender import listar_emails_enviados_por_chamado
    remetente=str(os.getenv("EDNNA_EMAIL_FROM","edi@netunna.com.br") or "").strip()
    itens=listar_emails_enviados_por_chamado(remetente=remetente, chamado_id=int(chamado_id))
    if not itens:
        return {"ok":False,"recuperados":0,"registrados":0,"motivo":"Nenhuma mensagem localizada em Sent Items."}
    data_inicio=str(itens[0].get("sentDateTime") or "")
    _, prazo=_datas_acompanhamento(chamado_id, regra_id)
    registrados=0; ignorados=0
    for idx,item in enumerate(itens):
        nota, marcador=_nota_sent_item(item,idx)
        if nota_marcador_ja_existe(chamado_id, marcador):
            ignorados += 1
            continue
        registrar_email_e_status_chamado(
            chamado_id=int(chamado_id), nota=nota, status_nome=status_nome,
            data_inicio=data_inicio, data_fim=prazo,
            assigned_to_id=assigned_to_id,
        )
        registrados += 1
        print(f"[EDNNA] Redmine histórico | RECUPERADO | chamado={chamado_id} | item={idx+1}/{len(itens)} | assunto={item.get('subject') or ''}", flush=True)
    concluir_redmine_pendente(chamado_id, regra_id, status_nome)
    return {"ok":True,"recuperados":len(itens),"registrados":registrados,"ignorados":ignorados}


def _reconciliar_item(item: dict) -> dict:
    cid=int(item.get('chamado_id') or 0); rid=str(item.get('regra_id') or '')
    status=str(item.get('redmine_pendente_status') or item.get('redmine_status_nome') or 'Aguardando Retorno Cliente')
    assigned=item.get('redmine_pendente_assigned_to_id')
    # Para pendências de e-mails já enviados, prioriza a fonte da verdade: Sent Items.
    try:
        hist=reconstruir_historico_sent_items(
            chamado_id=cid, regra_id=rid, status_nome=status, assigned_to_id=assigned
        )
        if hist.get('ok'):
            return {"ok":True,"chamado_id":cid,"historico":hist}
    except Exception as exc:
        print(f"[EDNNA] Redmine histórico | fallback outbox | chamado={cid} | {type(exc).__name__}: {exc}", flush=True)
    data_inicio,data_fim=_datas_acompanhamento(cid,rid)
    registrar_email_e_status_chamado(
        chamado_id=cid,
        nota=str(item.get('redmine_pendente_nota') or ''),
        status_nome=status,
        data_inicio=data_inicio, data_fim=data_fim,
        assigned_to_id=assigned,
    )
    concluir_redmine_pendente(cid,rid,status)
    return {"ok":True,"chamado_id":cid,"historico":{"fallback":True}}


def reconciliar_redmine_pendentes(limite:int=10) -> dict:
    itens=listar_redmine_pendentes()[:max(1,int(limite))]
    ok=[]; pend=[]
    for item in itens:
        cid=int(item.get('chamado_id') or 0); rid=str(item.get('regra_id') or '')
        try:
            _reconciliar_item(item); ok.append(cid)
        except Exception as exc:
            agendar_redmine_pendente(cid,rid,nota=str(item.get('redmine_pendente_nota') or ''),status_nome=str(item.get('redmine_pendente_status') or ''),assigned_to_id=item.get('redmine_pendente_assigned_to_id'),erro=f"{type(exc).__name__}: {exc}")
            pend.append(cid)
    if itens:
        print(f"[EDNNA] Redmine reconciliação | consultados={len(itens)} | atualizados={ok} | pendentes={pend}", flush=True)
    return {"consultados":len(itens),"atualizados":ok,"pendentes":pend}


def reconciliar_redmine_chamado(chamado_id:int, regra_id:str="") -> dict:
    """Força reconciliação sem tocar no envio de e-mail."""
    itens=[x for x in listar_redmine_pendentes() if int(x.get("chamado_id") or 0)==int(chamado_id)]
    if regra_id:
        itens=[x for x in itens if str(x.get("regra_id") or "")==str(regra_id)]
    if not itens:
        return {"consultados":0,"atualizados":[],"pendentes":[],"mensagem":"Nenhuma atualização Redmine pendente para este chamado."}
    ok=[]; pend=[]; erros=[]
    for item in itens:
        cid=int(item.get('chamado_id') or 0); rid=str(item.get('regra_id') or '')
        try:
            resultado=_reconciliar_item(item)
            ok.append(cid)
            print(f"[EDNNA] Redmine reconciliação MANUAL | OK | chamado={cid} | regra={rid} | historico={resultado.get('historico')}", flush=True)
        except Exception as exc:
            erro=f"{type(exc).__name__}: {exc}"
            agendar_redmine_pendente(cid,rid,nota=str(item.get('redmine_pendente_nota') or ''),status_nome=str(item.get('redmine_pendente_status') or ''),assigned_to_id=item.get('redmine_pendente_assigned_to_id'),erro=erro)
            pend.append(cid); erros.append(erro)
            print(f"[EDNNA] Redmine reconciliação MANUAL | PENDENTE | chamado={cid} | regra={rid} | {erro}", flush=True)
    return {"consultados":len(itens),"atualizados":ok,"pendentes":pend,"erros":erros}
