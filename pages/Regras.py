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
from ednna.motor_inclusoes_operacional import diagnosticar_regras_operacionais
from ui.operational_data import chamados_ativos_df, redmine_link

st.set_page_config(page_title="EDNNA · Central de Regras", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
.stApp{background:#f5f8fc}.block-container{max-width:1450px;padding:1.1rem 1.6rem 2rem}
.rule-hero{background:#fff;border:1px solid #dfe8f4;border-radius:18px;padding:18px 22px;margin:8px 0 16px;box-shadow:0 5px 18px rgba(24,75,140,.04)}
.rule-title{font-size:1.45rem;font-weight:900;color:#12366c}.rule-sub{color:#6f84a2;font-size:.9rem;margin-top:3px}
[data-testid="stMetric"]{background:#fff;border:1px solid #dfe8f4;border-radius:14px;padding:10px 14px}
div.stButton>button{border-radius:10px!important;font-weight:750!important;min-height:38px!important;width:auto!important;padding:.4rem .8rem!important}div.stButton>button[kind="primary"]{background:#1268e8!important;color:#fff!important;border-color:#1268e8!important}div.stButton>button[kind="primary"] p{color:#fff!important}
</style>""", unsafe_allow_html=True)

cback, _ = st.columns([1, 7])
with cback:
    if st.button("← Painel EDI", width="stretch"):
        st.switch_page("pages/Painel_EDI.py")

st.markdown('<div class="rule-hero"><div class="rule-title">🧠 Central de Regras EDNNA</div><div class="rule-sub">Veja a regra, os chamados que ela encontrou e o motivo de cada estado. Depois decida, conscientemente, o que permanece assistido e o que a EDNNA pode executar sozinha.</div></div>', unsafe_allow_html=True)

if st.button('🧩 Ensinar nova regra à EDNNA', width='content'):
    st.switch_page('pages/Construtor_Regras.py')

regras = listar_regras_operacionais()
if not regras:
    st.info("Nenhuma regra operacional foi aprendida ainda.")
    st.stop()

# Diagnóstico operacional usa o mesmo snapshot da Home; nenhuma ação externa é executada aqui.
df_ativos = chamados_ativos_df()
snapshot_regras = pd.DataFrame()
if not df_ativos.empty:
    snapshot_regras = df_ativos.rename(columns={
        'id':'#','cliente':'Clientes','tipo':'Tipo','estado':'Estado','prioridade':'Prioridade',
        'assunto':'Assunto','responsavel':'Atribuído a','projeto':'Projeto'
    }).copy()
diag_regras = diagnosticar_regras_operacionais(snapshot_regras) if not snapshot_regras.empty else {'regras': []}
diag_por_id = {str(x.get('regra_id') or ''): x for x in (diag_regras.get('regras') or [])}

hom = [r for r in regras if r.get("estado_revisao") == "HOMOLOGADA"]
revisar = [r for r in regras if r.get("estado_revisao") != "HOMOLOGADA"]
autorizadas = [r for r in hom if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA") in {"ASSISTIDA", "AUTOMATICA"}]
bloqueadas = [r for r in hom if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA") == "BLOQUEADA"]

m1,m2,m3,m4 = st.columns(4)
m1.metric("Regras conhecidas", len(regras))
m2.metric("A revisar / homologar", len(revisar))
m3.metric("Homologadas", len(hom))
m4.metric("Autorizadas no motor", len(autorizadas))

st.caption("Fluxo: 1) revisar e homologar → 2) autorizar como assistida ou automática. Automática só fica disponível quando o workflow possui executor implementado.")

# v3.28.58 — aceleração controlada: um único comando promove para AUTOMATICA
# somente regras já HOMOLOGADAS cujo executor está realmente disponível.
# Regras sem executor continuam bloqueadas; nenhuma homologação é criada aqui.
aptas_auto = [r for r in hom if (r.get("workflow") or obter_workflow(r.get("player"))).get("prontidao") == "ASSISTIDA_DISPONIVEL"]
pendentes_auto = [r for r in aptas_auto if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA").upper() != "AUTOMATICA"]
if pendentes_auto:
    st.warning(f"⚡ {len(pendentes_auto)} regra(s) homologada(s) com executor disponível ainda não estão em modo automático.")
    if st.button("⚡ Colocar TODAS as homologadas aptas em AUTOMÁTICO", type="primary", key="central_auto_todas", width="content"):
        ok, erros = 0, []
        for rr in pendentes_auto:
            rid = str(rr.get("regra_id") or "")
            try:
                autorizar_regra_motor(rid, modo="AUTOMATICA", autorizado_por="OPERADOR_EDNNA", observacoes="Autorização em lote explícita: executar automaticamente todas as regras já homologadas e com executor disponível.")
                ok += 1
            except Exception as exc:
                erros.append(f"{rr.get('player')}: {exc}")
        if ok:
            st.success(f"{ok} regra(s) promovida(s) para execução automática.")
        if erros:
            st.error("Não foi possível ativar: " + " | ".join(erros))
        st.rerun()

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
            if st.button("✅ Revisar e homologar", key=f"central_hom_{rid}", type="primary", width="content"):
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
                st.info("Executor disponível. Escolha se a regra exige confirmação humana ou se a EDNNA pode executar automaticamente.")
                c_ass, c_auto = st.columns(2)
                with c_ass:
                    if st.button("▶️ Autorizar assistida", key=f"central_auth_{rid}", type="primary", width="content"):
                        try:
                            autorizar_regra_motor(rid, modo="ASSISTIDA", autorizado_por="OPERADOR_EDNNA")
                            st.success(f"{player}: operação assistida autorizada.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
                with c_auto:
                    if st.button("⚡ Autorizar automática", key=f"central_auto_{rid}", width="content"):
                        try:
                            autorizar_regra_motor(rid, modo="AUTOMATICA", autorizado_por="OPERADOR_EDNNA", observacoes="Autorização explícita para execução automática de regra homologada.")
                            st.success(f"{player}: execução automática autorizada.")
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
        modo = str((rr.get("autorizacao_motor") or {}).get("modo") or "ASSISTIDA").upper()
        dg = diag_por_id.get(rid) or {}
        situacao = str(dg.get("situacao") or "SEM_DIAGNOSTICO")
        total_demanda = int(dg.get("total_chamados") or 0)
        with st.expander(f"{player} · {rid} · {modo} · {situacao.replace('_',' ')} · {total_demanda} chamado(s)", expanded=(modo == "ASSISTIDA")):
            a,b,c,d = st.columns(4)
            a.metric("Conhecimento", "Homologado")
            b.metric("Executor", wf.get("prontidao") or "—")
            c.metric("Motor", modo.title())
            d.metric("Chamados ativos", total_demanda)
            st.info(str(dg.get("motivo") or "Diagnóstico operacional indisponível."))
            chamados_dg = dg.get("chamados") or []
            if chamados_dg:
                st.markdown("**Chamados encontrados para esta regra**")
                for ch in chamados_dg:
                    cid = int(ch.get("id") or 0)
                    st.markdown(f"- [#{cid}]({redmine_link(cid)}) · {html.escape(str(ch.get('cliente') or 'Cliente não informado'))} · **{html.escape(str(ch.get('motivo') or 'Revisar'))}** · próxima ação: {html.escape(str(ch.get('acao_sugerida') or 'Revisar'))}")
            else:
                st.caption("Nenhum chamado ativo compatível. A regra está disponível, mas não há demanda para ela neste momento.")
            ca, cb = st.columns(2)
            with ca:
                if modo == "ASSISTIDA" and wf.get("prontidao") == "ASSISTIDA_DISPONIVEL":
                    if st.button("⚡ Tornar AUTOMÁTICA", key=f"central_promote_{rid}", type="primary", width="content"):
                        autorizar_regra_motor(rid, modo="AUTOMATICA", autorizado_por="OPERADOR_EDNNA", observacoes="Promoção explícita após revisão dos chamados e do diagnóstico operacional na Central de Regras v3.28.59.")
                        st.success(f"{player}: a EDNNA está autorizada a executar esta regra automaticamente.")
                        st.rerun()
            with cb:
                if st.button("⏸️ Suspender regra", key=f"central_suspend_{rid}", width="content"):
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
