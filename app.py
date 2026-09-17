from __future__ import annotations
import sqlite3
from pathlib import Path
import streamlit as st
from version import APP_VERSION, APP_RELEASE

st.set_page_config(page_title="EDNNA — Inteligência Operacional EDI", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{display:none!important}
.stApp{background:linear-gradient(135deg,#f3f7ff 0%,#f8fafc 48%,#eef4ff 100%);color:#172b4d}
.block-container{max-width:1280px;padding:1.25rem 2rem 2rem}
.ed-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.brand{font-size:1.15rem;font-weight:900;letter-spacing:.08em;color:#1877f2}.online{background:#e8f7ee;color:#16803d;border-radius:999px;padding:7px 12px;font-weight:750;font-size:.82rem}
.hero{background:rgba(255,255,255,.92);border:1px solid #dce6f4;border-radius:28px;padding:28px 34px;box-shadow:0 14px 40px rgba(24,119,242,.09);min-height:300px;display:flex;align-items:center}.eyebrow{font-size:.72rem;font-weight:900;letter-spacing:.14em;color:#1877f2;text-transform:uppercase}.title{font-size:2.35rem;font-weight:900;line-height:1.05;margin:8px 0 12px;color:#172b4d}.copy{font-size:1.05rem;color:#5b6f88;line-height:1.55}.pulse{color:#1877f2;font-weight:900}.avatar{animation:float 3.2s ease-in-out infinite;filter:drop-shadow(0 14px 18px rgba(24,119,242,.18))}@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
.kpi{background:#fff;border:1px solid #e0e7f0;border-radius:18px;padding:15px 18px;margin-top:14px;min-height:88px}.klabel{font-size:.76rem;font-weight:850;color:#718096;text-transform:uppercase}.knum{font-size:1.75rem;font-weight:900;color:#172b4d}.knote{font-size:.76rem;color:#8796aa}
div.stButton>button{border-radius:14px!important;min-height:52px!important;font-weight:800!important;border:1px solid #d5dfed!important;background:#fff!important;box-shadow:0 3px 10px rgba(20,50,90,.05)}div.stButton>button:hover{border-color:#1877f2!important;color:#1877f2!important;transform:translateY(-1px)}
.action-title{font-size:1.05rem;font-weight:900;margin-top:22px;margin-bottom:2px}.action-sub{font-size:.86rem;color:#7b8ca5;margin-bottom:10px}.foot{text-align:center;color:#91a0b4;font-size:.72rem;margin-top:22px}
</style>
""", unsafe_allow_html=True)

def db_count(path: Path, candidates):
    if not path.exists(): return None
    try:
        con=sqlite3.connect(str(path)); cur=con.cursor()
        for sql in candidates:
            try:
                v=cur.execute(sql).fetchone()[0]; con.close(); return int(v or 0)
            except Exception: pass
        con.close()
    except Exception: pass
    return None

def rules_summary():
    try:
        from ednna.aprendizado_operacional import listar_regras_operacionais
        rs=listar_regras_operacionais() or []
        hom=sum(1 for r in rs if r.get('estado_operacional')=='HOMOLOGADA')
        rev=sum(1 for r in rs if r.get('estado_operacional')=='PRONTA_PARA_REVISAO')
        wait=sum(1 for r in rs if r.get('estado_operacional')=='AGUARDANDO_ENRIQUECIMENTO')
        return len(rs),hom,rev,wait
    except Exception:return 0,0,0,0

def chamados_count():
    p=Path('/home/data/painel.db')
    if not p.exists(): p=Path('data/painel.db')
    return db_count(p,["select count(*) from chamados", "select count(*) from snapshot_chamados", "select count(*) from issues"]) or 0

total_rules,hom,rev,wait=rules_summary(); chamados=chamados_count(); cobertura=round(hom/total_rules*100) if total_rules else 0
if rev:
    title=f"Tenho {rev} decisão{'ões' if rev != 1 else ''} para você."
    copy="O restante da operação continua comigo. Você entra apenas onde sua decisão faz diferença."
elif wait:
    title="Estou aprendendo enquanto você trabalha."
    copy=f"Tenho {wait} procedimento(s) sendo enriquecido(s) agora. Não preciso de nenhuma ação sua neste momento."
else:
    title="Está tranquilo por aqui."
    copy=f"Estou acompanhando a operação EDI e aviso quando alguma decisão precisar de você."

st.markdown('<div class="ed-top"><div class="brand">EDNNA · NETUNNA</div><div class="online">● Operando</div></div>', unsafe_allow_html=True)
left,right=st.columns([1.05,3.5],vertical_alignment='center')
with left:
    avatar=Path('assets/ednna_avatar.png')
    if avatar.exists():
        st.markdown('<div class="avatar">',unsafe_allow_html=True); st.image(str(avatar),width=245); st.markdown('</div>',unsafe_allow_html=True)
with right:
    st.markdown(f'<div class="hero"><div><div class="eyebrow">Inteligência Operacional EDI</div><div class="title">{title}</div><div class="copy">{copy}</div><div class="copy" style="margin-top:14px"><span class="pulse">{cobertura}%</span> das regras conhecidas estão homologadas.</div></div></div>',unsafe_allow_html=True)

k1,k2,k3,k4=st.columns(4)
for col,label,num,note in [(k1,'Chamados',chamados,'acompanhados'),(k2,'Homologadas',hom,'regras no patrimônio'),(k3,'Para você',rev,'prontas para revisão'),(k4,'Aprendendo',wait,'em enriquecimento')]:
    with col: st.markdown(f'<div class="kpi"><div class="klabel">{label}</div><div class="knum">{num}</div><div class="knote">{note}</div></div>',unsafe_allow_html=True)

st.markdown('<div class="action-title">O que você quer fazer?</div><div class="action-sub">Entre somente na área que precisa. A EDNNA continua trabalhando em segundo plano.</div>',unsafe_allow_html=True)
a,b,c=st.columns(3)
with a:
    if st.button('📊  Abrir Painel EDI',use_container_width=True):
        st.session_state['shell_main_navigation']='Visão Geral'; st.switch_page('pages/Painel_EDI.py')
with b:
    if st.button('🧠  Aprendizado e homologação',use_container_width=True):
        st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
with c:
    if st.button('📥  Atendimentos da EDNNA',use_container_width=True):
        st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
d,e,f=st.columns(3)
with d:
    if st.button('⚡  Automações',use_container_width=True):
        st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')
with e:
    if st.button('👥  Equipe e capacidade',use_container_width=True):
        st.session_state['shell_main_navigation']='Equipe'; st.switch_page('pages/Painel_EDI.py')
with f:
    if st.button('⚙️  Área técnica',use_container_width=True):
        st.session_state['shell_main_navigation']='EDNNA'; st.switch_page('pages/Painel_EDI.py')

st.markdown(f'<div class="foot">EDNNA v{APP_VERSION} · {APP_RELEASE} · Home operacional</div>',unsafe_allow_html=True)
