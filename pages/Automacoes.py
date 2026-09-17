import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import regras_df
setup('⚡ Automações')
r=regras_df()
if r.empty: st.info('Nenhuma regra operacional disponível.')
else:
    mask=r.get('estado_revisao','').fillna('').eq('HOMOLOGADA') | r.estado.fillna('').eq('HOMOLOGADA')
    h=r[mask]
    st.markdown(f'<div class="op-card"><div class="op-k">Regras homologadas</div><div class="op-n">{len(h)}</div><div class="op-note">patrimônio operacional aprovado</div></div>',unsafe_allow_html=True)
    st.subheader('Em operação / prontas para operação')
    if h.empty: st.info('Ainda não há regras homologadas.')
    for _,x in h.iterrows(): st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br>{x.get("operacao") or "Inclusão"} · <span class="pill">Homologada</span><br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
footer()
