from __future__ import annotations
import json, sqlite3
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent

def _db(name):
    prod=Path('/home/data')/name
    return prod if prod.exists() else ROOT/'data'/name

def chamados_df():
    p=_db('ednna.db')
    if not p.exists(): return pd.DataFrame()
    try:
        con=sqlite3.connect(str(p)); df=pd.read_sql_query('select * from chamados',con); con.close(); return df
    except Exception:return pd.DataFrame()

def regras_df():
    p=_db('ednna.db')
    if not p.exists(): return pd.DataFrame()
    try:
        con=sqlite3.connect(str(p))
        a=pd.read_sql_query('select * from aprendizados_operacionais',con)
        r=pd.read_sql_query('select regra_id as regra_rev, estado as estado_revisao, destinatario_confirmado, observacoes, homologado_em from revisoes_regras_operacionais',con)
        con.close()
        if a.empty:return a
        return a.merge(r,left_on='regra_id',right_on='regra_rev',how='left')
    except Exception:return pd.DataFrame()

def resumo():
    c=chamados_df(); r=regras_df()
    total=len(c)
    terceiros=int(c['estado'].fillna('').astype(str).str.contains('terceir|aguard',case=False,regex=True).sum()) if not c.empty and 'estado' in c else 0
    em_atuacao=max(total-terceiros,0)
    hom=int((r.get('estado_revisao',pd.Series(dtype=str)).fillna('').eq('HOMOLOGADA')).sum()) if not r.empty else 0
    # fallback para estado do aprendizado
    if not r.empty and hom==0 and 'estado' in r: hom=int(r['estado'].fillna('').eq('HOMOLOGADA').sum())
    rev=int((r.get('estado',pd.Series(dtype=str)).fillna('').eq('PRONTA_PARA_REVISAO')).sum()) if not r.empty else 0
    aprend=int((~r.get('estado',pd.Series(dtype=str)).fillna('').isin(['HOMOLOGADA','PRONTA_PARA_REVISAO'])).sum()) if not r.empty else 0
    return dict(total=total,terceiros=terceiros,em_atuacao=em_atuacao,homologadas=hom,revisao=rev,aprendendo=aprend,regras=len(r))


def redmine_link(issue_id):
    try: return f"https://chamados.nteia.com/issues/{int(issue_id)}"
    except Exception: return ""

def com_links_redmine(df):
    if df is None or df.empty or 'id' not in df.columns: return df
    out=df.copy(); out['Chamado']=out['id'].apply(redmine_link); return out
