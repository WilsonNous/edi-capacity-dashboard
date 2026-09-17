import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import regras_df
setup('🧠 Aprendizado e homologação')
tech,_=st.columns([1.2,5])
with tech:
    if st.button('⚙️ Modo técnico',width="stretch"):
        st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
r=regras_df()
if r.empty: st.info('A EDNNA ainda não possui regras de aprendizado disponíveis neste ambiente.')
else:
    estado=r['estado'].fillna('EM_APRENDIZADO')
    rev=r[estado.eq('PRONTA_PARA_REVISAO')]; hom=r[(estado.eq('HOMOLOGADA')) | (r.get('estado_revisao','').fillna('').eq('HOMOLOGADA'))]; estudo=r[~r.index.isin(rev.index) & ~r.index.isin(hom.index)]
    c1,c2,c3=st.columns(3)
    for c,l,n,nota in [(c1,'Em estudo',len(estudo),'procedimentos em aprendizado'),(c2,'Para revisar',len(rev),'precisam da sua decisão'),(c3,'Homologadas',len(hom),'conhecimento aprovado')]:
        with c: st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div><div class="op-note">{nota}</div></div>',unsafe_allow_html=True)
    st.subheader('Precisam de você')
    if rev.empty: st.success('Nenhuma regra aguarda sua revisão agora.')
    for _,x in rev.iterrows():
        cols=st.columns([4,1]);
        with cols[0]: st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br><span class="pill">Pronta para revisão</span> · {int(x.get("completude") or 0)}% de completude<br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
        with cols[1]:
            if st.button('Revisar',key='rev_'+str(x.get('regra_id')),width="stretch"):
                st.session_state['ednna_regra_foco']=x.get('regra_id'); st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
    with st.expander(f'Em aprendizado ({len(estudo)})'):
        for _,x in estudo.sort_values('completude',ascending=False).iterrows(): st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_',' ').title()}")
footer()
