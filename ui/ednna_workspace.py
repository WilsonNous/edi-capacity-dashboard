from __future__ import annotations

from pathlib import Path
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from ednna.motor_acoes import (
    avaliar_acao,
    gerar_rascunho,
)

from ednna.acompanhamento_acoes import (
    obter_acompanhamento,
    adquirir_envio,
    confirmar_envio_real,
    registrar_falha_envio,
    marcar_redmine_atualizado,
    marcar_status_redmine,
    registrar_falha_redmine,
    registrar_resposta,
    registrar_responsabilidade_ednna,
    rotulo_estado,
)

from ednna.email_sender import (
    enviar_email_graph,
)


from ednna.executor_automatico import (
    executar_acoes_automaticas,
)


from ednna.redmine_writer import (
    adicionar_nota_chamado,
    alterar_status_chamado,
    atribuir_chamado_ednna,
    montar_nota_email_enviado,
    registrar_email_e_status_chamado,
)

from ednna.contexto_relacionamentos import (
    analisar_contexto_cancelamento,
    analisar_contexto_operacional,
)
from ednna.planejador_cancelamentos import (
    preparar_plano_cancelamento,
)
from ednna.planejador_inclusoes import (
    preparar_aprendizado_inclusao,
    descobrir_candidatos_inclusao,
)
from ednna.orquestrador_cancelamentos import (
    marcar_etapa, resumo_orquestracao, rotulo_etapa,
)


def _carregar_css() -> None:
    css_path = (
        Path(__file__).resolve().parent.parent
        / "styles"
        / "ednna_workspace.css"
    )

    if not css_path.exists():
        return

    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def _rotulo_intencao(valor: str) -> str:
    mapa = {
        "NAO_CLASSIFICADO": "Não classificado",
        "FALTA_ARQUIVO": "Falta de arquivo",
        "INCLUSAO_ESTABELECIMENTO": "Inclusão de estabelecimento",
        "RELACIONAMENTO_CREDENCIAMENTO": "Relacionamento / credenciamento",
        "DUVIDA_ORIENTACAO": "Dúvida / orientação",
        "REPROCESSAMENTO": "Reprocessamento",
    }

    texto = str(valor or "").strip()

    if texto in mapa:
        return mapa[texto]

    if not texto:
        return "Sem classificação"

    return (
        texto
        .replace("_", " ")
        .strip()
        .title()
    )


def render_ednna_workspace(
    *,
    ednna_analisados: pd.DataFrame,
    snapshot_global: pd.DataFrame | None = None,
    resumo_oportunidades_fn,
    calcular_prontidao_automacao_fn,
    ranking_clientes_fn,
    preparar_tabela_com_link_redmine_fn,
    ajustar_grafico_fn,
    facebook_colors: list[str],
    redmine_web_url: str,
    catalogo_ednna: dict,
    catalogo_operacional_ednna: dict,
) -> None:
    """
    Workspace visual da EDNNA — v3.28.3 Carteira EDNNA baseada no snapshot global.

    Esta camada não consulta o Redmine nem grava SQLite.
    """

    _carregar_css()


    # ====================================================
    # v3.16 — WORKSPACE EDNNA
    # ====================================================
    # Organização visual da inteligência operacional.
    # Não altera classificação, SQLite, Redmine ou execução.
    # ====================================================

    st.markdown(
        """
        <div class="ednna-hero">
            <div class="ednna-hero-eyebrow">EDNNA · INTELIGÊNCIA OPERACIONAL</div>
            <div class="ednna-hero-title">Central Operacional EDI</div>
            <div class="ednna-hero-sub">O que precisa de atenção, o que a EDNNA já entendeu e o que está pronto para avançar.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    base_demandas = ednna_analisados[
        ednna_analisados["EDNNA - Situação"] == "AGUARDANDO_PRIMEIRO_COMBATE"
    ].copy()

    resumo_auto = executar_acoes_automaticas(
        base_demandas
    )

    if resumo_auto.get("habilitado"):
        enviados_auto = int(
            resumo_auto.get(
                "enviados",
                0,
            )
            or 0
        )

        redmine_pendente_auto = int(
            resumo_auto.get(
                "redmine_pendente",
                0,
            )
            or 0
        )

        erros_envio_auto = int(
            resumo_auto.get(
                "erros_envio",
                0,
            )
            or 0
        )

        if enviados_auto:
            st.success(
                f"🤖 EDNNA executou automaticamente {enviados_auto} "
                "ação(ões) homologada(s) nesta atualização."
            )

        if redmine_pendente_auto:
            st.warning(
                f"⚠️ {redmine_pendente_auto} e-mail(s) foram enviados, "
                "mas ainda possuem atualização pendente no Redmine."
            )

        if erros_envio_auto:
            st.error(
                f"🔴 {erros_envio_auto} ação(ões) automática(s) falharam "
                "na etapa de envio."
            )

    if base_demandas.empty:
        st.info("Não há chamados analisados aguardando primeiro combate.")

    else:
        resumo_op = resumo_oportunidades_fn(base_demandas)
        prontidao_df = calcular_prontidao_automacao_fn(base_demandas)

        regras_homologadas_total = int(
            (
                base_demandas.get(
                    "EDNNA - Regra operacional",
                    pd.Series("", index=base_demandas.index),
                )
                .fillna("")
                .astype(str)
                .str.strip()
                != ""
            ).sum()
        )

        prontos_rascunho_total = int(
            (
                base_demandas.get(
                    "EDNNA - Apto para rascunho",
                    pd.Series("", index=base_demandas.index),
                )
                .fillna("")
                .astype(str)
                .str.upper()
                == "SIM"
            ).sum()
        )

        completos_total = int(
            (
                base_demandas.get(
                    "EDNNA - Dados operacionais completos",
                    pd.Series("", index=base_demandas.index),
                )
                .fillna("")
                .astype(str)
                .str.upper()
                == "SIM"
            ).sum()
        )

        # v3.26 — indicadores executivos: entendimento e atenção, não detalhes técnicos
        intencao_serie = base_demandas.get(
            "EDNNA - Intenção",
            pd.Series("NAO_CLASSIFICADO", index=base_demandas.index),
        ).fillna("NAO_CLASSIFICADO").astype(str)
        reconhecidos_executivo = int((intencao_serie != "NAO_CLASSIFICADO").sum())
        cancelamentos_executivo = int((intencao_serie == "CANCELAMENTO_TRAFEGO").sum())
        conflitos_executivo = int(
            (base_demandas.get(
                "EDNNA - Conflito de classificação",
                pd.Series("", index=base_demandas.index),
            ).fillna("").astype(str).str.upper() == "SIM").sum()
        )

        # v3.26 — navegação curta, orientada à tarefa
        ws_resumo, ws_acoes, ws_inteligencia, ws_regras = st.tabs(
            [
                "Visão geral",
                "Operação",
                "Inteligência",
                "Regras",
            ]
        )

        # ================================================
        # RESUMO
        # ================================================
        with ws_resumo:

            st.markdown(
                '<div class="ednna-section-kicker">VISÃO EXECUTIVA</div>',
                unsafe_allow_html=True,
            )
            r1, r2, r3, r4 = st.columns(4)

            cards_exec = [
                (r1, "Primeiro combate", len(base_demandas), "Demandas que aguardam atuação", "blue"),
                (r2, "Padrões reconhecidos", reconhecidos_executivo, "Demandas já compreendidas pela EDNNA", "green"),
                (r3, "Cancelamentos", cancelamentos_executivo, "Demandas de cancelamento identificadas", "blue"),
                (r4, "Requer atenção", conflitos_executivo, "Conflitos de classificação para revisão", "yellow"),
            ]
            for coluna, rotulo, valor, nota, cor in cards_exec:
                with coluna:
                    st.markdown(
                        f"""
                        <div class="ednna-card ednna-card-{cor}">
                            <div class="ednna-card-label">{rotulo}</div>
                            <div class="ednna-card-value">{valor}</div>
                            <div class="ednna-card-note">{nota}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.markdown(
                '<div class="ednna-section-title">Panorama operacional</div>',
                unsafe_allow_html=True,
            )

            intencoes_resumo = (
                base_demandas["EDNNA - Intenção"]
                .fillna("NAO_CLASSIFICADO")
                .astype(str)
                .value_counts()
                .rename_axis("Intenção técnica")
                .reset_index(name="Chamados")
            )

            intencoes_resumo["Intenção"] = (
                intencoes_resumo["Intenção técnica"]
                .map(_rotulo_intencao)
            )

            # ==================================================
            # v3.17.1 — LEITURA RÁPIDA DINÂMICA
            # ==================================================

            total_atual = len(base_demandas)

            sem_classificacao_atual = int(
                (
                    base_demandas["EDNNA - Intenção"]
                    .fillna("NAO_CLASSIFICADO")
                    .astype(str)
                    == "NAO_CLASSIFICADO"
                ).sum()
            )

            reconhecidos_atual = max(
                total_atual - sem_classificacao_atual,
                0,
            )

            conflitos_atual = int(
                (
                    base_demandas.get(
                        "EDNNA - Conflito de classificação",
                        pd.Series("", index=base_demandas.index),
                    )
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    == "SIM"
                ).sum()
            )

            alta_prontidao_atual = int(
                resumo_op.get(
                    "alta_prontidao",
                    0,
                )
                or 0
            )

            c_res1, c_res2 = st.columns([1.35, 1])

            with c_res1:
                fig_resumo = px.bar(
                    intencoes_resumo.sort_values("Chamados"),
                    x="Chamados",
                    y="Intenção",
                    orientation="h",
                    text_auto=True,
                    color_discrete_sequence=facebook_colors,
                )
                fig_resumo.update_layout(
                    height=max(330, 42 * len(intencoes_resumo)),
                    xaxis_title="Chamados",
                    yaxis_title="",
                )
                ajustar_grafico_fn(fig_resumo)
                st.plotly_chart(fig_resumo, width="stretch")

            with c_res2:
                st.markdown("**Leitura rápida**")

                pct_reconhecidos = (
                    reconhecidos_atual
                    / total_atual
                    * 100
                    if total_atual
                    else 0.0
                )

                pct_sem_classificacao = (
                    sem_classificacao_atual
                    / total_atual
                    * 100
                    if total_atual
                    else 0.0
                )

                reconhecidas = (
                    intencoes_resumo[
                        intencoes_resumo["Intenção técnica"]
                        != "NAO_CLASSIFICADO"
                    ]
                    .sort_values(
                        "Chamados",
                        ascending=False,
                    )
                    .reset_index(
                        drop=True
                    )
                )

                principal_nome = ""
                principal_qtd = 0
                segunda_nome = ""
                segunda_qtd = 0

                if not reconhecidas.empty:
                    principal_nome = str(
                        reconhecidas.iloc[0]["Intenção"]
                    )
                    principal_qtd = int(
                        reconhecidas.iloc[0]["Chamados"]
                    )

                if len(reconhecidas) > 1:
                    segunda_nome = str(
                        reconhecidas.iloc[1]["Intenção"]
                    )
                    segunda_qtd = int(
                        reconhecidas.iloc[1]["Chamados"]
                    )

                st.write(
                    f"**{pct_reconhecidos:.1f}%** dos chamados já possuem padrão reconhecido "
                    f"(**{reconhecidos_atual} de {total_atual}**)."
                )

                st.write(
                    f"**{pct_sem_classificacao:.1f}%** ainda precisam evoluir na classificação "
                    f"(**{sem_classificacao_atual} chamado(s)**)."
                )

                if principal_nome:
                    st.write(
                        f"**{principal_nome}** é a principal demanda reconhecida, "
                        f"com **{principal_qtd} chamado(s)**."
                    )

                if segunda_nome:
                    st.write(
                        f"**{segunda_nome}** aparece em seguida, "
                        f"com **{segunda_qtd} chamado(s)**."
                    )

                if conflitos_atual > 0:
                    st.warning(
                        f"⚠️ Existem **{conflitos_atual} conflito(s) de classificação** "
                        "que merecem revisão operacional."
                    )
                else:
                    st.success(
                        "✅ Nenhum conflito de classificação identificado no conjunto atual."
                    )

                if alta_prontidao_atual > 0:
                    st.info(
                        f"🧠 **{alta_prontidao_atual} grupo(s)** apresentam alta prontidão "
                        "para estudo de automação."
                    )
                else:
                    st.caption(
                        "Nenhum grupo apresenta alta prontidão para estudo de automação neste momento."
                    )

                st.caption(
                    "Leitura executiva calculada automaticamente sobre o conjunto atual analisado pela EDNNA."
                )


            # v3.28.1 — carteira operacional formalmente atribuída à EDNNA no Redmine.
            st.markdown("#### Chamados com a EDNNA")
            st.caption(
                "Visão dos chamados atualmente atribuídos à automação EDI. "
                "A lista usa o responsável presente no snapshot do Redmine."
            )
            # v3.28.3 — a carteira precisa olhar o snapshot GLOBAL de chamados
            # abertos do Redmine, e não somente o subconjunto Estado == Aberto
            # usado pela inteligência de primeiro combate. Chamados assumidos pela
            # EDNNA normalmente já estão em Em andamento / Aguardando Retorno.
            base_carteira = (
                snapshot_global.copy()
                if isinstance(snapshot_global, pd.DataFrame) and not snapshot_global.empty
                else ednna_analisados.copy()
            )

            ednna_user_id = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
            mascara_ednna = pd.Series(False, index=base_carteira.index)

            # Critério principal: ID imutável do usuário EDNNA no Redmine.
            if "_Atribuído a ID" in base_carteira.columns:
                ids_resp = pd.to_numeric(base_carteira["_Atribuído a ID"], errors="coerce")
                mascara_ednna = mascara_ednna | ids_resp.eq(ednna_user_id)

            # Compatibilidade com snapshots anteriores à v3.28.3, que ainda não
            # possuem o ID do responsável persistido na linha transformada.
            if "Atribuído a" in base_carteira.columns:
                nomes_resp = base_carteira["Atribuído a"].fillna("").astype(str).str.casefold()
                mascara_ednna = mascara_ednna | nomes_resp.str.contains("ednna", regex=False)

            carteira_ednna = base_carteira[mascara_ednna].copy()

            ce1, ce2 = st.columns([1, 3])
            ce1.metric("Sob responsabilidade EDNNA", len(carteira_ednna))
            with ce2:
                st.caption(
                    "Quando a EDNNA assume uma ação homologada, o chamado passa para esta carteira "
                    "até que o próximo passo exija atuação humana ou encerramento do fluxo."
                )

            if carteira_ednna.empty:
                st.info("Nenhum chamado do snapshot atual está atribuído à EDNNA.")
            else:
                colunas_carteira = [
                    c for c in [
                        "#", "Clientes", "Origem", "Atribuído a", "Estado", "Prioridade", "Tipo", "Assunto",
                        "EDNNA - Regra operacional", "EDNNA - Situação",
                    ] if c in carteira_ednna.columns
                ]
                tabela_carteira, config_carteira = preparar_tabela_com_link_redmine_fn(
                    carteira_ednna[colunas_carteira]
                )
                st.dataframe(
                    tabela_carteira,
                    width="stretch",
                    hide_index=True,
                    column_config=config_carteira,
                )

        # ================================================
        # AÇÕES
        # ================================================
        with ws_acoes:

            st.markdown(
                '<div class="ednna-section-title">Operação assistida</div>',
                unsafe_allow_html=True,
            )
            regras_auto = [
                regra
                for regra in (
                    catalogo_operacional_ednna.get(
                        "regras",
                        [],
                    )
                    if isinstance(
                        catalogo_operacional_ednna,
                        dict,
                    )
                    else []
                )
                if bool(
                    regra.get(
                        "executavel",
                        False,
                    )
                )
                and bool(
                    regra.get(
                        "auto_executar",
                        False,
                    )
                )
            ]

            if regras_auto:
                st.caption(
                    "A EDNNA opera em modo híbrido: procedimentos homologados podem ser "
                    "executados automaticamente; demais chamados continuam em análise "
                    "ou modo assistido."
                )
            else:
                st.caption(
                    "Nenhuma regra está habilitada para execução automática neste momento."
                )

            todos_procedimento = (
                ednna_analisados[
                    ednna_analisados.get(
                        "EDNNA - Regra operacional",
                        pd.Series(
                            "",
                            index=ednna_analisados.index,
                        ),
                    )
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    != ""
                ]
                .copy()
            )

            candidatos_acao = (
                base_demandas[
                    base_demandas.get(
                        "EDNNA - Regra operacional",
                        pd.Series(
                            "",
                            index=base_demandas.index,
                        ),
                    )
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    != ""
                ]
                .copy()
            )

            em_acompanhamento = 0
            prontos_para_executar = 0
            atencao_pendente = 0

            estados_acompanhamento = {
                "ENVIANDO",
                "AGUARDANDO_RESPOSTA",
                "PRAZO_VENCIDO",
                "RESPOSTA_RECEBIDA",
            }

            # v3.21.3 — a lista "Chamado para avaliar" contém
            # somente chamados ainda pendentes de execução.
            if not candidatos_acao.empty:
                indices_pendentes_acao = []

                for idx_cand, row_cand in candidatos_acao.iterrows():

                    try:
                        chamado_cand = int(
                            float(
                                row_cand.get(
                                    "#",
                                    0,
                                )
                            )
                        )

                        regra_cand = str(
                            row_cand.get(
                                "EDNNA - Regra operacional",
                                "",
                            )
                            or ""
                        ).strip()

                        if not regra_cand:
                            continue

                        acomp_cand = obter_acompanhamento(
                            chamado_cand,
                            regra_cand,
                        )

                        estado_cand = str(
                            acomp_cand.get(
                                "estado",
                                "RASCUNHO",
                            )
                            or "RASCUNHO"
                        ).strip()

                        if estado_cand not in estados_acompanhamento:
                            indices_pendentes_acao.append(
                                idx_cand
                            )

                    except Exception:
                        # Se não conseguirmos consultar o acompanhamento,
                        # mantemos o chamado visível para revisão humana.
                        indices_pendentes_acao.append(
                            idx_cand
                        )

                candidatos_acao = candidatos_acao.loc[
                    indices_pendentes_acao
                ].copy()

            for _, row_proc in todos_procedimento.iterrows():

                try:
                    chamado_proc = int(
                        float(
                            row_proc.get(
                                "#",
                                0,
                            )
                        )
                    )

                    regra_proc = str(
                        row_proc.get(
                            "EDNNA - Regra operacional",
                            "",
                        )
                        or ""
                    ).strip()

                    if not regra_proc:
                        continue

                    acomp_proc = obter_acompanhamento(
                        chamado_proc,
                        regra_proc,
                    )

                    estado_proc = str(
                        acomp_proc.get(
                            "estado",
                            "RASCUNHO",
                        )
                        or "RASCUNHO"
                    ).strip()

                    if estado_proc in estados_acompanhamento:
                        em_acompanhamento += 1

                except Exception:
                    pass

            for _, row_pendente in candidatos_acao.iterrows():

                try:
                    chamado_pendente = int(
                        float(
                            row_pendente.get(
                                "#",
                                0,
                            )
                        )
                    )

                    regra_pendente = str(
                        row_pendente.get(
                            "EDNNA - Regra operacional",
                            "",
                        )
                        or ""
                    ).strip()

                    acomp_pendente = obter_acompanhamento(
                        chamado_pendente,
                        regra_pendente,
                    )

                    estado_pendente = str(
                        acomp_pendente.get(
                            "estado",
                            "RASCUNHO",
                        )
                        or "RASCUNHO"
                    ).strip()

                except Exception:
                    estado_pendente = "RASCUNHO"

                apto_pendente = (
                    str(
                        row_pendente.get(
                            "EDNNA - Apto para rascunho",
                            "",
                        )
                        or ""
                    )
                    .strip()
                    .upper()
                    == "SIM"
                )

                if estado_pendente in estados_acompanhamento:
                    continue

                if apto_pendente:
                    prontos_para_executar += 1
                else:
                    atencao_pendente += 1

            if todos_procedimento.empty:
                st.info(
                    "Nenhum chamado possui procedimento operacional conhecido."
                )
            else:
                a1, a2, a3, a4 = st.columns(
                    4
                )

                a1.metric(
                    "Com procedimento",
                    len(
                        todos_procedimento
                    ),
                    help=(
                        "Total de chamados do conjunto atual que possuem "
                        "alguma regra operacional reconhecida."
                    ),
                )

                a2.metric(
                    "🟢 Prontos para executar",
                    prontos_para_executar,
                    help=(
                        "Chamados ainda pendentes que possuem dados suficientes "
                        "e não foram enviados."
                    ),
                )

                a3.metric(
                    "🟡 Em acompanhamento",
                    em_acompanhamento,
                    help=(
                        "Chamados já enviados ou em monitoramento de resposta."
                    ),
                )

                a4.metric(
                    "⚠️ Atenção",
                    atencao_pendente,
                    help=(
                        "Chamados com procedimento conhecido, mas ainda sem "
                        "condições suficientes para execução."
                    ),
                )

                st.caption(
                    "Importante: quando um chamado é automatizado ele deixa de ser "
                    "contado como 'pronto para executar' e passa para 'em acompanhamento'. "
                    "Por isso o número de pendentes pode cair sem que uma automação tenha sido perdida."
                )

                if candidatos_acao.empty:
                    st.info(
                        "Nenhum chamado pendente de execução neste momento. "
                        "Os chamados já automatizados permanecem em acompanhamento."
                    )

                else:
                    opcoes_acao = []

                    for idx_acao, row_acao in candidatos_acao.iterrows():
                        chamado_label = str(row_acao.get("#", ""))
                        if chamado_label.endswith(".0"):
                            chamado_label = chamado_label[:-2]

                        cliente_label = str(row_acao.get("Clientes", "") or "Sem cliente")
                        origem_label = str(
                            row_acao.get("EDNNA - Origem operacional", "")
                            or row_acao.get("Origem", "")
                            or "Sem origem"
                        )

                        pronto_label = (
                            "🟢"
                            if str(row_acao.get("EDNNA - Apto para rascunho", "")).upper() == "SIM"
                            else "🟡"
                        )

                        opcoes_acao.append(
                            (
                                idx_acao,
                                f"{pronto_label} #{chamado_label} • {cliente_label} • {origem_label}",
                            )
                        )

                    indice_acao = st.selectbox(
                        "Chamado para avaliar",
                        options=[item[0] for item in opcoes_acao],
                        format_func=lambda valor: next(
                            (rotulo for idx, rotulo in opcoes_acao if idx == valor),
                            str(valor),
                        ),
                        key="ednna_acao_chamado_v316",
                    )

                    if indice_acao is None:
                        st.warning(
                            "A seleção anterior não é mais válida. "
                            "Atualize a página para carregar os chamados pendentes."
                        )
                        st.stop()

                    linha_acao = candidatos_acao.loc[
                        indice_acao
                    ]
                    avaliacao_acao = avaliar_acao(linha_acao)

                    with st.container(border=True):
                        chamado_card = str(linha_acao.get("#", ""))
                        if chamado_card.endswith(".0"):
                            chamado_card = chamado_card[:-2]

                        cliente_card = str(
                            linha_acao.get("Clientes", "")
                            or "Sem cliente"
                        )

                        origem_card = str(
                            linha_acao.get("EDNNA - Origem operacional", "")
                            or linha_acao.get("Origem", "")
                            or "Sem origem"
                        )

                        subtipo_raw = str(
                            linha_acao.get("EDNNA - Subtipo", "")
                            or ""
                        )

                        subtipo_visual = {
                            "ARQUIVO_NAO_RECEBIDO": "Arquivo não recebido",
                            "ARQUIVO_CORROMPIDO": "Arquivo corrompido",
                            "FALTA_REGISTRO": "Falta de registro",
                        }.get(
                            subtipo_raw,
                            subtipo_raw.replace("_", " ").title()
                            if subtipo_raw
                            else "Sem subtipo",
                        )

                        status_html = (
                            '<span class="ednna-status-ready">🟢 Pronto</span>'
                            if avaliacao_acao.get("apto_rascunho")
                            else '<span class="ednna-status-warn">🟡 Atenção</span>'
                        )

                        st.markdown(
                            f"""
                            <div class="ednna-action-head">
                                <div>
                                    <div class="ednna-action-title">#{chamado_card} • {cliente_card}</div>
                                    <div class="ednna-action-meta">{origem_card} • {subtipo_visual}</div>
                                </div>
                                <div>{status_html}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        convenio_val = str(
                            linha_acao.get("EDNNA - Convênio", "")
                            or "—"
                        )
                        referencia_val = str(
                            linha_acao.get("EDNNA - Referência operacional", "")
                            or "—"
                        )
                        tipo_val = str(
                            linha_acao.get("EDNNA - Tipos arquivo", "")
                            or "—"
                        )
                        nsa_val = str(
                            linha_acao.get("EDNNA - NSA referência", "")
                            or "—"
                        )

                        st.markdown(
                            f"""
                            <div class="ednna-data-grid">
                                <div class="ednna-data-item">
                                    <div class="ednna-data-label">Convênio</div>
                                    <div class="ednna-data-value">{convenio_val}</div>
                                </div>
                                <div class="ednna-data-item">
                                    <div class="ednna-data-label">Referência</div>
                                    <div class="ednna-data-value">{referencia_val}</div>
                                </div>
                                <div class="ednna-data-item">
                                    <div class="ednna-data-label">Tipo</div>
                                    <div class="ednna-data-value">{tipo_val}</div>
                                </div>
                                <div class="ednna-data-item">
                                    <div class="ednna-data-label">NSA</div>
                                    <div class="ednna-data-value">{nsa_val}</div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        procedimento_nome = (
                            avaliacao_acao.get("regra_nome")
                            or "Sem procedimento homologado."
                        )
                        procedimento_nota = (
                            avaliacao_acao.get("motivo", "")
                            or ""
                        )

                        st.markdown(
                            f"""
                            <div class="ednna-procedure-box">
                                <div class="ednna-procedure-title">Procedimento</div>
                                <div class="ednna-procedure-name">{procedimento_nome}</div>
                                <div class="ednna-procedure-note">{procedimento_nota}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        acao_left, acao_right = st.columns(
                            [1.1, 3.9]
                        )

                        with acao_left:
                            st.link_button(
                                "Abrir no Redmine",
                                f"{redmine_web_url}/issues/{chamado_card}",
                                width="stretch",
                            )

                        with acao_right:
                            if avaliacao_acao.get("apto_rascunho"):
                                rascunho = gerar_rascunho(linha_acao)

                                with st.expander(
                                    "✉️ Visualizar rascunho",
                                    expanded=False,
                                ):
                                    st.markdown("**Para**")
                                    st.caption(
                                        "; ".join(
                                            rascunho.get(
                                                "destinatarios",
                                                [],
                                            )
                                        )
                                        or "Sem destinatários definidos."
                                    )

                                    if rascunho.get("cc"):
                                        st.markdown("**Cc**")
                                        st.caption(
                                            "; ".join(
                                                rascunho.get(
                                                    "cc",
                                                    [],
                                                )
                                            )
                                        )

                                    st.markdown("**Assunto**")
                                    st.code(
                                        rascunho.get("assunto", ""),
                                        language=None,
                                    )

                                    st.markdown("**Mensagem**")
                                    st.text_area(
                                        "Rascunho do e-mail",
                                        value=rascunho.get("corpo", ""),
                                        height=300,
                                        key=f"rascunho_v3161_{chamado_card}",
                                        label_visibility="collapsed",
                                    )

                                    st.caption(
                                        "Modo assistido: o rascunho não é enviado "
                                        "e nenhuma alteração é feita no Redmine."
                                    )


                                try:
                                    chamado_int = int(float(chamado_card))
                                    regra_id_acao = str(
                                        avaliacao_acao.get("regra_id", "")
                                        or ""
                                    )

                                    if regra_id_acao:
                                        acompanhamento = obter_acompanhamento(
                                            chamado_int,
                                            regra_id_acao,
                                        )

                                        st.markdown("**Acompanhamento**")

                                        estado_acomp = acompanhamento.get(
                                            "estado",
                                            "RASCUNHO",
                                        )

                                        st.write(
                                            rotulo_estado(
                                                estado_acomp
                                            )
                                        )

                                        enviado_em = (
                                            acompanhamento.get("enviado_em", "")
                                            or ""
                                        )
                                        prazo_em = (
                                            acompanhamento.get("prazo_resposta_em", "")
                                            or ""
                                        )
                                        resposta_em = (
                                            acompanhamento.get("resposta_recebida_em", "")
                                            or ""
                                        )

                                        if enviado_em:
                                            st.caption(
                                                "Envio registrado em: "
                                                + enviado_em
                                            )

                                        if prazo_em:
                                            st.caption(
                                                "Prazo de resposta: "
                                                + prazo_em
                                            )

                                        if resposta_em:
                                            st.caption(
                                                "Resposta registrada em: "
                                                + resposta_em
                                            )

                                        redmine_ok_em = (
                                            acompanhamento.get(
                                                "redmine_atualizado_em",
                                                "",
                                            )
                                            or ""
                                        )

                                        redmine_erro = (
                                            acompanhamento.get(
                                                "redmine_erro",
                                                "",
                                            )
                                            or ""
                                        )

                                        if redmine_ok_em:
                                            st.success(
                                                "✅ E-mail registrado no chamado do Redmine."
                                            )

                                            estado_snapshot = str(
                                                linha_acao.get(
                                                    "Estado",
                                                    "",
                                                )
                                                or ""
                                            ).strip()

                                            estado_confirmado_ednna = str(
                                                acompanhamento.get(
                                                    "redmine_status_nome",
                                                    "",
                                                )
                                                or ""
                                            ).strip()

                                            estado_redmine_atual = (
                                                estado_confirmado_ednna
                                                or estado_snapshot
                                            )

                                            if estado_confirmado_ednna:
                                                st.caption(
                                                    "Status confirmado pela EDNNA no Redmine: "
                                                    f"{estado_confirmado_ednna}."
                                                )

                                            if (
                                                estado_acomp
                                                in {
                                                    "AGUARDANDO_RESPOSTA",
                                                    "PRAZO_VENCIDO",
                                                }
                                                and estado_redmine_atual.casefold()
                                                == "aberto"
                                            ):
                                                st.warning(
                                                    "⚠️ O chamado ainda está como Aberto "
                                                    "no conjunto atual do painel."
                                                )

                                                if st.button(
                                                    "🔄 Alterar para Aguardando Retorno Cliente",
                                                    key=(
                                                        f"status_cliente_"
                                                        f"{chamado_card}_"
                                                        f"{regra_id_acao}"
                                                    ),
                                                ):
                                                    try:
                                                        alterar_status_chamado(
                                                            chamado_id=chamado_int,
                                                            status_nome=(
                                                                "Aguardando Retorno Cliente"
                                                            ),
                                                            data_inicio=enviado_em,
                                                            data_fim=prazo_em,
                                                        )

                                                        marcar_status_redmine(
                                                            chamado_int,
                                                            regra_id_acao,
                                                            "Aguardando Retorno Cliente",
                                                        )

                                                        st.success(
                                                            "Status do chamado atualizado "
                                                            "para Aguardando Retorno Cliente."
                                                        )
                                                        st.rerun()

                                                    except Exception as exc_status:
                                                        st.error(
                                                            "Não foi possível alterar o "
                                                            f"status no Redmine: {exc_status}"
                                                        )

                                        elif enviado_em:
                                            if redmine_erro:
                                                st.warning(
                                                    "⚠️ E-mail enviado, mas a atualização "
                                                    "do Redmine está pendente."
                                                )

                                                with st.expander(
                                                    "Detalhe da pendência Redmine",
                                                    expanded=False,
                                                ):
                                                    st.code(
                                                        redmine_erro,
                                                        language=None,
                                                    )

                                                rotulo_redmine = (
                                                    "🔄 Repetir atualização no Redmine"
                                                )

                                            else:
                                                st.info(
                                                    "📌 Este envio ocorreu antes da integração "
                                                    "automática com o Redmine. O e-mail não será "
                                                    "reenviado."
                                                )

                                                rotulo_redmine = (
                                                    "📝 Registrar este envio no Redmine"
                                                )

                                            if st.button(
                                                rotulo_redmine,
                                                key=(
                                                    f"registrar_redmine_"
                                                    f"{chamado_card}_"
                                                    f"{regra_id_acao}"
                                                ),
                                            ):
                                                try:
                                                    nota_retry = (
                                                        montar_nota_email_enviado(
                                                            remetente=rascunho.get(
                                                                "remetente",
                                                                "edi@netunna.com.br",
                                                            ),
                                                            para=rascunho.get(
                                                                "destinatarios",
                                                                [],
                                                            ),
                                                            cc=rascunho.get(
                                                                "cc",
                                                                [],
                                                            ),
                                                            assunto=rascunho.get(
                                                                "assunto",
                                                                "",
                                                            ),
                                                            corpo=rascunho.get(
                                                                "corpo",
                                                                "",
                                                            ),
                                                            enviado_em=enviado_em,
                                                            prazo_resposta_em=prazo_em,
                                                        )
                                                    )

                                                    registrar_email_e_status_chamado(
                                                        chamado_id=chamado_int,
                                                        nota=nota_retry,
                                                        status_nome=(
                                                            "Aguardando Retorno Cliente"
                                                        ),
                                                        data_inicio=enviado_em,
                                                        data_fim=prazo_em,
                                                    )

                                                    marcar_redmine_atualizado(
                                                        chamado_int,
                                                        regra_id_acao,
                                                    )

                                                    marcar_status_redmine(
                                                        chamado_int,
                                                        regra_id_acao,
                                                        "Aguardando Retorno Cliente",
                                                    )

                                                    st.success(
                                                        "Envio registrado no chamado do Redmine."
                                                    )
                                                    st.rerun()

                                                except Exception as exc_retry:
                                                    registrar_falha_redmine(
                                                        chamado_int,
                                                        regra_id_acao,
                                                        str(
                                                            exc_retry
                                                        ),
                                                    )

                                                    st.error(
                                                        "A atualização do Redmine "
                                                        f"continua pendente: {exc_retry}"
                                                    )

                                        if estado_acomp in {
                                            "RASCUNHO",
                                            "ERRO_ENVIO",
                                        }:
                                            envio_habilitado = bool(
                                                rascunho.get(
                                                    "executavel",
                                                    False,
                                                )
                                            )

                                            if not envio_habilitado:
                                                st.info(
                                                    "Esta regra ainda não permite envio real."
                                                )
                                            else:
                                                if rascunho.get("requer_aprovacao_humana", False):
                                                    st.warning(
                                                        "⚠️ Procedimento sensível: cancelamentos exigem aprovação humana explícita. "
                                                        "Esta regra nunca é executada automaticamente."
                                                    )

                                                confirmar = st.checkbox(
                                                    (
                                                        "Aprovo este cancelamento e confirmo o envio pela EDNNA"
                                                        if rascunho.get("requer_aprovacao_humana", False)
                                                        else "Confirmo o envio deste e-mail pela EDNNA"
                                                    ),
                                                    key=(
                                                        f"confirmar_envio_"
                                                        f"{chamado_card}_"
                                                        f"{regra_id_acao}"
                                                    ),
                                                )

                                                if st.button(
                                                    "📨 Enviar pela EDNNA",
                                                    type="primary",
                                                    disabled=not confirmar,
                                                    key=(
                                                        f"acao_enviar_real_"
                                                        f"{chamado_card}_"
                                                        f"{regra_id_acao}"
                                                    ),
                                                ):
                                                    adquirido, _ = adquirir_envio(
                                                        chamado_int,
                                                        regra_id_acao,
                                                    )

                                                    if not adquirido:
                                                        st.warning(
                                                            "Este envio já foi iniciado "
                                                            "ou concluído por outra sessão."
                                                        )
                                                        st.rerun()

                                                    try:
                                                        resultado_email = enviar_email_graph(
                                                            remetente=rascunho.get(
                                                                "remetente",
                                                                "edi@netunna.com.br",
                                                            ),
                                                            para=rascunho.get(
                                                                "destinatarios",
                                                                [],
                                                            ),
                                                            cc=rascunho.get(
                                                                "cc",
                                                                [],
                                                            ),
                                                            assunto=rascunho.get(
                                                                "assunto",
                                                                "",
                                                            ),
                                                            corpo=rascunho.get(
                                                                "corpo",
                                                                "",
                                                            ),
                                                        )

                                                        acompanhamento_envio = (
                                                            confirmar_envio_real(
                                                                chamado_int,
                                                                regra_id_acao,
                                                                prazo_dias_uteis=(
                                                                    rascunho.get(
                                                                        "prazo_resposta_dias_uteis",
                                                                        1,
                                                                    )
                                                                ),
                                                                email_assunto=rascunho.get("assunto", ""),
                                                                graph_message_id=resultado_email.get("message_id", ""),
                                                                graph_conversation_id=resultado_email.get("conversation_id", ""),
                                                                graph_internet_message_id=resultado_email.get("internet_message_id", ""),
                                                            )
                                                        )

                                                        try:
                                                            responsabilidade = atribuir_chamado_ednna(chamado_id=chamado_int)
                                                            registrar_responsabilidade_ednna(
                                                                chamado_int, regra_id_acao,
                                                                responsabilidade.get("responsavel_anterior_id"),
                                                                responsabilidade.get("responsavel_anterior_nome", ""),
                                                            )
                                                            nota_redmine = (
                                                                montar_nota_email_enviado(
                                                                    remetente=rascunho.get(
                                                                        "remetente",
                                                                        "edi@netunna.com.br",
                                                                    ),
                                                                    para=rascunho.get(
                                                                        "destinatarios",
                                                                        [],
                                                                    ),
                                                                    cc=rascunho.get(
                                                                        "cc",
                                                                        [],
                                                                    ),
                                                                    assunto=rascunho.get(
                                                                        "assunto",
                                                                        "",
                                                                    ),
                                                                    corpo=rascunho.get(
                                                                        "corpo",
                                                                        "",
                                                                    ),
                                                                    enviado_em=(
                                                                        acompanhamento_envio.get(
                                                                            "enviado_em",
                                                                            "",
                                                                        )
                                                                    ),
                                                                    prazo_resposta_em=(
                                                                        acompanhamento_envio.get(
                                                                            "prazo_resposta_em",
                                                                            "",
                                                                        )
                                                                    ),
                                                                )
                                                            )

                                                            registrar_email_e_status_chamado(
                                                                chamado_id=chamado_int,
                                                                nota=nota_redmine,
                                                                status_nome=rascunho.get(
                                                                    "status_pos_envio",
                                                                    "Aguardando Retorno Cliente",
                                                                ),
                                                                data_inicio=(
                                                                    acompanhamento_envio.get(
                                                                        "enviado_em",
                                                                        "",
                                                                    )
                                                                ),
                                                                data_fim=(
                                                                    acompanhamento_envio.get(
                                                                        "prazo_resposta_em",
                                                                        "",
                                                                    )
                                                                ),
                                                            )

                                                            marcar_redmine_atualizado(
                                                                chamado_int,
                                                                regra_id_acao,
                                                            )

                                                            marcar_status_redmine(
                                                                chamado_int,
                                                                regra_id_acao,
                                                                rascunho.get(
                                                                    "status_pos_envio",
                                                                    "Aguardando Retorno Cliente",
                                                                ),
                                                            )

                                                            st.success(
                                                                "E-mail enviado e chamado "
                                                                "atualizado no Redmine."
                                                            )

                                                        except Exception as exc_redmine:
                                                            registrar_falha_redmine(
                                                                chamado_int,
                                                                regra_id_acao,
                                                                str(
                                                                    exc_redmine
                                                                ),
                                                            )

                                                            st.warning(
                                                                "O e-mail foi enviado, mas "
                                                                "a atualização do Redmine falhou. "
                                                                "A EDNNA não reenviará o e-mail."
                                                            )

                                                        st.rerun()

                                                    except Exception as exc:
                                                        registrar_falha_envio(
                                                            chamado_int,
                                                            regra_id_acao,
                                                            str(exc),
                                                        )
                                                        st.error(
                                                            "Falha no envio do e-mail: "
                                                            f"{exc}"
                                                        )

                                        elif estado_acomp in {
                                            "AGUARDANDO_RESPOSTA",
                                            "PRAZO_VENCIDO",
                                        }:
                                            if st.button(
                                                "📥 Informar manualmente que recebemos resposta",
                                                key=(
                                                    f"acao_resposta_"
                                                    f"{chamado_card}_"
                                                    f"{regra_id_acao}"
                                                ),
                                            ):
                                                registrar_resposta(
                                                    chamado_int,
                                                    regra_id_acao,
                                                )
                                                st.rerun()

                                            if estado_acomp == "PRAZO_VENCIDO":
                                                st.error(
                                                    "Prazo vencido. "
                                                    "Ação sugerida: cobrar retorno."
                                                )

                                        elif estado_acomp == "ENVIANDO":
                                            st.info(
                                                "Envio em andamento por outra sessão."
                                            )

                                        if (
                                            estado_acomp == "ERRO_ENVIO"
                                            and acompanhamento.get("erro_envio")
                                        ):
                                            st.error(
                                                "Última tentativa de envio falhou: "
                                                + str(acompanhamento.get("erro_envio"))
                                            )

                                        st.caption(
                                            "O envio real é realizado pelo Microsoft Graph "
                                            "e registrado no SQLite compartilhado. "
                                            "O acompanhamento da resposta continua centralizado na EDNNA."
                                        )

                                except Exception as exc:
                                    st.warning(
                                        "Não foi possível carregar o acompanhamento "
                                        f"da ação: {exc}"
                                    )

        # ================================================
        # INTELIGÊNCIA
        # ================================================
        with ws_inteligencia:

            st.markdown(
                '<div class="ednna-section-title">Inteligência operacional</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Use esta área para descobrir padrões repetitivos antes de transformar "
                "uma ocorrência em regra operacional."
            )

            st.markdown("### 🔬 Central de Descoberta — Inclusões")
            st.caption(
                "Inventário de inclusões encontrado diretamente no snapshot aberto do Redmine. "
                "Não exige regra homologada nem atribuição à EDNNA: primeiro descobrimos; depois homologamos uma por vez."
            )
            base_descoberta = snapshot_global.copy() if isinstance(snapshot_global, pd.DataFrame) and not snapshot_global.empty else ednna_analisados.copy()
            inventario_inc = descobrir_candidatos_inclusao(base_descoberta)
            candidatos_inc = pd.DataFrame(inventario_inc.get("candidatos", []))
            grupos_inc = pd.DataFrame(inventario_inc.get("players", []))
            di1, di2, di3 = st.columns(3)
            di1.metric("Inclusões descobertas", inventario_inc.get("total", 0))
            di2.metric("Players identificados", len([x for x in inventario_inc.get("players", []) if x.get("player") != "NÃO IDENTIFICADO"]))
            di3.metric("A homologar", len(inventario_inc.get("players", [])))

            if candidatos_inc.empty:
                st.info("Nenhum chamado de inclusão foi localizado no snapshot atual.")
            else:
                if not grupos_inc.empty:
                    with st.expander("Ver inventário por player", expanded=True):
                        grupos_view = grupos_inc.copy()
                        grupos_view["Chamados"] = grupos_view["chamados"].apply(
                            lambda xs: ", ".join(f"#{int(x)}" for x in xs)
                        )
                        grupos_view = grupos_view.rename(columns={"player": "Player", "quantidade": "Casos"})
                        st.dataframe(grupos_view[["Player", "Casos", "Chamados"]], width="stretch", hide_index=True)

                ids_descoberta = candidatos_inc["id"].astype(int).tolist()
                rot_descoberta = {
                    int(r["id"]): f"#{int(r['id'])} · {r.get('cliente') or 'Sem cliente'} · {r.get('player') or 'Player não identificado'} · {str(r.get('assunto') or '')[:58]}"
                    for _, r in candidatos_inc.iterrows()
                }
                selecao_descoberta = st.selectbox(
                    "Inclusão para investigar",
                    ids_descoberta,
                    format_func=lambda x: rot_descoberta.get(int(x), f"#{x}"),
                    key="ednna_descoberta_inclusao_v3289",
                )
                dc1, dc2 = st.columns([1, 3])
                with dc1:
                    investigar_descoberta = st.button(
                        "🔎 Investigar inclusão",
                        key="ednna_investigar_inclusao_v3289",
                        width="stretch",
                    )
                with dc2:
                    st.caption("A investigação consulta BP, relações, AR e inclusões anteriores somente quando você solicitar.")
                with st.expander(f"Ver candidatos ({len(candidatos_inc)})", expanded=False):
                    tab_inc = candidatos_inc.rename(columns={"id": "#", "cliente": "Clientes", "player": "Player", "estado": "Estado", "tipo": "Tipo", "assunto": "Assunto"})
                    cols_inc = [c for c in ["#", "Clientes", "Player", "Estado", "Tipo", "Assunto"] if c in tab_inc.columns]
                    tab_inc, cfg_inc = preparar_tabela_com_link_redmine_fn(tab_inc[cols_inc].copy())
                    st.dataframe(tab_inc, width="stretch", hide_index=True, column_config=cfg_inc)

                if investigar_descoberta:
                    try:
                        with st.spinner("EDNNA reconstruindo BP, AR e histórico da inclusão..."):
                            aprendizado_desc = preparar_aprendizado_inclusao(int(selecao_descoberta), force=False)
                        st.session_state["ednna_aprendizado_descoberta_v3289"] = aprendizado_desc
                    except Exception as exc_desc:
                        st.error(f"Não foi possível investigar a inclusão: {exc_desc}")
                aprendizado_desc = st.session_state.get("ednna_aprendizado_descoberta_v3289")
                if isinstance(aprendizado_desc, dict):
                    cid_desc = int(aprendizado_desc.get("chamado_id", 0) or 0)
                    if cid_desc == int(selecao_descoberta):
                        st.markdown(f"#### Resultado da descoberta — [#{cid_desc}]({redmine_web_url}/issues/{cid_desc})")
                        if aprendizado_desc.get("blueprint_id"):
                            bid = int(aprendizado_desc["blueprint_id"])
                            st.success(f"BP/Novo Cliente localizado: [#{bid}]({redmine_web_url}/issues/{bid})")
                        qualidade = (aprendizado_desc.get("contexto") or {}).get("qualidade_contexto") or {}
                        if qualidade:
                            fonte_ctx = qualidade.get("fonte") or "—"
                            atualizado_ctx = qualidade.get("atualizado_em") or "—"
                            if qualidade.get("parcial"):
                                st.warning(
                                    f"Contexto parcial — Redmine indisponível em parte da investigação. "
                                    f"Fonte: {fonte_ctx} · última referência: {atualizado_ctx}. "
                                    "A EDNNA colocou os dados pendentes na fila de enriquecimento automático."
                                )
                            else:
                                st.caption(f"Contexto: {fonte_ctx} · última referência: {atualizado_ctx}")
                        regras_desc = aprendizado_desc.get("regras", []) or []
                        if regras_desc:
                            # v3.28.12 — síntese primeiro; detalhes históricos ficam recolhidos.
                            for regra_desc in regras_desc:
                                player = regra_desc.get("player") or "Player não identificado"
                                ars = regra_desc.get("aberturas_relacionamento", []) or []
                                ants = regra_desc.get("inclusoes_anteriores", []) or []
                                fontes = regra_desc.get("fontes", []) or []
                                dados = regra_desc.get("dados_identificados", {}) or {}

                                st.markdown(f"### 🎯 Investigação orientada — {player}")
                                s1, s2, s3 = st.columns(3)
                                s1.metric("Canal provável", regra_desc.get("canal_sugerido") or "—")
                                s2.metric("Confiança", regra_desc.get("confianca") or "—")
                                s3.metric("Histórico do player", f"{len(ants)} inclusão(ões)")

                                if ars:
                                    st.success(
                                        "Abertura de relacionamento específica localizada: "
                                        + " · ".join(f"[#{x}]({redmine_web_url}/issues/{x})" for x in ars)
                                    )
                                else:
                                    st.warning(f"Abertura de relacionamento específica de {player} ainda não localizada.")

                                if ants:
                                    st.markdown(
                                        "**Inclusões anteriores relevantes:** "
                                        + " · ".join(f"[#{x}]({redmine_web_url}/issues/{x})" for x in ants)
                                    )
                                    st.info(
                                        "A EDNNA encontrou histórico do mesmo adquirente. O próximo passo é comparar "
                                        "essas ocorrências para extrair o procedimento anterior antes da homologação."
                                    )
                                else:
                                    st.info(
                                        "Ainda não há inclusão anterior do mesmo adquirente no contexto reconstruído. "
                                        "A investigação permanece em descoberta."
                                    )

                                with st.expander("Ver dados e evidências encontrados", expanded=False):
                                    emails = dados.get("emails", []) or []
                                    cnpjs = dados.get("cnpjs", []) or []
                                    ecs = dados.get("ecs", []) or []
                                    st.markdown("**E-mails identificados:** " + (" · ".join(emails) if emails else "nenhum"))
                                    st.markdown("**CNPJs identificados:** " + (" · ".join(cnpjs) if cnpjs else "nenhum"))
                                    st.markdown("**ECs/Convênios identificados:** " + (" · ".join(ecs) if ecs else "nenhum"))
                                    if fontes:
                                        st.markdown("**Fontes consultadas:**")
                                        for fonte in fontes:
                                            fid = fonte.get("id")
                                            evento = fonte.get("evento") or "contexto"
                                            if fid:
                                                st.markdown(f"- [#{fid}]({redmine_web_url}/issues/{fid}) · {evento}")

                                with st.expander("Ver diagnóstico técnico da regra candidata", expanded=False):
                                    st.write(f"Regra sugerida: {regra_desc.get('regra_sugerida')}")
                                    st.write(f"Estado: {regra_desc.get('status_regra')}")
                                    st.write(regra_desc.get("motivo_bloqueio") or "Regra ainda não homologada.")

                                st.caption("Somente investigação. Nenhuma ação é executada sem homologação explícita.")
                        else:
                            st.warning("A EDNNA ainda não conseguiu formar uma regra candidata para esta inclusão.")

            st.divider()
            st.markdown("### 🧠 Central de Atuação EDNNA")
            st.caption(
                "A EDNNA acompanha atuações ativas e reconstrói o contexto operacional a partir do BP/Novo Cliente, "
                "aberturas de relacionamento, inclusões, alterações, faltas de arquivo e cancelamentos vinculados."
            )

            # v3.28.6 — a Central deixa de depender apenas da fila de primeiro combate.
            # União entre chamados formalmente com a EDNNA e chamados classificados pela inteligência.
            base_global = snapshot_global.copy() if isinstance(snapshot_global, pd.DataFrame) and not snapshot_global.empty else ednna_analisados.copy()
            ids_ativos: set[int] = set()
            ednna_user_id_central = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
            if not base_global.empty and "#" in base_global.columns:
                if "_Atribuído a ID" in base_global.columns:
                    resp_ids = pd.to_numeric(base_global["_Atribuído a ID"], errors="coerce")
                    ids_ativos.update(pd.to_numeric(base_global.loc[resp_ids.eq(ednna_user_id_central), "#"], errors="coerce").dropna().astype(int).tolist())
                if "Atribuído a" in base_global.columns:
                    mask_nome = base_global["Atribuído a"].fillna("").astype(str).str.casefold().str.contains("ednna", regex=False)
                    ids_ativos.update(pd.to_numeric(base_global.loc[mask_nome, "#"], errors="coerce").dropna().astype(int).tolist())
            if not ednna_analisados.empty and "#" in ednna_analisados.columns:
                ids_ativos.update(pd.to_numeric(ednna_analisados["#"], errors="coerce").dropna().astype(int).tolist())

            central_df = base_global[pd.to_numeric(base_global.get("#", pd.Series(index=base_global.index, dtype=float)), errors="coerce").isin(ids_ativos)].copy() if ids_ativos else pd.DataFrame()
            if not central_df.empty:
                central_df["__id_atuacao"] = pd.to_numeric(central_df["#"], errors="coerce")
                central_df = central_df[central_df["__id_atuacao"].notna()].copy()
                central_df["__id_atuacao"] = central_df["__id_atuacao"].astype(int)
                central_df = central_df.drop_duplicates("__id_atuacao")

            ids_com_ednna: set[int] = set()
            if not base_global.empty and "#" in base_global.columns:
                if "_Atribuído a ID" in base_global.columns:
                    mask_ednna_id = pd.to_numeric(base_global["_Atribuído a ID"], errors="coerce").eq(ednna_user_id_central)
                    ids_com_ednna.update(pd.to_numeric(base_global.loc[mask_ednna_id, "#"], errors="coerce").dropna().astype(int).tolist())
                if "Atribuído a" in base_global.columns:
                    mask_ednna_nome = base_global["Atribuído a"].fillna("").astype(str).str.casefold().str.contains("ednna", regex=False)
                    ids_com_ednna.update(pd.to_numeric(base_global.loc[mask_ednna_nome, "#"], errors="coerce").dropna().astype(int).tolist())
            ca1, ca2, ca3 = st.columns(3)
            ca1.metric("Atuações na Central", len(central_df))
            ca2.metric("Com a EDNNA", len(ids_com_ednna))
            ca3.metric("Contexto histórico", "BP + relações")

            if central_df.empty:
                st.info("Nenhuma atuação EDNNA foi localizada no snapshot atual.")
                contexto_chamado_id = 0
                analisar_contexto = False
                atualizar_contexto = False
            else:
                def _texto_atuacao(row):
                    cid = int(row.get("__id_atuacao"))
                    cliente = str(row.get("Clientes", "") or "Cliente não identificado").strip()
                    tipo = str(row.get("Tipo", "") or "").strip()
                    estado = str(row.get("Estado", "") or "").strip()
                    assunto = str(row.get("Assunto", "") or "").strip()
                    return f"#{cid} · {cliente} · {tipo or estado}{(' · ' + assunto[:52]) if assunto else ''}"
                central_df["__rotulo_atuacao"] = central_df.apply(_texto_atuacao, axis=1)
                ids_central = central_df["__id_atuacao"].tolist()
                rotulos_central = dict(zip(ids_central, central_df["__rotulo_atuacao"]))
                contexto_salvo = st.session_state.get("ednna_contexto_operacional_v3286")
                id_salvo = int(contexto_salvo.get("chamado_id", 0) or 0) if isinstance(contexto_salvo, dict) else 0
                indice_padrao = ids_central.index(id_salvo) if id_salvo in ids_central else 0
                contexto_chamado_id = st.selectbox(
                    "Chamado para analisar contexto", ids_central, index=indice_padrao,
                    format_func=lambda x: rotulos_central.get(x, f"#{x}"),
                    key="ednna_central_atuacao_selecionado_v3286",
                )
                col_fila, col_analisar, col_atualizar = st.columns([2.2, 1, 1])
                with col_fila:
                    st.caption(f"{len(central_df)} atuação(ões) disponível(is). O histórico só é consultado quando solicitado.")
                with col_analisar:
                    analisar_contexto = st.button("🔎 Abrir contexto", key="ednna_contexto_operacional_analisar_v3286", width="stretch")
                with col_atualizar:
                    atualizar_contexto = st.button("🔄 Atualizar histórico", key="ednna_contexto_operacional_force_v3286", width="stretch")
                with st.expander(f"Ver Central de Atuação ({len(central_df)})", expanded=False):
                    cols = [c for c in ["#", "Clientes", "Origem", "Atribuído a", "Estado", "Prioridade", "Tipo", "Assunto"] if c in central_df.columns]
                    tab, cfg = preparar_tabela_com_link_redmine_fn(central_df[cols].copy())
                    st.dataframe(tab, width="stretch", hide_index=True, column_config=cfg)
            if contexto_chamado_id and (analisar_contexto or atualizar_contexto):
                try:
                    with st.spinner("EDNNA reconstruindo histórico do relacionamento..."):
                        contexto = analisar_contexto_operacional(int(contexto_chamado_id), force=bool(atualizar_contexto))
                    st.session_state["ednna_contexto_operacional_v3286"] = contexto
                    # Evita exibir um plano antigo quando o operador muda de cancelamento.
                    plano_anterior = st.session_state.get("ednna_plano_cancelamento_dados_v325")
                    if isinstance(plano_anterior, dict) and int(plano_anterior.get("chamado_id", 0) or 0) != int(contexto_chamado_id):
                        st.session_state.pop("ednna_plano_cancelamento_dados_v325", None)
                except Exception as exc_ctx:
                    st.error(f"Não foi possível reconstruir o contexto histórico: {exc_ctx}")

            contexto = st.session_state.get("ednna_contexto_operacional_v3286")
            if contexto and int(contexto.get("chamado_id", 0)) == int(contexto_chamado_id):
                st.markdown(
                    f"**[#{contexto.get('chamado_id')}]({redmine_web_url}/issues/{contexto.get('chamado_id')}) • "
                    f"{contexto.get('cliente') or 'Cliente não identificado'}**  "
                    f"— Evento atual: **{contexto.get('evento_atual') or 'OUTRO'}**"
                )
                if contexto.get("blueprint_id"):
                    st.caption(
                        f"Blueprint/Novo Cliente localizado: [{contexto.get('blueprint_id')}]({redmine_web_url}/issues/{contexto.get('blueprint_id')}) • "
                        f"{contexto.get('chamados_consultados', 0)} chamados consultados • modo somente leitura"
                    )
                else:
                    st.warning("Blueprint/Novo Cliente não localizado entre as relações diretas do chamado.")

                linhas_ctx = []
                for rel_ctx in contexto.get("relacionamentos", []):
                    estado_ctx = rel_ctx.get("estado", "DADOS_INSUFICIENTES")
                    rotulo_ctx = {
                        "RELACIONAMENTO_LOCALIZADO": "🟢 Relacionamento localizado",
                        "CANCELADO_CONFIRMADO": "⚪ Já cancelado anteriormente",
                        "DADOS_INSUFICIENTES": "⚠️ Dados insuficientes",
                    }.get(estado_ctx, estado_ctx)
                    fontes_ids = rel_ctx.get("fontes", []) or []
                    linhas_ctx.append({
                        "Player": rel_ctx.get("player", ""),
                        "Estado histórico": rotulo_ctx,
                        "Fontes": f"{len(fontes_ids)} chamado(s)" if fontes_ids else "—",
                        "Cancelamento anterior": "Sim" if rel_ctx.get("cancelamento_anterior") else "—",
                    })

                if linhas_ctx:
                    st.dataframe(pd.DataFrame(linhas_ctx), width="stretch", hide_index=True)
                    tratar = sum(1 for x in contexto.get("relacionamentos", []) if x.get("estado") == "RELACIONAMENTO_LOCALIZADO")
                    cancelados = sum(1 for x in contexto.get("relacionamentos", []) if x.get("estado") == "CANCELADO_CONFIRMADO")
                    insuficientes = sum(1 for x in contexto.get("relacionamentos", []) if x.get("estado") == "DADOS_INSUFICIENTES")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Relacionamentos a tratar", tratar)
                    m2.metric("Já cancelados", cancelados)
                    m3.metric("Dados insuficientes", insuficientes)
                    with st.expander("Ver linha do tempo e fontes", expanded=False):
                        for rel_ctx in contexto.get("relacionamentos", []):
                            st.markdown(f"**{rel_ctx.get('player')}**")
                            fontes_ids = rel_ctx.get("fontes", []) or []
                            cancelamento_anterior = rel_ctx.get("cancelamento_anterior")
                            links_fontes = [
                                f"[#{fid}]({redmine_web_url}/issues/{fid})"
                                for fid in fontes_ids
                            ]
                            if links_fontes:
                                st.markdown("Fontes: " + " · ".join(links_fontes))
                            if cancelamento_anterior:
                                st.markdown(
                                    f"Cancelamento anterior: [#{cancelamento_anterior}]"
                                    f"({redmine_web_url}/issues/{cancelamento_anterior})"
                                )
                            eventos_ctx = rel_ctx.get("eventos", [])
                            if not eventos_ctx:
                                st.caption("Nenhum evento histórico relacionado localizado.")
                                continue
                            tabela_eventos = pd.DataFrame([{
                                "Chamado": f"#{e.get('id')}", "Evento": e.get("evento"),
                                "Estado": e.get("estado"), "Tipo": e.get("tipo"),
                                "Assunto": e.get("assunto"), "Data": e.get("data"),
                            } for e in eventos_ctx])
                            tabela_eventos_link = tabela_eventos.copy()
                            tabela_eventos_link["#"] = tabela_eventos_link["Chamado"].str.replace("#", "", regex=False)
                            tabela_eventos_link = tabela_eventos_link.drop(columns=["Chamado"])
                            cols_eventos = ["#"] + [c for c in tabela_eventos_link.columns if c != "#"]
                            tabela_eventos_link, config_eventos = preparar_tabela_com_link_redmine_fn(
                                tabela_eventos_link[cols_eventos]
                            )
                            st.dataframe(
                                tabela_eventos_link,
                                width="stretch",
                                hide_index=True,
                                column_config=config_eventos,
                            )
                else:
                    st.warning("Nenhum relacionamento operacional foi reconstruído para este cancelamento.")

                eh_cancelamento_contexto = str(contexto.get("evento_atual") or "").upper() == "CANCELAMENTO"
                st.markdown("#### Plano assistido de cancelamento" if eh_cancelamento_contexto else "#### Contexto operacional do relacionamento")
                st.caption(
                    "A EDNNA prepara rascunhos somente para players com procedimento homologado. "
                    "GETNET pode ser disparado após revisão e aprovação humana explícita."
                    if eh_cancelamento_contexto else
                    "Este histórico é a base compartilhada para futuras regras homologadas de abertura, inclusão, falta de arquivo e demais atuações."
                )
                eh_inclusao_contexto = str(contexto.get("evento_atual") or "").upper() == "INCLUSAO"
                if eh_inclusao_contexto:
                    st.markdown("#### Laboratório de inclusão")
                    st.caption("A EDNNA reconstrói BP, Abertura de Relacionamento e inclusões anteriores para propor uma regra candidata. Nenhuma ação externa é executada nesta etapa.")
                    if st.button("🧠 Aprender procedimento de inclusão", key="ednna_btn_aprender_inclusao_v3288"):
                        try:
                            with st.spinner("EDNNA reconstruindo o procedimento histórico de inclusão..."):
                                aprendizado = preparar_aprendizado_inclusao(int(contexto_chamado_id), force=False)
                            st.session_state["ednna_aprendizado_inclusao_v3288"] = aprendizado
                        except Exception as exc_inc:
                            st.error(f"Não foi possível preparar o aprendizado de inclusão: {exc_inc}")

                    aprendizado = st.session_state.get("ednna_aprendizado_inclusao_v3288")
                    if isinstance(aprendizado, dict) and int(aprendizado.get("chamado_id", 0) or 0) == int(contexto_chamado_id):
                        if aprendizado.get("blueprint_id"):
                            st.success(f"BP/Novo Cliente localizado: #{aprendizado.get('blueprint_id')}")
                        for regra in aprendizado.get("regras", []) or []:
                            st.markdown(f"**{regra.get('regra_sugerida')} — {regra.get('player')}**")
                            r1, r2, r3 = st.columns(3)
                            r1.metric("Canal", regra.get("canal_sugerido") or "—")
                            r2.metric("Confiança", regra.get("confianca") or "—")
                            r3.metric("Situação", "Não homologada")
                            ars = regra.get("aberturas_relacionamento", []) or []
                            ants = regra.get("inclusoes_anteriores", []) or []
                            if ars:
                                st.markdown("Abertura(s) de Relacionamento: " + " · ".join(f"[#{x}]({redmine_web_url}/issues/{x})" for x in ars))
                            else:
                                st.warning("Abertura de Relacionamento ainda não localizada no universo relacionado ao BP.")
                            if ants:
                                st.markdown("Inclusões anteriores: " + " · ".join(f"[#{x}]({redmine_web_url}/issues/{x})" for x in ants))
                            dados = regra.get("dados_identificados", {}) or {}
                            st.write({"E-mails encontrados": dados.get("emails", []), "CNPJs encontrados": dados.get("cnpjs", []), "ECs encontrados": dados.get("ecs", [])})
                            with st.expander("Ver fontes usadas no aprendizado", expanded=False):
                                for fonte in regra.get("fontes", []) or []:
                                    fid = fonte.get("id")
                                    st.markdown(f"[#{fid}]({redmine_web_url}/issues/{fid}) — {fonte.get('evento') or 'fonte'} — {fonte.get('assunto') or ''}")
                            st.info(regra.get("motivo_bloqueio"))

                if eh_cancelamento_contexto and st.button("🧭 Preparar plano e rascunhos", key="ednna_btn_preparar_plano_cancelamento_v325"):
                    try:
                        with st.spinner("Preparando o plano de cancelamento a partir do histórico..."):
                            plano = preparar_plano_cancelamento(int(contexto_chamado_id), force=False)
                        st.session_state["ednna_plano_cancelamento_dados_v325"] = plano
                    except Exception as exc_plano:
                        st.error(f"Não foi possível preparar o plano: {exc_plano}")

                plano = st.session_state.get("ednna_plano_cancelamento_dados_v325")
                if not isinstance(plano, dict):
                    plano = None
                if eh_cancelamento_contexto and plano and int(plano.get("chamado_id", 0)) == int(contexto_chamado_id):
                    resumo_plano = plano.get("resumo", {})
                    pc1, pc2, pc3, pc4 = st.columns(4)
                    pc1.metric("Prontos para revisão", resumo_plano.get("prontos", 0))
                    pc2.metric("Dados incompletos", resumo_plano.get("incompletos", 0))
                    pc3.metric("Conflitos", resumo_plano.get("conflitos", 0))
                    pc4.metric("Já cancelados", resumo_plano.get("ja_cancelados", 0))
                    if resumo_plano.get("sem_procedimento", 0):
                        st.caption(
                            f"{resumo_plano.get('sem_procedimento', 0)} player(s) ainda sem procedimento de cancelamento homologado."
                        )

                    orq = resumo_orquestracao(int(contexto_chamado_id))
                    if orq.get("total"):
                        st.markdown("##### Orquestração por player")
                        st.caption(f"Progresso externo: {orq['concluidas']} de {orq['total']} etapa(s) concluída(s).")
                        df_orq = pd.DataFrame([{
                            "Player": e.get("player"),
                            "Situação": rotulo_etapa(e.get("estado")),
                            "Procedimento": e.get("regra_id") or "—",
                        } for e in orq.get("etapas", [])])
                        st.dataframe(df_orq, use_container_width=True, hide_index=True)

                    for item_plano in plano.get("itens", []):
                        status_plano = item_plano.get("status_plano")
                        icone_plano = {
                            "PRONTO_REVISAO": "🟢",
                            "DADOS_INCOMPLETOS": "🟡",
                            "CONFLITO_HISTORICO": "🔴",
                            "JA_CANCELADO": "⚪",
                            "PROCEDIMENTO_NAO_HOMOLOGADO": "🔵",
                        }.get(status_plano, "•")
                        fontes_plano = ", ".join(f"#{x}" for x in item_plano.get("fontes", [])) or "—"
                        with st.expander(
                            f"{icone_plano} {item_plano.get('player')} — {item_plano.get('rotulo')}",
                            expanded=(status_plano == "PRONTO_REVISAO"),
                        ):
                            st.caption(f"Fontes históricas: {fontes_plano}")
                            st.write(item_plano.get("motivo", ""))
                            identificadores = item_plano.get("identificadores", [])
                            if identificadores:
                                st.write("**Identificador(es) encontrado(s):** " + ", ".join(identificadores))
                            rascunho_plano = item_plano.get("rascunho") or {}
                            if status_plano == "PRONTO_REVISAO" and rascunho_plano:
                                st.text_input(
                                    "Para",
                                    value="; ".join(rascunho_plano.get("destinatarios", [])),
                                    disabled=True,
                                    key=f"plano_para_{contexto_chamado_id}_{item_plano.get('player')}",
                                )
                                st.text_input(
                                    "Cc",
                                    value="; ".join(rascunho_plano.get("cc", [])),
                                    disabled=True,
                                    key=f"plano_cc_{contexto_chamado_id}_{item_plano.get('player')}",
                                )
                                st.text_input(
                                    "Assunto",
                                    value=rascunho_plano.get("assunto", ""),
                                    disabled=True,
                                    key=f"plano_assunto_{contexto_chamado_id}_{item_plano.get('player')}",
                                )
                                st.text_area(
                                    "Rascunho",
                                    value=rascunho_plano.get("corpo", ""),
                                    height=260,
                                    disabled=True,
                                    key=f"plano_corpo_{contexto_chamado_id}_{item_plano.get('player')}",
                                )
                                regra_plano = str(rascunho_plano.get("regra_id") or "CANCELAMENTO-GETNET-001")
                                chamado_plano = int(contexto_chamado_id)
                                acompanhamento_plano = obter_acompanhamento(chamado_plano, regra_plano)
                                estado_plano_envio = str(acompanhamento_plano.get("estado") or "RASCUNHO")

                                if estado_plano_envio in {"AGUARDANDO_RESPOSTA", "PRAZO_VENCIDO", "RESPOSTA_RECEBIDA", "ENVIANDO"}:
                                    st.info(
                                        "Este procedimento já possui acompanhamento EDNNA: "
                                        + rotulo_estado(estado_plano_envio)
                                    )
                                else:
                                    # Barreira visual e operacional: GETNET só libera envio com cliente,
                                    # EC(s), destinatários, assunto e corpo efetivamente preenchidos.
                                    ecs_validos = [str(x).strip() for x in item_plano.get("identificadores", []) if str(x).strip()]
                                    validacao_envio = bool(
                                        str(plano.get("cliente") or "").strip()
                                        and ecs_validos
                                        and rascunho_plano.get("destinatarios")
                                        and str(rascunho_plano.get("assunto") or "").strip()
                                        and str(rascunho_plano.get("corpo") or "").strip()
                                        and all(ec in str(rascunho_plano.get("corpo") or "") for ec in ecs_validos)
                                    )
                                    if not validacao_envio:
                                        st.error(
                                            "Envio bloqueado: Cliente + EC(s) + destinatários + assunto + corpo "
                                            "precisam estar completos e validados."
                                        )
                                    else:
                                        aprovar_plano = st.checkbox(
                                            "Aprovo este cancelamento GETNET e confirmo o envio pela EDNNA",
                                            key=f"aprovar_plano_getnet_{chamado_plano}_{item_plano.get('player')}",
                                        )
                                        if st.button(
                                            "📨 Disparar cancelamento GETNET",
                                            type="primary",
                                            disabled=not aprovar_plano,
                                            key=f"enviar_plano_getnet_{chamado_plano}_{item_plano.get('player')}",
                                        ):
                                            adquirido, _ = adquirir_envio(chamado_plano, regra_plano)
                                            if not adquirido:
                                                st.warning("Este envio já foi iniciado ou concluído por outra sessão.")
                                                st.rerun()
                                            try:
                                                resultado_email = enviar_email_graph(
                                                    remetente=rascunho_plano.get("remetente", "edi@netunna.com.br"),
                                                    para=rascunho_plano.get("destinatarios", []),
                                                    cc=rascunho_plano.get("cc", []),
                                                    assunto=rascunho_plano.get("assunto", ""),
                                                    corpo=rascunho_plano.get("corpo", ""),
                                                )
                                                acompanhamento_envio = confirmar_envio_real(
                                                    chamado_plano,
                                                    regra_plano,
                                                    prazo_dias_uteis=rascunho_plano.get("prazo_resposta_dias_uteis", 1),
                                                    email_assunto=rascunho_plano.get("assunto", ""),
                                                    graph_message_id=resultado_email.get("message_id", ""),
                                                    graph_conversation_id=resultado_email.get("conversation_id", ""),
                                                    graph_internet_message_id=resultado_email.get("internet_message_id", ""),
                                                )
                                                marcar_etapa(chamado_plano, str(item_plano.get("player") or "GETNET"), "AGUARDANDO_RESPOSTA", "Solicitação enviada pela EDNNA.")
                                                responsabilidade = atribuir_chamado_ednna(chamado_id=chamado_plano)
                                                registrar_responsabilidade_ednna(
                                                    chamado_plano, regra_plano,
                                                    responsabilidade.get("responsavel_anterior_id"),
                                                    responsabilidade.get("responsavel_anterior_nome", ""),
                                                )
                                                nota_redmine = montar_nota_email_enviado(
                                                    remetente=rascunho_plano.get("remetente", "edi@netunna.com.br"),
                                                    para=rascunho_plano.get("destinatarios", []),
                                                    cc=rascunho_plano.get("cc", []),
                                                    assunto=rascunho_plano.get("assunto", ""),
                                                    corpo=rascunho_plano.get("corpo", ""),
                                                    enviado_em=acompanhamento_envio.get("enviado_em", ""),
                                                    prazo_resposta_em=acompanhamento_envio.get("prazo_resposta_em", ""),
                                                )
                                                registrar_email_e_status_chamado(
                                                    chamado_id=chamado_plano,
                                                    nota=nota_redmine,
                                                    status_nome="Aguardando Retorno Adquirente",
                                                    data_inicio=acompanhamento_envio.get("enviado_em", ""),
                                                    data_fim=acompanhamento_envio.get("prazo_resposta_em", ""),
                                                    assigned_to_id=int(responsabilidade.get("ednna_user_id") or 166),
                                                )
                                                marcar_redmine_atualizado(chamado_plano, regra_plano)
                                                marcar_status_redmine(chamado_plano, regra_plano, "Aguardando Retorno Adquirente")
                                                st.success("Cancelamento GETNET enviado. Chamado atribuído à EDNNA e colocado em acompanhamento.")
                                                st.rerun()
                                            except Exception as exc_envio_plano:
                                                registrar_falha_redmine(chamado_plano, regra_plano, str(exc_envio_plano))
                                                st.error(
                                                    "O e-mail pode ter sido enviado, mas a finalização operacional apresentou erro. "
                                                    "A EDNNA não fará reenvio automático. Detalhe: " + str(exc_envio_plano)
                                                )

            st.divider()

            intencoes = (
                base_demandas["EDNNA - Intenção"]
                .fillna("NAO_CLASSIFICADO")
                .value_counts()
                .rename_axis("Intenção")
                .reset_index(name="Chamados")
            )

            opcoes_intencao = intencoes["Intenção"].astype(str).tolist()
            intencao_sel = st.selectbox(
                "Explorar intenção",
                opcoes_intencao,
                key="ednna_intencao_observatorio_v316",
            )

            detalhe_intencao = base_demandas[
                base_demandas["EDNNA - Intenção"]
                .fillna("NAO_CLASSIFICADO")
                .astype(str)
                == str(intencao_sel)
            ].copy()

            total_intencao = len(detalhe_intencao)
            completos_op = int(
                (
                    detalhe_intencao.get(
                        "EDNNA - Dados operacionais completos",
                        pd.Series("", index=detalhe_intencao.index),
                    )
                    .astype(str)
                    .str.upper()
                    == "SIM"
                ).sum()
            )
            convenio_op = int(
                (
                    detalhe_intencao.get(
                        "EDNNA - Convênio",
                        pd.Series("", index=detalhe_intencao.index),
                    )
                    .fillna("").astype(str).str.strip() != ""
                ).sum()
            )
            referencia_op = int(
                (
                    detalhe_intencao.get(
                        "EDNNA - Referência operacional",
                        pd.Series("", index=detalhe_intencao.index),
                    )
                    .fillna("").astype(str).str.strip() != ""
                ).sum()
            )
            tipo_op = int(
                (
                    detalhe_intencao.get(
                        "EDNNA - Tipos arquivo",
                        pd.Series("", index=detalhe_intencao.index),
                    )
                    .fillna("").astype(str).str.strip() != ""
                ).sum()
            )
            nsa_op = int(
                (
                    detalhe_intencao.get(
                        "EDNNA - NSA referência",
                        pd.Series("", index=detalhe_intencao.index),
                    )
                    .fillna("").astype(str).str.strip() != ""
                ).sum()
            )

            q1, q2, q3, q4, q5, q6 = st.columns(6)
            q1.metric("Candidatos", total_intencao)
            q2.metric("Dados completos", completos_op)
            q3.metric("Com convênio", convenio_op)
            q4.metric("Com referência", referencia_op)
            q5.metric("Com tipo", tipo_op)
            q6.metric("Com NSA", nsa_op)

            st.caption(
                "Dados completos = Convênio + referência/data + tipo de arquivo + último NSA conhecido. "
                "Esse indicador mede qualidade do dado, não autorização de automação."
            )

            i1, i2 = st.columns(2)

            with i1:
                st.markdown("**Clientes com maior recorrência**")
                if "Clientes" in detalhe_intencao.columns and not detalhe_intencao.empty:
                    rank_cli = ranking_clientes_fn(detalhe_intencao).head(15)
                    if not rank_cli.empty:
                        fig_cli_ed = px.bar(
                            rank_cli.sort_values("Chamados"),
                            x="Chamados",
                            y="Cliente",
                            orientation="h",
                            text_auto=True,
                            color_discrete_sequence=facebook_colors,
                        )
                        fig_cli_ed.update_layout(
                            height=380,
                            xaxis_title="Chamados",
                            yaxis_title="",
                        )
                        ajustar_grafico_fn(fig_cli_ed)
                        st.plotly_chart(fig_cli_ed, width="stretch")
                    else:
                        st.info("Sem clientes identificados.")

            with i2:
                st.markdown("**Origens com maior recorrência**")
                if "Origem" in detalhe_intencao.columns and not detalhe_intencao.empty:
                    rank_origem = (
                        detalhe_intencao["Origem"]
                        .fillna("Sem origem")
                        .astype(str)
                        .value_counts()
                        .head(15)
                        .rename_axis("Origem")
                        .reset_index(name="Chamados")
                    )
                    fig_ori_ed = px.bar(
                        rank_origem.sort_values("Chamados"),
                        x="Chamados",
                        y="Origem",
                        orientation="h",
                        text_auto=True,
                        color_discrete_sequence=facebook_colors,
                    )
                    fig_ori_ed.update_layout(
                        height=380,
                        xaxis_title="Chamados",
                        yaxis_title="",
                    )
                    ajustar_grafico_fn(fig_ori_ed)
                    st.plotly_chart(fig_ori_ed, width="stretch")

            with st.expander("Ver chamados candidatos", expanded=False):
                cols_demanda = [
                    c for c in [
                        "#","Clientes","Origem","Atribuído a","Prioridade","Tipo","Assunto",
                        "Tempo em aberto (dias)","EDNNA - Intenção","EDNNA - Subtipo",
                        "EDNNA - Origem operacional","EDNNA - Convênio",
                        "EDNNA - Referência operacional","EDNNA - Tipos arquivo",
                        "EDNNA - NSA referência","EDNNA - Completude operacional (%)",
                        "EDNNA - Dados operacionais completos","EDNNA - Campos faltantes",
                        "EDNNA - Regra operacional","EDNNA - Ação operacional",
                        "EDNNA - Apto para rascunho","EDNNA - Motivo ação",
                        "EDNNA - Confiança","EDNNA - Regra","EDNNA - Ação sugerida",
                    ]
                    if c in detalhe_intencao.columns
                ]

                ordenacao = []
                ascend = []

                if "EDNNA - Confiança" in detalhe_intencao.columns:
                    ordenacao.append("EDNNA - Confiança")
                    ascend.append(False)

                if "Tempo em aberto (dias)" in detalhe_intencao.columns:
                    ordenacao.append("Tempo em aberto (dias)")
                    ascend.append(False)

                detalhe_ordenado = (
                    detalhe_intencao.sort_values(ordenacao, ascending=ascend)
                    if ordenacao
                    else detalhe_intencao
                )

                tabela_dem, config_dem = preparar_tabela_com_link_redmine_fn(
                    detalhe_ordenado[cols_demanda]
                )
                st.dataframe(
                    tabela_dem,
                    width="stretch",
                    hide_index=True,
                    column_config=config_dem,
                )

                csv_obs = (
                    detalhe_ordenado[cols_demanda]
                    .to_csv(index=False, sep=";", encoding="utf-8-sig")
                    .encode("utf-8-sig")
                )
                st.download_button(
                    "Baixar candidatos desta intenção",
                    data=csv_obs,
                    file_name=(
                        "ednna_candidatos_"
                        + str(intencao_sel).lower().replace(" ", "_")
                        + ".csv"
                    ),
                    mime="text/csv",
                    key="download_ednna_intencao_v316",
                )

        # ================================================
        # REGRAS
        # ================================================
        with ws_regras:

            st.markdown(
                '<div class="ednna-section-title">Catálogo operacional</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "O catálogo combina regras automáticas e assistidas. "
                "Procedimentos sensíveis, como cancelamento de tráfego, exigem aprovação humana."
            )

            regras_operacionais = catalogo_operacional_ednna.get("regras", [])

            if regras_operacionais:
                regras_op_df = pd.DataFrame(regras_operacionais)
                colunas_op = [
                    c for c in [
                        "id",
                        "nome",
                        "intencao",
                        "origens",
                        "modo",
                        "homologada",
                        "executavel",
                    ]
                    if c in regras_op_df.columns
                ]
                st.dataframe(
                    regras_op_df[colunas_op],
                    width="stretch",
                    hide_index=True,
                )
                st.success(
                    "🟢 Modo do catálogo operacional: RASCUNHO ASSISTIDO."
                )
            else:
                st.info("Nenhuma regra operacional homologada cadastrada.")

            st.divider()
            st.markdown("**Regras candidatas em observação**")

            regras_catalogo = catalogo_ednna.get("regras", [])

            if regras_catalogo:
                catalogo_df = pd.DataFrame(regras_catalogo)
                colunas_catalogo = [
                    c for c in [
                        "id",
                        "nome",
                        "intencao",
                        "acao_sugerida",
                        "risco",
                        "homologada",
                        "executavel",
                    ]
                    if c in catalogo_df.columns
                ]
                st.dataframe(
                    catalogo_df[colunas_catalogo],
                    width="stretch",
                    hide_index=True,
                )
                st.warning(
                    "🟡 Observação: prontidão e confiança servem para priorizar estudo. "
                    "Essas regras ainda não estão autorizadas para execução."
                )

            st.divider()
            st.markdown("**Ranking de prontidão para estudo**")

            if not prontidao_df.empty:
                st.dataframe(
                    prontidao_df,
                    width="stretch",
                    hide_index=True,
                )

                graf_pront = prontidao_df[
                    prontidao_df["Intenção"] != "NAO_CLASSIFICADO"
                ].copy()

                if not graf_pront.empty:
                    fig_pront = px.bar(
                        graf_pront.sort_values("Prontidão"),
                        x="Prontidão",
                        y="Intenção",
                        orientation="h",
                        text="Chamados",
                        color_discrete_sequence=facebook_colors,
                    )
                    fig_pront.update_traces(
                        texttemplate="%{text} chamados",
                        textposition="outside",
                        cliponaxis=False,
                    )
                    fig_pront.update_layout(
                        height=max(340, 44 * len(graf_pront)),
                        xaxis_title="Índice de prontidão",
                        yaxis_title="",
                    )
                    ajustar_grafico_fn(fig_pront)
                    st.plotly_chart(fig_pront, width="stretch")
