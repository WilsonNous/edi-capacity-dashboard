from ednna.security import require_admin
import streamlit as st
from collections import Counter
from ui.operational_shell import setup, footer
from ui.operational_data import regras_df
from ednna.escola_continua import sincronizar_regras_homologadas, listar_matriculas
from ednna.homologacao import homologar_e_ativar, estado_regra, alterar_estado
setup('🧠 Central de Aprendizagem · EDNNA'); require_admin()
tech,_=st.columns([1.2,5])
with tech:
    if st.button('⚙️ Modo técnico',width='stretch'):
        st.session_state['shell_main_navigation']='Motor EDNNA'; st.switch_page('pages/Painel_EDI.py')
st.markdown('### 🎓 A EDNNA está matriculada na operação')
st.caption('Eu estudo os históricos, aprendo com a operação real e volto ao professor quando encontro algo que merece decisão humana.')
st.info('📚 **Minha rotina:** Estudo → Prova → Prova surpresa ponderada → Professor → Homologação → Trabalho → Revisão → Novo aprendizado.')
r=regras_df()
if r.empty: st.info('Ainda não encontrei regras de aprendizado disponíveis neste ambiente.')
else:
    estado=r['estado'].fillna('EM_APRENDIZADO'); rev=r[estado.eq('PRONTA_PARA_REVISAO')]; hom=r[(estado.eq('HOMOLOGADA'))|(r.get('estado_revisao','').fillna('').eq('HOMOLOGADA'))]; estudo=r[~r.index.isin(rev.index)&~r.index.isin(hom.index)]; sincronizar_regras_homologadas(r); matriculas=listar_matriculas(); atrasadas=[m for m in matriculas if m['situacao_visual']=='REVISAO_ATRASADA']; divergentes=[m for m in matriculas if m['situacao_visual']=='PRECISO_DO_PROFESSOR']; saudaveis=[m for m in matriculas if m['situacao_visual']=='CONHECIMENTO_SAUDAVEL']
    if divergentes: st.warning(f'👩‍🏫 Professor, encontrei **{len(divergentes)} matéria(s) com divergência**. Preservei as regras e trouxe para sua revisão.')
    elif atrasadas: st.warning(f'📚 Tenho **{len(atrasadas)} matéria(s) com revisão atrasada**.')
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
            if st.button('Corrigir prova',key='rev_'+str(x.get('regra_id')),width='stretch'): st.session_state['ednna_regra_foco']=x.get('regra_id'); st.session_state['shell_main_navigation']='Motor EDNNA'; st.switch_page('pages/Painel_EDI.py')
    with st.expander(f'📚 Na sala de estudo ({len(estudo)})'):
        for _,x in estudo.sort_values('completude',ascending=False).iterrows(): st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_',' ').title()}")
    st.subheader('🔄 Minha agenda de revisão')
    for m in matriculas:
        dias=int(m['dias_para_revisao']); prazo=f'atrasada há {abs(dias)} dia(s)' if dias<0 else ('revisão hoje' if dias==0 else f'revisão em {dias} dia(s)')
        with st.expander(f"🎓 {m.get('player') or m['regra_id']} · {prazo}"):
            a,b,c,d=st.columns(4); a.metric('Matrícula',m['matriculada_em']); b.metric('Última revisão',m.get('ultima_revisao_em') or 'Ainda não revisada'); c.metric('Aderência atual','—' if m.get('aderencia_atual') is None else f"{float(m['aderencia_atual']):.0f}%"); d.metric('Novas evidências',m.get('evidencias_desde_revisao',0))
st.divider(); st.subheader('⛏️ Biblioteca histórica · Aberturas de Relacionamento'); st.caption('Aprendo com até 6 bons cadernos e faço prova surpresa com históricos inéditos. A nota final considera também a idade da evidência e a criticidade do que mudou.')
try:
    from ednna.minerador_aberturas import descobrir_no_redmine,listar_propostas,simular_proposta,simular_prova_surpresa
    from ednna.prova_ponderada import avaliar as avaliar_ponderada
    if st.button('🔎 Estudar Redmine',key='minerar_aberturas'):
        with st.spinner('📚 Estou estudando os históricos e separando questões inéditas...'): st.session_state['mineracao_aberturas_resultado']=descobrir_no_redmine(limite_detalhes_por_player=6,limite_prova_surpresa_por_player=12)
    for p in listar_propostas():
        with st.expander(f"{p.get('player')} · {p.get('regra_id')}"):
            x1,x2,x3,x4=st.columns(4); x1.metric('Caderno inicial',p.get('evidencias',0)); x2.metric('Universo encontrado',p.get('universo_encontrado',p.get('evidencias',0))); x3.metric('Posso fazer',p.get('automatizaveis_agora',0)); x4.metric('Preciso do professor',p.get('checkpoints_humanos',0)); st.caption('Aprendi com: '+', '.join('#'+str(i) for i in p.get('casos_ids',[])))
            surpresa_ids=p.get('prova_surpresa_ids',[])
            if surpresa_ids: st.caption('🧩 Prova surpresa: '+', '.join('#'+str(i) for i in surpresa_ids))
            for e in p.get('etapas',[]): st.write(f"{'✓' if e.get('confianca')=='ALTA' else '◐'} **{e.get('descricao')}** · {'EDNNA' if e.get('responsavel')=='EDNNA' else 'Humano'} · recorrência {e.get('recorrencia_pct')}%")
            rid=str(p.get('regra_id') or ''); a,b=st.columns(2)
            with a:
                if st.button('🧪 Fazer prova do caderno',key='btn_sim_'+rid,width='stretch'): st.session_state['resultado_sim_'+rid]=simular_proposta(p)
            with b:
                if st.button('🎁 Fazer prova surpresa',key='btn_surpresa_'+rid,width='stretch',disabled=not bool(surpresa_ids)):
                    prova=simular_prova_surpresa(p); st.session_state['resultado_surpresa_'+rid]=prova
                    if prova.get('completa',False): st.session_state['ponderada_'+rid]=avaliar_ponderada(p,prova)
            sim=st.session_state.get('resultado_sim_'+rid)
            if sim: st.info(f"**Prova do caderno:** {sim.get('compativeis')}/{sim.get('casos')} · **{int(sim.get('compatibilidade_pct') or 0)}%**.")
            surpresa=st.session_state.get('resultado_surpresa_'+rid); ponderada=st.session_state.get('ponderada_'+rid); atual=estado_regra(rid)
            if surpresa: st.caption(f"Nota bruta estrutural: {surpresa.get('compativeis')}/{surpresa.get('casos')} históricos · {int(surpresa.get('compatibilidade_pct') or 0)}%")
            if ponderada:
                nota=int(ponderada.get('nota_ponderada_pct') or 0); situ=ponderada.get('situacao'); c1,c2,c3=st.columns(3); c1.metric('Nota ponderada',f'{nota}%'); c2.metric('Corte para aprovação','85%'); c3.metric('Divergências críticas recentes',len(ponderada.get('criticas_recentes') or []))
                if situ=='APROVADA_PARA_PROFESSOR':
                    st.success(f'🎓 **Professor, passei na prova com {nota}%.** Estou pronta para sua homologação.')
                    if not atual or atual.get('estado')=='SUSPENSA':
                        professor=st.text_input('Professor responsável',key='prof_'+rid,placeholder='Seu nome')
                        confirma=st.checkbox('Revisei o procedimento, os checkpoints humanos e autorizo esta versão para produção.',key='conf_'+rid)
                        if st.button('🎓 Homologar e ▶️ ativar regra',key='ativar_'+rid,type='primary',disabled=not confirma or not professor.strip(),width='stretch'):
                            try:
                                atual=homologar_e_ativar(p,ponderada,professor); st.success(f"✅ Regra {rid} v{atual['versao']} ATIVA. Agora posso praticar esta matéria em produção dentro do procedimento homologado."); st.rerun()
                            except Exception as e: st.error(f'Não consegui homologar: {e}')
                elif situ=='RECUPERACAO': st.warning(f'🧠 **Fiquei com {nota}%.** Estou em recuperação.')
                elif situ=='REVISAO_CRITICA': st.warning(f'👩‍🏫 **Minha média foi {nota}%, mas encontrei divergência crítica recente.** Preciso do professor.')
                else: st.warning(f'📚 **Minha nota ponderada foi {nota}%.** Ainda preciso estudar esta matéria.')
                with st.expander('📊 Como cheguei à nota'):
                    for q in ponderada.get('casos') or []: st.write(f"**#{q['chamado_id']}** · {q['idade_dias']} dias · peso {int(q['peso_recencia']*100)}% · aderência {q['cobertura_bruta_pct']}% · nota {q['nota_ponderada_pct']}%")
            if atual:
                estado=atual.get('estado'); icone={'ATIVA':'🟢','EM_OBSERVACAO':'🟡','SUSPENSA':'🔴'}.get(estado,'⚪'); st.info(f"{icone} **Produção: {estado.replace('_',' ')}** · v{atual.get('versao')} · homologada por {atual.get('homologado_por')} · nota {atual.get('nota')}%")
                if estado in ('ATIVA','EM_OBSERVACAO'):
                    cobs,csusp=st.columns(2)
                    if cobs.button('👀 Colocar em observação',key='obs_'+rid,width='stretch',disabled=estado=='EM_OBSERVACAO'): alterar_estado(rid,'EM_OBSERVACAO',atual.get('homologado_por'),'Observação manual do professor'); st.rerun()
                    if csusp.button('⏸️ Suspender regra',key='susp_'+rid,width='stretch'): alterar_estado(rid,'SUSPENSA',atual.get('homologado_por'),'Suspensão manual do professor'); st.rerun()
            if surpresa:
                reprovados=[d for d in (surpresa.get('detalhes') or []) if int(d.get('cobertura_pct') or 0)<80]
                if reprovados:
                    faltas=Counter(f for d in reprovados for f in (d.get('faltantes') or [])); st.markdown(f'#### 👩‍🏫 Tenho {len(reprovados)} questão(ões) para revisar')
                    for d in sorted(reprovados,key=lambda z:int(z.get('cobertura_pct') or 0)): st.write(f"**#{d.get('chamado_id')}** · {int(d.get('cobertura_pct') or 0)}% · "+', '.join(str(x).replace('_',' ').title() for x in d.get('faltantes') or []))
                    if faltas: st.info('🧠 **O que preciso reaprender:** '+', '.join(f"{str(k).replace('_',' ').title()} ({v}x)" for k,v in faltas.most_common(4)))
                with st.expander('🔬 Ver prova técnica'): st.json(surpresa)
            if not atual: st.caption('🔒 Nota aprovada leva ao professor. Somente o professor homologa e autoriza a regra para produção.')
except Exception as exc: st.error(f'Não consegui carregar a escola: {type(exc).__name__}: {exc}')
st.divider(); st.caption('🎓 Aprender não é autorizar. A versão homologada é a que trabalha; conhecimento novo volta ao professor.'); footer()
