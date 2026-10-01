from datetime import date

from ednna.security import require_admin
import streamlit as st
from ui.operational_shell import setup, footer
from ui.operational_data import regras_df
from ednna.escola_continua import sincronizar_regras_homologadas, listar_matriculas

setup('🧠 Central de Aprendizagem · EDNNA')
require_admin()

tech, _ = st.columns([1.2, 5])
with tech:
    if st.button('⚙️ Modo técnico', width='stretch'):
        st.session_state['shell_main_navigation'] = 'Motor EDNNA'
        st.switch_page('pages/Painel_EDI.py')

st.markdown('### 🎓 A EDNNA está matriculada na operação')
st.caption('Eu estudo os históricos, aprendo com a operação real e volto ao professor quando encontro algo que merece decisão humana.')
st.info('📚 **Minha rotina:** Estudo → Prova → Professor → Homologação → Trabalho → Revisão da matéria → Novo aprendizado.')

r = regras_df()
if r.empty:
    st.info('Ainda não encontrei regras de aprendizado disponíveis neste ambiente.')
else:
    estado = r['estado'].fillna('EM_APRENDIZADO')
    rev = r[estado.eq('PRONTA_PARA_REVISAO')]
    hom = r[(estado.eq('HOMOLOGADA')) | (r.get('estado_revisao', '').fillna('').eq('HOMOLOGADA'))]
    estudo = r[~r.index.isin(rev.index) & ~r.index.isin(hom.index)]
    sincronizar_regras_homologadas(r)
    matriculas = listar_matriculas()
    atrasadas = [m for m in matriculas if m['situacao_visual'] == 'REVISAO_ATRASADA']
    proximas = [m for m in matriculas if m['situacao_visual'] == 'REVISAO_PROXIMA']
    divergentes = [m for m in matriculas if m['situacao_visual'] == 'PRECISO_DO_PROFESSOR']
    saudaveis = [m for m in matriculas if m['situacao_visual'] == 'CONHECIMENTO_SAUDAVEL']

    if divergentes:
        st.warning(f'👩‍🏫 Professor, encontrei **{len(divergentes)} matéria(s) com divergência**. Não alterei nenhuma regra; deixei tudo separado para sua revisão.')
    elif atrasadas:
        st.warning(f'📚 Tenho **{len(atrasadas)} matéria(s) com revisão atrasada**. O conhecimento continua preservado, mas está na hora de estudar os casos recentes.')
    elif proximas:
        st.info(f'🗓️ Estou em dia. Tenho **{len(proximas)} matéria(s)** entrando em revisão nos próximos 7 dias.')
    elif matriculas:
        st.success(f'😊 Estou com a matéria em dia: **{len(saudaveis)} conhecimento(s)** sem divergência ou revisão vencida.')

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, '📖 Em estudo', len(estudo), 'matérias sendo aprendidas'),
        (c2, '📝 Provas para corrigir', len(rev), 'precisam do professor'),
        (c3, '🎓 Matriculadas', len(matriculas), 'conhecimento homologado'),
        (c4, '👩‍🏫 Atenção', len(divergentes) + len(atrasadas), 'divergências ou revisão vencida'),
    ]
    for c, l, n, nota in cards:
        with c:
            st.markdown(f'<div class="op-card"><div class="op-k">{l}</div><div class="op-n">{n}</div><div class="op-note">{nota}</div></div>', unsafe_allow_html=True)

    st.subheader('👩‍🏫 Professores, preciso de vocês')
    st.caption('Só trago para cá o que realmente precisa de decisão humana. A ideia é reduzir cliques e deixar clara a próxima ação.')
    if rev.empty and not divergentes:
        st.success('Nenhuma prova ou divergência aguarda sua decisão agora.')
    for _, x in rev.iterrows():
        cols = st.columns([4, 1])
        with cols[0]:
            st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br><span class="pill">Prova pronta</span> · {int(x.get("completude") or 0)}% de completude<br><small>{x.get("regra_id")}</small></div>', unsafe_allow_html=True)
        with cols[1]:
            if st.button('Corrigir prova', key='rev_' + str(x.get('regra_id')), width='stretch'):
                st.session_state['ednna_regra_foco'] = x.get('regra_id')
                st.session_state['shell_main_navigation'] = 'Motor EDNNA'
                st.switch_page('pages/Painel_EDI.py')

    with st.expander(f'📚 Na sala de estudo ({len(estudo)})'):
        for _, x in estudo.sort_values('completude', ascending=False).iterrows():
            st.write(f"**{x.get('player') or x.get('regra_id')}** — {int(x.get('completude') or 0)}% · {str(x.get('estado') or '').replace('_', ' ').title()}")

    st.subheader('🔄 Minha agenda de revisão')
    st.caption('Conhecimento homologado não vira verdade eterna. Eu guardo quando aprendi, quando revisei e quando preciso voltar à matéria.')
    if not matriculas:
        st.info('Ainda não tenho matérias homologadas matriculadas.')
    else:
        for m in matriculas:
            situacao = m['situacao_visual']
            icone = {'PRECISO_DO_PROFESSOR':'👩‍🏫', 'REVISAO_ATRASADA':'⚠️', 'REVISAO_PROXIMA':'🗓️', 'CONHECIMENTO_SAUDAVEL':'🎓'}.get(situacao, '📚')
            titulo = m.get('player') or m['regra_id']
            dias = int(m['dias_para_revisao'])
            prazo = f'atrasada há {abs(dias)} dia(s)' if dias < 0 else ('revisão hoje' if dias == 0 else f'revisão em {dias} dia(s)')
            aderencia = '—' if m.get('aderencia_atual') is None else f"{float(m['aderencia_atual']):.0f}%"
            with st.expander(f"{icone} {titulo} · {prazo}"):
                a, b, c, d = st.columns(4)
                a.metric('Matrícula', m['matriculada_em'])
                b.metric('Última revisão', m.get('ultima_revisao_em') or 'Ainda não revisada')
                c.metric('Aderência atual', aderencia)
                d.metric('Novas evidências', m.get('evidencias_desde_revisao', 0))
                st.caption(f"Regra {m['regra_id']} · ciclo {m['ciclo_dias']} dias · próxima revisão {m['proxima_revisao_em']}")
                if m.get('divergencias_abertas'):
                    st.warning(f"Professor, encontrei {m['divergencias_abertas']} divergência(s) desde a última revisão. Preservei a regra ativa e separei o assunto para reestudo.")

st.divider()
st.subheader('⛏️ Biblioteca histórica · Aberturas de Relacionamento')
st.caption('Aqui eu consulto os cadernos antigos do Redmine, reconstruo etapas e proponho novas matérias. Não me dou nota nem me aprovo sozinha.')
try:
    from ednna.minerador_aberturas import descobrir_no_redmine, listar_propostas, simular_proposta
    cmin1, _ = st.columns([1.4, 4])
    with cmin1:
        if st.button('🔎 Estudar Redmine', key='minerar_aberturas', width='stretch'):
            with st.spinner('📚 Estou estudando os históricos de Aberturas de Relacionamento...'):
                st.session_state['mineracao_aberturas_resultado'] = descobrir_no_redmine(limite_detalhes_por_player=6)
            st.success('Terminei esta rodada de estudos. Separei minhas conclusões; nenhuma matéria foi homologada automaticamente.')
    res = st.session_state.get('mineracao_aberturas_resultado') or {}
    if res:
        a, b, c, d = st.columns(4)
        a.metric('Cadernos encontrados', res.get('candidatos_rasos', 0)); b.metric('Cadernos estudados', res.get('detalhados', 0)); c.metric('Matérias / players', res.get('players', 0)); d.metric('Problemas no estudo', len(res.get('erros') or []))
    propostas = listar_propostas()
    if not propostas:
        st.info('Ainda não preparei matérias novas. O estudo histórico começa quando você aciona o botão.')
    for p in propostas:
        with st.expander(f"{p.get('player')} · {p.get('regra_id')}"):
            x1, x2, x3, x4 = st.columns(4)
            x1.metric('Evidências', p.get('evidencias', 0)); x2.metric('Compatibilidade', f"{p.get('compatibilidade', 0)}%")
            x3.metric('Posso fazer', p.get('automatizaveis_agora', 0)); x4.metric('Preciso do professor', p.get('checkpoints_humanos', 0))
            st.caption('Cadernos estudados: chamados ' + ', '.join('#' + str(i) for i in p.get('casos_ids', [])))
            for e in p.get('etapas', []):
                dono = 'EDNNA' if e.get('responsavel') == 'EDNNA' else 'Humano'
                conf = '✓' if e.get('confianca') == 'ALTA' else '◐'
                st.write(f"{conf} **{e.get('descricao')}** · {dono} · recorrência {e.get('recorrencia_pct')}%")
            regra_id = str(p.get('regra_id') or '')
            if st.button('🧪 Fazer prova nos históricos', key='btn_sim_' + regra_id):
                st.session_state['resultado_sim_' + regra_id] = simular_proposta(p)
            sim = st.session_state.get('resultado_sim_' + regra_id)
            if sim:
                compat = int(sim.get('compatibilidade_pct') or 0)
                frase = 'Fui muito bem nesta prova.' if compat >= 90 else ('O padrão está consistente, mas ainda tenho pontos para revisar.' if compat >= 70 else 'Professor, esta matéria ainda não está madura. Encontrei diferenças importantes nos históricos.')
                st.info(f"**{frase}**\n\n{sim.get('compativeis')}/{sim.get('casos')} casos atingiram ≥80% das etapas recorrentes · compatibilidade do backtest: **{compat}%**.")
                with st.expander('🔬 Ver resultado técnico da prova'):
                    st.write(sim)
            st.warning('📌 Esta ainda é uma matéria candidata. Só trabalho sozinha depois de revisão, homologação e autorização explícitas.')
except Exception as exc:
    st.error(f'Não consegui carregar o minerador de aberturas: {type(exc).__name__}: {exc}')

st.divider()
st.caption('🎓 Quanto melhor o chamado for registrado, melhor eu aprendo. Contexto, evidência e conclusão fazem parte da aula.')
footer()
