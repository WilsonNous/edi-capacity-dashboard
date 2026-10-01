from ednna.security import require_admin
import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import regras_df
setup('🧠 Aprendizado e homologação')
require_admin()
tech,_=st.columns([1.2,5])
with tech:
    if st.button('⚙️ Modo técnico',width="stretch"):
        st.session_state['shell_main_navigation']='Motor EDNNA'; st.switch_page('pages/Painel_EDI.py')
r=regras_df()
if r.empty: st.info('A EDNNA ainda não possui regras de aprendizado disponíveis neste ambiente.')
else:
    estado=r['estado'].fillna('EM_APRENDIZADO')
    rev=r[estado.eq('PRONTA_PARA_REVISAO')]; hom=r[(estado.eq('HOMOLOGADA')) | (r.get('estado_revisao','').fillna('').eq('HOMOLOGADA'))]; estudo=r[~r.index.isin(rev.index) & ~r.index.isin(hom.index)]
    c1,c2,c3=st.columns(3)
    for c,l,n,nota in [(c1,'Em estudo',len(estudo),'procedimentos em aprendizado'),(c2,'Para revisar',len(rev),'precisam da sua decisão'),(c3,'Homologadas',len(hom),'conhecimento aprovado')]:
        with c: st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div><div class="op-note">{nota}</div></div>',unsafe_allow_html=True)
    st.subheader('Precisam de você')
    if rev.empty: st.success('Nenhuma regra aguarda sua revisão agora.')
    for _,x in rev.iterrows():
        cols=st.columns([4,1]);
        with cols[0]: st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br><span class="pill">Pronta para revisão</span> · {int(x.get("completude") or 0)}% de completude<br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
        with cols[1]:
            if st.button('Revisar',key='rev_'+str(x.get('regra_id')),width="stretch"):
                st.session_state['ednna_regra_foco']=x.get('regra_id'); st.session_state['shell_main_navigation']='Motor EDNNA'; st.switch_page('pages/Painel_EDI.py')
    with st.expander(f'Em aprendizado ({len(estudo)})'):
        for _,x in estudo.sort_values('completude',ascending=False).iterrows(): st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_',' ').title()}")

st.divider()
st.subheader('⛏️ Descoberta histórica · Aberturas de Relacionamento')
st.caption('A EDNNA procura históricos concluídos, reconstrói etapas e propõe automações. Nenhuma regra é homologada ou autorizada automaticamente.')
try:
    from ednna.minerador_aberturas import descobrir_no_redmine, listar_propostas, simular_proposta
    cmin1,cmin2=st.columns([1.4,4])
    with cmin1:
        if st.button('🔎 Minerar Redmine', key='minerar_aberturas', width='stretch'):
            with st.spinner('Analisando Aberturas de Relacionamento com pressão controlada no Redmine...'):
                st.session_state['mineracao_aberturas_resultado']=descobrir_no_redmine(limite_detalhes_por_player=6)
            st.success('Mineração concluída. As propostas continuam bloqueadas até revisão/homologação.')
    res=st.session_state.get('mineracao_aberturas_resultado') or {}
    if res:
        a,b,c,d=st.columns(4)
        a.metric('Candidatos',res.get('candidatos_rasos',0)); b.metric('Detalhados',res.get('detalhados',0)); c.metric('Players',res.get('players',0)); d.metric('Erros',len(res.get('erros') or []))
    propostas=listar_propostas()
    if not propostas:
        st.info('Ainda não há propostas de abertura mineradas. A mineração só ocorre quando um administrador aciona o botão.')
    for p in propostas:
        titulo=f"{p.get('player')} · {p.get('regra_id')}"
        with st.expander(titulo):
            x1,x2,x3,x4=st.columns(4)
            x1.metric('Evidências',p.get('evidencias',0)); x2.metric('Compatibilidade',f"{p.get('compatibilidade',0)}%")
            x3.metric('Automatizáveis',p.get('automatizaveis_agora',0)); x4.metric('Checkpoints',p.get('checkpoints_humanos',0))
            st.caption('Fontes: chamados ' + ', '.join('#'+str(i) for i in p.get('casos_ids',[])))
            for e in p.get('etapas',[]):
                dono='EDNNA' if e.get('responsavel')=='EDNNA' else 'Humano'
                conf='✓' if e.get('confianca')=='ALTA' else '◐'
                st.write(f"{conf} **{e.get('descricao')}** · {dono} · recorrência {e.get('recorrencia_pct')}%")
            if st.button('🧪 Simular nos históricos',key='sim_'+p.get('regra_id','')):
                sim=simular_proposta(p); st.session_state['sim_'+p.get('regra_id','')]=sim
            sim=st.session_state.get('sim_'+p.get('regra_id',''))
            if sim:
                st.info(f"Backtest estrutural: {sim.get('compativeis')}/{sim.get('casos')} casos com ≥80% das etapas recorrentes · compatibilidade {sim.get('compatibilidade_pct')}%.")
            st.warning('Candidata apenas para revisão. A EDNNA não executará esta abertura até existir homologação e autorização explícitas.')
except Exception as exc:
    st.error(f'Não foi possível carregar o minerador de aberturas: {type(exc).__name__}: {exc}')

footer()
