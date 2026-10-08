from __future__ import annotations

import hashlib, os, re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ednna.armazenamento import carregar_snapshot_chamados
from ednna.email_sender import GRAPH_BASE_URL, _graph_get, baixar_mensagem_eml
from ednna.redmine_writer import REDMINE_URL, _headers, upload_arquivo_redmine, obter_status_id_por_nome
from ednna.regras_ocorrencias import obter_regra_ocorrencia

FRANCIMAR="francimar.tondello@grupoargenta.com.br"
PLAYERS=("SENFF","POLICARD","STONE","CIELO","GREENCARD","ROTACARD")
TIPOS=(("FALTA_VENDAS",r"falt(?:a|am|ando)?\s+(?:de\s+)?vendas|sem vendas|n[aã]o (?:achei|encontrei) vendas"),("DOMICILIO_BANCARIO",r"domic[ií]lio"),("ERRO_LAYOUT_ARQUIVO",r"meio de captura|modalidade .*n[aã]o [ée] v[aá]lid|erro.*arquivo"),("REPROCESSAMENTO",r"reprocess"),("FALTA_ARQUIVO",r"falta.*arquivo|arquivo.*falt"))
CNPJ_RE=re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"); EC_RE=re.compile(r"(?i)\bEC\s*[:#-]?\s*(\d{5,})\b"); DATA_RE=re.compile(r"\b(\d{2}/\d{2}(?:/\d{4})?)\b")

def _remetente(msg:dict[str,Any])->str:
    return str((((msg.get("from") or {}).get("emailAddress") or {}).get("address") or "")).strip().casefold()

def classificar_ocorrencias_simrede(msg:dict[str,Any])->list[dict]:
    if _remetente(msg)!=FRANCIMAR: return []
    body=msg.get("body") or {}
    texto=re.sub(r"<[^>]+>"," ",str(body.get("content") or msg.get("bodyPreview") or ""))
    texto=re.sub(r"\s+"," ",texto).strip()
    texto=re.split(r"(?i)\bEm\s+(?:seg|ter|qua|qui|sex|s[aá]b|dom)\.?[, ]|\bFrom:\s|\bDe:\s",texto,maxsplit=1)[0].strip()
    up=texto.upper()
    players=[p for p in PLAYERS if p in up]
    tipos=[n for n,rx in TIPOS if re.search(rx,texto,re.I)]
    cnpjs=sorted(set(CNPJ_RE.findall(texto)))
    ecs=sorted(set(EC_RE.findall(texto)))
    datas=sorted(set(DATA_RE.findall(texto)))
    if not players or not tipos: return []
    out=[]
    # Uma demanda por adquirente + natureza. CNPJs/ECs e períodos são itens
    # agrupados no mesmo chamado, nunca chamados separados por estabelecimento.
    for player in players:
        for tipo in tipos:
            raw=f"SIM_REDE|{player}|{tipo}|{','.join(cnpjs)}|{','.join(ecs)}|{','.join(datas)}"
            out.append({"cliente":"SIM REDE","player":player,"tipo":tipo,"cnpjs":cnpjs,"ecs":ecs,"periodos":datas,"chave":hashlib.sha256(raw.encode()).hexdigest()[:24],"assunto_origem":str(msg.get("subject") or ""),"message_id":str(msg.get("id") or ""),"internet_message_id":str(msg.get("internetMessageId") or ""),"recebida_em":str(msg.get("receivedDateTime") or "")})
    return out

def _ja_existe(oc:dict)->int|None:
    for row in carregar_snapshot_chamados() or []:
        blob=" ".join(str(row.get(k) or "") for k in ("Assunto","Descrição","Cliente","Origem","Adquirente","Player")).upper()
        if oc["player"] not in blob: continue
        if "SIM REDE" not in blob or oc["tipo"].replace("_", " ") not in blob: continue
        if str(row.get("Estado") or "").strip().upper() in {"REJEITADO", "CONCLUÍDO", "CANCELADO", "FECHADO"}: continue
        alvos=[*oc.get("cnpjs", []), *oc.get("ecs", [])]
        if alvos and not any(str(alvo).upper() in blob for alvo in alvos): continue
        try: return int(row.get("id") or row.get("ID") or 0) or None
        except Exception: pass
    return None

def _prazo_dias_uteis(base, dias:int):
    atual=base; restantes=max(0,dias)
    while restantes>0:
        atual+=timedelta(days=1)
        if atual.weekday()<5: restantes-=1
    return atual

def _criar_chamado(oc:dict,*,eml:bytes|None=None)->int:
    ids=[int(x.strip()) for x in os.getenv("EDDY_SIMREDE_REDMINE_PROJECT_IDS",os.getenv("REDMINE_PROJECT_IDS","5,42")).split(",") if x.strip()]
    if not ids: raise RuntimeError("Projetos EDI Card/EDI Value não configurados")
    project_id=int(os.getenv("EDDY_SIMREDE_REDMINE_PROJECT_ID",str(ids[0])) or ids[0])
    tracker_id=int(os.getenv("EDDY_SIMREDE_REDMINE_TRACKER_ID","1") or 1)
    ednna_user_id=int(os.getenv("REDMINE_EDNNA_USER_ID","166") or 166)
    status_id=obter_status_id_por_nome("Aberto")
    hoje=datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    prazo=_prazo_dias_uteis(hoje,int(os.getenv("EDDY_SIMREDE_PRAZO_DIAS_UTEIS","2") or 2))
    cnpjs=", ".join(oc.get("cnpjs") or []) or "não informado"
    ecs=", ".join(oc.get("ecs") or []) or "não informado"
    periodos=", ".join(oc.get("periodos") or []) or "não informado"
    subject=f"SIM REDE - {oc['player']} - {oc['tipo'].replace('_',' ')}"
    desc=(
        "Solicitação SIM REDE recebida por e-mail de Francimar Tondello e registrada automaticamente pelo EDDY.\n\n"
        f"Ocorrência: {oc['tipo'].replace('_',' ')}\n"
        f"Player: {oc['player']}\n"
        f"CNPJ(s): {cnpjs}\n"
        f"EC(s): {ecs}\n"
        f"Período(s) informado(s): {periodos}\n\n"
        f"Assunto original: {oc.get('assunto_origem') or ''}\n"
        f"Solicitação do cliente: validar a ocorrência informada por Francimar e atuar conforme o procedimento EDI homologado para {oc['player']}.\n"
        "Origem: EMAIL_FRANCIMAR_SIM_REDE\n"
        f"Chave de correlação: {oc['chave']}\n"
        f"Internet-Message-ID: {oc.get('internet_message_id','')}"
    )
    uploads=[]
    if eml:
        up=upload_arquivo_redmine(conteudo=eml,filename=f"SIMREDE_{oc['chave']}.eml")
        uploads=[{"token":up["token"],"filename":up["filename"],"content_type":up["content_type"],"description":"E-mail original de Francimar / SIM REDE"}]
    import requests
    issue={"project_id":project_id,"tracker_id":tracker_id,"subject":subject,"description":desc,"assigned_to_id":ednna_user_id,"status_id":status_id,"start_date":hoje.isoformat(),"due_date":prazo.isoformat(),"uploads":uploads}
    resp=requests.post(f"{REDMINE_URL}/issues.json",headers=_headers(),json={"issue":issue},timeout=(20,60))
    if resp.status_code not in {200,201}: raise RuntimeError(f"Redmine criação SIM REDE falhou: HTTP {resp.status_code} - {resp.text[:500]}")
    cid=int(((resp.json() or {}).get("issue") or {}).get("id") or 0)
    if not cid: raise RuntimeError("Redmine não retornou ID do chamado SIM REDE")
    return cid

def processar_entrada_francimar(*,limite:int=100)->dict:
    caixas=[x.strip() for x in str(os.getenv("EDDY_SIMREDE_MAILBOXES","wilson.martins@netunna.com.br,edi@netunna.com.br")).split(",") if x.strip()]
    resumo={"mensagens":0,"ocorrencias":0,"existentes":0,"abertos":[],"erros":[]}; vistos=set()
    for caixa in caixas:
        dados=_graph_get(f"{GRAPH_BASE_URL}/users/{caixa}/mailFolders/inbox/messages",params={"$select":"id,subject,internetMessageId,receivedDateTime,from,body,bodyPreview","$orderby":"receivedDateTime desc","$top":str(max(1,limite))})
        for msg in dados.get("value",[]) or []:
            if _remetente(msg)!=FRANCIMAR: continue
            resumo["mensagens"]+=1; ocorrencias=classificar_ocorrencias_simrede(msg)
            if not ocorrencias: continue
            eml=None
            for oc in ocorrencias:
                resumo["ocorrencias"]+=1
                if oc["chave"] in vistos: resumo["existentes"]+=1; continue
                vistos.add(oc["chave"]); existente=_ja_existe(oc)
                if existente: resumo["existentes"]+=1; continue
                try:
                    if eml is None: eml=baixar_mensagem_eml(caixa_postal=caixa,message_id=str(msg.get("id") or ""))
                    regra=obter_regra_ocorrencia(oc["player"],oc["tipo"])
                    cid=_criar_chamado(oc,eml=eml); resumo["abertos"].append({"chamado_id":cid,"player":oc["player"],"tipo":oc["tipo"],"chave":oc["chave"],"regra_id":(regra or {}).get("regra_id"),"modo_motor":(regra or {}).get("modo_motor")})
                    print(f"[EDDY] SIM REDE | chamado aberto #{cid} | player={oc['player']} | tipo={oc['tipo']} | responsavel=EDNNA | origem=Francimar",flush=True)
                except Exception as exc: resumo["erros"].append(f"{oc['chave']}: {type(exc).__name__}: {exc}")
    print(f"[EDDY] SIM REDE | mensagens={resumo['mensagens']} | ocorrencias={resumo['ocorrencias']} | existentes={resumo['existentes']} | abertos={len(resumo['abertos'])} | erros={len(resumo['erros'])}",flush=True)
    return resumo
