from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Any
from ednna.armazenamento import conectar, agora_brasil_iso
CICLO_PADRAO_DIAS=30

def _hoje_brasil(): return datetime.fromisoformat(agora_brasil_iso()).date()
def _init():
    with conectar() as conn: conn.executescript('''CREATE TABLE IF NOT EXISTS escola_matriculas (regra_id TEXT PRIMARY KEY,player TEXT,matriculada_em TEXT NOT NULL,ultima_revisao_em TEXT,proxima_revisao_em TEXT NOT NULL,ciclo_dias INTEGER NOT NULL DEFAULT 30,status TEXT NOT NULL DEFAULT 'MATRICULADA',evidencias_desde_revisao INTEGER NOT NULL DEFAULT 0,divergencias_abertas INTEGER NOT NULL DEFAULT 0,aderencia_atual REAL,atualizado_em TEXT NOT NULL); CREATE TABLE IF NOT EXISTS escola_revisoes (id INTEGER PRIMARY KEY AUTOINCREMENT,regra_id TEXT NOT NULL,revisada_em TEXT NOT NULL,resultado TEXT NOT NULL,aderencia REAL,evidencias INTEGER NOT NULL DEFAULT 0,divergencias INTEGER NOT NULL DEFAULT 0,observacao TEXT);''')
def _iso_dia(v:Any):
    if isinstance(v,datetime): return v.date().isoformat()
    if isinstance(v,date): return v.isoformat()
    t=str(v or '').strip(); return t[:10] if t else _hoje_brasil().isoformat()
def matricular(regra_id,player='',*,ciclo_dias=CICLO_PADRAO_DIAS,matriculada_em=None):
    _init(); inicio=date.fromisoformat(_iso_dia(matriculada_em)); ciclo=max(1,int(ciclo_dias or CICLO_PADRAO_DIAS)); proxima=(inicio+timedelta(days=ciclo)).isoformat()
    with conectar() as c:c.execute('''INSERT INTO escola_matriculas(regra_id,player,matriculada_em,proxima_revisao_em,ciclo_dias,atualizado_em) VALUES(?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET player=CASE WHEN excluded.player<>'' THEN excluded.player ELSE escola_matriculas.player END,ciclo_dias=excluded.ciclo_dias,atualizado_em=excluded.atualizado_em''',(regra_id,player or '',inicio.isoformat(),proxima,ciclo,agora_brasil_iso()))
def registrar_revisao(regra_id,*,resultado,aderencia=None,evidencias=0,divergencias=0,observacao='',revisada_em=None):
    _init(); dia=date.fromisoformat(_iso_dia(revisada_em))
    with conectar() as c: row=c.execute('SELECT ciclo_dias FROM escola_matriculas WHERE regra_id=?',(regra_id,)).fetchone(); ciclo=int(row[0]) if row else CICLO_PADRAO_DIAS
    if not row: matricular(regra_id,ciclo_dias=ciclo,matriculada_em=dia)
    proxima=(dia+timedelta(days=ciclo)).isoformat(); divergencias=max(0,int(divergencias or 0)); situacao='DIVERGENCIA_DETECTADA' if divergencias else 'CONHECIMENTO_SAUDAVEL'
    with conectar() as c:
        c.execute('INSERT INTO escola_revisoes(regra_id,revisada_em,resultado,aderencia,evidencias,divergencias,observacao) VALUES(?,?,?,?,?,?,?)',(regra_id,dia.isoformat(),resultado,aderencia,int(evidencias or 0),divergencias,observacao or ''))
        c.execute('UPDATE escola_matriculas SET ultima_revisao_em=?,proxima_revisao_em=?,status=?,evidencias_desde_revisao=0,divergencias_abertas=?,aderencia_atual=?,atualizado_em=? WHERE regra_id=?',(dia.isoformat(),proxima,situacao,divergencias,aderencia,agora_brasil_iso(),regra_id))
def registrar_evidencia(regra_id,*,divergente=False):
    _init()
    with conectar() as c:c.execute("UPDATE escola_matriculas SET evidencias_desde_revisao=evidencias_desde_revisao+1,divergencias_abertas=divergencias_abertas+?,status=CASE WHEN ?=1 THEN 'DIVERGENCIA_DETECTADA' ELSE status END,atualizado_em=? WHERE regra_id=?",(1 if divergente else 0,1 if divergente else 0,agora_brasil_iso(),regra_id))
def listar_matriculas():
    _init(); hoje=_hoje_brasil()
    with conectar() as c: rows=c.execute('SELECT regra_id,player,matriculada_em,ultima_revisao_em,proxima_revisao_em,ciclo_dias,status,evidencias_desde_revisao,divergencias_abertas,aderencia_atual FROM escola_matriculas ORDER BY proxima_revisao_em,player,regra_id').fetchall()
    out=[]
    for row in rows:
        d=dict(row); prox=date.fromisoformat(d['proxima_revisao_em']); d['dias_para_revisao']=(prox-hoje).days
        if d['divergencias_abertas']: d['situacao_visual']='PRECISO_DO_PROFESSOR'
        elif prox<hoje:d['situacao_visual']='REVISAO_ATRASADA'
        elif prox<=hoje+timedelta(days=7):d['situacao_visual']='REVISAO_PROXIMA'
        else:d['situacao_visual']='CONHECIMENTO_SAUDAVEL'
        out.append(d)
    return out
def sincronizar_regras_homologadas(regras):
    if regras is None or getattr(regras,'empty',True):return 0
    total=0
    for _,x in regras.iterrows():
        if str(x.get('estado') or '')=='HOMOLOGADA' or str(x.get('estado_revisao') or '')=='HOMOLOGADA':
            rid=str(x.get('regra_id') or '').strip()
            if rid:
                origem=x.get('homologado_em') or x.get('atualizado_em') or None; matricular(rid,str(x.get('player') or ''),matriculada_em=origem); total+=1
    return total
