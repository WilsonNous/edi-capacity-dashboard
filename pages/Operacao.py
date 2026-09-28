from __future__ import annotations
import html
import pandas as pd
import streamlit as st
from version import APP_VERSION
from ui.operational_shell import setup, footer
from ui.operational_data import chamados_ativos_df, redmine_link
from ednna.motor_inclusoes_operacional import avaliar_fila_inclusoes, preparar_atuacao_assistida, gerar_rascunho_inclusao, executar_atuacao_assistida_email
from ednna.followup_engine import avaliar_followups, executar_followup, followup_automatico
from ednna.acompanhamento_acoes import listar_redmine_pendentes, listar_acoes_aguardando_resposta, listar_acoes_recentes, obter_acompanhamento
from ednna.redmine_outbox import reconciliar_redmine_chamado
from ednna.planejador_inclusoes import rastrear_descoberta_chamado

setup('🦾 Operação de hoje')
st.caption('Seu painel de interação com a EDNNA: o que precisa de você, o que ela está cuidando, o que fez e onde travou.')

# Atualização explícita = sincronização real. Navegação comum continua local-first.
if st.button('🔄 Atualizar fila agora', type='primary', width='content', key='op_refresh_3320'):
    try:
        from redmine_api import buscar_chamados_projetos
        with st.spinner('Sincronizando chamados abertos com o Redmine...'):
            buscar_chamados_projetos(status_id='open', completar_custom_fields=True, force_refresh=True)
        st.cache_data.clear()
        st.session_state['op_calcular_3320']=True
        st.success('Fotografia operacional sincronizada.')
        st.rerun()
    except Exception as exc:
        st.warning(f'Redmine indisponível. Mantendo a última fotografia válida: {type(exc).__name__}: {exc}')
        st.session_state['op_calcular_3320']=True

# Sempre abre imediatamente com SQLite/cache.
df=chamados_ativos_df()
try: aguardando=listar_acoes_aguardando_resposta()
except Exception: aguardando=[]
try: rm_pend=listar_redmine_pendentes()
except Exception: rm_pend=[]
try: recentes=listar_acoes_recentes(60)
except Exception: recentes=[]

snapshot=pd.DataFrame()
if not df.empty:
    snapshot=df.rename(columns={'id':'#','cliente':'Clientes','tipo':'Tipo','estado':'Estado','prioridade':'Prioridade','assunto':'Assunto','responsavel':'Atribuído a','projeto':'Projeto','origem':'Origem','descricao':'Descrição','alterado_em':'Alterado'}).copy()
try: fila=avaliar_fila_inclusoes(snapshot) if not snapshot.empty else {'resumo':{},'itens':[]}
except Exception as exc:
    st.error(f'Fila operacional indisponível: {type(exc).__name__}: {exc}'); fila={'resumo':{},'itens':[]}
try: fups=avaliar_followups()
except Exception: fups={'total':0,'prontos':0,'itens':[]}

itens=fila.get('itens') or []
# Somente interação humana real.
human_states={'AGUARDANDO_DADOS','AGUARDANDO_DESTINATARIO','REGRA_HOMOLOGADA_NAO_AUTORIZADA','AGUARDANDO_VERIFICACAO_HISTORICO','REGRA_NAO_HOMOLOGADA'}
preciso=[x for x in itens if x.get('estado_motor') in human_states]
preciso += [x for x in itens if x.get('estado_motor')=='PRONTO_OPERACAO_ASSISTIDA' and str(x.get('modo_motor') or '').upper()!='AUTOMATICA']
falhas=[x for x in itens if x.get('estado_motor') in {'PLAYER_AMBIGUO','AGUARDANDO_EXECUTOR'}]
# Reconciliação é exceção técnica, nunca motivo para reenvio.
for x in rm_pend:
    falhas.append({'id':x.get('chamado_id'),'cliente':'','player':'REDMINE','estado_motor':'REDMINE_PENDENTE','acao_sugerida':'Reconciliar Redmine','regra_id':x.get('regra_id'),'redmine_erro':x.get('redmine_erro')})

# Cards de orientação, não dashboard genérico.
c1,c2,c3,c4=st.columns(4)
c1.metric('🔴 Preciso de você',len(preciso))
c2.metric('🟢 Estou cuidando',len(aguardando))
c3.metric('🤖 Fiz / acompanhei',len(recentes))
c4.metric('⚠️ Não consegui continuar',len(falhas))

st.markdown('## 🔴 Preciso de você')
st.caption('Somente situações que exigem análise, autorização, complemento ou execução assistida aparecem aqui.')
if not preciso:
    st.success('Nenhuma interação humana pendente neste momento.')
else:
    for x in preciso[:30]:
        cid=int(x.get('id') or 0); estado=str(x.get('estado_motor') or '')
        cliente=html.escape(str(x.get('cliente') or 'Cliente não informado')); player=html.escape(str(x.get('player') or ''))
        with st.container(border=True):
            st.markdown(f'**[#{cid}]({redmine_link(cid)}) · {cliente} · {player}**')
            st.write(f"**Por que estou chamando você:** {x.get('acao_sugerida') or estado.replace('_',' ')}")
            if estado=='PRONTO_OPERACAO_ASSISTIDA':
                st.caption('Regra assistida: a EDNNA preparou a atuação, mas sua confirmação ainda é necessária.')
                if st.button('🧾 Preparar atuação', key=f'prep_{cid}_3320'):
                    st.session_state[f'pacote_{cid}_3320']=preparar_atuacao_assistida(x)
                pacote=st.session_state.get(f'pacote_{cid}_3320')
                if pacote:
                    r=gerar_rascunho_inclusao(pacote)
                    if r.get('ok'):
                        para=st.text_input('Para',', '.join(r.get('para') or []),key=f'para_{cid}_3320')
                        cc=st.text_input('Cc',', '.join(r.get('cc') or []),key=f'cc_{cid}_3320')
                        assunto=st.text_input('Assunto',r.get('assunto') or '',key=f'ass_{cid}_3320')
                        corpo=st.text_area('Mensagem',r.get('corpo') or '',height=260,key=f'body_{cid}_3320')
                        pacote['email_override']={'para':[z.strip() for z in para.replace(';',',').split(',') if z.strip()],'cc':[z.strip() for z in cc.replace(';',',').split(',') if z.strip()],'assunto':assunto,'corpo':corpo}
                        ok=st.checkbox('Revisei e autorizo esta atuação.',key=f'ok_{cid}_3320')
                        if st.button('📨 Executar agora',disabled=not ok,key=f'exec_{cid}_3320'):
                            res=executar_atuacao_assistida_email(pacote)
                            if res.get('ok'): st.success('Atuação executada. A EDNNA assumirá o acompanhamento.'); st.rerun()
                            else: st.warning(res.get('motivo') or 'Ação não executada.')

st.markdown('## 🟢 Estou cuidando')
st.caption('Você não precisa agir agora. Aqui ficam os chamados que a EDNNA já atuou e está acompanhando.')
if not aguardando:
    st.info('Nenhum acompanhamento persistido neste momento.')
else:
    mapa_df={int(r['id']):r for _,r in df.iterrows() if pd.notna(r.get('id'))} if not df.empty else {}
    for a in aguardando[:50]:
        cid=int(a.get('chamado_id') or 0); row=mapa_df.get(cid,{})
        cliente=str(row.get('cliente') or 'Cliente não informado'); player=str(row.get('origem') or '')
        prazo=str(a.get('prazo_resposta_em') or '')
        estado=str(a.get('estado') or 'AGUARDANDO_RESPOSTA').replace('_',' ')
        with st.container(border=True):
            st.markdown(f'**[#{cid}]({redmine_link(cid)}) · {html.escape(cliente)} · {html.escape(player)}**')
            cols=st.columns(3)
            cols[0].write(f'**Status:** {estado}')
            cols[1].write(f"**Última atuação:** {a.get('followup_ultimo_em') or a.get('enviado_em') or 'registrada'}")
            cols[2].write(f"**Próxima ação:** {'follow-up automático no prazo' if prazo else 'monitorar retorno'}")
            if prazo: st.caption(f'Prazo de resposta: {prazo} · Responsável: EDNNA')

st.markdown('## 🤖 Fiz / acompanhei')
st.caption('Últimas atuações persistidas pela EDNNA. Serve como trilha operacional rápida.')
if not recentes:
    st.info('Ainda não há atuações persistidas para mostrar.')
else:
    mapa_df={int(r['id']):r for _,r in df.iterrows() if pd.notna(r.get('id'))} if not df.empty else {}
    for a in recentes[:20]:
        cid=int(a.get('chamado_id') or 0); row=mapa_df.get(cid,{})
        quando=a.get('followup_ultimo_em') or a.get('enviado_em') or a.get('atualizado_em') or ''
        acao='Follow-up enviado' if int(a.get('followup_count') or 0)>0 else 'Primeira atuação enviada'
        st.markdown(f"**{quando}** · [#{cid}]({redmine_link(cid)}) · {html.escape(str(row.get('cliente') or ''))} · **{acao}** · `{html.escape(str(a.get('regra_id') or ''))}`")

st.markdown('## ⚠️ Não consegui continuar')
st.caption('Exceções reais: identificação ambígua, executor ausente ou reconciliação técnica. A EDNNA explica o motivo.')
if not falhas:
    st.success('Nenhuma exceção operacional pendente.')
else:
    for x in falhas[:30]:
        cid=int(x.get('id') or 0); motivo=x.get('redmine_erro') or x.get('acao_sugerida') or x.get('estado_motor')
        with st.container(border=True):
            st.markdown(f'**[#{cid}]({redmine_link(cid)}) · {html.escape(str(x.get("cliente") or ""))} · {html.escape(str(x.get("player") or ""))}**')
            st.write(f'**Motivo:** {motivo}')
            if x.get('estado_motor')=='REDMINE_PENDENTE':
                if st.button('🔄 Reconciliar Redmine',key=f'rm_{cid}_{x.get("regra_id")}_3320'):
                    rr=reconciliar_redmine_chamado(cid,str(x.get('regra_id') or ''))
                    if rr.get('atualizados'): st.success('Reconciliado sem reenviar e-mail.'); st.rerun()
                    else: st.error('; '.join(rr.get('erros') or ['Redmine continua pendente']))

# Follow-ups automáticos ficam deliberadamente fora da fila humana.
fup_ready=[x for x in (fups.get('itens') or []) if x.get('estado_followup')=='FOLLOWUP_PRONTO']
auto=[x for x in fup_ready if followup_automatico(x)]
assist=[x for x in fup_ready if not followup_automatico(x)]
if auto: st.info(f'🤖 {len(auto)} follow-up(s) automático(s) prontos: a EDNNA executará pelo worker; nenhum clique é necessário.')
if assist:
    with st.expander(f'📨 Follow-ups assistidos que precisam de você · {len(assist)}',expanded=True):
        for f in assist:
            cid=int(f.get('chamado_id') or 0)
            texto=st.text_area(f'#{cid} · follow-up {f.get("proximo_followup")}',f.get('texto_followup') or '',height=160,key=f'fup_{cid}_{f.get("regra_id")}_3320')
            if st.button('Enviar follow-up',key=f'fupgo_{cid}_{f.get("regra_id")}_3320'):
                fx=dict(f); fx['texto_followup']=texto; executar_followup(fx); st.success('Follow-up enviado.'); st.rerun()

with st.expander('🔎 Rastrear um chamado',expanded=False):
    st.caption('Diagnóstico local: mostra se o chamado entrou na fotografia e se o motor o descobriu.')
    cid_trace=st.number_input('Número do chamado',min_value=1,step=1,value=49286,key='trace_3320')
    if st.button('Rastrear',key='trace_go_3320'):
        tr=rastrear_descoberta_chamado(snapshot,int(cid_trace))
        st.json(tr)

footer()
