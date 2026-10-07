from pathlib import Path
import html
import streamlit as st
from version import APP_VERSION, APP_RELEASE
from ui.operational_data import resumo, resumo_trabalho_ednna, chamados_ativos_df
from ednna.aprendizado_operacional import garantir_greencard_pronta, garantir_safrapay_pronta, garantir_itau_pronto
from ednna.monitor_respostas import iniciar_monitor_respostas_background
from ednna.security import current_user, role_label, audit, display_name

# O package ednna.* permanece por compatibilidade técnica. A identidade de produto 4.x é EDDY.
iniciar_monitor_respostas_background()
for nome, bootstrap in [('Greencard', garantir_greencard_pronta), ('Safrapay', garantir_safrapay_pronta), ('Itau', garantir_itau_pronto)]:
    try:
        bootstrap()
    except Exception as exc:
        print(f'[EDDY] Bootstrap {nome} pendente: {exc}', flush=True)

ROOT = Path(__file__).resolve().parent
AVATAR = ROOT / 'assets' / 'eddy_avatar.png'
FAVICON = ROOT / 'assets' / 'eddy_favicon.png'
st.set_page_config(page_title='EDDY · Netunna', page_icon=str(FAVICON) if FAVICON.exists() else '🦾', layout='wide', initial_sidebar_state='collapsed')

user = current_user()
if not user.authenticated:
    audit('ACCESS_BLOCKED', 'Home sem identidade Easy Auth', user)
    st.error('Acesso não autenticado. Entre novamente com sua conta corporativa Netunna.'); st.stop()
if user.role == 'BLOCKED':
    audit('ACCESS_DENIED', 'Domínio não autorizado', user)
    st.error('Esta conta não está autorizada a acessar o EDDY.'); st.stop()

st.markdown('''<style>
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
.stApp{background:linear-gradient(180deg,#f7faff,#f2f6fc);color:#102a56}.block-container{max-width:1500px;padding:1rem 1.55rem 1.2rem}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:4px 8px 13px}.brand{font-size:1.2rem;font-weight:950;color:#1268e8;letter-spacing:.04em}.sub{font-size:.68rem;letter-spacing:.16em;color:#6e8fc5;text-transform:uppercase}.status{display:inline-flex;align-items:center;gap:7px;background:#e9f8ef;color:#138348;padding:8px 14px;border-radius:999px;font-weight:850;font-size:.84rem}.dot{width:8px;height:8px;border-radius:50%;background:#17a85b}
.hero,.section{background:#fff;border:1px solid #dfe8f4;border-radius:20px;box-shadow:0 7px 22px rgba(24,75,140,.05)}.hero{padding:20px;margin-bottom:14px}.section{padding:16px 19px;margin-top:14px}.greet{font-size:.9rem;font-weight:700;color:#476787}.title{font-size:2rem;font-weight:950;line-height:1.08;color:#0d326d;margin:6px 0 10px}.copy{font-size:.94rem;line-height:1.5;color:#607591}.copy b{color:#1268e8}.section-title{font-size:1.12rem;font-weight:950;color:#102f62}.section-sub{font-size:.76rem;color:#7790b2;margin:3px 0 12px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{background:#fbfdff;border:1px solid #e1eaf6;border-radius:15px;padding:13px 14px;min-height:94px}.label{font-size:.75rem;color:#526b8c;font-weight:700}.num{font-size:1.65rem;font-weight:950;color:#1268e8;line-height:1.05;margin:6px 0}.note{font-size:.7rem;color:#8093ae}.voice{background:#f2f7ff;border:1px solid #dce8f8;border-radius:15px;padding:13px 15px;margin-top:14px;color:#476787;font-size:.8rem;line-height:1.45}.voice b{color:#17386b}.avatar img{border-radius:22px;box-shadow:0 12px 28px rgba(19,105,232,.15)}
div.stButton>button{border-radius:14px!important;min-height:62px!important;font-weight:850!important;border:1px solid #dce7f4!important;background:#fff!important;color:#17386b!important}div.stButton>button:hover{border-color:#1268e8!important;color:#1268e8!important;transform:translateY(-1px)}.foot{text-align:center;color:#8ba0bd;font-size:.68rem;margin-top:16px}@media(max-width:950px){.grid4,.grid3{grid-template-columns:repeat(2,1fr)}.title{font-size:1.6rem}}
</style>''', unsafe_allow_html=True)

r = resumo(); trabalho = resumo_trabalho_ednna(); df = chamados_ativos_df(); cobertura = round(r['homologadas']/r['regras']*100) if r['regras'] else 0
if r['revisao'] == 1: title = 'Tenho 1 decisão para você.'
elif r['revisao'] > 1: title = f"Tenho {r['revisao']} decisões para você."
elif r['aprendendo'] > 0: title = 'Estou aprendendo enquanto você trabalha.'
else: title = 'A operação está sob acompanhamento.'

st.markdown(f'<div class="topbar"><div><div class="brand">EDDY · NETUNNA</div><div class="sub">Super inteligência especializada em EDI</div></div><div style="text-align:right"><div class="status"><span class="dot"></span> Operando</div><div style="font-size:.68rem;color:#6f84a2;margin-top:4px">{html.escape(user.email)} · {html.escape(role_label(user.role))}</div></div></div>', unsafe_allow_html=True)

st.markdown('<div class="hero">', unsafe_allow_html=True)
av, main = st.columns([1,4], vertical_alignment='center')
with av:
    if AVATAR.exists():
        st.markdown('<div class="avatar">', unsafe_allow_html=True); st.image(str(AVATAR), width='stretch'); st.markdown('</div>', unsafe_allow_html=True)
    else: st.markdown('<div style="font-size:4rem;text-align:center">🦾</div>', unsafe_allow_html=True)
with main:
    st.markdown(f'<div class="greet">Olá, {html.escape(display_name(user) or "você")}! Eu sou o EDDY.</div><div class="title">{html.escape(title)}</div><div class="copy">Estou acompanhando <b>{r["total"]} chamados ativos</b>. A equipe e eu continuamos trabalhando; você entra onde sua decisão faz diferença.<br><b>{cobertura}%</b> das regras conhecidas estão homologadas e <b>{trabalho["regras_automaticas"]}</b> já estão autorizadas para atuação automática.</div>', unsafe_allow_html=True)
pct = round(r['terceiros']/r['total']*100) if r['total'] else 0
st.markdown(f'<div class="voice"><b>💡 Minha leitura agora:</b> {r["terceiros"]} chamados aguardam terceiros ({pct}% da carteira); estou acompanhando {trabalho["acompanhando"]} e tenho {r["revisao"]} decisão(ões) para o professor.</div></div>', unsafe_allow_html=True)

def cards(items, cols='grid4'):
    return f'<div class="{cols}">' + ''.join(f'<div class="card"><div class="label">{html.escape(str(a))}</div><div class="num">{b}</div><div class="note">{html.escape(str(c))}</div></div>' for a,b,c in items) + '</div>'

estado=[('Chamados ativos',r['total'],'carteira ativa do Redmine'),('Equipe / atuação',r['em_atuacao'],'fora da espera por terceiros'),('Aguardando terceiros',r['terceiros'],'dependência externa'),('Comigo',trabalho['acompanhando'],'sob acompanhamento EDDY')]
st.markdown('<div class="section"><div class="section-title">〽 Estado da operação</div><div class="section-sub">Uma leitura rápida da carteira antes de entrar nos módulos.</div>'+cards(estado)+'</div>', unsafe_allow_html=True)

impact=[('Atuações executadas',trabalho['atuacoes'],'operações persistidas'),('Em acompanhamento',trabalho['acompanhando'],'retornos acompanhados'),('Follow-ups',trabalho['followups'],'cobranças automáticas'),('Regras automáticas',trabalho['regras_automaticas'],'procedimentos autorizados'),('Conhecimento',trabalho['clientes_conhecidos'],f"{trabalho['blueprints']} registros · {trabalho['participantes']} contatos"),('Redmine pendente',trabalho['redmine_pendente'],'reconciliações pendentes')]
st.markdown('<div class="section"><div class="section-title">🦾 O que estou fazendo por você</div><div class="section-sub">Trabalho já absorvido pelo EDDY.</div>'+cards(impact,'grid3')+'</div>', unsafe_allow_html=True)

if not df.empty and 'responsavel' in df.columns:
    vc=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts().head(4)
    pessoas=[(str(n),int(v),'responsável Redmine') for n,v in vc.items()]+[('EDDY',int(trabalho['atuacoes']),'inteligência EDI')]
    st.markdown('<div class="section"><div class="section-title">👥 Quem está com o quê?</div><div class="section-sub">Distribuição operacional. EDDY aparece como inteligência; usuários técnicos continuam sendo usuários do Redmine.</div>'+cards(pessoas)+'</div>', unsafe_allow_html=True)

st.markdown('<div class="section"><div class="section-title">Acesso rápido</div><div class="section-sub">Cada botão leva diretamente ao assunto proposto. O Painel EDI fica reservado à observabilidade da carteira.</div>', unsafe_allow_html=True)
if user.is_admin:
    nav=[('🦾 Operação de hoje','pages/Operacao.py'),('🧠 Central de Regras','pages/Regras.py'),('🎓 Central de Aprendizagem','pages/Aprendizado.py'),('⚡ Automações','pages/Automacoes.py'),('📡 Observabilidade','pages/Observabilidade.py'),('📚 Conhecimento','pages/Conhecimento.py'),('📥 Atendimentos','pages/Atendimentos.py'),('👥 Equipe','pages/Equipe.py'),('📊 Painel EDI','pages/Painel_EDI.py')]
elif user.is_edi:
    nav=[('🦾 Operação de hoje','pages/Operacao.py'),('⚡ Automações','pages/Automacoes.py'),('📚 Conhecimento','pages/Conhecimento.py'),('📥 Atendimentos','pages/Atendimentos.py'),('👥 Equipe','pages/Equipe.py'),('📊 Painel EDI','pages/Painel_EDI.py')]
else: nav=[('👥 Equipe','pages/Equipe.py'),('📊 Painel EDI','pages/Painel_EDI.py')]
for i in range(0,len(nav),3):
    row=nav[i:i+3]; cols=st.columns(len(row))
    for col,(label,page) in zip(cols,row):
        with col:
            if st.button(label,width='stretch',key='nav_'+page):
                if 'Painel_EDI' in page: st.session_state['shell_main_navigation']='Visão Geral'
                st.switch_page(page)
st.markdown('</div>', unsafe_allow_html=True)

if user.is_edi:
    st.markdown('<div class="section"><div class="section-title">Como eu carrego</div><div class="section-sub">Interface primeiro, dados depois.</div>'+cards([('1 · Imediato','SQLite','Home e navegação usam cache local.'),('2 · Sob demanda','Módulos','Cada área calcula somente o que precisa.'),('3 · Segundo plano','Snapshots','Redmine e demais fontes atualizam sem travar a Home.')],'grid3')+'</div>', unsafe_allow_html=True)

st.markdown(f'<div class="foot">EDDY v{APP_VERSION} · {APP_RELEASE} · Netunna &nbsp;|&nbsp; Inteligência EDI que trabalha com você.</div>', unsafe_allow_html=True)
