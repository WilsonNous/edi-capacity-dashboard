from __future__ import annotations

import hashlib, os, re
from typing import Any
from ednna.armazenamento import carregar_snapshot_chamados
from ednna.email_sender import GRAPH_BASE_URL, _graph_get, baixar_mensagem_eml
from ednna.redmine_writer import REDMINE_URL, _headers, upload_arquivo_redmine

FRANCIMAR="francimar.tondello@grupoargenta.com.br"
PLAYERS=("SENFF","POLICARD","STONE","CIELO","GREENCARD","ROTACARD")
TIPOS=(("FALTA_VENDAS",r"falt(?:a|am|ando)?\s+(?:de\s+)?vendas|sem vendas|n[aã]o (?:achei|encontrei) vendas"),("DOMICILIO_BANCARIO",r"domic[ií]lio"),("ERRO_LAYOUT_ARQUIVO",r"meio de captura|modalidade .*n[aã]o [ée] v[aá]lid|erro.*arquivo"),("REPROCESSAMENTO",r"reprocess"),("FALTA_ARQUIVO",r"falta.*arquivo|arquivo.*falt"))
CNPJ_RE=re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"); EC_RE=re.compile(r"(?i)\bEC\s*[:#-]?\s*(\d{5,})\b"); DATA_RE=re.compile(r"\b(\d{2}/\d{2}(?:/\d{4})?)\b")

def _remetente(msg:dict[str,Any])->str:
    return str((((msg.get("from") or {}).get("emailAddress") or {}).get("address") or "")).strip().casefold()

def classificar_ocorrencias_simrede(msg:dict[str,Any])->list[dict]:
    if _remetente(msg)!=FRANCIMAR: return []
    body=msg.get("body") or {}; texto=re.sub(r"<[^>]+>"," ",str(body.get("content") or msg.get("bodyPreview") or "")); texto=re.sub(r"\s+"," ",texto).strip(); up=texto.upper()
    players=[p for p in PLAYERS if p in up]; tipos=[n for n,rx in TIPOS if re.search(rx,texto,re.I)]
    cnpjs=sorted(set(CNPJ_RE.findall(texto))); ecs=sorted(set(EC_RE.findall(texto))); datas=sorted(set(DATA_RE.findall(texto)))
    if not players or not tipos: return []
    out=[]
    for player in players:
      for tipo in tipos:
       for alvo in (cnpjs or ecs or [""]):
        raw=f"SIM_REDE|{player}|{tipo}|{alvo}|{','.join(datas)}"
        out.append({"cliente":"SIM REDE","player":player,"tipo":tipo,"cnpj":alvo if "/" in alvo else "","ec":alvo if alvo and "/" not in alvo else "","periodos":datas,"chave":hashlib.sha256(raw.encode()).hexdigest()[:24],"assunto_origem":str(msg.get("subject") or ""),"message_id":str(msg.get("id") or ""),"internet_message_id":str(msg.get("internetMessageId") or ""),"recebida_em":str(msg.get("receivedDateTime") or "")})
    return out

def _ja_existe(oc:dict)->int|None:
    for row in carregar_snapshot_chamados() or []:
        blob=" ".join(str(row.get(k) or "") for k in ("Assunto","Descrição","Cliente","Origem","Adquirente","Player")).upper()
        if oc["player"] not in blob: continue
        alvo=(oc.get("cnpj") or oc.get("ec") or "").upper()
        if alvo and alvo not in blob: continue
        try: return int(row.get("id") or row.get("ID") or 0) or None
        except Exception: pass
    return None

def _criar_chamado(oc:dict,*,eml:bytes|None=None)->int:
    project_id=int(os.getenv("EDDY_SIMREDE_REDMINE_PROJECT_ID","0") or 0); tracker_id=int(os.getenv("EDDY_SIMREDE_REDMINE_TRACKER_ID","0") or 0)
    if not project_id or not tracker_id: raise RuntimeError("EDDY_SIMREDE_REDMINE_PROJECT_ID/TRACKER_ID não configurados")
    alvo=oc.get("cnpj") or oc.get("ec") or "LOTE"; subject=f"SIM REDE - {oc['player']} - {oc['tipo'].replace('_',' ')} - {alvo}"
    desc=("Demanda criada automaticamente pelo EDDY a partir de e-mail operacional de Francimar Tondello.\n"+f"Player: {oc['player']}\nTipo: {oc['tipo']}\nCNPJ: {oc.get('cnpj','')}\nEC: {oc.get('ec','')}\nPeríodo(s): {', '.join(oc.get('periodos') or [])}\nOrigem: EMAIL_FRANCIMAR_SIM_REDE\nChave de correlação: {oc['chave']}\nInternet-Message-ID: {oc.get('internet_message_id','')}")
    uploads=[]
    if eml:
        up=upload_arquivo_redmine(conteudo=eml,filename=f"SIMREDE_{oc['chave']}.eml"); uploads=[{"token":up["token"],"filename":up["filename"],"content_type":up["content_type"],"description":"Evidência original SIM REDE"}]
    import requests
    resp=requests.post(f"{REDMINE_URL}/issues.json",headers=_headers(),json={"issue":{"project_id":project_id,"tracker_id":tracker_id,"subject":subject,"description":desc,"uploads":uploads}},timeout=(20,60))
    if resp.status_code not in {200,201}: raise RuntimeError(f"Redmine criação SIM REDE falhou: HTTP {resp.status_code} - {resp.text[:500]}")
    return int(((resp.json() or {}).get("issue") or {}).get("id") or 0)

def processar_entrada_francimar(*,limite:int=100)->dict:
    caixas=[x.strip() for x in str(os.getenv("EDDY_SIMREDE_MAILBOXES","wilson.martins@netunna.com.br,edi@netunna.com.br")).split(",") if x.strip()]
    resumo={"mensagens":0,"ocorrencias":0,"existentes":0,"abertos":[],"erros":[]}; vistos=set()
    for caixa in caixas:
        dados=_graph_get(f"{GRAPH_BASE_URL}/users/{caixa}/mailFolders/inbox/messages",params={"$select":"id,subject,internetMessageId,receivedDateTime,from,body,bodyPreview","$orderby":"receivedDateTime desc","$top":str(max(1,limite))})
        for msg in dados.get("value",[]) or []:
            \n            if _remetente(msg)!=FRANCIMAR: continue\n            resumo["mensagens"]+=1; ocorrencias=classificar_ocorrencias_simrede(msg)
            if not ocorrencias: continue
            eml=None
            for oc in ocorrencias:
                resumo["ocorrencias"]+=1; existente=_ja_existe(oc)
                if existente: resumo["existentes"]+=1; continue
                try:
                    if eml is None: eml=baixar_mensagem_eml(caixa_postal=caixa,message_id=str(msg.get("id") or ""))
                    cid=_criar_chamado(oc,eml=eml); resumo["abertos"].append({"chamado_id":cid,"player":oc["player"],"tipo":oc["tipo"],"chave":oc["chave"]})
                    print(f"[EDDY] SIM REDE | chamado aberto #{cid} | player={oc['player']} | tipo={oc['tipo']} | origem=Francimar",flush=True)
                except Exception as exc: resumo["erros"].append(f"{oc['chave']}: {type(exc).__name__}: {exc}")
    print(f"[EDDY] SIM REDE | mensagens={resumo['mensagens']} | ocorrencias={resumo['ocorrencias']} | existentes={resumo['existentes']} | abertos={len(resumo['abertos'])} | erros={len(resumo['erros'])}",flush=True)
    return resumo
