import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import chamados_df
setup('📥 Atendimentos da EDNNA')
df=chamados_df()
if df.empty: st.info('Nenhum chamado disponível no snapshot local da EDNNA.')
else:
    c1,c2,c3=st.columns(3); total=len(df); terc=int(df.estado.fillna('').str.contains('terceir|aguard',case=False,regex=True).sum()); venc=int((df.tempo_aberto_dias.fillna(0)>30).sum())
    for c,l,n in [(c1,'Monitorados',total),(c2,'Aguardando / terceiros',terc),(c3,'Acima de 30 dias',venc)]:
        with c: st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div></div>',unsafe_allow_html=True)
    st.subheader('Chamados acompanhados')
    cols=[x for x in ['id','cliente','responsavel','tipo','estado','prioridade','assunto','tempo_aberto_dias'] if x in df.columns]
    st.dataframe(df[cols].sort_values('tempo_aberto_dias',ascending=False) if 'tempo_aberto_dias' in cols else df[cols],use_container_width=True,hide_index=True)
footer()
