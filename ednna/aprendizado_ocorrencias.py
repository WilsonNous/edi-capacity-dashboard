from __future__ import annotations

"""Aprendizado incremental de ocorrências EDI a partir do snapshot local.

Objetivo: ampliar a Escola do EDDY para problemas recorrentes sem provocar
consultas pontuais em massa ao Redmine. O snapshot local é a primeira fonte;
journals detalhados podem ser estudados depois, de forma limitada.
"""
import json
import re
from collections import Counter, defaultdict
from ednna.armazenamento import conectar, agora_brasil_iso

PADROES = {\n    "FALTA_VENDAS": [r"(?i)falta\\s+(?:de\\s+)?vendas?", r"(?i)n[aã]o\\s+(?:localizamos|localizei|encontramos|encontrei).{0,60}vendas?", r"(?i)sem\\s+vendas?"],
    "FALTA_ARQUIVO": [
        r"(?i)falta\s+(?:de\s+)?arquivo", r"(?i)arquivo\s+(?:n[aã]o\s+)?(?:recebid|cheg|dispon)",
        r"(?i)n[aã]o\s+(?:recebemos|recebi).{0,50}arquivo", r"(?i)arquivo.{0,50}n[aã]o\s+cheg",
    ],
    "FALTA_REGISTRO": [
        r"(?i)falta\s+(?:de\s+)?registro", r"(?i)registro\s+(?:n[aã]o\s+)?(?:consta|localiz|encontr)",
        r"(?i)(?:venda|transa[cç][aã]o|ec).{0,60}n[aã]o\s+(?:consta|localiz|encontr)",
    ],
    "ARQUIVO_INCOMPLETO": [r"(?i)arquivo.{0,50}incomplet", r"(?i)faltam?.{0,40}(?:dados|registros|movimentos)"],
    "ARQUIVO_INVALIDO": [r"(?i)arquivo.{0,50}(?:inv[aá]lid|rejeitad|fora\s+do\s+layout)", r"(?i)layout.{0,40}(?:inv[aá]lid|diverg)"],
    "DIVERGENCIA_VALOR": [r"(?i)diverg[eê]ncia.{0,30}valor", r"(?i)valor.{0,30}(?:diverg|incorret)"],
    "DIVERGENCIA_EC": [r"(?i)diverg[eê]ncia.{0,30}(?:ec|estabelecimento)", r"(?i)(?:ec|estabelecimento).{0,30}(?:diverg|incorret)"],
    "DUPLICIDADE": [r"(?i)(?:arquivo|registro|transa[cç][aã]o).{0,40}duplicad", r"(?i)duplicidade"],
    "ATRASO_ARQUIVO": [r"(?i)atraso.{0,30}arquivo", r"(?i)arquivo.{0,40}(?:atrasad|fora\s+do\s+prazo|sla)"],
    "REPROCESSAMENTO": [r"(?i)reprocess", r"(?i)reenvi.{0,30}arquivo"],
}

def _init():
    with conectar() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS aprendizado_ocorrencias (
            chamado_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cliente TEXT,
            player TEXT,
            assunto TEXT,
            fonte TEXT NOT NULL DEFAULT 'SNAPSHOT_LOCAL',
            payload_json TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY(chamado_id,tipo)
        )""")

def _id(row):
    for k in ("#","ID","id","Chamado"):
        try:
            v=row.get(k)
            if v not in (None,""): return int(float(str(v).replace("#","").strip()))
        except Exception: pass
    return 0

def _texto(row):
    return "\n".join(str(row.get(k) or "") for k in ("Tipo","Assunto","Descrição","Origem","Clientes","Estado"))

def classificar_ocorrencias(row: dict) -> list[str]:
    texto=_texto(row)
    return [tipo for tipo,padroes in PADROES.items() if any(re.search(p,texto) for p in padroes)]

def aprender_snapshot(snapshot: list[dict], limite: int = 250) -> dict:
    _init(); cont=Counter(); exemplos=defaultdict(list); persistidos=0
    for row in (snapshot or [])[:max(1,int(limite))]:
        if not isinstance(row,dict): continue
        cid=_id(row)
        if not cid: continue
        for tipo in classificar_ocorrencias(row):
            payload={"chamado_id":cid,"tipo":tipo,"cliente":str(row.get("Clientes") or ""),"player":str(row.get("Origem") or ""),"assunto":str(row.get("Assunto") or ""),"estado":str(row.get("Estado") or ""),"fonte":"SNAPSHOT_LOCAL"}
            with conectar() as c:
                c.execute("""INSERT INTO aprendizado_ocorrencias(chamado_id,tipo,cliente,player,assunto,fonte,payload_json,atualizado_em)
                    VALUES(?,?,?,?,?,'SNAPSHOT_LOCAL',?,?)
                    ON CONFLICT(chamado_id,tipo) DO UPDATE SET cliente=excluded.cliente,player=excluded.player,assunto=excluded.assunto,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em""",
                    (cid,tipo,payload["cliente"],payload["player"],payload["assunto"],json.dumps(payload,ensure_ascii=False),agora_brasil_iso()))
            persistidos+=1; cont[tipo]+=1
            if len(exemplos[tipo])<8: exemplos[tipo].append(cid)
    return {"persistidos":persistidos,"tipos":dict(cont),"exemplos":dict(exemplos),"fonte":"SNAPSHOT_LOCAL"}

def resumo_aprendizado() -> list[dict]:
    _init()
    with conectar() as c:
        rows=c.execute("""SELECT tipo,COUNT(*) qtd,COUNT(DISTINCT player) players,MAX(atualizado_em) atualizado_em
                          FROM aprendizado_ocorrencias GROUP BY tipo ORDER BY qtd DESC,tipo""").fetchall()
    return [{"tipo":r[0],"evidencias":int(r[1]),"players":int(r[2]),"atualizado_em":r[3]} for r in rows]

def exemplos_tipo(tipo: str, limite: int = 10) -> list[dict]:
    _init()
    with conectar() as c:
        rows=c.execute("""SELECT payload_json FROM aprendizado_ocorrencias WHERE tipo=? ORDER BY chamado_id DESC LIMIT ?""",(str(tipo),max(1,int(limite)))).fetchall()
    return [json.loads(r[0]) for r in rows]
