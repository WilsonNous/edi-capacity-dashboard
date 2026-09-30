from __future__ import annotations
from ednna.security import require_edi
import html
import pandas as pd
import streamlit as st
from version import APP_VERSION
from ednna.security import current_user, display_name
from ednna.linguagem import quantidade, verbo
from ui.operational_shell import setup, footer
from ui.operational_data import chamados_ativos_df, redmine_link
from ednna.motor_inclusoes_operacional import avaliar_fila_inclusoes, preparar_atuacao_assistida, gerar_rascunho_inclusao, executar_atuacao_assistida_email
from ednna.followup_engine import avaliar_followups, executar_followup, followup_automatico
from ednna.acompanhamento_acoes import listar_redmine_pendentes, listar_acoes_aguardando_resposta, listar_acoes_recentes
from ednna.planejador_inclusoes import rastrear_descoberta_chamado

setup('🦾 Operação')
require_edi()
st.caption('Sua central de interação com a EDNNA. Aqui aparece o que precisa de você; o restante fica sob responsabilidade dela.')

if st.button('🔄 Sincronizar agora', type='primary', width='content', key='op_refresh_3325'):
    try:
        from redmine_api import buscar_chamados_projetos
        with st.spinner('Atualizando a carteira ativa no Redmine...'):
            buscar_chamados_projetos(status_id='open', completar_custom_fields=True, force_refresh=True)
        st.cache_data.clear()
        st.success('Carteira ativa sincronizada.')
        st.rerun()
    except Exception as exc:
        st.warning(f'Redmine indisponível. Mantendo a última fotografia válida: {type(exc).__name__}: {exc}')

df=chamados_ativos_df()
active_ids={int(v) for v in df.get('id',pd.Series(dtype=int)).dropna().tolist()} if not df.empty else set()
mapa_df={int(r['id']):r for _,r in df.iterrows() if pd.notna(r.get('id'))} if not df.empty else {}

try: aguardando_bruto=listar_acoes_aguardando_resposta()
except Exception: aguardando_bruto=[]
# A carteira status=open é soberana para a UX operacional. Chamado rejeitado,
# concluído, cancelado ou fechado não continua em acompanhamento visual.
aguardando=[a for a in aguardando_bruto if int(a.get('chamado_id') or 0) in active_ids]
try: rm_pend=[a for a in listar_redmine_pendentes() if int(a.get('chamado_id') or 0) in active_ids]
except Exception: rm_pend=[]
try: recentes=listar_acoes_recentes(80)
except Exception: recentes=[]

snapshot=pd.DataFrame()
if not df.empty:
    snapshot=df.rename(columns={'id':'#','cliente':'Clientes','tipo':'Tipo','estado':'Estado','prioridade':'Prioridade','assunto':'Assunto','responsavel':'Atribuído a','projeto':'Projeto','origem':'Origem','descricao':'Descrição','alterado_em':'Alterado'}).copy()
try: fila=avaliar_fila_inclusoes(snapshot) if not snapshot.empty else {'resumo':{},'itens':[]}
except Exception as exc:
    st.error(f'Fila operacional indisponível: {type(exc).__name__}: {exc}'); fila={'resumo':{},'itens':[]}
try: fups=avaliar_followups()
except Exception: fups={'total':0,'prontos':0,'automaticos_prontos':0,'assistidos_prontos':0,'itens':[]}

# Follow-up vencido automático continua pertencendo à EDNNA. Se a regra é
# assistida, quando o prazo vence a decisão passa para 'Preciso de você'.
fup_assistidos_prontos=[x for x in fups.get('itens',[]) if x.get('estado_followup')=='FOLLOWUP_PRONTO' and not followup_automatico(x)]
fup_auto_prontos=[x for x in fups.get('itens',[]) if x.get('estado_followup')=='FOLLOWUP_PRONTO' and followup_automatico(x)]
fup_assistidos_ids={int(x.get('chamado_id') or 0) for x in fup_assistidos_prontos}

itens=fila.get('itens') or []
human_states={'AGUARDANDO_DADOS','AGUARDANDO_DESTINATARIO','REGRA_HOMOLOGADA_NAO_AUTORIZADA','REGRA_NAO_HOMOLOGADA'}
preciso=[x for x in itens if x.get('estado_motor') in human_states]
preciso += [x for x in itens if x.get('estado_motor')=='PRONTO_OPERACAO_ASSISTIDA' and str(x.get('modo_motor') or '').upper()!='AUTOMATICA']
preciso += [{'id':x.get('chamado_id'),'cliente':x.get('cliente') or '', 'player':x.get('player') or '',
            'estado_motor':'FOLLOWUP_ASSISTIDO_PRONTO','acao_sugerida':'Autorizar/enviar follow-up assistido',
            'regra_id':x.get('regra_id'),'followup_item':x} for x in fup_assistidos_prontos]
falhas=[x for x in itens if x.get('estado_motor') in {'PLAYER_AMBIGUO','AGUARDANDO_EXECUTOR'}]
historico_auto=[x for x in itens if x.get('estado_motor')=='AGUARDANDO_VERIFICACAO_HISTORICO']
redmine_auto=[]
for x in rm_pend:
    tent=int(x.get('redmine_tentativas') or 0)
    item={'id':x.get('chamado_id'),'cliente':'','player':'REDMINE','estado_motor':'REDMINE_PENDENTE',
          'acao_sugerida':'Reconciliação automática Redmine','regra_id':x.get('regra_id'),
          'redmine_erro':x.get('redmine_erro'),'redmine_tentativas':tent}
    (falhas if tent>=3 else redmine_auto).append(item)

# Detecta automações vencidas para dar visibilidade sem transformá-las em tarefa humana.
agora=pd.Timestamp.now(tz='America/Sao_Paulo')
atrasados=[]
for a in aguardando:
    prazo=str(a.get('prazo_resposta_em') or '')
    if prazo:
        try:
            if pd.Timestamp(prazo) <= agora and int(a.get('chamado_id') or 0) not in fup_assistidos_ids:
                atrasados.append(a)
        except Exception: pass

# Um follow-up assistido já vencido deixou de ser responsabilidade automática;
# aparece em 'Preciso de você', não duplica em 'Estou cuidando'.
aguardando_ednna=[a for a in aguardando if int(a.get('chamado_id') or 0) not in fup_assistidos_ids]
cuidando_total=len(aguardando_ednna)+len(historico_auto)+len(redmine_auto)
usuario = current_user()
nome_usuario = display_name(usuario) or 'você'
st.markdown(f"### {'Bom dia' if agora.hour<12 else 'Boa tarde' if agora.hour<18 else 'Boa noite'}, {nome_usuario}. "
            f"Preciso de você em **{quantidade(len(preciso), 'situação', 'situações')}**. Estou cuidando de **{quantidade(cuidando_total, 'chamado')}**.")

c1,c2,c3,c4=st.columns(4)
c1.metric('🔴 Você',len(preciso),help='Somente decisões ou ações que a EDNNA não pode tomar sozinha.')
c2.metric('🟢 EDNNA',cuidando_total,help='Acompanhamentos, histórico e reconciliações automáticas.')
c3.metric('🤖 Realizado',len(recentes),help='Atuações persistidas recentemente.')
c4.metric('⚠️ Exceções',len(falhas),help='Situações em que a automação realmente travou.')

if atrasados:
    st.warning(f"⏱️ **{quantidade(len(atrasados), 'acompanhamento')}** {verbo(len(atrasados), 'está', 'estão')} com execução automática atrasada. A EDNNA tentará executá-los no próximo ciclo; acompanhe em **Estou cuidando → Atrasados**.")
if fup_assistidos_prontos:
    st.info(f"👤 **{quantidade(len(fup_assistidos_prontos), 'follow-up')}** {verbo(len(fup_assistidos_prontos), 'depende', 'dependem')} de ação humana porque a regra está em modo assistido. Eles aparecem em **Preciso de você**.")

tab_voce,tab_ednna,tab_feito,tab_exc=st.tabs([
    f'🔴 Preciso de você · {len(preciso)}',
    f'🟢 Estou cuidando · {cuidando_total}',
    f'🤖 Fiz / acompanhei · {len(recentes)}',
    f'⚠️ Exceções · {len(falhas)}'
])

with tab_voce:
    st.caption('Só entra aqui o que realmente exige decisão, autorização, dado ou confirmação humana.')
    busca=st.text_input('🔎 Filtrar por chamado, cliente ou player',key='busca_voce_3325',placeholder='Ex.: 49229, Sander, REDECARD')
    lista=preciso
    if busca.strip():
        q=busca.casefold().strip()
        lista=[x for x in lista if q in f"{x.get('id')} {x.get('cliente')} {x.get('player')} {x.get('acao_sugerida')}".casefold()]
    if not lista:
        st.success('Nenhuma interação humana pendente.')
    for x in lista[:50]:
        cid=int(x.get('id') or 0); estado=str(x.get('estado_motor') or '')
        cliente=str(x.get('cliente') or 'Cliente não informado'); player=str(x.get('player') or '')
        cols=st.columns([1.1,2.5,1.6,2.2])
        cols[0].markdown(f'**[#{cid}]({redmine_link(cid)})**')
        cols[1].write(cliente)
        cols[2].write(player or '—')
        cols[3].write(f"**{x.get('acao_sugerida') or estado.replace('_',' ')}**")
        if estado=='FOLLOWUP_ASSISTIDO_PRONTO':
            fitem=x.get('followup_item') or {}
            with st.expander(f'Revisar follow-up assistido #{cid}'):
                st.text_area('Mensagem de acompanhamento', fitem.get('texto_followup') or '', height=180, disabled=True, key=f'fup_body_{cid}_3345')
                ok_fup=st.checkbox('Revisei e autorizo este follow-up.', key=f'fup_ok_{cid}_3345')
                if st.button('📨 Enviar follow-up agora', disabled=not ok_fup, key=f'fup_send_{cid}_3345'):
                    res=executar_followup(fitem)
                    if res.get('ok'):
                        st.success('Follow-up enviado. A EDNNA continua acompanhando o retorno.'); st.rerun()
                    else:
                        st.warning(res.get('motivo') or 'Follow-up não executado.')
        if estado=='PRONTO_OPERACAO_ASSISTIDA':
            with st.expander(f'Revisar atuação assistida #{cid}'):
                if st.button('🧾 Preparar atuação', key=f'prep_{cid}_3325'):
                    st.session_state[f'pacote_{cid}_3325']=preparar_atuacao_assistida(x)
                pacote=st.session_state.get(f'pacote_{cid}_3325')
                if pacote:
                    r=gerar_rascunho_inclusao(pacote)
                    if r.get('ok'):
                        para=st.text_input('Para',', '.join(r.get('para') or []),key=f'para_{cid}_3325')
                        cc=st.text_input('Cc',', '.join(r.get('cc') or []),key=f'cc_{cid}_3325')
                        assunto=st.text_input('Assunto',r.get('assunto') or '',key=f'ass_{cid}_3325')
                        corpo=st.text_area('Mensagem',r.get('corpo') or '',height=220,key=f'body_{cid}_3325')
                        pacote['email_override']={'para':[z.strip() for z in para.replace(';',',').split(',') if z.strip()],
                            'cc':[z.strip() for z in cc.replace(';',',').split(',') if z.strip()],'assunto':assunto,'corpo':corpo}
                        ok=st.checkbox('Revisei e autorizo esta atuação.',key=f'ok_{cid}_3325')
                        if st.button('📨 Executar agora',disabled=not ok,key=f'exec_{cid}_3325'):
                            res=executar_atuacao_assistida_email(pacote)
                            if res.get('ok'): st.success('Atuação executada. A EDNNA assumirá o acompanhamento.'); st.rerun()
                            else: st.warning(res.get('motivo') or 'Ação não executada.')
        st.divider()

with tab_ednna:
    st.caption('Você não precisa agir aqui. Use esta visão para fiscalizar o trabalho que a EDNNA assumiu.')
    filtro=st.segmented_control('Mostrar', ['Todos','No prazo','Atrasados','Redmine','Histórico'], default='Todos', key='filtro_cuidando_3325')
    busca=st.text_input('🔎 Buscar acompanhamento',key='busca_cuidando_3325',placeholder='Chamado, cliente ou player')
    if redmine_auto and filtro in ('Todos','Redmine'):
        st.info(f"🔄 **{quantidade(len(redmine_auto), 'atualização', 'atualizações')}** {verbo(len(redmine_auto), 'está', 'estão')} em reconciliação automática.")
    if historico_auto and filtro in ('Todos','Histórico'):
        st.info(f"🧠 **{quantidade(len(historico_auto), 'chamado')}** {verbo(len(historico_auto), 'está', 'estão')} com histórico sendo sincronizado automaticamente.")
    linhas=[]
    for a in aguardando_ednna:
        cid=int(a.get('chamado_id') or 0); row=mapa_df.get(cid,{})
        prazo=str(a.get('prazo_resposta_em') or '')
        vencido=False
        if prazo:
            try: vencido=pd.Timestamp(prazo)<=agora
            except Exception: pass
        if filtro=='No prazo' and vencido: continue
        if filtro=='Atrasados' and not vencido: continue
        if filtro in ('Redmine','Histórico'): continue
        cliente=str(row.get('cliente') or 'Cliente não informado'); player=str(row.get('origem') or '')
        if busca.strip() and busca.casefold() not in f'{cid} {cliente} {player}'.casefold(): continue
        ultima=a.get('followup_ultimo_em') or a.get('enviado_em') or 'registrada'
        modo_auto = followup_automatico(a)
        proxima=('Execução automática atrasada' if vencido and modo_auto else 'Follow-up aguardando operador' if vencido else (f'Follow-up {prazo[:16].replace("T"," ")}' if prazo else 'Monitorar retorno'))
        linhas.append((cid,cliente,player,str(a.get('estado') or 'AGUARDANDO_RESPOSTA').replace('_',' '),ultima,proxima,vencido,a))
    if not linhas and filtro not in ('Redmine','Histórico'):
        st.info('Nenhum acompanhamento neste filtro.')
    for cid,cliente,player,estado,ultima,proxima,vencido,a in linhas[:80]:
        cols=st.columns([1.0,2.3,1.5,1.7,2.1])
        cols[0].markdown(f'**[#{cid}]({redmine_link(cid)})**')
        cols[1].write(cliente)
        cols[2].write(player or '—')
        cols[3].write('🔴 Atrasado' if vencido else '🟢 No prazo')
        cols[4].write(proxima)
        with st.expander(f'Detalhes #{cid}',expanded=False):
            st.write(f'**Estado:** {estado}')
            st.write(f'**Última atuação:** {ultima}')
            st.write(f"**Regra:** {a.get('regra_id') or '—'}")
            st.write('**Responsável:** EDNNA')
        st.divider()

with tab_feito:
    st.caption('Trilha operacional recente. Chamados que deixaram a carteira ativa permanecem apenas como auditoria histórica.')
    busca=st.text_input('🔎 Buscar no realizado',key='busca_feito_3325')
    mostrados=0
    for a in recentes[:80]:
        cid=int(a.get('chamado_id') or 0); row=mapa_df.get(cid,{})
        cliente=str(row.get('cliente') or '')
        regra=str(a.get('regra_id') or '')
        if busca.strip() and busca.casefold() not in f'{cid} {cliente} {regra}'.casefold(): continue
        quando=a.get('followup_ultimo_em') or a.get('enviado_em') or a.get('atualizado_em') or ''
        acao='Follow-up enviado' if int(a.get('followup_count') or 0)>0 else 'Primeira atuação enviada'
        situacao='' if cid in active_ids else ' · histórico/fora da carteira ativa'
        st.markdown(f"**{quando}** · [#{cid}]({redmine_link(cid)}) · {html.escape(cliente or 'cliente histórico')} · **{acao}** · `{html.escape(regra)}`{situacao}")
        mostrados+=1
    if not mostrados: st.info('Nenhuma atuação encontrada.')

with tab_exc:
    st.caption('Somente falhas reais de automação aparecem aqui. Trabalho técnico recuperável continua com a EDNNA.')
    if not falhas: st.success('Nenhuma exceção operacional neste momento.')
    for x in falhas[:50]:
        cid=int(x.get('id') or 0)
        st.error(f"#{cid} · {x.get('cliente') or ''} · {x.get('player') or ''} — {x.get('acao_sugerida') or x.get('estado_motor')}")
        if x.get('redmine_erro'): st.caption(str(x.get('redmine_erro')))

with st.expander('🔎 Rastrear um chamado'):
    cid_txt=st.text_input('Número do chamado',key='trace_id_3325',placeholder='Ex.: 49286')
    if st.button('Rastrear',key='trace_go_3325') and cid_txt.strip():
        try:
            diag=rastrear_descoberta_chamado(snapshot,int(cid_txt))
            st.json(diag)
        except Exception as exc: st.warning(f'Não foi possível rastrear: {type(exc).__name__}: {exc}')

st.markdown('<a href="/Operacao" target="_blank" rel="noopener noreferrer">↗ Abrir Central de Operações em nova aba</a>', unsafe_allow_html=True)
st.caption('Segurança operacional: chamados Rejeitados, Concluídos, Cancelados ou Fechados são bloqueados por pre-flight no Redmine antes de e-mail ou follow-up.')
footer()
