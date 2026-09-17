import streamlit as st
from ui.operational_shell import setup,footer
setup('⚙️ Área técnica da EDNNA')
st.warning('Esta área contém diagnóstico, corpus, evidências e ferramentas de homologação. É a camada técnica da EDNNA.')
if st.button('Abrir backend técnico',type='primary'):
    st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
footer()
