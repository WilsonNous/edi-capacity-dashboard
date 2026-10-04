from ednna.security import require_admin
import streamlit as st
from ui.operational_shell import setup,footer
setup('⚙️ Área técnica do EDDY')
require_admin()
st.warning('Esta área contém diagnóstico, corpus, evidências e ferramentas de homologação. É a camada técnica do EDDY para a operação EDI.')
if st.button('Abrir backend técnico',type='primary'):
    # Identificador interno legado preservado durante a migração 4.0.
    st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
footer()
