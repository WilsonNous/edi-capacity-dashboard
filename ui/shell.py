from __future__ import annotations
from pathlib import Path
import streamlit as st

# O Painel EDI volta a ser exclusivamente analítico. Recursos do EDDY possuem
# páginas próprias e nunca devem ser simulados como abas internas do painel.
MAIN_TAB_LABELS = {
    'Visão Geral': 'Visão geral',
    'Equipe': 'Equipe',
    'Tempo em aberto': 'Tempo em aberto',
    'Tipos de demanda': 'Tipos de demanda',
    'Lista de chamados': 'Lista de chamados',
}

EDDY_DESTINOS = [
    ('🦾 Operação de hoje', 'pages/Operacao.py'),
    ('🧠 Central de Regras', 'pages/Regras.py'),
    ('🎓 Central de Aprendizagem', 'pages/Aprendizado.py'),
    ('⚡ Automações', 'pages/Automacoes.py'),
    ('📡 Observabilidade', 'pages/Observabilidade.py'),
]

def carregar_shell_css() -> None:
    css_path = Path(__file__).resolve().parent.parent / 'styles' / 'shell.css'
    if css_path.exists():
        st.markdown(f'<style>{css_path.read_text(encoding="utf-8")}</style>', unsafe_allow_html=True)

def render_sidebar() -> str:
    with st.sidebar:
        st.markdown('''<div class="shell-brand"><div class="shell-brand-icon">N</div><div><div class="shell-brand-title">Netunna</div><div class="shell-brand-sub">Painel EDI</div></div></div>''', unsafe_allow_html=True)
        st.markdown('<div class="shell-menu-group">PAINEL EDI</div>', unsafe_allow_html=True)
        opcao = st.radio('Navegação do painel', list(MAIN_TAB_LABELS), label_visibility='collapsed', key='shell_main_navigation')

        st.markdown('<div class="shell-menu-group">EDDY · INTELIGÊNCIA EDI</div>', unsafe_allow_html=True)
        # page_link navega diretamente para a função proposta. Não há mais
        # botão/aba "Motor EDDY" que primeiro abre o Painel EDI.
        for label, pagina in EDDY_DESTINOS:
            st.page_link(pagina, label=label)

        st.caption('Painel = análise da carteira. EDDY = inteligência, aprendizado e execução. Cada atalho abre diretamente o módulo correspondente.')
        st.markdown('<div class="shell-menu-group">PLATAFORMA</div>', unsafe_allow_html=True)
        st.markdown('''<div class="shell-status"><span class="shell-status-dot"></span><div><strong>Produção</strong><br><small>Azure App Service</small></div></div>''', unsafe_allow_html=True)
    return MAIN_TAB_LABELS.get(opcao, 'Visão geral')

def tabs_com_default(labels: list[str], default_label: str):
    try:
        return st.tabs(labels, default=default_label)
    except TypeError:
        return st.tabs(labels)
