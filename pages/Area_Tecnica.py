from ednna.security import require_admin
import streamlit as st
from ui.operational_shell import setup,footer

setup('⚙️ Área técnica do EDDY')
require_admin()
st.warning('Esta área contém diagnóstico, corpus, evidências e ferramentas de homologação. É a camada técnica do EDDY para a operação EDI.')
st.caption('Os recursos técnicos do EDDY permanecem no contexto da inteligência EDI; o Painel EDI é reservado à análise da carteira.')

c1,c2,c3=st.columns(3)
with c1:
    if st.button('📡 Observabilidade',type='primary',width='stretch'):
        st.switch_page('pages/Observabilidade.py')
with c2:
    if st.button('🧠 Central de Regras',width='stretch'):
        st.switch_page('pages/Regras.py')
with c3:
    if st.button('🎓 Central de Aprendizagem',width='stretch'):
        st.switch_page('pages/Aprendizado.py')

footer()
