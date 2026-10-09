from __future__ import annotations
from ednna.security import require_admin

import html
import streamlit as st
import pandas as pd

from version import APP_VERSION
from ednna.aprendizado_operacional import (
    listar_regras_operacionais, obter_revisao, obter_aprendizado, salvar_revisao_assistida,
    homologar_regra_assistida, obter_autorizacao_motor, autorizar_regra_motor,
    garantir_greencard_pronta, garantir_safrapay_pronta,
)
from ednna.workflows_inclusao import obter_workflow, WORKFLOWS, salvar_configuracao_regra, listar_catalogo_workflows
from ednna.motor_inclusoes_operacional import diagnosticar_regras_operacionais
from ui.operational_data import chamados_ativos_df, redmine_link
from ednna.construtor_regras import listar_regras_treinaveis, explicar_regra
from ednna.prontidao_operacional import avaliar_prontidao_regra
from ednna.motor_aberturas import avaliar_abertura, avaliar_aberturas_homologadas, autorizar_abertura_assistida
from ednna.motor_falta_arquivo import avaliar_falta_arquivo, listar_regras_aprendidas
from ednna.homologacao import listar_homologacoes_mais_recentes

st.set_page_config(page_title="EDDY · Central de Regras", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")
require_admin()
st.markdown("""<style>
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
.stApp{background:#f5f8fc}.block-container{max-width:1450px;padding:1.1rem 1.6rem 2rem}
.rule-hero{background:#fff;border:1px solid #dfe8f4;border-radius:18px;padding:18px 22px;margin:8px 0 16px;box-shadow:0 5px 18px rgba(24,75,140,.04)}
.rule-title{font-size:1.45rem;font-weight:900;color:#12366c}.rule-sub{color:#6f84a2;font-size:.9rem;margin-top:3px}
[data-testid="stMetric"]{background:#fff;border:1px solid #dfe8f4;border-radius:14px;padding:10px 14px}
div.stButton>button{border-radius:10px!important;font-weight:750!important;min-height:38px!important;width:auto!important;padding:.4rem .8rem!important}div.stButton>button[kind="primary"]{background:#1268e8!important;color:#fff!important;border-color:#1268e8!important}div.stButton>button[kind="primary"] p{color:#fff!important}
</style>""", unsafe_allow_html=True)

cback,_=st.columns([1,7])
with cback:
    if st.button("← EDDY",width="stretch"): st.switch_page("app.py")

st.markdown('<div class="rule-hero"><div class="rule-title">🧠 Central de Regras EDDY</div><div class="rule-sub">Veja a regra, os chamados que ele encontrou e o motivo de cada estado. Depois decida, conscientemente, o que permanece assistido e o que o EDDY pode executar sozinho.</div></div>',unsafe_allow_html=True)
if st.button('🧩 Ensinar nova regra ao EDDY',width='content'): st.switch_page('pages/Construtor_Regras.py')

try: garantir_greencard_pronta()
except Exception as exc: st.warning(f"Greencard ainda não pôde ser preparada automaticamente: {exc}")
try: garantir_safrapay_pronta()
except Exception as exc: st.warning(f"Safrapay ainda não pôde ser preparada automaticamente: {exc}")

regras=listar_regras_operacionais(); regras_treinaveis=listar_regras_treinaveis(); catalogo_declarativo=listar_catalogo_workflows()
df_ativos=chamados_ativos_df(); snapshot_regras=pd.DataFrame()
if not df_ativos.empty:
    snapshot_regras=df_ativos.rename(columns={'id':'#','cliente':'Clientes','tipo':'Tipo','estado':'Estado','prioridade':'Prioridade','assunto':'Assunto','responsavel':'Atribuído a','projeto':'Projeto'}).copy()
diag_regras=diagnosticar_regras_operacionais(snapshot_regras) if not snapshot_regras.empty else {'regras':[]}
diag_por_id={str(x.get('regra_id') or ''):x for x in (diag_regras.get('regras') or [])}

with st.expander("🔎 Saúde técnica das regras",expanded=False):
    linhas_saude=[]
    for wf in catalogo_declarativo:
        faltantes=list(wf.get("executores_faltantes") or [])
        linhas_saude.append({"Player":wf.get("player"),"Workflow":str(wf.get("workflow") or "").replace("_"," ").title(),"Canal":str(wf.get("canal") or "").replace("_"," "),"Situação":"Executor disponível" if not faltantes and wf.get("ativa",True) else ("Inativa" if not wf.get("ativa",True) else "Aguardando executor"),"Executor pendente":", ".join(faltantes)})
    _df_saude=pd.DataFrame(linhas_saude); _disp=int((_df_saude["Situação"]=="Executor disponível").sum()) if not _df_saude.empty else 0; _pend=int((_df_saude["Situação"]=="Aguardando executor").sum()) if not _df_saude.empty else 0
    sc1,sc2,sc3=st.columns(3); sc1.metric("Workflows conhecidos",len(_df_saude)); sc2.metric("Com executor disponível",_disp); sc3.metric("Aguardando executor",_pend); st.dataframe(_df_saude,hide_index=True,width="stretch")
    st.caption("Esta visão valida a infraestrutura do workflow. Homologação e autorização continuam sendo decisões separadas e aparecem na configuração de cada regra.")

hom=[r for r in regras if r.get("estado_revisao")=="HOMOLOGADA"]; revisar=[r for r in regras if r.get("estado_revisao")!="HOMOLOGADA"]
autorizadas=[r for r in hom if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA") in {"ASSISTIDA","AUTOMATICA"}]
bloqueadas=[r for r in hom if str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA")=="BLOQUEADA"]
m1,m2,m3,m4=st.columns(4); m1.metric("Regras configuradas",len(catalogo_declarativo)+len(regras_treinaveis)); m2.metric("A revisar / homologar",len(revisar)); m3.metric("Homologadas",len(hom)); m4.metric("Autorizadas no motor",len(autorizadas))
st.caption("Fluxo: 1) revisar e homologar → 2) autorizar como assistida ou automática. Automática só fica disponível quando o workflow possui executor implementado.")

# EDDY 4.3 — transforma a prontidão em uma fila de demandas técnicas/operacionais.
# Assim a Central não mostra apenas "bloqueada": ela diz o que falta fazer.
players_prontidao=list(dict.fromkeys(
    [str(r.get("player") or "").strip().upper() for r in regras if str(r.get("player") or "").strip()]
    + [str(w.get("player") or "").strip().upper() for w in catalogo_declarativo if str(w.get("player") or "").strip()]
))
matriz_prontidao=[avaliar_prontidao_regra(p) for p in players_prontidao]
demandas_prontidao=[x for x in matriz_prontidao if not x.get("pronta")]
prontas_prontidao=[x for x in matriz_prontidao if x.get("pronta")]
with st.expander(f"🚦 Prontidão operacional · {len(prontas_prontidao)} prontas · {len(demandas_prontidao)} demandas",expanded=True):
    st.caption("Esta fila separa conhecimento, workflow, executor e autorização. Cada bloqueio vira uma demanda objetiva para colocar o EDDY para trabalhar.")
    if demandas_prontidao:
        ordem={"AUTORIZAR_MOTOR":0,"IMPLEMENTAR_EXECUTOR":1,"DEFINIR_WORKFLOW":2,"ATIVAR_WORKFLOW":3,"APRENDER":4}
        for item in sorted(demandas_prontidao,key=lambda x:(ordem.get(str(x.get("estado_prontidao")),9),str(x.get("player")))):
            estado=str(item.get("estado_prontidao") or "REVISAR")
            icone={"AUTORIZAR_MOTOR":"🟠","IMPLEMENTAR_EXECUTOR":"🛠️","DEFINIR_WORKFLOW":"🧭","ATIVAR_WORKFLOW":"⏯️","APRENDER":"🧠"}.get(estado,"⚠️")
            st.markdown(
                f"{icone} **{item.get('player')}** · `{item.get('regra_id') or 'sem regra homologada'}` · "
                f"**{estado.replace('_',' ')}** — {item.get('proxima_acao')}. "
                f"Bloqueios: `{', '.join(item.get('bloqueios') or []) or '—'}`"
            )
    else:
        st.success("Todas as regras conhecidas estão operacionalmente prontas.")

# Promoção em lote desabilitada: autorização é individual, auditável e
# dependente da operação e dos checkpoints de cada workflow.
st.caption("A autorização automática é individual por regra. Não há promoção em lote.")

aba0,aba1,aba2,aba3=st.tabs([f"📚 Todas as regras ({len(catalogo_declarativo)+len(regras_treinaveis)})",f"1 · Revisar e homologar ({len(revisar)})",f"2 · Autorizar motor ({len(bloqueadas)})",f"Regras ativas ({len(autorizadas)})"])
with aba0:
    st.caption("Este é o catálogo operacional do EDDY. Abra uma regra para ver o modelo configurado, alterar parâmetros seguros ou inativá-la sem apagar seu histórico.")
    filtro=st.text_input("Buscar regra",placeholder="Ex.: SICREDI, GREENCARD, banco, inclusão...",key="catalogo_busca"); alvo=str(filtro or '').casefold().strip()
    for wf in catalogo_declarativo:
        player=str(wf.get("player") or ""); texto=" ".join([player,str(wf.get("workflow") or ""),str(wf.get("tipo_player") or ""),str(wf.get("regra_dados") or "")]).casefold()
        if alvo and alvo not in texto: continue
        ativa=bool(wf.get("ativa",True)); status="ATIVA" if ativa else "INATIVA"
        with st.expander(f"{player} · {wf.get('workflow') or 'SEM WORKFLOW'} · {status}",expanded=(player=="SICREDI" and not alvo)):
            a,b,c,d=st.columns(4); a.metric("Tipo",wf.get("tipo_player") or "—"); b.metric("Canal",wf.get("canal") or "—"); c.metric("Executor",wf.get("prontidao") or "—"); d.metric("Estado",status)
            st.write("**Como está configurada**"); st.write(wf.get("regra_dados") or "Regra declarativa sem descrição operacional detalhada."); st.write("**Dados obrigatórios:**",", ".join(wf.get("campos_obrigatorios") or []) or "—"); st.write("**Etapas:**"," → ".join(wf.get("etapas") or []) or "—")
            extras=[]
            for k in ("destinatario_padrao","fonte_dados","status_pos_envio","sla_primeiro_followup_horas","van_solicitada","layout_extrato","periodicidade"):
                if wf.get(k) not in (None,""): extras.append(f"**{k}:** {wf.get(k)}")
            if extras: st.markdown("  \n".join(extras))
            with st.form(f"edit_cfg_{player}"):
                st.markdown("**Editar configuração operacional segura**"); nova_ativa=st.checkbox("Regra ativa",value=ativa); novo_dest=st.text_input("Destinatário padrão",value=str(wf.get("destinatario_padrao") or ""),help="Deixe vazio quando o destinatário for resolvido pelo Blueprint/regra."); nova_desc=st.text_area("Descrição / regra operacional",value=str(wf.get("regra_dados") or ""),height=110); novo_sla=st.number_input("Primeiro follow-up (horas)",min_value=1,max_value=720,value=int(wf.get("sla_primeiro_followup_horas") or 48),step=1)
                if st.form_submit_button("💾 Salvar alterações",type="primary"):
                    override={"regra_dados":nova_desc}; override["destinatario_padrao"]=novo_dest.strip() if novo_dest.strip() else ""; override["sla_primeiro_followup_horas"]=int(novo_sla); salvar_configuracao_regra(player,ativa=nova_ativa,override=override); st.success(f"{player}: configuração salva. Histórico preservado."); st.rerun()
    if regras_treinaveis:
        st.markdown("### Regras ensinadas pelo Construtor")
        for rt in regras_treinaveis:
            with st.expander(f"{rt['player']} · {rt['nome']} · {rt['estado']}"):
                st.write(explicar_regra(rt)); st.caption(f"ID {rt['id']} · Canal {rt['canal']} · Fonte {rt['fonte_dados']}")
                if st.button("✏️ Abrir para editar/testar",key=f"open_train_{rt['id']}"): st.session_state["ednna_editar_regra_id"]=rt['id']; st.switch_page("pages/Construtor_Regras.py")

with aba1:
    if not revisar: st.success("Não há regras aguardando homologação.")
    for rr in revisar:
        rid=str(rr.get("regra_id") or ""); player=str(rr.get("player") or "Player"); aprendido=rr.get("payload") or obter_aprendizado(rid) or {}; rev=obter_revisao(rid); wf=rr.get("workflow") or obter_workflow(player); comp=int(rr.get("completude") or aprendido.get("completude") or 0); recorr=list(dict.fromkeys(aprendido.get("destinatarios_recorrentes") or [])); sugerido=str(rev.get("destinatario_confirmado") or "") or (recorr[0] if recorr else "")
        with st.expander(f"{player} · {rid} · {comp}% · {rr.get('estado_operacional') or rr.get('estado') or 'A revisar'}",expanded=True):
            a,b,c=st.columns(3); a.metric("Completude",f"{comp}%"); b.metric("Canal",wf.get("canal") or "—"); c.metric("Executor",wf.get("prontidao") or "—"); st.write(f"**Workflow:** `{wf.get('workflow') or 'NAO_CLASSIFICADO'}`")
            if wf.get("procedimento_confirmado"): st.success("Procedimento operacional confirmado. O histórico complementa a evidência, mas não bloqueia a homologação.")
            if recorr: st.caption("Destinatários encontrados: "+" · ".join(recorr))
            dest=st.text_input("Destinatário confirmado",value=sugerido,key=f"central_dest_{rid}",placeholder="contato@player.com.br"); obs=st.text_area("Observação da homologação",value=str(rev.get("observacoes") or ""),key=f"central_obs_{rid}",height=75)
            if st.button("✅ Revisar e homologar",key=f"central_hom_{rid}",type="primary",width="content"):
                try: salvar_revisao_assistida(rid,destinatario_confirmado=dest,observacoes=obs,revisado_por="OPERADOR_EDNNA"); homologar_regra_assistida(rid,revisado_por="OPERADOR_EDNNA"); st.success(f"{player}: regra homologada. Agora ela aparecerá na etapa 2 para autorização do motor."); st.rerun()
                except Exception as exc: st.error(f"Não foi possível homologar {player}: {exc}")

with aba2:
    if not bloqueadas: st.success("Nenhuma regra homologada aguarda autorização.")
    for rr in bloqueadas:
        rid=str(rr.get("regra_id") or ""); player=str(rr.get("player") or "Player"); wf=rr.get("workflow") or obter_workflow(player)
        with st.expander(f"{player} · {rid} · BLOQUEADA",expanded=True):
            a,b,c=st.columns(3); a.metric("Conhecimento","Homologado"); b.metric("Executor",wf.get("prontidao") or "—"); c.metric("Motor","Bloqueado"); st.caption("Canal: "+str(wf.get("canal") or "—")+" · Workflow: "+str(wf.get("workflow") or "—"))
            if wf.get("prontidao")=="ASSISTIDA_DISPONIVEL":
                st.info("Executor disponível. Escolha se a regra exige confirmação humana ou se o EDDY pode executar automaticamente.")
                c_ass,c_auto=st.columns(2)
                with c_ass:
                    if st.button("▶️ Autorizar assistida",key=f"central_auth_{rid}",type="primary",width="content"):
                        try: autorizar_regra_motor(rid,modo="ASSISTIDA",autorizado_por="OPERADOR_EDNNA"); st.success(f"{player}: operação assistida autorizada."); st.rerun()
                        except Exception as exc: st.error(str(exc))
                with c_auto:
                    if st.button("⚡ Autorizar automática",key=f"central_auto_{rid}",width="content"):
                        try: autorizar_regra_motor(rid,modo="AUTOMATICA",autorizado_por="OPERADOR_EDNNA",observacoes="Autorização explícita para execução automática de regra homologada."); st.success(f"{player}: execução automática autorizada."); st.rerun()
                        except Exception as exc: st.error(str(exc))
            else:
                falt=wf.get("executores_faltantes") or []; st.warning("Não pode ser ativada ainda: o executor deste workflow não está disponível."+((" Falta: "+" · ".join(falt)) if falt else ""))

with aba3:
    if not autorizadas: st.info("Nenhuma regra está autorizada no motor.")
    for rr in autorizadas:
        rid=str(rr.get("regra_id") or ""); player=str(rr.get("player") or "Player"); wf=rr.get("workflow") or obter_workflow(player); modo=str((rr.get("autorizacao_motor") or {}).get("modo") or "ASSISTIDA").upper(); dg=diag_por_id.get(rid) or {}; situacao=str(dg.get("situacao") or "SEM_DIAGNOSTICO"); total_demanda=int(dg.get("total_chamados") or 0)
        with st.expander(f"{player} · {rid} · {modo} · {situacao.replace('_',' ')} · {total_demanda} chamado(s)",expanded=(modo=="ASSISTIDA")):
            a,b,c,d=st.columns(4); a.metric("Conhecimento","Homologado"); b.metric("Executor",wf.get("prontidao") or "—"); c.metric("Motor",modo.title()); d.metric("Chamados ativos",total_demanda); st.info(str(dg.get("motivo") or "Diagnóstico operacional indisponível.")); chamados_dg=dg.get("chamados") or []
            if chamados_dg:
                st.markdown("**Chamados encontrados para esta regra**")
                for ch in chamados_dg:
                    cid=int(ch.get("id") or 0); st.markdown(f"- [#{cid}]({redmine_link(cid)}) · {html.escape(str(ch.get('cliente') or 'Cliente não informado'))} · **{html.escape(str(ch.get('motivo') or 'Revisar'))}** · próxima ação: {html.escape(str(ch.get('acao_sugerida') or 'Revisar'))}")
            else: st.caption("Nenhum chamado ativo compatível. A regra está disponível, mas não há demanda para ela neste momento.")
            ca,cb=st.columns(2)
            with ca:
                if modo=="ASSISTIDA" and wf.get("prontidao")=="ASSISTIDA_DISPONIVEL":
                    if st.button("⚡ Tornar AUTOMÁTICA",key=f"central_promote_{rid}",type="primary",width="content"):
                        autorizar_regra_motor(rid,modo="AUTOMATICA",autorizado_por="OPERADOR_EDNNA",observacoes="Promoção explícita após revisão dos chamados e do diagnóstico operacional na Central de Regras."); st.success(f"{player}: o EDDY está autorizado a executar esta regra automaticamente."); st.rerun()
            with cb:
                if st.button("⏸️ Suspender regra",key=f"central_suspend_{rid}",width="content"): autorizar_regra_motor(rid,modo="BLOQUEADA",autorizado_por="OPERADOR_EDNNA"); st.rerun()

st.divider(); rows=[]
for r in regras:
    wf=r.get("workflow") or obter_workflow(r.get("player")); pr=avaliar_prontidao_regra(r.get("player")); rows.append({"Player":r.get("player"),"Regra":r.get("regra_id"),"Conhecimento":r.get("estado_operacional") or r.get("estado"),"Workflow":wf.get("workflow"),"Executor":wf.get("prontidao"),"Motor":str((r.get("autorizacao_motor") or {}).get("modo") or "BLOQUEADA"),"Prontidão":pr.get("estado_prontidao"),"Bloqueios":", ".join(pr.get("bloqueios") or []),"Próxima ação":pr.get("proxima_acao")})
st.markdown("### Inventário completo"); st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True); st.caption(f"EDDY v{APP_VERSION} · Central de Regras")
# Inventário unificado: regras do aprendizado de inclusão e homologações da Escola.
# A aprovação excepcional não habilita envios nem remove checkpoints do executor.
st.divider()
st.subheader("📚 Inventário unificado · Escola + Central")
_homologacoes_escola = listar_homologacoes_mais_recentes()
_ids_catalogo = {str(x.get("regra_id") or "") for x in regras}
_linhas_unificadas = []
for _h in _homologacoes_escola:
    _rid = str(_h.get("regra_id") or "")
    _operacao = ("ABERTURA" if _rid.upper().startswith("ABERTURA-") else
                 "INCLUSAO" if _rid.upper().startswith("INCLUSAO-") else
                 "FALTA_ARQUIVO" if _rid.upper().startswith(("FALTA-ARQUIVO-", "FALTA_ARQUIVO-", "AUSENCIA-ARQUIVO-")) else "OUTRA")
    _autorizacao = obter_autorizacao_motor(_rid) or {}
    _linhas_unificadas.append({
        "Regra da Escola": _rid, "Player": _h.get("player"), "Operação": _operacao,
        "Homologação": _h.get("estado"), "Nota": _h.get("nota"),
        "Autorização": _autorizacao.get("modo") or "NÃO AUTORIZADA",
        "No catálogo operacional": "SIM" if _rid in _ids_catalogo else "NÃO · VINCULAR",
        "Executor externo": "NÃO VALIDADO" if _operacao in {"ABERTURA", "FALTA_ARQUIVO"} else "VERIFICAR WORKFLOW",
    })
if _linhas_unificadas:
    st.dataframe(pd.DataFrame(_linhas_unificadas), hide_index=True, width="stretch")
    st.caption("Inventário das homologações persistidas. O vínculo com o catálogo e a autorização são independentes; não há ativação automática.")
else:
    st.info("Ainda não há homologações persistidas disponíveis nesta instância.")
st.divider()

st.subheader("⚙️ Motores operacionais EDDY")
st.caption("Inclusão, abertura e falta de arquivo são operações distintas. Homologação de conhecimento não equivale a execução liberada.")
_motor_inclusoes = len([h for h in _homologacoes_escola if str(h.get("regra_id") or "").upper().startswith("INCLUSAO-")])
_motor_aberturas = avaliar_aberturas_homologadas()
_mi, _ma, _mf = st.columns(3)
_mi.metric("Inclusões cadastradas", _motor_inclusoes)
_ma.metric("Aberturas homologadas", len(_motor_aberturas))
_regras_falta = listar_regras_aprendidas()
_mf.metric("Falta de arquivo · homologadas", len(_regras_falta))
with st.expander("🏦 Motor de Aberturas · homologação e preparação assistida", expanded=False):
    st.warning("Preparação assistida não envia solicitações, não atualiza Redmine e não conclui abertura. O executor externo permanece pendente.")
    if _motor_aberturas:
        st.dataframe(pd.DataFrame([{"Regra":x["regra_id"],"Player":x.get("player"),"Estado":x.get("estado"),"Modo":x.get("modo"),"Executável":x.get("executavel")} for x in _motor_aberturas]),hide_index=True,width="stretch")
        _aberturas_homologadas = [x for x in _motor_aberturas if x.get("estado") == "AGUARDANDO_AUTORIZACAO"]
        if _aberturas_homologadas:
            _abertura_id = st.selectbox("Regra de abertura para preparação assistida", [x["regra_id"] for x in _aberturas_homologadas], key="abertura_regra")
            _abertura_responsavel = st.text_input("Responsável pela autorização",key="abertura_responsavel")
            _abertura_justificativa = st.text_area("Justificativa técnica (mínimo 20 caracteres)",key="abertura_justificativa")
            if st.button("Autorizar somente preparação assistida",key="abertura_autorizar",disabled=not _abertura_responsavel.strip() or len(_abertura_justificativa.strip())<20):
                try:
                    autorizar_abertura_assistida(_abertura_id,responsavel=_abertura_responsavel,justificativa=_abertura_justificativa)
                    st.success("Preparação assistida registrada. Envio externo permanece bloqueado.")
                    st.rerun()
                except Exception as _exc:
                    st.error(str(_exc))
    else:
        st.info("Nenhuma abertura homologada encontrada. As propostas continuam visíveis na seção da Escola.")
with st.expander("📁 Motor de Falta de Arquivo · diagnóstico",expanded=False):
    st.caption("A triagem depende de evidências reais de calendário, janela, recepção e frequência. Nenhum disparo externo é realizado.")
    st.write("Estados: aguardando dados, fora do calendário, dentro da janela, conferência de recepção e falta confirmada.")
    if _regras_falta:
        st.dataframe(pd.DataFrame(_regras_falta),hide_index=True,width="stretch")
    else:
        st.info("Nenhuma homologação identificada pelos identificadores de falta de arquivo. Verificar a nomenclatura das regras aprendidas.")
    st.warning("Integração com recepção real e executor de cobrança ainda pendente; nenhuma ação externa autorizada.")

st.divider()
st.subheader("📋 Homologações da Escola e decisões do professor")
st.caption("Esta visão inclui regras aprovadas na Central de Aprendizagem que antes não apareciam no inventário de inclusão. Aprovar conhecimento e liberar execução são decisões separadas.")
from ednna.homologacao import listar_homologacoes_mais_recentes, alterar_estado, homologar_por_decisao_humana
from ednna.minerador_aberturas import listar_propostas

_homologacoes=listar_homologacoes_mais_recentes()
_propostas=listar_propostas()
_por_id={str(p.get("regra_id") or ""):p for p in _propostas if p.get("regra_id")}
_hom_ids={str(h["regra_id"]) for h in _homologacoes}
_ids_operacionais={str(r.get("regra_id") or "") for r in regras}
_unificadas=[]
for h in _homologacoes:
    _unificadas.append({"Regra":h["regra_id"],"Player":h.get("player"),"Origem":"Escola / homologação","Estado":h.get("estado"),"Nota":h.get("nota"),"Responsável":h.get("homologado_por"),"Motor":"Autorização independente"})
for p in _propostas:
    rid=str(p.get("regra_id") or "")
    if rid and rid not in _hom_ids:
        _unificadas.append({"Regra":rid,"Player":p.get("player"),"Origem":"Escola / proposta","Estado":"EM_APRENDIZADO","Nota":"—","Responsável":"—","Motor":"BLOQUEADA"})
for rr in regras:
    rid=str(rr.get("regra_id") or "")
    if rid and rid not in _hom_ids:
        _unificadas.append({"Regra":rid,"Player":rr.get("player"),"Origem":"Aprendizado / inclusão","Estado":rr.get("estado_revisao") or rr.get("estado"),"Nota":rr.get("completude"),"Responsável":"—","Motor":(rr.get("autorizacao_motor") or {}).get("modo","BLOQUEADA")})
if _unificadas:
    st.dataframe(pd.DataFrame(_unificadas),hide_index=True,width="stretch")
else:
    st.info("Ainda não há regras persistidas nas fontes consultadas.")

for h in _homologacoes:
    rid=str(h["regra_id"])
    with st.expander(f"🎓 {h.get('player') or 'Player'} · {rid} · {h.get('estado')} · {h.get('nota')}%"):
        st.caption(f"Versão {h.get('versao')} · Homologada por {h.get('homologado_por')} · {h.get('motivo') or 'Sem observações'}")
        aut_escola=obter_autorizacao_motor(rid)
        wf_escola=obter_workflow(h.get("player"))
        modo_escola=str(aut_escola.get("modo") or "BLOQUEADA")
        st.write(f"**Motor:** {modo_escola} · **Executor:** {wf_escola.get('prontidao') or 'NÃO IDENTIFICADO'}")
        operacao_escola = str(rid).split("-",1)[0].upper()
        pode_autorizar_escola = operacao_escola == "INCLUSAO" and h.get("estado") in {"ATIVA","EM_OBSERVACAO"} and wf_escola.get("prontidao")=="ASSISTIDA_DISPONIVEL"
        if pode_autorizar_escola:
            col_ass,col_auto=st.columns(2)
            with col_ass:
                if st.button("▶ Autorizar assistida",key="school_ass_"+rid):
                    autorizar_regra_motor(rid,modo="ASSISTIDA",autorizado_por="OPERADOR_EDNNA",observacoes="Autorização da regra homologada na Escola")
                    st.rerun()
            with col_auto:
                if st.button("⚡ Autorizar automática",key="school_auto_"+rid):
                    autorizar_regra_motor(rid,modo="AUTOMATICA",autorizado_por="OPERADOR_EDNNA",observacoes="Autorização explícita da regra homologada na Escola; sujeito aos checkpoints")
                    st.rerun()
        elif h.get("estado")!="SUSPENSA":
            st.warning("Execução não liberada: regras de abertura e outras operações exigem executor específico; inclusão exige executor disponível.")
        if h.get("estado")!="SUSPENSA":
            if st.button("⏸ Suspender homologação",key="school_suspend_"+rid):
                alterar_estado(rid,"SUSPENSA","OPERADOR_EDNNA","Suspensão manual na Central de Regras")
                from ednna.aprendizado_operacional import _garantir_tabela_autorizacoes_motor
                from ednna.armazenamento import conectar, agora_brasil_iso
                _garantir_tabela_autorizacoes_motor()
                with conectar() as conn:
                    agora=agora_brasil_iso()
                    conn.execute("UPDATE autorizacoes_motor SET modo='BLOQUEADA', autorizado_por=?, autorizado_em=?, observacoes=?, atualizado_em=? WHERE regra_id=?",
                                 ("OPERADOR_EDNNA", agora, "Suspensão manual da homologação da Escola", agora, rid))
                st.rerun()
        else:
            st.warning("Regra suspensa. A reativação exige decisão explícita e revisão do procedimento.")
            if st.button("▶ Reativar em observação",key="school_resume_"+rid):
                alterar_estado(rid,"EM_OBSERVACAO","OPERADOR_EDNNA","Reativação manual supervisionada")
                st.rerun()

for rid,p in _por_id.items():
    if rid in _hom_ids: continue
    with st.expander(f"👨‍🏫 Aprovar por decisão humana · {p.get('player') or rid} · {rid}"):
        st.warning("A aprovação excepcional preserva a nota e inicia em observação. Não autoriza envio automático; exige executor e liberação operacional próprios.")
        professor=st.text_input("Responsável pela decisão",key="override_prof_"+rid)
        motivo=st.text_area("Justificativa técnica e riscos aceitos",key="override_reason_"+rid)
        nota=st.number_input("Nota de aprendizado verificada (%)",min_value=0,max_value=100,value=0,key="override_score_"+rid)
        confirma=st.checkbox("Revisei evidências, destinatários, segurança e checkpoints; autorizo a homologação em observação.",key="override_confirm_"+rid)
        if st.button("✅ Homologar excepcionalmente",key="override_approve_"+rid,disabled=not confirma):
            try:
                homologar_por_decisao_humana(p,professor,motivo,nota=int(nota))
                st.success("Homologação registrada em observação. A execução permanece sujeita à autorização do motor.")
                st.rerun()
            except Exception as exc: st.error(str(exc))
