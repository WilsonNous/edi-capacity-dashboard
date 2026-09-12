from __future__ import annotations

from pathlib import Path

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
    montar_nota_email_enviado,
    registrar_email_e_status_chamado,
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
    Workspace visual da EDNNA — v3.21.3.

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
            <div class="ednna-hero-title">🤖 Workspace operacional da EDNNA</div>
            <div class="ednna-hero-sub">
                Acompanhe qualidade dos dados, ações assistidas, recorrências e regras
                sem percorrer uma página única e extensa.
            </div>
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

        ws_resumo, ws_acoes, ws_inteligencia, ws_regras = st.tabs(
            [
                "🏠 Resumo",
                "🤖 Ações",
                "📊 Inteligência",
                "⚙️ Regras",
            ]
        )

        # ================================================
        # RESUMO
        # ================================================
        with ws_resumo:

            r1, r2, r3, r4 = st.columns(4)

            with r1:
                st.markdown(
                    f"""
                    <div class="ednna-card ednna-card-blue">
                        <div class="ednna-card-label">CANDIDATOS</div>
                        <div class="ednna-card-value">{len(base_demandas)}</div>
                        <div class="ednna-card-note">Demandas aguardando primeiro combate</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with r2:
                st.markdown(
                    f"""
                    <div class="ednna-card ednna-card-green">
                        <div class="ednna-card-label">DADOS COMPLETOS</div>
                        <div class="ednna-card-value">{completos_total}</div>
                        <div class="ednna-card-note">Convênio + referência + tipo + NSA</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with r3:
                st.markdown(
                    f"""
                    <div class="ednna-card ednna-card-purple">
                        <div class="ednna-card-label">COM REGRA HOMOLOGADA</div>
                        <div class="ednna-card-value">{regras_homologadas_total}</div>
                        <div class="ednna-card-note">Possuem procedimento operacional conhecido</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with r4:
                st.markdown(
                    f"""
                    <div class="ednna-card ednna-card-yellow">
                        <div class="ednna-card-label">PRONTOS PARA RASCUNHO</div>
                        <div class="ednna-card-value">{prontos_rascunho_total}</div>
                        <div class="ednna-card-note">Somente modo assistido</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                '<div class="ednna-section-title">Panorama das demandas</div>',
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

        # ================================================
        # AÇÕES
        # ================================================
        with ws_acoes:

            st.markdown(
                '<div class="ednna-section-title">Ações propostas pela EDNNA</div>',
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
                                                confirmar = st.checkbox(
                                                    "Confirmo o envio deste e-mail pela EDNNA",
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
                                                        enviar_email_graph(
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
                                                            )
                                                        )

                                                        try:
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
                                                                status_nome=(
                                                                    "Aguardando Retorno Cliente"
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
                                                                "Aguardando Retorno Cliente",
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
                '<div class="ednna-section-title">Inteligência e recorrência</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Use esta área para descobrir padrões repetitivos antes de transformar "
                "uma ocorrência em regra operacional."
            )

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
                "Regras homologadas podem gerar somente rascunhos assistidos. "
                "Nenhuma ação é executada automaticamente."
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
