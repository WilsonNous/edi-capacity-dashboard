from __future__ import annotations

import html
import streamlit as st
import pandas as pd

from version import APP_VERSION
from ednna.aprendizado_operacional import (
    listar_regras_operacionais,
    obter_revisao,
    obter_aprendizado,
    salvar_revisao_assistida,
    homologar_regra_assistida,
    obter_autorizacao_motor,
    autorizar_regra_motor,
)
from ednna.workflows_inclusao import obter_workflow

st.set_page_config(page_title="EDNNA · Central de Regras", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
.stApp{background:#f5f8fc}.block-container{max-width:1450px;padding:1.1rem 1.6rem 2rem}
.rule-hero{background:#fff;border:1px solid #dfe8f4;border-radius:18px;padding:18px 22px;margin:8px 0 16px;box-shadow:0 5px 18px rgba(24,75,140,.04)}
.rule-title{font-size:1.45rem;font-weight:900;color:#12366c}.rule-sub{color:#6f84a2;font-size:.9rem;margin-top:3px}
[data-testid="stMetric"]{background:#fff;border:1px solid #dfe8f4;border-radius:14px;padding:10px 14px}
div.stButton>button{border-radius:11px;font-weight:750}
</style>""", unsafe_allow_html=True)

cback, _ = st.columns([1, 7])
with cback:
    if st.button("← Painel EDI", width="stretch"):
        st.switch_page("pages/Painel_EDI.py")

st.markdown('<div class="rule-hero"><div class="rule-title">🧠 Central de Regras EDNNA</div><div class="rule-sub">Uma tela só para revisar, homologar, autorizar e suspender regras. Homologação aprova o conhecimento; autorização libera o uso assistido pelo motor.</div></div>', unsafe_allow_html=True)

regras = listar_regras_operacionais()
if not regras:
    st.info("Nenhuma regra operacional foi aprendida ainda.")
    st.stop()

hom = [r for r in regras if r.get("estado_revisao") == "HOMOLOGADA"]
revisar = [r for r in regras if r.get("estado_revisao") != "HOMOLOGADA"]
autorizadas = [r for r in hom if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA") == "ASSISTIDA"]
bloqueadas = [r for r in hom if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA") != "ASSISTIDA"]

m1,m2,m3,m4 = st.columns(4)
m1.metric("Regras conhecidas", len(regras))
m2.metric("A revisar / homologar", len(revisar))
m3.metric("Homologadas", len(hom))
m4.metric("Autorizadas no motor", len(autorizadas))

st.caption("Fluxo correto: 1) revisar e homologar → 2) autorizar operação assistida. Uma regra ainda não homologada não aparece como autorizável.")

aba1, aba2, aba3 = st.tabs([f"1 · Revisar e homologar ({len(revisar)})", f"2 · Autorizar motor ({len(bloqueadas)})", f"Regras ativas ({len(autorizadas)})"])

with aba1:
    if not revisar:
        st.success("Não há regras aguardando homologação.")
    for rr in revisar:
        rid = str(rr.get("regra_id") or "")
        player = str(rr.get("player") or "Player")
        aprendido = rr.get("payload") or obter_aprendizado(rid) or {}
        rev = obter_revisao(rid)
        wf = rr.get("workflow") or obter_workflow(player)
        comp = int(rr.get("completude") or aprendido.get("completude") or 0)
        recorr = list(dict.fromkeys(aprendido.get("destinatarios_recorrentes") or []))
        sugerido = str(rev.get("destinatario_confirmado") or "") or (recorr[0] if recorr else "")
        with st.expander(f"{player} · {rid} · {comp}% · {rr.get('estado_operacional') or rr.get('estado') or 'A revisar'}", expanded=True):
            a,b,c = st.columns(3)
            a.metric("Completude", f"{comp}%")
            b.metric("Canal", wf.get("canal") or "—")
            c.metric("Executor", wf.get("prontidao") or "—")
            st.write(f"**Workflow:** `{wf.get('workflow') or 'NAO_CLASSIFICADO'}`")
            if wf.get("procedimento_confirmado"):
                st.success("Procedimento operacional confirmado. O histórico complementa a evidência, mas não bloqueia a homologação.")
            if recorr:
                st.caption("Destinatários encontrados: " + " · ".join(recorr))
            dest = st.text_input("Destinatário confirmado", value=sugerido, key=f"central_dest_{rid}", placeholder="contato@player.com.br")
            obs = st.text_area("Observação da homologação", value=str(rev.get("observacoes") or ""), key=f"central_obs_{rid}", height=75)
            if st.button("✅ Revisar e homologar", key=f"central_hom_{rid}", type="primary", width="stretch"):
                try:
                    salvar_revisao_assistida(rid, destinatario_confirmado=dest, observacoes=obs, revisado_por="OPERADOR_EDNNA")
                    homologar_regra_assistida(rid, revisado_por="OPERADOR_EDNNA")
                    st.success(f"{player}: regra homologada. Agora ela aparecerá na etapa 2 para autorização do motor.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível homologar {player}: {exc}")

with aba2:
    if not bloqueadas:
        st.success("Nenhuma regra homologada aguarda autorização.")
    for rr in bloqueadas:
        rid = str(rr.get("regra_id") or "")
        player = str(rr.get("player") or "Player")
        wf = rr.get("workflow") or obter_workflow(player)
        with st.expander(f"{player} · {rid} · BLOQUEADA", expanded=True):
            a,b,c = st.columns(3)
            a.metric("Conhecimento", "Homologado")
            b.metric("Executor", wf.get("prontidao") or "—")
            c.metric("Motor", "Bloqueado")
            st.caption("Canal: " + str(wf.get("canal") or "—") + " · Workflow: " + str(wf.get("workflow") or "—"))
            if wf.get("prontidao") == "ASSISTIDA_DISPONIVEL":
                st.info("Esta regra já pode ser liberada para operação assistida. A confirmação humana continua obrigatória antes de ação externa.")
                if st.button("▶️ Autorizar operação assistida", key=f"central_auth_{rid}", type="primary", width="stretch"):
                    try:
                        autorizar_regra_motor(rid, modo="ASSISTIDA", autorizado_por="OPERADOR_EDNNA")
                        st.success(f"{player}: operação assistida autorizada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                falt = wf.get("executores_faltantes") or []
                st.warning("Não pode ser ativada ainda: o executor deste workflow não está disponível." + ((" Falta: " + " · ".join(falt)) if falt else ""))

with aba3:
    if not autorizadas:
        st.info("Nenhuma regra está autorizada no motor.")
    for rr in autorizadas:
        rid = str(rr.get("regra_id") or "")
        player = str(rr.get("player") or "Player")
        wf = rr.get("workflow") or obter_workflow(player)
        with st.expander(f"{player} · {rid} · ASSISTIDA", expanded=False):
            a,b,c = st.columns(3)
            a.metric("Conhecimento", "Homologado")
            b.metric("Executor", wf.get("prontidao") or "—")
            c.metric("Motor", "Assistida")
            if st.button("⏸️ Suspender regra", key=f"central_suspend_{rid}", width="stretch"):
                autorizar_regra_motor(rid, modo="BLOQUEADA", autorizado_por="OPERADOR_EDNNA")
                st.rerun()

st.divider()
rows=[]
for r in regras:
    wf=r.get("workflow") or obter_workflow(r.get("player"))
    rows.append({"Player":r.get("player"),"Regra":r.get("regra_id"),"Conhecimento":r.get("estado_operacional") or r.get("estado"),"Motor":str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA"),"Executor":wf.get("prontidao"),"Workflow":wf.get("workflow")})
st.markdown("### Inventário completo")
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
st.caption(f"EDNNA v{APP_VERSION} · Central de Regras")
