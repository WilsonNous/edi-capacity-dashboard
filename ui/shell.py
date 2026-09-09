from __future__ import annotations

from pathlib import Path

import streamlit as st


MAIN_TAB_LABELS = {
    "Visão Geral": "Visão geral",
    "EDNNA": "🤖 EDNNA",
    "Equipe": "Equipe",
    "Tempo em aberto": "Tempo em aberto",
    "Tipos de demanda": "Tipos de demanda",
    "Lista de chamados": "Lista de chamados",
}


def carregar_shell_css() -> None:
    css_path = (
        Path(__file__).resolve().parent.parent
        / "styles"
        / "shell.css"
    )

    if not css_path.exists():
        return

    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="shell-brand">
                <div class="shell-brand-icon">N</div>
                <div>
                    <div class="shell-brand-title">Netunna</div>
                    <div class="shell-brand-sub">Painel EDI</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="shell-menu-group">GERAL</div>',
            unsafe_allow_html=True,
        )

        opcao = st.radio(
            "Navegação principal",
            [
                "Visão Geral",
                "EDNNA",
                "Equipe",
                "Tempo em aberto",
                "Tipos de demanda",
                "Lista de chamados",
            ],
            label_visibility="collapsed",
            key="shell_main_navigation",
        )

        st.markdown(
            '<div class="shell-menu-group">OPERAÇÃO</div>',
            unsafe_allow_html=True,
        )

        st.caption(
            "Filtros e análises usam o snapshot compartilhado. "
            "Cada navegador mantém sua própria seleção."
        )

        st.markdown(
            '<div class="shell-menu-group">PLATAFORMA</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="shell-status">
                <span class="shell-status-dot"></span>
                <div>
                    <strong>Produção</strong><br>
                    <small>Azure App Service</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return MAIN_TAB_LABELS.get(
        opcao,
        "Visão geral",
    )


def tabs_com_default(
    labels: list[str],
    default_label: str,
):
    """
    Usa default quando a versão do Streamlit suporta.
    Mantém fallback compatível com versões anteriores.
    """
    try:
        return st.tabs(
            labels,
            default=default_label,
        )
    except TypeError:
        return st.tabs(
            labels
        )
