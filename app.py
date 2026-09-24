from pathlib import Path
import html
import re
import streamlit as st
import pandas as pd
from version import APP_VERSION, APP_RELEASE
from ui.operational_data import resumo, resumo_trabalho_ednna, chamados_ativos_df, redmine_link
from ednna.motor_inclusoes_operacional import avaliar_fila_inclusoes, diagnosticar_regras_operacionais, preparar_atuacao_assistida, gerar_rascunho_inclusao, executar_atuacao_assistida_email
from ednna.followup_engine import avaliar_followups, executar_followup
from ednna.acompanhamento_acoes import listar_redmine_pendentes, obter_acompanhamento
from ednna.redmine_outbox import reconciliar_redmine_chamado

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

:root{--ed-blue:#1268e8;--ed-navy:#0b2d61;--ed-muted:#6f84a2}
html,body,[class*="css"],.stApp{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.brand-main{font-size:1.18rem;letter-spacing:.035em}.brand-sub{font-size:.66rem;letter-spacing:.18em}
.st-key-hero_shell{border-color:#dbe6f4;box-shadow:0 10px 30px rgba(24,75,140,.055)}
.hero-copy{padding:18px 14px 13px 7px}.greet{font-size:.88rem;font-weight:650;color:#476787}.hero-title{font-size:1.92rem;letter-spacing:-.025em;margin:5px 0 10px}.hero-text{font-size:.94rem;line-height:1.5;color:#607591}
.ops-head,.section-title,.module-title{letter-spacing:-.012em}.klabel{font-size:.74rem;font-weight:650}.knum{letter-spacing:-.035em}.knote{line-height:1.3}
.insight-card{padding:10px 13px}.insight b{letter-spacing:-.01em}.section-shell{padding:16px 19px}.person{transition:transform .15s ease,box-shadow .15s ease}.person:hover{transform:translateY(-1px);box-shadow:0 7px 18px rgba(24,75,140,.06)}
div.stButton>button{font-size:.82rem!important;letter-spacing:-.005em!important}
/* Operação deve ter a mesma escala visual dos demais módulos da Home. */
.st-key-ednna_operation_shell{background:#fff;border:1px solid #e0e9f5;border-radius:20px;padding:14px 18px;margin-top:14px;box-shadow:0 5px 18px rgba(24,75,140,.04)}
.st-key-ednna_operation_shell [data-testid="stMetric"]{background:#f8fbff;border:1px solid #e1eaf6;border-radius:14px;padding:9px 12px;min-height:78px}
.st-key-ednna_operation_shell [data-testid="stMetricValue"]{font-size:1.42rem}
.st-key-ednna_operation_shell div.stButton>button{min-height:40px!important;width:auto!important;padding:.45rem .9rem!important;border-radius:10px!important}.st-key-ednna_operation_shell div.stButton>button[kind=primary]{background:#1268e8!important;color:#fff!important;border-color:#1268e8!important}.st-key-ednna_operation_shell div.stButton>button[kind=primary] p{color:#fff!important}
</style>''', unsafe_allow_html=True)

r = resumo(); trabalho = resumo_trabalho_ednna(); df = chamados_ativos_df(); cobertura = round(r['homologadas']/r['regras']*100) if r['regras'] else 0
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
    st.markdown(f'''<div class="hero-copy"><div class="greet">Olá! Eu sou a EDNNA.</div><div class="hero-title">{html.escape(title)}</div><div class="hero-text">Estou acompanhando <b>{r['total']} chamados ativos</b>. A equipe e a EDNNA continuam trabalhando; você entra apenas onde sua decisão faz diferença.</div><div class="hero-text" style="margin-top:8px"><b>{cobertura}%</b> das regras conhecidas estão homologadas. <b>{trabalho['regras_automaticas']}</b> já estão autorizadas para atuação automática.</div></div>''', unsafe_allow_html=True)
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
    if trabalho['atuacoes']: ins.append((f"{trabalho['atuacoes']} atuações", 'já absorvidas pela EDNNA'))
    if ins:
        cells=''.join(f'<div class="insight"><b>{html.escape(a)}</b>{html.escape(b)}</div>' for a,b in ins[:3])
        st.markdown(f'<div class="insight-card"><div class="insight-title"><span>💡 Leitura da EDNNA</span><span style="font-weight:700;color:#1268e8">fotografia atual</span></div><div class="insight-grid">{cells}</div></div>', unsafe_allow_html=True)
with opscol:
    st.markdown('<div class="ops-panel"><div class="ops-head"><span>〽 Estado da operação</span><span class="ops-pill">✚ Em acompanhamento</span></div>', unsafe_allow_html=True)
    k1,k2=st.columns(2); k3,k4=st.columns(2)
    data=[(k1,'Chamados ativos',r['total'],'carteira ativa do Redmine',''),(k2,'Equipe / Atuação',r['em_atuacao'],'fora de espera por terceiros',''),(k3,'Aguardando terceiros',r['terceiros'],'dependência externa',''),(k4,'EDNNA',trabalho['acompanhando'],'chamados sob acompanhamento','ednna')]
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
people.append(('EDNNA',trabalho['atuacoes'],'atuações absorvidas · inteligência','intel'))
html_people=[]
for nome,n,note,kind in people:
    if kind=='redmine_ai': initials='⚙'; ptype='Usuário operacional Redmine'; cls='ai'
    elif kind=='intel': initials='✦'; ptype='Inteligência operacional'; cls='ai'
    else:
        initials=''.join(x[0] for x in nome.split()[:2]).upper() if nome else '—'; ptype='Responsável Redmine'; cls=''
    html_people.append(f'<div class="person"><div class="person-top"><div class="initial {cls}">{html.escape(initials)}</div><div><div class="pname">{html.escape(nome)}</div><div class="ptype">{html.escape(ptype)}</div></div></div><div class="pnum">{n}</div><div class="pnote">{html.escape(note)}</div></div>')
st.markdown('<div class="people-grid">'+''.join(html_people)+'</div><div class="redmine-note">Os IDs individuais de chamados permanecem clicáveis nas telas de Equipe e Atendimentos.</div></div>', unsafe_allow_html=True)


# v3.29.4 — números que demonstram o trabalho absorvido pela inteligência.
st.markdown('<div class="section-shell"><div class="section-title">✦ O que estou fazendo por você</div><div class="section-sub">Indicadores locais do trabalho já absorvido pela EDNNA. Sem consulta externa para abrir esta tela.</div>', unsafe_allow_html=True)
t1,t2,t3,t4=st.columns(4)
for col,label,num,note in [
    (t1,'Atuações executadas',trabalho['atuacoes'],'envios confirmados / operações persistidas'),
    (t2,'Em acompanhamento',trabalho['acompanhando'],'retornos que estou acompanhando'),
    (t3,'Regras automáticas',trabalho['regras_automaticas'],'procedimentos autorizados para agir'),
    (t4,'Conhecimento',trabalho['blueprints'],f"Blueprints · {trabalho['clientes_conhecidos']} cliente(s)"),
]:
    with col: st.metric(label,num,help=note)
st.caption(f"Follow-ups executados: {trabalho['followups']} · Redmine pendente de reconciliação: {trabalho['redmine_pendente']} · Contatos conhecidos em Blueprint: {trabalho['participantes']}")
st.markdown('</div>', unsafe_allow_html=True)

# v3.29.1 — Home intencionalmente leve.
# Operação, regras e conhecimento possuem telas próprias; a Home não executa
# motores nem consulta serviços externos ao ser aberta ou ao retornar de outra página.
st.markdown(
    '<div class="section-shell"><div class="module-title">Acesso rápido</div>'
    '<div class="module-sub">A Home abre com o último snapshot local. Escolha o assunto; dados externos são atualizados somente dentro do módulo correspondente.</div>',
    unsafe_allow_html=True,
)
nav_rows = [
    [
        ('🦾  Operação de hoje','pages/Operacao.py'),
        ('🧠  Central de Regras','pages/Regras.py'),
        ('📚  Conhecimento do cliente','pages/Conhecimento.py'),
        ('📥  Atendimentos','pages/Atendimentos.py'),
    ],
    [
        ('🔬  Aprendizado','pages/Aprendizado.py'),
        ('⚡  Automações','pages/Automacoes.py'),
        ('👥  Equipe e capacidade','pages/Equipe.py'),
        ('📊  Painel EDI','pages/Painel_EDI.py'),
    ],
]
for linha in nav_rows:
    cols = st.columns(len(linha))
    for col,(label,page) in zip(cols,linha):
        with col:
            if st.button(label,width='stretch',key=f'nav_{page}'):
                if 'Painel_EDI' in page: st.session_state['shell_main_navigation']='Visão Geral'
                st.switch_page(page)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="section-shell"><div class="module-title">Como a EDNNA carrega</div>'
    '<div class="module-sub">Interface primeiro, dados depois — sem bloquear a navegação.</div>'
    '<div class="insight-grid">'
    '<div class="insight"><b>1 · Imediato</b>Home e navegação usam SQLite/cache local.</div>'
    '<div class="insight"><b>2 · Sob demanda</b>Cada módulo calcula apenas o que precisa.</div>'
    '<div class="insight"><b>3 · Segundo plano</b>Redmine e demais fontes atualizam snapshots sem travar a Home.</div>'
    '</div></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="foot">EDNNA v{APP_VERSION} · {APP_RELEASE} · Netunna &nbsp;&nbsp;|&nbsp;&nbsp; Inteligência que trabalha com você.</div>', unsafe_allow_html=True)
