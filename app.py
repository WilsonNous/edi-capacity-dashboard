from pathlib import Path
import streamlit as st
from version import APP_VERSION, APP_RELEASE
from ui.operational_data import resumo, chamados_df

st.set_page_config(page_title='EDNNA — Inteligência Operacional EDI',page_icon='🤖',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}.stApp{background:linear-gradient(135deg,#f3f7ff,#f8fafc 48%,#eef4ff);color:#172b4d}.block-container{max-width:1280px;padding:1.25rem 2rem 2rem}.top{display:flex;justify-content:space-between;align-items:center}.brand{font-size:1.15rem;font-weight:900;letter-spacing:.08em;color:#1877f2}.online{background:#e8f7ee;color:#16803d;border-radius:999px;padding:7px 12px;font-weight:800}.hero{background:#fff;border:1px solid #dce6f4;border-radius:26px;padding:26px 32px;box-shadow:0 12px 34px rgba(24,119,242,.08);min-height:260px;display:flex;align-items:center}.eyebrow{font-size:.72rem;font-weight:900;letter-spacing:.14em;color:#1877f2;text-transform:uppercase}.title{font-size:2.15rem;font-weight:900;line-height:1.08;margin:8px 0 12px}.copy{font-size:1rem;color:#5b6f88;line-height:1.5}.avatar{animation:float 3.2s ease-in-out infinite;filter:drop-shadow(0 14px 18px rgba(24,119,242,.18))}@keyframes float{50%{transform:translateY(-8px)}}.kpi{background:#fff;border:1px solid #e0e7f0;border-radius:17px;padding:14px 16px;min-height:86px}.klabel{font-size:.72rem;font-weight:850;color:#718096;text-transform:uppercase}.knum{font-size:1.7rem;font-weight:900}.knote{font-size:.74rem;color:#8796aa}.section{font-size:1.05rem;font-weight:900;margin:22px 0 8px}.sub{font-size:.84rem;color:#7b8ca5;margin-top:-5px;margin-bottom:10px}div.stButton>button{border-radius:14px!important;min-height:50px!important;font-weight:800!important;border:1px solid #d5dfed!important;background:#fff!important}div.stButton>button:hover{border-color:#1877f2!important;color:#1877f2!important}.person{background:#fff;border:1px solid #e0e7f0;border-radius:15px;padding:12px 14px}.pname{font-weight:850}.pnum{font-size:1.25rem;font-weight:900;color:#1877f2}.insight-wrap{background:#fff;border:1px solid #e0e7f0;border-radius:16px;padding:10px 14px;margin:6px 0 14px}.insight-row{display:flex;gap:8px;align-items:flex-start;padding:7px 2px;border-bottom:1px solid #edf2f7;font-size:.86rem;line-height:1.35;color:#40556f}.insight-row:last-child{border-bottom:none}.insight-icon{font-size:.9rem;line-height:1.3}.insight-row b{color:#075eb8}.foot{text-align:center;color:#91a0b4;font-size:.72rem;margin-top:22px}</style>''',unsafe_allow_html=True)

r=resumo(); df=chamados_df(); cobertura=round(r['homologadas']/r['regras']*100) if r['regras'] else 0
if r['revisao']==1: title='Tenho 1 decisão para você.'
elif r['revisao']>1: title=f"Tenho {r['revisao']} decisões para você."
elif r['aprendendo']: title='Estou aprendendo enquanto você trabalha.'
else:title='A operação está sob acompanhamento.'
copy=f"Estou acompanhando {r['total']} chamados junto com a equipe. Você entra apenas onde sua decisão faz diferença."
if r['revisao']>0: avatar_state='👉 Preciso da sua decisão'
elif r['aprendendo']>0: avatar_state='🧠 Analisando a operação'
else: avatar_state='😊 Operação acompanhada'

st.markdown('<div class="top"><div class="brand">EDNNA · NETUNNA</div><div class="online">● Operando</div></div>',unsafe_allow_html=True)
a,b=st.columns([1.05,3.6],vertical_alignment='center')
with a:
    av=Path('assets/ednna_avatar.png')
    if av.exists(): st.markdown('<div class="avatar">',unsafe_allow_html=True); st.image(str(av),width=235); st.markdown('</div>',unsafe_allow_html=True); st.caption(avatar_state)
with b: st.markdown(f'<div class="hero"><div><div class="eyebrow">Inteligência Operacional EDI</div><div class="title">{title}</div><div class="copy">{copy}</div><div class="copy" style="margin-top:12px"><b style="color:#1877f2">{cobertura}%</b> das regras conhecidas estão homologadas.</div></div></div>',unsafe_allow_html=True)

c1,c2,c3,c4=st.columns(4)
for c,l,n,note in [(c1,'Chamados gerais',r['total'],'em acompanhamento'),(c2,'Equipe / atuação',r['em_atuacao'],'fora de espera por terceiros'),(c3,'Aguardando terceiros',r['terceiros'],'dependência externa'),(c4,'EDNNA',r['revisao']+r['aprendendo'],'procedimentos em atenção')]:
    with c: st.markdown(f'<div class="kpi"><div class="klabel">{l}</div><div class="knum">{n}</div><div class="knote">{note}</div></div>',unsafe_allow_html=True)

# Leitura inteligente da fotografia atual
ins=[]
if r['total']:
    pct=round(r['terceiros']/r['total']*100)
    if pct>=50: ins.append(f'**{pct}% dos chamados dependem de terceiros.** A maior parte da operação está condicionada a retornos externos.')
if not df.empty and 'responsavel' in df.columns:
    vc=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts()
    if len(vc):
        nome,n=vc.index[0],int(vc.iloc[0]); pct=round(n/len(df)*100)
        if pct>=35: ins.append(f'**{nome} concentra {pct}% dos chamados distribuídos.** É o maior volume individual da fotografia atual.')
if r['revisao']:
    ins.append(f'**{r["revisao"]} procedimento' + (' está' if r['revisao']==1 else 's estão') + ' pronto' + ('' if r['revisao']==1 else 's') + ' para decisão.** Sua homologação é o ponto de maior impacto agora.')
if ins:
    st.markdown('<div class="section">💡 Leitura da EDNNA</div><div class="sub">O que merece atenção agora.</div>',unsafe_allow_html=True)
    import re
    rows=[]
    for x in ins[:3]:
        html=re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', x)
        rows.append(f'<div class="insight-row"><span class="insight-icon">•</span><span>{html}</span></div>')
    st.markdown('<div class="insight-wrap">'+''.join(rows)+'</div>',unsafe_allow_html=True)

st.markdown('<div class="section">Quem está com o quê?</div><div class="sub">Distribuição atual dos chamados por responsável. A EDNNA aparece separadamente como camada de inteligência.</div>',unsafe_allow_html=True)
if not df.empty and 'responsavel' in df:
    top=df.responsavel.fillna('Sem responsável').replace('','Sem responsável').value_counts().head(4)
    cols=st.columns(5)
    for col,(nome,n) in zip(cols[:4],top.items()):
        with col: st.markdown(f'<div class="person"><div class="pname">{nome}</div><div class="pnum">{n}</div><div class="knote">chamados</div></div>',unsafe_allow_html=True)
    with cols[4]: st.markdown(f'<div class="person"><div class="pname">🤖 EDNNA</div><div class="pnum">{r["revisao"]+r["aprendendo"]}</div><div class="knote">regras em atenção</div></div>',unsafe_allow_html=True)
else: st.caption('A distribuição da equipe aparecerá assim que o snapshot local estiver disponível.')

st.markdown('<div class="section">O que você quer fazer?</div><div class="sub">Cada botão abre somente o módulo escolhido. O painel completo fica isolado em Painel EDI.</div>',unsafe_allow_html=True)
a,b,c=st.columns(3)
with a:
    if st.button('📊  Painel EDI',width="stretch"): st.session_state['shell_main_navigation']='Visão Geral'; st.switch_page('pages/Painel_EDI.py')
with b:
    if st.button('🧠  Aprendizado e homologação',width="stretch"): st.switch_page('pages/Aprendizado.py')
with c:
    if st.button('📥  Atendimentos da EDNNA',width="stretch"): st.switch_page('pages/Atendimentos.py')
d,e=st.columns(2)
with d:
    if st.button('⚡  Automações',width="stretch"): st.switch_page('pages/Automacoes.py')
with e:
    if st.button('👥  Equipe e capacidade',width="stretch"): st.switch_page('pages/Equipe.py')
st.markdown(f'<div class="foot">EDNNA v{APP_VERSION} · {APP_RELEASE} · cockpit operacional</div>',unsafe_allow_html=True)
