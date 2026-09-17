import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import chamados_df
setup('👥 Equipe e capacidade')
df=chamados_df()
if df.empty: st.info('Nenhum chamado disponível para calcular a distribuição da equipe.')
else:
    s=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts().reset_index(); s.columns=['Responsável','Chamados']
    st.markdown(f'<div class="op-card"><div class="op-k">Chamados distribuídos</div><div class="op-n">{len(df)}</div><div class="op-note">visão por responsável atual</div></div>',unsafe_allow_html=True)
    st.subheader('Quem está com o quê?')
    st.dataframe(s,use_container_width=True,hide_index=True)
    nome=st.selectbox('Ver chamados de',s['Responsável'].tolist())
    base=df[df.responsavel.fillna('Sem responsável').replace('','Sem responsável').eq(nome)]
    cols=[x for x in ['id','cliente','tipo','estado','prioridade','assunto','tempo_aberto_dias'] if x in base.columns]
    st.dataframe(base[cols],use_container_width=True,hide_index=True)
footer()
