from __future__ import annotations
import html
import pandas as pd
import streamlit as st
from version import APP_VERSION
from ui.operational_shell import setup, footer
from ui.operational_data import chamados_ativos_df, redmine_link
from ednna.motor_inclusoes_operacional import avaliar_fila_inclusoes, diagnosticar_regras_operacionais, preparar_atuacao_assistida, gerar_rascunho_inclusao, executar_atuacao_assistida_email
from ednna.followup_engine import avaliar_followups, executar_followup
from ednna.acompanhamento_acoes import listar_redmine_pendentes, listar_acoes_aguardando_resposta, obter_acompanhamento
from ednna.redmine_outbox import reconciliar_redmine_chamado

setup('🦾 Operação de hoje')
st.caption('A tela abre imediatamente com dados locais. O diagnóstico pesado só roda quando você pedir atualização da fila.')

# snapshot local compartilhado
df = chamados_ativos_df()
try:
    _aguardando_local = listar_acoes_aguardando_resposta()
except Exception:
    _aguardando_local = []
try:
    _redmine_local = listar_redmine_pendentes()
except Exception:
    _redmine_local = []

st.markdown("### Fotografia imediata")
c1,c2,c3=st.columns(3)
c1.metric("Chamados ativos", len(df))
c2.metric("Aguardando resposta", len(_aguardando_local))
c3.metric("Redmine pendente", len(_redmine_local))
st.caption("Estes números vêm do SQLite/cache local e aparecem sem consultar o Redmine.")

if st.button("🔄 Atualizar fila operacional", type="primary", width="content", key="op_refresh_3292"):
    st.session_state["op_calcular_3292"] = True

if not st.session_state.get("op_calcular_3292"):
    st.info("A tela está pronta. Clique em **Atualizar fila operacional** para recalcular regras, chamados prontos, pendências e diagnósticos. Voltar para a EDNNA não executa esse cálculo novamente.")
    footer()
    st.stop()

# Operação real também na Home bonita da EDNNA — o backend deixa de ser obrigatório.
op_shell = st.container(key='ednna_operation_shell')
with op_shell:
    st.markdown('<div class="module-title">🦾 Trabalho de hoje</div><div class="module-sub">A EDNNA mostra primeiro o que pode fazer, o que precisa de você e o que já está acompanhando.</div>', unsafe_allow_html=True)
    snapshot_motor = pd.DataFrame()
    if not df.empty:
        snapshot_motor = df.rename(columns={
            'id':'#','cliente':'Clientes','tipo':'Tipo','estado':'Estado','prioridade':'Prioridade',
            'assunto':'Assunto','responsavel':'Atribuído a','projeto':'Projeto'
        }).copy()
    
    try:
        with st.spinner('Calculando fila operacional a partir do snapshot local...'):
            fila_home = avaliar_fila_inclusoes(snapshot_motor) if not snapshot_motor.empty else {'resumo':{},'itens':[]}
    except Exception as exc:
        st.error(f'Falha ao calcular fila operacional: {type(exc).__name__}: {exc}')
        fila_home={'resumo':{},'itens':[]}
    
    try:
        follow_home = avaliar_followups()
    except Exception as exc:
        st.warning(f'Follow-up indisponível neste ciclo: {type(exc).__name__}: {exc}')
        follow_home={'total':0,'prontos':0,'itens':[]}
    try: redmine_pendentes = listar_redmine_pendentes()
    except Exception: redmine_pendentes = []
    
    try:
        diagnostico_home = diagnosticar_regras_operacionais(snapshot_motor) if not snapshot_motor.empty else {'regras': [], 'fila': fila_home}
    except Exception as exc:
        st.warning(f'Diagnóstico por regra indisponível neste ciclo: {type(exc).__name__}: {exc}')
        diagnostico_home={'regras': [], 'fila': fila_home}
    regras_diag = diagnostico_home.get('regras') or []
    precisa_voce = sum(1 for x in (fila_home.get('itens') or []) if x.get('estado_motor') in {'AGUARDANDO_DADOS','AGUARDANDO_DESTINATARIO','REGRA_HOMOLOGADA_NAO_AUTORIZADA','AGUARDANDO_VERIFICACAO_HISTORICO','PLAYER_AMBIGUO'})
    problemas_ident = sum(1 for x in (fila_home.get('itens') or []) if x.get('estado_motor') in {'PLAYER_AMBIGUO','REGRA_NAO_HOMOLOGADA'})
    op1,op2,op3,op4,op5=st.columns(5)
    op1.metric('Prontos para executar', int((fila_home.get('resumo') or {}).get('prontas',0) or 0))
    op2.metric('Precisam de você', precisa_voce)
    op3.metric('Aguardando resposta', int(follow_home.get('total',0) or 0))
    op4.metric('Follow-up pronto', int(follow_home.get('prontos',0) or 0))
    op5.metric('Problemas de identificação', problemas_ident)

    assistidas_diag=[x for x in regras_diag if x.get('modo')=='ASSISTIDA']
    if assistidas_diag:
        with st.expander(f"👤 Regras assistidas · {len(assistidas_diag)} — veja os chamados e decida o que automatizar", expanded=True):
            st.caption('Aqui fica claro se a regra está sem demanda ou se existe chamado bloqueado, pronto ou já em acompanhamento. A mudança para automático continua exigindo autorização explícita na Central de Regras.')
            for dg in assistidas_diag:
                icone={'PRONTA':'🟢','SEM_DEMANDA':'⚪','PRECISA_DE_VOCE':'🟡','ERRO_TECNICO':'🔴','IDENTIFICACAO':'🔴','EM_ACOMPANHAMENTO':'🔵'}.get(dg.get('situacao'),'⚫')
                st.markdown(f"**{icone} {html.escape(str(dg.get('player')))}** · `{html.escape(str(dg.get('regra_id')))}` · **{html.escape(str(dg.get('situacao')).replace('_',' '))}** — {html.escape(str(dg.get('motivo')))}")
                if dg.get('chamados'):
                    for ch in dg.get('chamados')[:8]:
                        cid_d=int(ch.get('id') or 0)
                        st.markdown(f"&nbsp;&nbsp;↳ [#{cid_d}]({redmine_link(cid_d)}) · {html.escape(str(ch.get('cliente') or 'Cliente não informado'))} · **{html.escape(str(ch.get('motivo')))}** · próxima ação: {html.escape(str(ch.get('acao_sugerida')))}")
                else:
                    st.caption('Sem chamado ativo correspondente neste momento.')
            if st.button('⚙️ Abrir Central de Regras para tornar automáticas', key='home_go_rules_32859', width='content'):
                st.switch_page('pages/Regras.py')

    prontos=[x for x in fila_home.get('itens',[]) if x.get('estado_motor')=='PRONTO_OPERACAO_ASSISTIDA']
    # Defesa de interface: a fonte transacional vence a fila do motor. Mesmo que
    # algum snapshot esteja defasado, jamais oferecemos nova atuação a chamado
    # que já esteja aguardando reconciliação Redmine.
    ids_rm_pendentes={int(x.get('chamado_id') or 0) for x in redmine_pendentes}
    prontos=[x for x in prontos if int(x.get('id') or 0) not in ids_rm_pendentes]
    if prontos:
        mapa={int(x['id']):x for x in prontos}
        cid=st.selectbox('Chamado pronto para atuação', list(mapa), format_func=lambda x:f"#{x} · {mapa[x].get('player')} · {mapa[x].get('cliente') or 'Sem cliente'}", key='home_ednna_operacao_sel_v32842')
        item=mapa[int(cid)]
        acompanhamento_home = obter_acompanhamento(int(cid), str(item.get('regra_id') or '')) or {}
        email_ja_enviado_home = bool(int(acompanhamento_home.get('envio_confirmado') or 0) == 1 or str(acompanhamento_home.get('graph_message_id') or '').strip() or str(acompanhamento_home.get('enviado_em') or '').strip())
        st.markdown(
            f"**Chamado:** [#{int(cid)}]({redmine_link(cid)}) &nbsp; · &nbsp; **Cliente:** {html.escape(str(item.get('cliente') or 'Sem cliente'))}"
        )
        if st.button('🧾 Preparar atuação', type='primary', width='content', key='home_ednna_prepare_v32842'):
            st.session_state['home_ednna_pacote_v32842']=preparar_atuacao_assistida(item)
        pacote=st.session_state.get('home_ednna_pacote_v32842')
        if pacote and int(pacote.get('chamado_id') or 0)==int(cid):
            rasc=gerar_rascunho_inclusao(pacote)
            if rasc.get('ok'):
                st.caption('Modo assistido: você pode ajustar destinatários, assunto e corpo antes do envio. A regra homologada não é alterada por esse ajuste pontual.')
                para_edit = st.text_input('Para', ', '.join(rasc.get('para') or []), key=f'home_ednna_para_{cid}_v3293')
                cc_edit = st.text_input('Cc', ', '.join(rasc.get('cc') or []), key=f'home_ednna_cc_{cid}_v3293')
                assunto_edit = st.text_input('Assunto', rasc.get('assunto') or '', key=f'home_ednna_assunto_{cid}_v3293')
                corpo_edit = st.text_area('Mensagem que será enviada', rasc.get('corpo') or '', height=300, key=f'home_ednna_preview_{cid}_v3293')
                pacote['email_override'] = {
                    'para':[x.strip() for x in para_edit.replace(';', ',').split(',') if x.strip()],
                    'cc':[x.strip() for x in cc_edit.replace(';', ',').split(',') if x.strip()],
                    'assunto':assunto_edit.strip(),
                    'corpo':corpo_edit,
                }
                if email_ja_enviado_home:
                    st.success('✓ E-mail já enviado — novo disparo bloqueado pela idempotência.')
                    ev_id=str(acompanhamento_home.get('graph_message_id') or acompanhamento_home.get('graph_internet_message_id') or '').strip()
                    ev_dt=str(acompanhamento_home.get('enviado_em') or '').strip()
                    st.caption(f"Evidência Graph: {ev_id or 'HTTP 202 confirmado'} · envio: {ev_dt or 'registrado'}")
                    pendente_deste=[x for x in redmine_pendentes if int(x.get('chamado_id') or 0)==int(cid)]
                    if pendente_deste:
                        erro_rm=str(pendente_deste[0].get('redmine_erro') or '').strip()
                        st.warning(f"Redmine pendente. {('Último erro: ' + erro_rm) if erro_rm else 'A atualização será reconciliada sem reenviar o e-mail.'}")
                        if st.button('🔄 Reconciliar Redmine agora', type='secondary', width='content', key=f'home_ednna_reconcile_{cid}_v32853'):
                            rr=reconciliar_redmine_chamado(int(cid), str(item.get('regra_id') or ''))
                            if rr.get('atualizados'):
                                st.success('Redmine atualizado com sucesso. Nenhum novo e-mail foi enviado.')
                                st.rerun()
                            else:
                                st.error('Redmine continua pendente: ' + '; '.join(rr.get('erros') or ['consulte o log do Azure']))
                else:
                    confirma=st.checkbox('Revisei destinatários, Cc, assunto e mensagem. Autorizo esta execução.', key=f'home_ednna_confirm_{cid}_v32853')
                    if st.button('📨 Executar agora', type='primary', width='content', disabled=not confirma, key=f'home_ednna_exec_{cid}_v32853'):
                        try:
                            res=executar_atuacao_assistida_email(pacote)
                            if res.get('ok'):
                                email=res.get('email') or {}
                                if email.get('sent_items_confirmed'):
                                    st.success('E-mail confirmado em Itens Enviados pelo Microsoft Graph.')
                                else:
                                    st.success('Microsoft Graph aceitou o envio (HTTP 202). A EDNNA preservou a idempotência.')
                                if (res.get('redmine') or {}).get('pendente'):
                                    st.warning('A atualização do Redmine ficou na fila de reconciliação. O e-mail não será reenviado.')
                                else:
                                    st.success('Redmine atualizado. Ciclo pós-envio concluído.')
                                st.session_state.pop('home_ednna_pacote_v32842',None)
                                st.rerun()
                            else: st.warning(res.get('motivo') or 'Ação não executada.')
                        except Exception as exc: st.error(f'Falha na execução: {type(exc).__name__}: {exc}')
            else: st.info(rasc.get('motivo') or 'Executor ainda não disponível para este workflow.')
    else:
        st.caption('Nenhuma inclusão autorizada está pronta para execução assistida neste instante.')

    fups=[x for x in follow_home.get('itens',[]) if x.get('estado_followup')=='FOLLOWUP_PRONTO']
    if fups:
        with st.expander(f"📨 Continuidade · {len(fups)} follow-up(s) pronto(s)", expanded=False):
            for fup in fups[:5]:
                cidf=int(fup.get('chamado_id') or 0)
                st.write(f"**#{cidf} · follow-up {fup.get('proximo_followup')}**")
                texto_fup = st.text_area('Mensagem de acompanhamento', fup.get('texto_followup') or '', height=180, key=f'home_fup_preview_{cidf}_{fup.get("regra_id")}_v3293')
                if st.button('Enviar follow-up agora', key=f'home_fup_exec_{cidf}_{fup.get("regra_id")}_v3293'):
                    try:
                        fup_exec=dict(fup); fup_exec['texto_followup']=texto_fup
                        executar_followup(fup_exec); st.success(f'Follow-up do chamado #{cidf} enviado.'); st.rerun()
                    except Exception as exc: st.error(f'Falha no follow-up: {type(exc).__name__}: {exc}')
    if redmine_pendentes:
        st.warning(f"Há {len(redmine_pendentes)} atualização(ões) pós-envio aguardando reconciliação com o Redmine. Os e-mails não serão reenviados.")
        with st.expander(f"🔄 Reconciliação Redmine · {len(redmine_pendentes)} pendente(s)", expanded=True):
            vistos=set()
            for pend in redmine_pendentes:
                cidp=int(pend.get('chamado_id') or 0); ridp=str(pend.get('regra_id') or '')
                chave=(cidp,ridp)
                if chave in vistos: continue
                vistos.add(chave)
                st.write(f"**Chamado [#{cidp}]({redmine_link(cidp)})** · `{ridp}`")
                erro=str(pend.get('redmine_erro') or '').strip()
                if erro: st.caption(f"Último erro: {erro}")
                if st.button('🔄 Reconciliar agora', key=f'home_rm_pending_{cidp}_{ridp}_v32856'):
                    rr=reconciliar_redmine_chamado(cidp,ridp)
                    if rr.get('atualizados'):
                        st.success(f"Chamado #{cidp}: histórico/status reconciliados sem novo e-mail."); st.rerun()
                    else:
                        st.error('Redmine continua pendente: ' + '; '.join(rr.get('erros') or ['consulte o log do Azure']))



footer()
