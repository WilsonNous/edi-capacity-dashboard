from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from ednna.security import require_admin
from ednna.observabilidade import listar_eventos, url_chamado, status_evento
from ui.operational_shell import setup, footer

setup('📡 Observabilidade')
require_admin()
st.caption('Acompanhe cada movimentação registrada pelo EDDY, com horário, resultado e acesso ao chamado no Redmine.')
st.markdown('<a href="/Observabilidade" target="_blank" rel="noopener noreferrer">↗ Abrir Observabilidade em nova aba</a>', unsafe_allow_html=True)

barra1, barra2, barra3 = st.columns([1.5, 1.2, 2.5])
with barra1:
    st.button('🔄 Atualizar agora', type='primary', use_container_width=True)
with barra2:
    auto = st.toggle('Atualização automática', value=True, key='obs_auto_refresh')
with barra3:
    intervalo = st.selectbox('Intervalo de atualização', [15, 30, 60, 120],
                            index=1, format_func=lambda n: f'{n} segundos',
                            disabled=not auto, key='obs_refresh_interval')

with st.expander('🔎 Filtros da Observabilidade', expanded=True):
    c1,c2,c3,c4 = st.columns([1.2,1.3,1.1,2.4])
    with c1:
        nivel = st.selectbox('Nível', ['Todos','INFO','WARNING','ERROR','BLOCKED'])
    with c2:
        categoria = st.selectbox('Categoria', ['Todas','EMAIL','REDMINE','FOLLOWUP','EXECUCAO','REGRA','SEGURANCA','CHECKPOINT'])
    with c3:
        chamado_txt = st.text_input('Chamado', placeholder='48256')
    with c4:
        busca = st.text_input('Buscar', placeholder='regra, player, evento ou detalhe')
    limite = st.slider('Quantidade de eventos', 50, 1000, 300, 50)

try:
    chamado = int(chamado_txt.strip()) if chamado_txt.strip() else None
except ValueError:
    chamado = None
    st.warning('Informe apenas o número do chamado.')

@st.fragment(run_every=f'{intervalo}s' if auto else None)
def exibir_eventos():
    aba_mov, aba_diag = st.tabs(['🧭 Movimentações', '🔧 Diagnóstico técnico'])
    with aba_mov:
        st.caption('Movimentações confirmadas, recebidas, bloqueadas ou pendentes. Os dados são somente leitura.')
    eventos = listar_eventos(limite=limite, nivel='' if nivel=='Todos' else nivel,
                             categoria='' if categoria=='Todas' else categoria,
                             chamado_id=chamado, busca=busca.strip())
    
    if not eventos:
        with aba_mov:
            st.info('Ainda não há movimentações registradas para este filtro.')
        with aba_diag:
            st.info('Sem eventos técnicos para os filtros selecionados.')
    else:
        df = pd.DataFrame(eventos)
        df['Status'] = df.apply(lambda x: status_evento(x.to_dict()), axis=1)
        df['Abrir chamado'] = df['chamado_id'].apply(url_chamado)
        df['chamado_id'] = df['chamado_id'].apply(lambda x: f'#{int(x)}' if pd.notna(x) and x else '—')
        dt = pd.to_datetime(df['created_at'], utc=True, errors='coerce').dt.tz_convert('America/Sao_Paulo')
        df.insert(0, 'Horário', dt.dt.strftime('%d/%m/%Y %H:%M:%S'))
        df = df.rename(columns={'nivel':'Nível','categoria':'Categoria','evento':'Evento','chamado_id':'Chamado','regra_id':'Regra','player':'Player','detalhe':'Detalhe'})
        cols = ['Horário','Chamado','Abrir chamado','Categoria','Evento','Status','Detalhe','Nível','Player','Regra']
        with aba_mov:
            st.dataframe(df[['Horário','Chamado','Abrir chamado','Evento','Status','Detalhe']],
                         hide_index=True, width='stretch', height=600,
                         column_config={'Abrir chamado': st.column_config.LinkColumn('Redmine', display_text='Abrir ↗'),
                                        'Detalhe': st.column_config.TextColumn('Detalhe', width='large')})
        with aba_diag:
            st.dataframe(df[cols], hide_index=True, width='stretch', height=600,
                         column_config={'Abrir chamado': st.column_config.LinkColumn('Redmine', display_text='Abrir ↗'),
                                        'Detalhe': st.column_config.TextColumn('Detalhe', width='large')})
        st.caption('Clique em Abrir ↗ para acessar o chamado. Eventos sem número de chamado não têm vínculo direto.')
    
    st.caption('Consulta realizada às ' + datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S') + ' (horário do servidor).')

exibir_eventos()

st.caption('O Log Stream do Azure continua sendo a fonte técnica de infraestrutura. Esta tela registra eventos operacionais estruturados do EDDY para diagnóstico e auditoria diária.')
footer()
