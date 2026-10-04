from ednna.security import require_admin
import streamlit as st
from ui.operational_shell import setup, footer
from ui.operational_data import regras_df
from ednna.escola_continua import sincronizar_regras_homologadas, listar_matriculas
from ednna.homologacao import homologar_e_ativar, estado_regra
from ednna.politica_aprendizagem import diagnosticar_prova, orientar_professor, NOTA_AUTONOMIA, NOTA_EXCECAO_HUMANA

setup('🎓 Central de Aprendizagem · EDDY'); require_admin()
st.caption('A prova mede; não ensina. Quando eu não estiver pronto, mostro ao professor o que precisa melhorar na matéria antes de reestudar.')
st.info('📚 **Minha rotina:** Estudo → Prova → Diagnóstico → Correção humana → Reestudo → Nova prova → Homologação → Trabalho → Revisão contínua.')

r=regras_df()
if r.empty:
    st.info('Ainda não encontrei regras de aprendizado disponíveis neste ambiente.')
else:
    estado=r['estado'].fillna('EM_APRENDIZADO')
    rev=r[estado.eq('PRONTA_PARA_REVISAO')]
    hom=r[(estado.eq('HOMOLOGADA'))|(r.get('estado_revisao','').fillna('').eq('HOMOLOGADA'))]
    estudo=r[~r.index.isin(rev.index)&~r.index.isin(hom.index)]
    sincronizar_regras_homologadas(r)
    matriculas=listar_matriculas(); atrasadas=[m for m in matriculas if m['situacao_visual']=='REVISAO_ATRASADA']; divergentes=[m for m in matriculas if m['situacao_visual']=='PRECISO_DO_PROFESSOR']; saudaveis=[m for m in matriculas if m['situacao_visual']=='CONHECIMENTO_SAUDAVEL']
    if divergentes: st.warning(f'👨‍🏫 Professor, encontrei **{len(divergentes)} matéria(s) com divergência**. Preservei as regras e trouxe para sua revisão.')
    elif atrasadas: st.warning(f'📚 Tenho **{len(atrasadas)} matéria(s) com revisão atrasada**.')
    elif matriculas: st.success(f'😊 Estou com a matéria em dia: **{len(saudaveis)} conhecimento(s)** sem divergência ou revisão vencida.')
    c1,c2,c3,c4=st.columns(4)
    for c,l,n,nota in [(c1,'📖 Em estudo',len(estudo),'matérias sendo aprendidas'),(c2,'📝 Provas para corrigir',len(rev),'precisam do professor'),(c3,'🎓 Matriculadas',len(matriculas),'conhecimento homologado'),(c4,'👨‍🏫 Atenção',len(divergentes)+len(atrasadas),'divergências ou revisão vencida')]:
        with c: st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div><div class="op-note">{nota}</div></div>',unsafe_allow_html=True)
    st.subheader('👨‍🏫 Professores, preciso de vocês')
    if rev.empty and not divergentes: st.success('Nenhuma prova ou divergência aguarda sua decisão agora.')
    for _,x in rev.iterrows():
        cols=st.columns([4,1])
        rid=str(x.get('regra_id') or '')
        with cols[0]: st.markdown(f'<div class="rule"><b>{x.get("player") or rid}</b><br><span class="pill">Prova pronta</span> · {int(x.get("completude") or 0)}% de completude<br><small>{rid}</small></div>',unsafe_allow_html=True)
        with cols[1]:
            if st.button('Corrigir prova',key='rev_'+rid,width='stretch'):
                st.session_state['eddy_regra_foco']=rid
                st.session_state['abrir_correcao_'+rid]=True
                st.rerun()
        if st.session_state.get('abrir_correcao_'+rid):
            st.info('A correção permanece na Escola do EDDY. Revise o diagnóstico abaixo, melhore os chamados/evidências indicados e depois mande o EDDY reestudar antes de aplicar nova prova.')
    with st.expander(f'📚 Na sala de estudo ({len(estudo)})'):
        for _,x in estudo.sort_values('completude',ascending=False).iterrows(): st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_',' ').title()}")
    st.subheader('🔄 Minha agenda de revisão')
    for m in matriculas:
        dias=int(m['dias_para_revisao']); prazo=f'atrasada há {abs(dias)} dia(s)' if dias<0 else ('revisão hoje' if dias==0 else f'revisão em {dias} dia(s)')
        with st.expander(f"🎓 {m.get('player') or m['regra_id']} · {prazo}"):
            a,b,c,d=st.columns(4); a.metric('Matrícula',m['matriculada_em']); b.metric('Última revisão',m.get('ultima_revisao_em') or 'Ainda não revisada'); c.metric('Aderência atual','—' if m.get('aderencia_atual') is None else f"{float(m['aderencia_atual']):.0f}%"); d.metric('Novas evidências',m.get('evidencias_desde_revisao',0))

st.divider(); st.subheader('⛏️ Biblioteca histórica · Aberturas de Relacionamento'); st.caption('Aprendo com bons cadernos e faço prova surpresa com históricos inéditos. A nota final considera também idade da evidência e criticidade do que mudou.')
try:
    from ednna.minerador_aberturas import descobrir_no_redmine,listar_propostas,simular_proposta,simular_prova_surpresa
    from ednna.prova_ponderada import avaliar as avaliar_ponderada
    if st.button('🔎 Estudar / reestudar Redmine',key='minerar_aberturas'):
        with st.spinner('📚 Estou estudando os históricos, incorporando as correções humanas e separando questões inéditas...'): st.session_state['mineracao_aberturas_resultado']=descobrir_no_redmine(limite_detalhes_por_player=6,limite_prova_surpresa_por_player=12)
    for p in listar_propostas():
        rid=str(p.get('regra_id') or '')
        with st.expander(f"{p.get('player')} · {rid}",expanded=bool(st.session_state.get('eddy_regra_foco')==rid)):
            x1,x2,x3,x4=st.columns(4); x1.metric('Caderno inicial',p.get('evidencias',0)); x2.metric('Universo encontrado',p.get('universo_encontrado',p.get('evidencias',0))); x3.metric('Posso fazer',p.get('automatizaveis_agora',0)); x4.metric('Preciso do professor',p.get('checkpoints_humanos',0)); st.caption('Aprendi com: '+', '.join('#'+str(i) for i in p.get('casos_ids',[])))
            surpresa_ids=p.get('prova_surpresa_ids',[])
            if surpresa_ids: st.caption('🧩 Prova surpresa independente: '+', '.join('#'+str(i) for i in surpresa_ids))
            for e in p.get('etapas',[]): st.write(f"{'✓' if e.get('confianca')=='ALTA' else '◐'} **{e.get('descricao')}** · {'EDDY' if e.get('responsavel') in ('EDNNA','EDDY') else 'Humano'} · recorrência {e.get('recorrencia_pct')}%")
            a,b=st.columns(2)
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
                nota=int(ponderada.get('nota_ponderada_pct') or 0); diagnostico=diagnosticar_prova(ponderada); c1,c2,c3=st.columns(3); c1.metric('Nota ponderada',f'{nota}%'); c2.metric('Autonomia recomendada',f'{NOTA_AUTONOMIA}%'); c3.metric('Divergências críticas recentes',len(ponderada.get('criticas_recentes') or []))
                st.markdown('#### 📚 Plano de estudo do EDDY')
                st.write(orientar_professor(diagnostico))
                casos=diagnostico.get('casos_para_revisar') or []
                if casos: st.caption('Chamados para o professor revisar: '+', '.join('#'+str(i) for i in casos))
                if nota>=NOTA_AUTONOMIA and not ponderada.get('criticas_recentes'):
                    st.success(f'🎓 **Professor, passei com {nota}%.** Estou apto para sua homologação e autonomia.')
                elif nota>=NOTA_EXCECAO_HUMANA and not ponderada.get('criticas_recentes'):
                    st.warning(f'👨‍🏫 **Fiquei com {nota}%.** Ainda não atingi {NOTA_AUTONOMIA}%, mas você pode homologar excepcionalmente se o risco for aceitável. Entrarei em observação.')
                elif ponderada.get('criticas_recentes'):
                    st.warning(f'👨‍🏫 **Minha média foi {nota}%, mas encontrei divergência crítica recente.** Corrija a matéria antes da homologação.')
                else:
                    st.warning(f'📚 **Fiquei com {nota}%.** Preciso que você melhore a matéria e depois mande eu reestudar; repetir a prova agora não me ensina.')
                if nota>=NOTA_EXCECAO_HUMANA and not ponderada.get('criticas_recentes') and (not atual or atual.get('estado')=='SUSPENSA'):
                    professor=st.text_input('Professor responsável',key='prof_'+rid,placeholder='Seu nome')
                    justificativa=''
                    if nota<NOTA_AUTONOMIA: justificativa=st.text_area('Justificativa da homologação excepcional',key='just_'+rid,placeholder='Explique por que as divergências restantes são de baixo risco e a regra pode entrar em observação.')
                    confirma=st.checkbox('Revisei o procedimento, os checkpoints humanos e autorizo esta versão para produção.',key='conf_'+rid)
                    bloqueado=not confirma or not professor.strip() or (nota<NOTA_AUTONOMIA and not justificativa.strip())
                    if st.button('🎓 Homologar regra',key='ativar_'+rid,type='primary',disabled=bloqueado,width='stretch'):
                        try:
                            atual=homologar_e_ativar(p,ponderada,professor,justificativa); st.success(f"✅ Regra {rid} v{atual['versao']} em {atual['estado'].replace('_',' ')}. O EDDY pode praticar dentro do procedimento homologado."); st.rerun()
                        except Exception as e: st.error(f'Não consegui homologar: {e}')
                with st.expander('📊 Como cheguei à nota'):
                    for q in ponderada.get('casos') or []: st.write(f"**#{q['chamado_id']}** · {q['idade_dias']} dias · peso {int(q['peso_recencia']*100)}% · aderência {q['cobertura_bruta_pct']}% · nota {q['nota_ponderada_pct']}%")
            if atual:
                estado_atual=atual.get('estado'); icone={'ATIVA':'🟢','EM_OBSERVACAO':'🟡','SUSPENSA':'🔴'}.get(estado_atual,'⚪'); st.info(f"{icone} **Produção: {estado_atual.replace('_',' ')}** · v{atual.get('versao')} · homologada por {atual.get('homologado_por')} · nota {atual.get('nota')}%")
except Exception as exc:
    st.warning(f'Não foi possível carregar a Escola de Aberturas: {type(exc).__name__}: {exc}')
footer()
