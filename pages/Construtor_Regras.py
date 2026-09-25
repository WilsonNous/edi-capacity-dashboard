from __future__ import annotations
import streamlit as st
from version import APP_VERSION
from ednna.construtor_regras import *

st.set_page_config(page_title="EDNNA · Ensinar regra", page_icon="🧩", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}.stApp{background:#f5f8fc}.block-container{max-width:1450px;padding:1.1rem 1.6rem 2rem}div.stButton>button{border-radius:10px!important;font-weight:750!important}</style>""", unsafe_allow_html=True)

c1,c2,_=st.columns([1,1,6])
with c1:
    if st.button("← EDNNA", width="stretch"): st.switch_page("app.py")
with c2:
    if st.button("🧠 Regras", width="stretch"): st.switch_page("pages/Regras.py")

st.title("🧩 Ensinar uma regra à EDNNA")
st.caption("Descreva o procedimento como a operação trabalha. A EDNNA estrutura, simula e explica o que aprendeu antes de qualquer homologação.")

regras=listar_regras_treinaveis()
aba_nova, aba_lab, aba_catalogo = st.tabs(["➕ Ensinar nova regra", "🧪 Laboratório", f"📚 Regras ensinadas ({len(regras)})"])

with aba_nova:
    st.subheader("1 · Como reconhecer")
    a,b,c=st.columns(3)
    player=a.text_input("Player / banco / adquirente", placeholder="Ex.: ROTACARD")
    nome=b.text_input("Nome da regra", placeholder="Ex.: Inclusão de estabelecimento")
    tipo=c.selectbox("Tipo", TIPOS)
    aliases_txt=st.text_input("Outros nomes que podem aparecer", placeholder="Ex.: ROTA CARD, ROTA-CARD (separe por vírgula)")
    tipos=st.multiselect("Que tipos de chamado atende?", ["Abertura de relacionamento","Inclusão de estabelecimento","Falta de arquivo","Cancelamento","Alteração","Outro"])

    st.subheader("2 · Que informações eu preciso?")
    vars_sel=st.multiselect("Variáveis obrigatórias", list(VARIAVEIS.keys()), format_func=lambda x: VARIAVEIS[x])
    fonte=st.selectbox("Onde procurar primeiro?", FONTES)

    st.subheader("3 · O que devo fazer?")
    etapas=st.multiselect("Monte o procedimento na ordem", list(ACOES.keys()), format_func=lambda x: ACOES[x])
    canal=st.selectbox("Canal principal", CANAIS)
    destinatario=st.text_input("Destinatário fixo, se existir", placeholder="Deixe vazio quando vier do Blueprint/cliente")
    descricao=st.text_area("Explique a regra com suas palavras", height=100, placeholder="Ex.: preencher formulário, mandar ao cliente, aguardar assinatura...")

    st.subheader("4 · Textos")
    assunto=st.text_input("Modelo de assunto", placeholder="[{{player}} - {{tipo}} - {{cliente}} - CN: {{chamado}}]")
    corpo=st.text_area("Corpo do e-mail", height=170, placeholder="Use variáveis como {{cliente}}, {{cnpjs}}, {{estabelecimento}}...")
    follow=st.text_area("Follow-up", height=100, placeholder="Texto que será usado se não houver resposta")

    if st.button("💾 Salvar como RASCUNHO", type="primary"):
        if not player.strip() or not nome.strip(): st.error("Informe pelo menos Player e Nome da regra.")
        else:
            rid=salvar_regra({"player":player,"nome":nome,"tipo_player":tipo,"aliases":[x.strip() for x in aliases_txt.split(',') if x.strip()],"tipos_chamado":tipos,"canal":canal,"fonte_dados":fonte,"destinatario":destinatario,"variaveis":vars_sel,"etapas":etapas,"assunto_template":assunto,"corpo_template":corpo,"followup_template":follow,"descricao":descricao,"estado":"RASCUNHO"})
            st.success(f"Regra {rid} salva. Agora leve-a ao Laboratório.")
            st.rerun()

with aba_lab:
    regras=listar_regras_treinaveis()
    if not regras: st.info("Ensine a primeira regra para liberar o laboratório.")
    else:
        mapa={f"{r['player']} · {r['nome']} · {r['estado']}":r for r in regras}
        escolhido=st.selectbox("Regra para testar", list(mapa.keys()))
        r=mapa[escolhido]
        st.info("🧠 **O que eu entendi:** "+explicar_regra(r))
        st.markdown("#### Teste sem enviar nada")
        cid=st.number_input("Chamado (opcional)", min_value=0, step=1)
        ass=st.text_input("Assunto do chamado para simulação")
        desc=st.text_area("Descrição do chamado", height=180)
        if st.button("🧪 Simular regra", type="primary"):
            res=testar_regra(r,ass,desc,int(cid) if cid else None)
            if res["identificada"]: st.success("Player/regra reconhecidos no texto.")
            else: st.error("Ainda não consegui reconhecer esta regra no texto.")
            st.json(res)
        st.divider()
        ca,cb=st.columns(2)
        with ca:
            if r["estado"]=="RASCUNHO" and st.button("➡️ Marcar como EM TESTE"):
                r["estado"]="EM_TESTE"; salvar_regra(r); st.rerun()
        with cb:
            if r["estado"]=="EM_TESTE" and st.button("✅ Homologar regra ensinada", type="primary"):
                r["estado"]="HOMOLOGADA"; salvar_regra(r); st.success("Homologada. Ela pode fornecer workflow declarativo ao motor; autorização automática continua separada na Central de Regras."); st.rerun()

with aba_catalogo:
    for r in listar_regras_treinaveis():
        with st.expander(f"{r['player']} · {r['nome']} · {r['estado']}"):
            st.write(explicar_regra(r))
            st.caption(f"ID: {r['id']} · Canal: {r['canal']} · Fonte: {r['fonte_dados']}")
            if r.get('destinatario'): st.write("**Destinatário:**",r['destinatario'])
            st.write("**Variáveis:**", ", ".join(VARIAVEIS.get(x,x) for x in r.get('variaveis',[])) or "—")
            st.write("**Etapas:**", " → ".join(ACOES.get(x,x) for x in r.get('etapas',[])) or "—")
            if r.get('corpo_template'): st.code(r['corpo_template'], language=None)

st.caption(f"EDNNA v{APP_VERSION} · Construtor de Regras · RASCUNHO → EM TESTE → HOMOLOGADA → autorização na Central de Regras")
