from __future__ import annotations
"""Outbox resiliente para efeitos pós-envio no Redmine."""
import os
from ednna.acompanhamento_acoes import agendar_redmine_pendente, concluir_redmine_pendente, listar_redmine_pendentes
from ednna.redmine_writer import registrar_email_e_status_chamado


def registrar_ou_enfileirar(*, chamado_id:int, regra_id:str, nota:str, status_nome:str, assigned_to_id:int|None=None) -> dict:
    try:
        res=registrar_email_e_status_chamado(chamado_id=chamado_id, nota=nota, status_nome=status_nome, assigned_to_id=assigned_to_id)
        concluir_redmine_pendente(chamado_id, regra_id, status_nome)
        return {"ok":True,"pendente":False,"redmine":res}
    except Exception as exc:
        agendar_redmine_pendente(chamado_id, regra_id, nota=nota, status_nome=status_nome, assigned_to_id=assigned_to_id, erro=f"{type(exc).__name__}: {exc}")
        print(f"[EDNNA] Redmine pós-envio | PENDENTE chamado={chamado_id} | regra={regra_id} | {type(exc).__name__}: {exc}", flush=True)
        return {"ok":False,"pendente":True,"erro":f"{type(exc).__name__}: {exc}"}


def reconciliar_redmine_pendentes(limite:int=10) -> dict:
    itens=listar_redmine_pendentes()[:max(1,int(limite))]
    ok=[]; pend=[]
    for item in itens:
        cid=int(item.get('chamado_id') or 0); rid=str(item.get('regra_id') or '')
        try:
            registrar_email_e_status_chamado(
                chamado_id=cid,
                nota=str(item.get('redmine_pendente_nota') or ''),
                status_nome=str(item.get('redmine_pendente_status') or 'Aguardando Retorno Cliente'),
                assigned_to_id=item.get('redmine_pendente_assigned_to_id'),
            )
            concluir_redmine_pendente(cid,rid,str(item.get('redmine_pendente_status') or ''))
            ok.append(cid)
        except Exception as exc:
            agendar_redmine_pendente(cid,rid,nota=str(item.get('redmine_pendente_nota') or ''),status_nome=str(item.get('redmine_pendente_status') or ''),assigned_to_id=item.get('redmine_pendente_assigned_to_id'),erro=f"{type(exc).__name__}: {exc}")
            pend.append(cid)
    if itens:
        print(f"[EDNNA] Redmine reconciliação | consultados={len(itens)} | atualizados={ok} | pendentes={pend}", flush=True)
    return {"consultados":len(itens),"atualizados":ok,"pendentes":pend}


def reconciliar_redmine_chamado(chamado_id:int, regra_id:str="") -> dict:
    """Força a reconciliação de um chamado sem tocar no envio de e-mail."""
    itens=[x for x in listar_redmine_pendentes() if int(x.get("chamado_id") or 0)==int(chamado_id)]
    if regra_id:
        itens=[x for x in itens if str(x.get("regra_id") or "")==str(regra_id)]
    if not itens:
        return {"consultados":0,"atualizados":[],"pendentes":[],"mensagem":"Nenhuma atualização Redmine pendente para este chamado."}
    ok=[]; pend=[]; erros=[]
    for item in itens:
        cid=int(item.get('chamado_id') or 0); rid=str(item.get('regra_id') or '')
        try:
            registrar_email_e_status_chamado(
                chamado_id=cid, nota=str(item.get('redmine_pendente_nota') or ''),
                status_nome=str(item.get('redmine_pendente_status') or 'Aguardando Retorno Cliente'),
                assigned_to_id=item.get('redmine_pendente_assigned_to_id'))
            concluir_redmine_pendente(cid,rid,str(item.get('redmine_pendente_status') or ''))
            ok.append(cid)
            print(f"[EDNNA] Redmine reconciliação MANUAL | OK | chamado={cid} | regra={rid}", flush=True)
        except Exception as exc:
            erro=f"{type(exc).__name__}: {exc}"
            agendar_redmine_pendente(cid,rid,nota=str(item.get('redmine_pendente_nota') or ''),status_nome=str(item.get('redmine_pendente_status') or ''),assigned_to_id=item.get('redmine_pendente_assigned_to_id'),erro=erro)
            pend.append(cid); erros.append(erro)
            print(f"[EDNNA] Redmine reconciliação MANUAL | PENDENTE | chamado={cid} | regra={rid} | {erro}", flush=True)
    return {"consultados":len(itens),"atualizados":ok,"pendentes":pend,"erros":erros}
