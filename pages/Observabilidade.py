from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from ednna.security import require_admin
from ednna.observabilidade import listar_eventos
from ui.operational_shell import setup, footer

setup('📡 Observabilidade')
require_admin()
st.caption('Eventos operacionais persistidos pela EDNNA. Visão administrativa sem necessidade de abrir o Log Stream do Azure para a rotina normal.')

c1,c2,c3,c4 = st.columns([1.2,1.3,1.1,2.4])
with c1:
    nivel = st.selectbox('Nível', ['Todos','INFO','WARNING','ERROR','BLOCKED'])
with c2:
    categoria = st.selectbox('Categoria', ['Todas','EMAIL','REDMINE','FOLLOWUP','EXECUCAO','REGRA','SEGURANCA'])
with c3:
    chamado_txt = st.text_input('Chamado', placeholder='48256')
with c4:
    busca = st.text_input('Buscar', placeholder='regra, player, evento ou detalhe')
limite = st.slider('Quantidade de eventos', 50, 1000, 300, 50)
if st.button('🔄 Atualizar agora', type='primary'):
    st.rerun()
try:
    chamado = int(chamado_txt.strip()) if chamado_txt.strip() else None
except ValueError:
    chamado = None
    st.warning('Informe apenas o número do chamado.')

eventos = listar_eventos(limite=limite, nivel='' if nivel=='Todos' else nivel,
                         categoria='' if categoria=='Todas' else categoria,
                         chamado_id=chamado, busca=busca.strip())

if not eventos:
    st.info('Ainda não há eventos estruturados para este filtro. A coleta da 3.34.1 começa a partir da implantação desta versão.')
else:
    df = pd.DataFrame(eventos)
    dt = pd.to_datetime(df['created_at'], utc=True, errors='coerce').dt.tz_convert('America/Sao_Paulo')
    df.insert(0, 'Horário', dt.dt.strftime('%d/%m/%Y %H:%M:%S'))
    df = df.rename(columns={'nivel':'Nível','categoria':'Categoria','evento':'Evento','chamado_id':'Chamado','regra_id':'Regra','player':'Player','detalhe':'Detalhe'})
    cols = ['Horário','Nível','Categoria','Chamado','Player','Regra','Evento','Detalhe']
    st.dataframe(df[cols], hide_index=True, width='stretch', height=600)

st.caption('O Log Stream do Azure continua sendo a fonte técnica de infraestrutura. Esta tela registra eventos operacionais estruturados da EDNNA para diagnóstico e auditoria diária.')
footer()
