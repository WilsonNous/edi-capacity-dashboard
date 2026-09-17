from pathlib import Path
import html
import re
import streamlit as st
from version import APP_VERSION, APP_RELEASE
from ui.operational_data import resumo, chamados_df

ROOT = Path(__file__).resolve().parent
AVATAR = ROOT / 'assets' / 'ednna_avatar.png'
FAVICON = ROOT / 'assets' / 'ednna_favicon.png'

st.set_page_config(
    page_title='EDNNA · Netunna',
    page_icon=str(FAVICON if FAVICON.exists() else AVATAR) if AVATAR.exists() else '✨',
    layout='wide', initial_sidebar_state='collapsed'
)

st.markdown('''<style>
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
.stApp{background:linear-gradient(180deg,#f7faff 0%,#f2f6fc 100%);color:#102a56}.block-container{max-width:1500px;padding:1rem 1.55rem 1.2rem}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:4px 8px 13px}.brand-main{font-size:1.25rem;font-weight:950;color:#1268e8;letter-spacing:.02em}.brand-sub{font-size:.72rem;letter-spacing:.14em;color:#6e8fc5;text-transform:uppercase}.status{display:inline-flex;align-items:center;gap:7px;background:#e9f8ef;color:#138348;padding:8px 14px;border-radius:999px;font-weight:850;font-size:.84rem}.status-dot{width:8px;height:8px;border-radius:50%;background:#17a85b}
.st-key-hero_shell{background:#fff;border:1px solid #e0e9f5;border-radius:22px;padding:10px 14px;box-shadow:0 8px 26px rgba(24,75,140,.06);margin-bottom:0}.st-key-hero_shell>div{gap:.65rem}.hero-copy{padding:20px 12px 12px 5px}.greet{font-size:1rem;color:#173f79;margin-bottom:4px}.hero-title{font-size:2rem;font-weight:950;line-height:1.08;color:#0d326d;margin:6px 0 12px}.hero-text{font-size:1rem;color:#59708f;line-height:1.48;max-width:680px}.hero-text b{color:#1268e8}.avatar-wrap{text-align:center;padding:4px 0}.avatar-wrap img{border-radius:18px;box-shadow:0 12px 28px rgba(19,105,232,.15);animation:ednnaFloat 3.4s ease-in-out infinite}.avatar-state{display:inline-block;margin-top:6px;padding:5px 10px;border-radius:999px;background:#eef5ff;color:#1769d2;font-size:.72rem;font-weight:800}@keyframes ednnaFloat{50%{transform:translateY(-5px)}}
.ops-panel{background:#fbfdff;border:1px solid #edf2f8;border-radius:18px;padding:13px;height:100%}.ops-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-weight:900;color:#17386b}.ops-pill{font-size:.72rem;color:#16834a;background:#eaf9f0;padding:6px 10px;border-radius:999px}.kpi{background:#fff;border:1px solid #e1eaf6;border-radius:15px;padding:13px 14px;min-height:103px;box-shadow:0 2px 8px rgba(24,75,140,.03)}.klabel{font-size:.78rem;color:#526b8c}.knum{font-size:1.72rem;font-weight:950;color:#0d326d;line-height:1.05;margin:5px 0}.knote{font-size:.72rem;color:#8093ae}.kpi.ednna .knum{color:#1268e8}
.insight-card{background:#f2f7ff;border:1px solid #e1ebf8;border-radius:14px;padding:9px 12px;margin-top:14px}.insight-title{display:flex;justify-content:space-between;align-items:center;font-size:.82rem;font-weight:900;color:#17386b;margin-bottom:8px}.insight-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0}.insight{padding:1px 12px;border-right:1px solid #dce7f5;font-size:.74rem;color:#59708f}.insight:first-child{padding-left:0}.insight:last-child{border-right:0}.insight b{display:block;color:#0d326d;font-size:.88rem;margin-bottom:1px}
.section-shell{background:#fff;border:1px solid #e0e9f5;border-radius:20px;padding:15px 18px;margin-top:14px;box-shadow:0 5px 18px rgba(24,75,140,.04)}.section-title{font-size:1.12rem;font-weight:950;color:#102f62}.section-sub{font-size:.76rem;color:#7790b2;margin:2px 0 11px}.people-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.person{background:#fff;border:1px solid #dfe8f4;border-radius:14px;padding:12px 13px;min-height:95px}.person-top{display:flex;align-items:center;gap:9px}.initial{width:34px;height:34px;border-radius:50%;background:#e7f0ff;color:#173f79;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:.75rem;flex:0 0 auto}.initial.ai{background:#edf4ff;color:#1268e8}.pname{font-weight:900;font-size:.82rem;color:#17386b;line-height:1.12}.ptype{font-size:.66rem;color:#8093ae;margin-top:2px}.pnum{font-size:1.35rem;font-weight:950;color:#1268e8;line-height:1.05;margin-top:8px}.pnote{font-size:.68rem;color:#8093ae}
.module-title{font-size:1.1rem;font-weight:950;color:#102f62;margin:0 0 2px}.module-sub{font-size:.72rem;color:#8093ae;margin-bottom:10px}div.stButton>button{border-radius:14px!important;min-height:70px!important;font-weight:850!important;border:1px solid #dce7f4!important;background:#fff!important;color:#17386b!important;box-shadow:0 2px 8px rgba(24,75,140,.03)!important}div.stButton>button:hover{border-color:#1268e8!important;color:#1268e8!important;transform:translateY(-1px)}
.foot{text-align:center;color:#8ba0bd;font-size:.68rem;margin-top:14px}.redmine-note{font-size:.67rem;color:#8ba0bd;text-align:right;margin-top:6px}
@media(max-width:1000px){.people-grid{grid-template-columns:repeat(2,1fr)}.insight-grid{grid-template-columns:1fr}.insight{border-right:0;border-bottom:1px solid #dce7f5;padding:6px 0}.insight:last-child{border-bottom:0}.hero-title{font-size:1.65rem}}
</style>''', unsafe_allow_html=True)

r = resumo(); df = chamados_df(); cobertura = round(r['homologadas']/r['regras']*100) if r['regras'] else 0
if r['revisao'] == 1: title = 'Tenho 1 decisão para você.'
elif r['revisao'] > 1: title = f"Tenho {r['revisao']} decisões para você."
elif r['aprendendo'] > 0: title = 'Estou aprendendo enquanto você trabalha.'
else: title = 'A operação está sob acompanhamento.'
if r['revisao'] > 0: state_label='Atenção · decisão pendente'
elif r['aprendendo'] > 0: state_label='Analisando a operação'
else: state_label='Operação acompanhada'

st.markdown('<div class="topbar"><div><div class="brand-main">EDNNA · NETUNNA</div><div class="brand-sub">Inteligência Operacional EDI</div></div><div class="status"><span class="status-dot"></span> Operando</div></div>', unsafe_allow_html=True)

hero = st.container(key='hero_shell')
with hero:
    avcol, copycol, opscol = st.columns([1.15, 2.55, 2.25], gap='medium', vertical_alignment='center')
with avcol:
    if AVATAR.exists():
        st.markdown('<div class="avatar-wrap">', unsafe_allow_html=True)
        st.image(str(AVATAR), width='stretch')
        st.markdown(f'<div class="avatar-state">{html.escape(state_label)}</div></div>', unsafe_allow_html=True)
with copycol:
    st.markdown(f'''<div class="hero-copy"><div class="greet">Olá! Eu sou a EDNNA.</div><div class="hero-title">{html.escape(title)}</div><div class="hero-text">Estou acompanhando <b>{r['total']} chamados</b>. A equipe e a EDNNA continuam trabalhando; você entra apenas onde sua decisão faz diferença.</div><div class="hero-text" style="margin-top:8px"><b>{cobertura}%</b> das regras conhecidas estão homologadas.</div></div>''', unsafe_allow_html=True)
    ins=[]
    if r['total']:
        pct=round(r['terceiros']/r['total']*100)
        if pct>=40: ins.append((f'{pct}%', 'dependem de terceiros'))
    if not df.empty and 'responsavel' in df.columns:
        vc=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts()
        # usuário Redmine da EDNNA é operacional; não usar como pessoa para apontamento de concentração
        vc_humana=vc[~vc.index.astype(str).str.lower().str.contains(r'ednna.*automa', regex=True)]
        if len(vc_humana):
            nome,n=vc_humana.index[0],int(vc_humana.iloc[0]); pct=round(n/len(df)*100)
            if pct>=30: ins.append((str(nome).split()[0], f'concentra {pct}%'))
    if r['revisao']: ins.append((f"{r['revisao']} procedimento" + ('' if r['revisao']==1 else 's'), 'pronto' + ('' if r['revisao']==1 else 's') + ' para decisão'))
    if ins:
        cells=''.join(f'<div class="insight"><b>{html.escape(a)}</b>{html.escape(b)}</div>' for a,b in ins[:3])
        st.markdown(f'<div class="insight-card"><div class="insight-title"><span>💡 Leitura da EDNNA</span><span style="font-weight:700;color:#1268e8">fotografia atual</span></div><div class="insight-grid">{cells}</div></div>', unsafe_allow_html=True)
with opscol:
    st.markdown('<div class="ops-panel"><div class="ops-head"><span>〽 Estado da operação</span><span class="ops-pill">✚ Em acompanhamento</span></div>', unsafe_allow_html=True)
    k1,k2=st.columns(2); k3,k4=st.columns(2)
    data=[(k1,'Chamados gerais',r['total'],'em acompanhamento',''),(k2,'Equipe / Atuação',r['em_atuacao'],'fora de espera por terceiros',''),(k3,'Aguardando terceiros',r['terceiros'],'dependência externa',''),(k4,'EDNNA',r['revisao']+r['aprendendo'],'regras em atenção','ednna')]
    for col,label,num,note,klass in data:
        with col: st.markdown(f'<div class="kpi {klass}"><div class="klabel">{label}</div><div class="knum">{num}</div><div class="knote">{note}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
# Distribuição: EDNNA Automação EDI é usuário real do Redmine; EDNNA inteligência é outra camada.
st.markdown('<div class="section-shell"><div class="section-title">👥 Quem está com o quê?</div><div class="section-sub">Distribuição dos chamados por responsável. O usuário “ednna automação edi” participa da operação no Redmine; a EDNNA Inteligência aparece separadamente.</div>', unsafe_allow_html=True)
people=[]
if not df.empty and 'responsavel' in df.columns:
    vc=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts()
    ednna_mask=vc.index.astype(str).str.lower().str.contains(r'ednna.*automa', regex=True)
    ednna_user=vc[ednna_mask]
    humanos=vc[~ednna_mask].head(3)
    for nome,n in humanos.items(): people.append((str(nome),int(n),'chamados','humano'))
    if len(ednna_user): people.append((str(ednna_user.index[0]),int(ednna_user.iloc[0]),'chamados · usuário Redmine','redmine_ai'))
while len(people)<4: people.append(('Sem responsável',0,'chamados','humano'))
people=people[:4]
people.append(('EDNNA',r['revisao']+r['aprendendo'],'regras em atenção · inteligência','intel'))
html_people=[]
for nome,n,note,kind in people:
    if kind=='redmine_ai': initials='⚙'; ptype='Usuário operacional Redmine'; cls='ai'
    elif kind=='intel': initials='✦'; ptype='Inteligência operacional'; cls='ai'
    else:
        initials=''.join(x[0] for x in nome.split()[:2]).upper() if nome else '—'; ptype='Responsável Redmine'; cls=''
    html_people.append(f'<div class="person"><div class="person-top"><div class="initial {cls}">{html.escape(initials)}</div><div><div class="pname">{html.escape(nome)}</div><div class="ptype">{html.escape(ptype)}</div></div></div><div class="pnum">{n}</div><div class="pnote">{html.escape(note)}</div></div>')
st.markdown('<div class="people-grid">'+''.join(html_people)+'</div><div class="redmine-note">Os IDs individuais de chamados permanecem clicáveis nas telas de Equipe e Atendimentos.</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-shell"><div class="module-title">O que você quer fazer?</div><div class="module-sub">Cada botão abre somente o módulo escolhido.</div>', unsafe_allow_html=True)
cols=st.columns(5)
labels=[('📊  Painel EDI','pages/Painel_EDI.py'),('🧠  Aprendizado e homologação','pages/Aprendizado.py'),('📥  Atendimentos da EDNNA','pages/Atendimentos.py'),('⚡  Automações','pages/Automacoes.py'),('👥  Equipe e capacidade','pages/Equipe.py')]
for col,(label,page) in zip(cols,labels):
    with col:
        if st.button(label,width='stretch'):
            if 'Painel_EDI' in page: st.session_state['shell_main_navigation']='Visão Geral'
            st.switch_page(page)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown(f'<div class="foot">EDNNA v{APP_VERSION} · {APP_RELEASE} · Netunna &nbsp;&nbsp;|&nbsp;&nbsp; Inteligência que trabalha com você.</div>', unsafe_allow_html=True)
