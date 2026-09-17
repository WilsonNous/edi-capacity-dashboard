from __future__ import annotations
import json, sqlite3
from pathlib import Path
import pandas as pd
from painel_cache import obter_metadado_json

ROOT=Path(__file__).resolve().parent.parent

def _db(name):
    prod=Path('/home/data')/name
    return prod if prod.exists() else ROOT/'data'/name

def _mapa_clientes_persistido():
    """Resolve IDs de Cliente sem depender do Redmine online."""
    campos = obter_metadado_json('redmine_catalogos_custom_fields', []) or []
    if not isinstance(campos, list):
        return {}
    for campo in campos:
        try:
            if int(campo.get('id', -1)) != 1:
                continue
        except Exception:
            continue
        mapa = {}
        for item in campo.get('possible_values', []) or []:
            valor = str(item.get('value') or '').strip()
            label = str(item.get('label') or '').strip()
            if valor:
                mapa[valor] = label or valor
        return mapa
    return {}

def _resolver_cliente(valor, mapa):
    if valor is None:
        return valor
    texto = str(valor).strip()
    if not texto or not mapa:
        return texto
    partes = [p.strip() for p in texto.split('/') if p.strip()]
    if not partes:
        return texto
    return ' / '.join(mapa.get(p, p) for p in partes)

def chamados_df():
    p=_db('ednna.db')
    if not p.exists(): return pd.DataFrame()
    try:
        con=sqlite3.connect(str(p)); df=pd.read_sql_query('select * from chamados',con); con.close()
        # Compatibilidade com snapshots antigos: IDs numéricos já gravados no
        # ednna.db são traduzidos pelo catálogo persistido do painel.db.
        if not df.empty and 'cliente' in df.columns:
            mapa = _mapa_clientes_persistido()
            if mapa:
                df['cliente'] = df['cliente'].apply(lambda v: _resolver_cliente(v, mapa))

        # A camada operacional representa a carteira ATIVA. Chamados encerrados
        # continuam preservados no ednna.db para histórico/aprendizado, porém não
        # podem inflar Home, Equipe, Atendimentos ou indicadores de carga.
        if not df.empty and 'estado' in df.columns:
            encerrado = df['estado'].fillna('').astype(str).str.strip().str.lower().str.contains(
                r'conclu|fechad|encerrad|resolvid|cancelad', regex=True
            )
            df = df.loc[~encerrado].copy()
        return df
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
