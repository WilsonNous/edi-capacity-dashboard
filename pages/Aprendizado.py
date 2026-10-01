from ednna.security import require_admin
import streamlit as st
from collections import Counter
from ui.operational_shell import setup, footer
from ui.operational_data import regras_df
from ednna.escola_continua import sincronizar_regras_homologadas, listar_matriculas

setup('🧠 Central de Aprendizagem · EDNNA'); require_admin()
tech,_=st.columns([1.2,5])
with tech:
    if st.button('⚙️ Modo técnico',width='stretch'):
        st.session_state['shell_main_navigation']='Motor EDNNA'; st.switch_page('pages/Painel_EDI.py')

st.markdown('### 🎓 A EDNNA está matriculada na operação')
st.caption('Eu estudo os históricos, aprendo com a operação real e volto ao professor quando encontro algo que merece decisão humana.')
st.info('📚 **Minha rotina:** Estudo → Prova → Prova surpresa → Professor → Homologação → Trabalho → Revisão → Novo aprendizado.')
r=regras_df()
if r.empty:
    st.info('Ainda não encontrei regras de aprendizado disponíveis neste ambiente.')
else:
    estado=r['estado'].fillna('EM_APRENDIZADO'); rev=r[estado.eq('PRONTA_PARA_REVISAO')]; hom=r[(estado.eq('HOMOLOGADA'))|(r.get('estado_revisao','').fillna('').eq('HOMOLOGADA'))]; estudo=r[~r.index.isin(rev.index)&~r.index.isin(hom.index)]
    sincronizar_regras_homologadas(r); matriculas=listar_matriculas(); atrasadas=[m for m in matriculas if m['situacao_visual']=='REVISAO_ATRASADA']; proximas=[m for m in matriculas if m['situacao_visual']=='REVISAO_PROXIMA']; divergentes=[m for m in matriculas if m['situacao_visual']=='PRECISO_DO_PROFESSOR']; saudaveis=[m for m in matriculas if m['situacao_visual']=='CONHECIMENTO_SAUDAVEL']
    if divergentes: st.warning(f'👩‍🏫 Professor, encontrei **{len(divergentes)} matéria(s) com divergência**. Não alterei nenhuma regra; deixei tudo separado para sua revisão.')
    elif atrasadas: st.warning(f'📚 Tenho **{len(atrasadas)} matéria(s) com revisão atrasada**. O conhecimento continua preservado, mas está na hora de estudar os casos recentes.')
    elif proximas: st.info(f'🗓️ Estou em dia. Tenho **{len(proximas)} matéria(s)** entrando em revisão nos próximos 7 dias.')
    elif matriculas: st.success(f'😊 Estou com a matéria em dia: **{len(saudaveis)} conhecimento(s)** sem divergência ou revisão vencida.')
    c1,c2,c3,c4=st.columns(4)
    for c,l,n,nota in [(c1,'📖 Em estudo',len(estudo),'matérias sendo aprendidas'),(c2,'📝 Provas para corrigir',len(rev),'precisam do professor'),(c3,'🎓 Matriculadas',len(matriculas),'conhecimento homologado'),(c4,'👩‍🏫 Atenção',len(divergentes)+len(atrasadas),'divergências ou revisão vencida')]:
        with c: st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div><div class="op-note">{nota}</div></div>',unsafe_allow_html=True)
    st.subheader('👩‍🏫 Professores, preciso de vocês')
    if rev.empty and not divergentes: st.success('Nenhuma prova ou divergência aguarda sua decisão agora.')
    for _,x in rev.iterrows():
        cols=st.columns([4,1])
        with cols[0]: st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br><span class="pill">Prova pronta</span> · {int(x.get("completude") or 0)}% de completude<br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
        with cols[1]:
            if st.button('Corrigir prova',key='rev_'+str(x.get('regra_id')),width='stretch'):
                st.session_state['ednna_regra_foco']=x.get('regra_id'); st.session_state['shell_main_navigation']='Motor EDNNA'; st.switch_page('pages/Painel_EDI.py')
    with st.expander(f'📚 Na sala de estudo ({len(estudo)})'):
        for _,x in estudo.sort_values('completude',ascending=False).iterrows(): st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_',' ').title()}")
    st.subheader('🔄 Minha agenda de revisão')
    for m in matriculas:
        situacao=m['situacao_visual']; icone={'PRECISO_DO_PROFESSOR':'👩‍🏫','REVISAO_ATRASADA':'⚠️','REVISAO_PROXIMA':'🗓️','CONHECIMENTO_SAUDAVEL':'🎓'}.get(situacao,'📚'); dias=int(m['dias_para_revisao']); prazo=f'atrasada há {abs(dias)} dia(s)' if dias<0 else ('revisão hoje' if dias==0 else f'revisão em {dias} dia(s)')
        with st.expander(f"{icone} {m.get('player') or m['regra_id']} · {prazo}"):
            a,b,c,d=st.columns(4); a.metric('Matrícula',m['matriculada_em']); b.metric('Última revisão',m.get('ultima_revisao_em') or 'Ainda não revisada'); c.metric('Aderência atual','—' if m.get('aderencia_atual') is None else f"{float(m['aderencia_atual']):.0f}%"); d.metric('Novas evidências',m.get('evidencias_desde_revisao',0))

st.divider(); st.subheader('⛏️ Biblioteca histórica · Aberturas de Relacionamento'); st.caption('Começo com até 6 bons cadernos para aprender. Depois faço uma prova surpresa com até 12 históricos que não usei no aprendizado.')
try:
    from ednna.minerador_aberturas import descobrir_no_redmine,listar_propostas,simular_proposta,simular_prova_surpresa
    cmin1,_=st.columns([1.4,4])
    with cmin1:
        if st.button('🔎 Estudar Redmine',key='minerar_aberturas',width='stretch'):
            with st.spinner('📚 Estou estudando os históricos e separando questões inéditas para a prova surpresa...'):
                st.session_state['mineracao_aberturas_resultado']=descobrir_no_redmine(limite_detalhes_por_player=6,limite_prova_surpresa_por_player=12)
            st.success('Terminei esta rodada. O caderno de estudo e a prova surpresa ficaram separados.')
    res=st.session_state.get('mineracao_aberturas_resultado') or {}
    if res:
        a,b,c,d=st.columns(4); a.metric('Candidatos encontrados',res.get('candidatos_rasos',0)); b.metric('Históricos detalhados',res.get('detalhados',0)); c.metric('Players',res.get('players',0)); d.metric('Erros',len(res.get('erros') or []))
    propostas=listar_propostas()
    if not propostas: st.info('Ainda não preparei matérias novas. O estudo começa quando você aciona o botão.')
    for p in propostas:
        with st.expander(f"{p.get('player')} · {p.get('regra_id')}"):
            x1,x2,x3,x4=st.columns(4); x1.metric('Caderno inicial',p.get('evidencias',0)); x2.metric('Universo encontrado',p.get('universo_encontrado',p.get('evidencias',0))); x3.metric('Posso fazer',p.get('automatizaveis_agora',0)); x4.metric('Preciso do professor',p.get('checkpoints_humanos',0))
            st.caption('Aprendi com: '+', '.join('#'+str(i) for i in p.get('casos_ids',[])))
            surpresa_ids=p.get('prova_surpresa_ids',[]); planejados=int(p.get('prova_surpresa_planejada') or len(surpresa_ids))
            if surpresa_ids: st.caption('🧩 Separei para a prova surpresa: '+', '.join('#'+str(i) for i in surpresa_ids))
            if not p.get('prova_surpresa_completa',True): st.warning(f'⚠️ A prova surpresa está incompleta: consegui carregar {len(surpresa_ids)} de {planejados} históricos planejados. Não vou publicar nota como se a prova estivesse completa.')
            for e in p.get('etapas',[]): st.write(f"{'✓' if e.get('confianca')=='ALTA' else '◐'} **{e.get('descricao')}** · {'EDNNA' if e.get('responsavel')=='EDNNA' else 'Humano'} · recorrência {e.get('recorrencia_pct')}%")
            rid=str(p.get('regra_id') or ''); col1,col2=st.columns(2)
            with col1:
                if st.button('🧪 Fazer prova do caderno',key='btn_sim_'+rid,width='stretch'): st.session_state['resultado_sim_'+rid]=simular_proposta(p)
            with col2:
                if st.button('🎁 Fazer prova surpresa',key='btn_surpresa_'+rid,width='stretch',disabled=not bool(surpresa_ids)): st.session_state['resultado_surpresa_'+rid]=simular_prova_surpresa(p)
            sim=st.session_state.get('resultado_sim_'+rid)
            if sim: st.info(f"**Prova do caderno:** {sim.get('compativeis')}/{sim.get('casos')} casos compatíveis · **{int(sim.get('compatibilidade_pct') or 0)}%**.")
            surpresa=st.session_state.get('resultado_surpresa_'+rid)
            if surpresa:
                if not surpresa.get('completa',False):
                    st.warning(f"👩‍🏫 **Prova surpresa incompleta.** Foram avaliados {surpresa.get('casos',0)} de {surpresa.get('planejados',0)} históricos planejados. A EDNNA não recebe nota até completar o conjunto inédito.")
                else:
                    comp=int(surpresa.get('compatibilidade_pct') or 0)
                    if comp>=90:
                        st.success(f"🎓 Professor, consegui aplicar o que aprendi em casos que eu não tinha estudado.\n\n**Prova surpresa:** {surpresa.get('compativeis')}/{surpresa.get('casos')} históricos inéditos compatíveis · **{comp}%**.")
                    elif comp>=70:
                        st.warning(f"🧠 Consegui generalizar parte da matéria, mas quero revisar alguns casos com você.\n\n**Prova surpresa:** {surpresa.get('compativeis')}/{surpresa.get('casos')} históricos inéditos compatíveis · **{comp}%**.")
                    else:
                        st.warning(f"👩‍🏫 Professor, encontrei diferenças importantes quando saí do meu caderno. Ainda não quero trabalhar sozinha nesta matéria.\n\n**Prova surpresa:** {surpresa.get('compativeis')}/{surpresa.get('casos')} históricos inéditos compatíveis · **{comp}%**.")

                    detalhes=surpresa.get('detalhes') or []
                    reprovados=[d for d in detalhes if int(d.get('cobertura_pct') or 0)<80]
                    if reprovados:
                        faltas=Counter(f for d in reprovados for f in (d.get('faltantes') or []))
                        st.markdown(f"#### 👩‍🏫 Professor, tenho {len(reprovados)} questão(ões) para revisar")
                        st.caption('Em vez de esconder a reprovação, eu separo exatamente os históricos e os pontos em que o padrão aprendido não se repetiu.')
                        for d in sorted(reprovados,key=lambda z:int(z.get('cobertura_pct') or 0)):
                            falt=', '.join(str(x).replace('_',' ').title() for x in d.get('faltantes') or []) or 'Nenhuma etapa faltante identificada'
                            st.markdown(f"**Chamado #{d.get('chamado_id')}** · aderência **{int(d.get('cobertura_pct') or 0)}%**  \nO que mudou: {falt}")
                        if faltas:
                            principais=', '.join(f"{str(k).replace('_',' ').title()} ({v}x)" for k,v in faltas.most_common(4))
                            st.info(f"🧠 **O que acredito que preciso reaprender:** os desvios mais recorrentes foram {principais}. Vou tratar isso como nova matéria, não como autorização para mudar a regra.")
                    else:
                        st.success('📘 Não encontrei questões abaixo do limite de 80% nesta prova surpresa.')
                with st.expander('🔬 Ver questões da prova surpresa'):
                    st.json(surpresa)
            st.caption('🔒 Estudar e passar nas provas não ativa a regra. Homologação e autorização continuam sendo decisões do professor.')
except Exception as exc:
    st.error(f'Não consegui carregar o minerador de aberturas: {type(exc).__name__}: {exc}')

st.divider(); st.caption('🎓 Quanto melhor o chamado for registrado, melhor eu aprendo. Contexto, evidência e conclusão fazem parte da aula.'); footer()
