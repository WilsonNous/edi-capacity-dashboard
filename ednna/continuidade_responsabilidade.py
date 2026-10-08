from __future__ import annotations

"""Classificador de próxima responsabilidade para continuidades EDI.

Não executa ações externas. Converte snapshot + memória transacional + journals
já armazenados em uma decisão explicável para o worker.
"""
import json
import os
from ednna.armazenamento import listar_journals
from ednna.acompanhamento_acoes import obter_responsavel_original_cancelamento

ESTADOS_TERCEIRO=("AGUARDANDO RETORNO","AGUARDANDO CLIENTE","AGUARDANDO ADQUIRENTE","AGUARDANDO BANCO","AGUARDANDO FORNECEDOR","AGUARDANDO TERCEIRO")
ESTADOS_HUMANO=("AGUARDANDO RETORNO CLIENTE","AGUARDANDO CLIENTE","AGUARDANDO USUARIO","AGUARDANDO USUÁRIO")
EDDY_USER_ID=int(os.getenv("REDMINE_EDNNA_USER_ID","166") or 166)

ASSIGNED_FIELDS={"assigned_to_id","assigned_to"}

def _txt(v): return str(v or "").strip()
def _upper(v): return _txt(v).upper()

def _detalhes(j):
    raw=j.get("detalhes_json")
    if isinstance(raw,list): return raw
    try: return json.loads(raw or "[]") if raw else []
    except Exception: return []

def _id(v):
    try: return int(float(v)) if v not in (None,"") else None
    except Exception: return None

def _assigned_snapshot(row:dict) -> tuple[int|None,str]:
    """Lê o responsável usando os nomes reais do snapshot do redmine_api."""
    rid=None
    for k in ("_Atribuído a ID","_Atribuido a ID","Responsável ID","Responsavel ID","assigned_to_id"):
        rid=_id(row.get(k))
        if rid is not None: break
    nome=_txt(row.get("Atribuído a") or row.get("Atribuido a") or row.get("Responsável") or row.get("Responsavel"))
    return rid,nome

def responsavel_historico(chamado_id:int) -> dict:
    """Reconstrói o responsável humano anterior ao EDDY pelos journals locais.

    Prioriza a transição explícita humano -> EDDY. Se o chamado legado nunca foi
    atribuído ao EDDY, não inventa uma origem a partir de qualquer autor/comentário.
    """
    journals=listar_journals(int(chamado_id))
    candidato=None
    for j in journals:
        for d in _detalhes(j):
            if _txt(d.get("property")).lower() not in {"attr","attribute"}: continue
            if _txt(d.get("name")).lower() not in ASSIGNED_FIELDS: continue
            old_id=_id(d.get("old_value")); new_id=_id(d.get("new_value"))
            if new_id==EDDY_USER_ID and old_id and old_id!=EDDY_USER_ID:
                candidato={"id":old_id,"nome":"","fonte":"JOURNAL_ATRIBUICAO"}
    return candidato or {}

def obter_responsavel_origem(chamado_id:int) -> dict:
    # memória transacional preservada é a fonte mais forte.
    r=obter_responsavel_original_cancelamento(int(chamado_id))
    if r: return {**r,"fonte":"MEMORIA_TRANSACIONAL"}
    return responsavel_historico(int(chamado_id))

def classificar_proxima_responsabilidade(row:dict, estado_motor:str="", acompanhamento:dict|None=None) -> dict:
    acompanhamento=acompanhamento or {}
    cid=int(float(row.get("#") or row.get("id") or 0))
    estado_tx=_upper(acompanhamento.get("estado"))
    status=_upper(row.get("Estado") or row.get("Status"))
    assigned_id, assigned_nome=_assigned_snapshot(row)

    if estado_tx in {"AGUARDANDO_RESPOSTA","PRAZO_VENCIDO"} and (acompanhamento.get("envio_confirmado") or acompanhamento.get("graph_message_id")):
        return {"chamado_id":cid,"decisao":"AGUARDAR_TERCEIRO","confianca":0.99,"motivo":"Há envio transacional confirmado; acompanhamento/follow-up pertence ao EDDY.","responsavel_origem":obter_responsavel_origem(cid)}
    if estado_tx in {"RESPOSTA_RECEBIDA","RESPOSTA_PENDENTE_REDMINE"}:
        return {"chamado_id":cid,"decisao":"ACAO_EDDY_DUE","confianca":0.95,"motivo":"Existe resposta recebida que precisa ser interpretada/sincronizada.","responsavel_origem":obter_responsavel_origem(cid)}

    origem=obter_responsavel_origem(cid)

    # Chamados legados podem já estar corretamente nas mãos de um humano sem
    # nunca terem passado pelo usuário técnico do EDDY. Nesse caso o responsável
    # atual é evidência forte de ownership, mas não é rotulado como "origem".
    atual_humano = bool(assigned_id and assigned_id != EDDY_USER_ID)
    if any(x in status for x in ESTADOS_HUMANO):
        if atual_humano:
            return {"chamado_id":cid,"decisao":"MANTER_RESPONSAVEL_ATUAL","confianca":0.95,"motivo":f"Status '{status}' depende de ação humana/cliente e o chamado já está atribuído a responsável humano.","responsavel_origem":origem,"responsavel_atual":{"id":assigned_id,"nome":assigned_nome,"fonte":"SNAPSHOT"}}

        if origem:
            return {"chamado_id":cid,"decisao":"DEVOLVER_ORIGEM","confianca":0.90,"motivo":f"Status '{status}' indica dependência humana/cliente e há responsável original preservado.","responsavel_origem":origem}
        return {"chamado_id":cid,"decisao":"DECISAO_HUMANA","confianca":0.65,"motivo":f"Status '{status}' sugere dependência humana, mas o responsável de origem não pôde ser provado.","responsavel_origem":{}}

    if any(x in status for x in ESTADOS_TERCEIRO):
        if atual_humano:
            return {"chamado_id":cid,"decisao":"MANTER_RESPONSAVEL_ATUAL","confianca":0.85,"motivo":"O Redmine indica espera de terceiro sem thread transacional do EDDY; o responsável humano atual permanece dono até reconstrução suficiente.","responsavel_origem":origem,"responsavel_atual":{"id":assigned_id,"nome":assigned_nome,"fonte":"SNAPSHOT"}}
        return {"chamado_id":cid,"decisao":"DECISAO_HUMANA","confianca":0.65,"motivo":"O Redmine indica espera de terceiro, mas não existe acompanhamento transacional que prove envio/thread.","responsavel_origem":origem}

    if _upper(estado_motor)=="CONTINUIDADE_ATUACAO_PREVIA":
        if atual_humano:
            return {"chamado_id":cid,"decisao":"MANTER_RESPONSAVEL_ATUAL","confianca":0.80,"motivo":"Há atuação histórica sem prova transacional do EDDY e o chamado já possui responsável humano atual.","responsavel_origem":origem,"responsavel_atual":{"id":assigned_id,"nome":assigned_nome,"fonte":"SNAPSHOT"}}
        return {"chamado_id":cid,"decisao":"DECISAO_HUMANA","confianca":0.60,"motivo":"Há atuação histórica, mas falta prova transacional suficiente para automatizar a próxima etapa.","responsavel_origem":origem}
    return {"chamado_id":cid,"decisao":"INDETERMINADO","confianca":0.50,"motivo":"Histórico disponível ainda não prova a próxima responsabilidade.","responsavel_origem":origem}

def classificar_lote(snapshot, diagnostico:dict, limite:int=30) -> dict:
    itens={int(x.get("chamado_id") or 0):x for x in diagnostico.get("itens",[]) if x.get("estado_motor") in {"CONTINUIDADE_ATUACAO_PREVIA","CONTINUIDADE_ESTADO_REDMINE"}}
    if not itens: return {"total":0,"decisoes":{},"itens":[]}
    from ednna.acompanhamento_acoes import obter_acompanhamento
    saida=[]; cont={}
    for _,r in snapshot.iterrows():
        try: cid=int(float(r.get("#") or 0))
        except Exception: continue
        if cid not in itens: continue
        regra=_txt(itens[cid].get("regra_id"))
        acomp=obter_acompanhamento(cid,regra) if regra else {}
        d=classificar_proxima_responsabilidade(r.to_dict(),itens[cid].get("estado_motor",""),acomp)
        # O contexto é um diagnóstico conservador, não autorização de disparo.
        try:
            from ednna.contexto_continuidade_universal import avaliar_contexto
            previa = itens[cid].get("estado_motor") == "CONTINUIDADE_ATUACAO_PREVIA"
            tx = str(acomp.get("estado") or "").upper()
            d["contexto_continuidade"] = avaliar_contexto(
                cid,
                houve_atuacao=previa,
                envio_confirmado=bool(acomp.get("envio_confirmado") or acomp.get("graph_message_id") or acomp.get("enviado_em")),
                retorno={"classificacao": "RESPOSTA_PENDENTE"} if tx in {"RESPOSTA_RECEBIDA", "RESPOSTA_PENDENTE_REDMINE"} else {},
            )
        except Exception as contexto_exc:
            d["contexto_continuidade"] = {"estado": "RECONCILIACAO_INDISPONIVEL", "erro": type(contexto_exc).__name__,
                                         "primeiro_envio_automatico_permitido": False}
        d["regra_id"]=regra; d["estado_motor"]=itens[cid].get("estado_motor","")
        saida.append(d); cont[d["decisao"]]=cont.get(d["decisao"],0)+1
        if len(saida)>=max(1,int(limite)): break
    return {"total":len(saida),"decisoes":cont,"itens":saida}
