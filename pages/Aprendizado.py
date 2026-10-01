from datetime import date, timedelta

from ednna.security import require_admin
import streamlit as st
from ui.operational_shell import setup, footer
from ui.operational_data import regras_df

setup('🧠 Central de Aprendizagem · EDNNA')
require_admin()

tech, _ = st.columns([1.2, 5])
with tech:
    if st.button('⚙️ Modo técnico', width="stretch"):
        st.session_state['shell_main_navigation'] = 'Motor EDNNA'
        st.switch_page('pages/Painel_EDI.py')

st.markdown('### 🎓 A EDNNA está matriculada na operação')
st.caption('Ela estuda os históricos, aprende com a operação real, pede ajuda quando encontra exceções e revisa periodicamente o que já foi homologado.')
st.info('📚 Ciclo de aprendizagem: **Estudo → Prova → Professor → Homologação → Trabalho → Revisão da matéria → Novo aprendizado.**')

r = regras_df()
if r.empty:
    st.info('A EDNNA ainda não possui regras de aprendizado disponíveis neste ambiente.')
else:
    estado = r['estado'].fillna('EM_APRENDIZADO')
    rev = r[estado.eq('PRONTA_PARA_REVISAO')]
    hom = r[(estado.eq('HOMOLOGADA')) | (r.get('estado_revisao', '').fillna('').eq('HOMOLOGADA'))]
    estudo = r[~r.index.isin(rev.index) & ~r.index.isin(hom.index)]

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, '📖 Em estudo', len(estudo), 'matérias sendo aprendidas'),
        (c2, '📝 Provas para corrigir', len(rev), 'precisam do professor'),
        (c3, '🎓 Matérias homologadas', len(hom), 'conhecimento aprovado'),
        (c4, '🔄 Revisão contínua', len(hom), 'matérias que não podem envelhecer'),
    ]
    for c, l, n, nota in cards:
        with c:
            st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div><div class="op-note">{nota}</div></div>', unsafe_allow_html=True)

    st.subheader('👩‍🏫 Professores, preciso de vocês')
    st.caption('Aqui ficam as matérias que a EDNNA estudou, mas que ainda dependem de decisão humana antes de virarem conhecimento operacional.')
    if rev.empty:
        st.success('Nenhuma prova aguarda correção agora.')
    for _, x in rev.iterrows():
        cols = st.columns([4, 1])
        with cols[0]:
            st.markdown(
                f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br>'
                f'<span class="pill">Pronta para revisão</span> · {int(x.get("completude") or 0)}% de completude<br>'
                f'<small>{x.get("regra_id")}</small></div>', unsafe_allow_html=True)
        with cols[1]:
            if st.button('Corrigir prova', key='rev_' + str(x.get('regra_id')), width="stretch"):
                st.session_state['ednna_regra_foco'] = x.get('regra_id')
                st.session_state['shell_main_navigation'] = 'Motor EDNNA'
                st.switch_page('pages/Painel_EDI.py')

    with st.expander(f'📚 Na sala de estudo ({len(estudo)})'):
        for _, x in estudo.sort_values('completude', ascending=False).iterrows():
            st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_', ' ').title()}")

    st.subheader('🔄 Revisão da matéria')
    st.caption('Conhecimento homologado não é verdade eterna. A operação muda; por isso a EDNNA mantém as matérias em revisão contínua.')
    hoje = date.today()
    proxima = hoje + timedelta(days=30)
    a, b, c = st.columns(3)
    a.metric('Matérias matriculadas', len(hom))
    b.metric('Ciclo padrão de revisão', '30 dias')
    c.metric('Próxima revisão de referência', proxima.strftime('%d/%m/%Y'))
    st.caption('Nesta etapa a agenda é apresentada como política da Central. A automação de reestudo periódico será persistida no motor em evolução própria, sem alterar silenciosamente regras homologadas.')

    if not hom.empty:
        with st.expander('🎓 Ver matérias homologadas'):
            for _, x in hom.sort_values('player', na_position='last').iterrows():
                st.write(f"🎓 **{x.get('player') or x.get('regra_id')}** · {x.get('regra_id')} · conhecimento em produção, sujeito a revisão")

st.divider()
st.subheader('⛏️ Biblioteca histórica · Aberturas de Relacionamento')
st.caption('A EDNNA consulta os cadernos antigos do Redmine, reconstrói etapas e propõe novas matérias. Nenhuma regra é homologada ou autorizada automaticamente.')
try:
    from ednna.minerador_aberturas import descobrir_no_redmine, listar_propostas, simular_proposta
    cmin1, cmin2 = st.columns([1.4, 4])
    with cmin1:
        if st.button('🔎 Estudar Redmine', key='minerar_aberturas', width='stretch'):
            with st.spinner('📚 Estou estudando os históricos de Aberturas de Relacionamento...'):
                st.session_state['mineracao_aberturas_resultado'] = descobrir_no_redmine(limite_detalhes_por_player=6)
            st.success('📚 Estudo concluído. Separei minhas conclusões para o professor; nenhuma matéria foi homologada automaticamente.')
    res = st.session_state.get('mineracao_aberturas_resultado') or {}
    if res:
        a, b, c, d = st.columns(4)
        a.metric('Cadernos encontrados', res.get('candidatos_rasos', 0))
        b.metric('Cadernos estudados', res.get('detalhados', 0))
        c.metric('Matérias / players', res.get('players', 0))
        d.metric('Problemas no estudo', len(res.get('erros') or []))

    propostas = listar_propostas()
    if not propostas:
        st.info('Ainda não há matérias propostas. O estudo histórico só começa quando um administrador aciona o botão.')
    for p in propostas:
        titulo = f"{p.get('player')} · {p.get('regra_id')}"
        with st.expander(titulo):
            x1, x2, x3, x4 = st.columns(4)
            x1.metric('Evidências', p.get('evidencias', 0))
            x2.metric('Compatibilidade', f"{p.get('compatibilidade', 0)}%")
            x3.metric('Posso fazer', p.get('automatizaveis_agora', 0))
            x4.metric('Preciso do professor', p.get('checkpoints_humanos', 0))
            st.caption('Cadernos estudados: chamados ' + ', '.join('#' + str(i) for i in p.get('casos_ids', [])))
            for e in p.get('etapas', []):
                dono = 'EDNNA' if e.get('responsavel') == 'EDNNA' else 'Humano'
                conf = '✓' if e.get('confianca') == 'ALTA' else '◐'
                st.write(f"{conf} **{e.get('descricao')}** · {dono} · recorrência {e.get('recorrencia_pct')}%")
            regra_id = str(p.get('regra_id') or '')
            button_key = 'btn_sim_' + regra_id
            result_key = 'resultado_sim_' + regra_id
            if st.button('🧪 Fazer prova nos históricos', key=button_key):
                st.session_state[result_key] = simular_proposta(p)
            sim = st.session_state.get(result_key)
            if sim:
                st.info(f"Resultado da prova: {sim.get('compativeis')}/{sim.get('casos')} casos com ≥80% das etapas recorrentes · compatibilidade {sim.get('compatibilidade_pct')}%.")
            st.warning('📌 Matéria candidata. Eu não executarei esta abertura até meu professor revisar, homologar e autorizar explicitamente.')
except Exception as exc:
    st.error(f'Não foi possível carregar o minerador de aberturas: {type(exc).__name__}: {exc}')

st.divider()
st.caption('🎓 Quanto melhor o chamado for registrado, melhor será o material de estudo da EDNNA. Evidência, contexto e conclusão fazem parte da aula.')
footer()
