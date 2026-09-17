import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import chamados_df, com_links_redmine
setup('👥 Equipe e capacidade')
df=chamados_df()
if df.empty: st.info('Nenhum chamado disponível para calcular a distribuição da equipe.')
else:
    s=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts().reset_index(); s.columns=['Responsável','Chamados']
    st.markdown(f'<div class="op-card"><div class="op-k">Chamados distribuídos</div><div class="op-n">{len(df)}</div><div class="op-note">visão por responsável atual</div></div>',unsafe_allow_html=True)
    st.subheader('Quem está com o quê?')
    st.dataframe(s,width="stretch",hide_index=True)
    nome=st.selectbox('Ver chamados de',s['Responsável'].tolist())
    base=df[df.responsavel.fillna('Sem responsável').replace('','Sem responsável').eq(nome)]
    base=com_links_redmine(base)
    cols=[x for x in ['Chamado','cliente','tipo','estado','prioridade','assunto','tempo_aberto_dias'] if x in base.columns]
    st.dataframe(base[cols],width="stretch",hide_index=True,column_config={'Chamado':st.column_config.LinkColumn('Chamado',display_text=r'/issues/(\d+)$')})
footer()
