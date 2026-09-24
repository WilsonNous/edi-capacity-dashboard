from __future__ import annotations

import streamlit as st

from ednna.blueprint_knowledge import listar_participantes, resumo_conhecimento
from ednna.contexto_relacionamentos import sincronizar_conhecimento_blueprint
from version import APP_VERSION

st.set_page_config(page_title="EDNNA · Conhecimento", page_icon="🧠", layout="wide")
st.title("🧠 Base de Conhecimento do Cliente")
st.caption(f"EDNNA {APP_VERSION} · Blueprints viram conhecimento persistente, incremental e rastreável.")

st.info("Informe um chamado pertencente ao contexto do cliente. A EDNNA localiza o BP/Novo Cliente e suas relações, procura anexos Excel que sejam Blueprints e incorpora apenas documentos novos.")

chamado = st.number_input("Chamado para sincronizar", min_value=1, step=1, value=1)
if st.button("🔄 Localizar e sincronizar Blueprints", type="primary"):
    with st.spinner("Reconstruindo contexto e analisando Blueprints..."):
        try:
            resultado = sincronizar_conhecimento_blueprint(int(chamado), force_contexto=True)
            st.session_state["bp_resultado"] = resultado
            st.success("Sincronização concluída.")
        except Exception as exc:
            st.error(f"Não foi possível sincronizar: {exc}")

resultado = st.session_state.get("bp_resultado") or {}
if resultado:
    cliente = str(resultado.get("cliente") or "")
    st.subheader(cliente or "Cliente")
    c1,c2,c3 = st.columns(3)
    c1.metric("Blueprints conhecidos", int(resultado.get("blueprints") or 0))
    c2.metric("Participantes", int(resultado.get("participantes") or 0))
    c3.metric("Última importação", str(resultado.get("ultima_importacao") or "—")[:19].replace("T"," "))

    sinc = resultado.get("sincronizacao") or []
    novos = [x for x in sinc if x.get("status") == "IMPORTADO"]
    erros = [x for x in sinc if str(x.get("status") or "").startswith("ERRO")]
    if novos: st.success(f"{len(novos)} Blueprint(s) novo(s) incorporado(s).")
    if erros: st.warning(f"{len(erros)} item(ns) exigem revisão técnica.")
    with st.expander("Evidências da sincronização", expanded=False):
        st.dataframe(sinc, use_container_width=True, hide_index=True)

    if cliente:
        participantes = listar_participantes(cliente)
        st.markdown("### Participantes conhecidos")
        if participantes:
            vis=[{"Nome":x.get("nome"),"Área":x.get("area"),"E-mail":x.get("email"),"Fonte":x.get("fonte_arquivo"),"Chamado":x.get("chamado_id"),"Attachment":x.get("attachment_id")} for x in participantes]
            st.dataframe(vis, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhum participante importado até o momento.")

        with st.expander("Abas e registros conhecidos", expanded=False):
            st.json(resumo_conhecimento(cliente).get("abas") or {})
