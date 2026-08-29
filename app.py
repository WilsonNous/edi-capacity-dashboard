from __future__ import annotations

import io
import os
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
from redmine_api import buscar_chamados_projetos, issue_para_linha

FACEBOOK_COLORS = ["#1877F2", "#42B72A", "#F7B928", "#E41E3F", "#8A3FFC", "#00A6A6", "#65676B"]
import streamlit as st

st.set_page_config(
    page_title="EDI — Painel de Capacidade e Atendimento",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root {
        --fb-blue: #1877F2;
        --fb-blue-dark: #166FE5;
        --fb-bg: #F0F2F5;
        --fb-card: #FFFFFF;
        --fb-text: #1C1E21;
        --fb-muted: #65676B;
        --fb-border: #DADDE1;
      }

      .stApp {
        background: var(--fb-bg);
        color: var(--fb-text);
      }

      /* Agora podemos ocultar o cabeçalho nativo sem risco:
         os filtros não usam mais a sidebar do Streamlit. */
      [data-testid="stHeader"],
      [data-testid="stToolbar"],
      [data-testid="stDecoration"],
      [data-testid="stSidebar"],
      [data-testid="stSidebarCollapsedControl"],
      [data-testid="collapsedControl"] {
        display: none !important;
      }

      [data-testid="stAppViewContainer"] > .main {
        padding-top: 0 !important;
      }

      .block-container {
        max-width: 1550px;
        padding-top: .55rem;
        padding-bottom: 1.5rem;
        padding-left: 1rem;
        padding-right: 1rem;
      }

      /* Barra superior inspirada no Facebook */
      .fb-topbar {
        background: #FFFFFF;
        border: 1px solid var(--fb-border);
        border-radius: 12px;
        min-height: 58px;
        padding: 10px 16px;
        margin-bottom: .85rem;
        box-shadow: 0 1px 2px rgba(0,0,0,.08);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
      }

      .fb-brand {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .fb-logo {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: var(--fb-blue);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 1rem;
      }

      .fb-title {
        font-size: 1.22rem;
        font-weight: 800;
        line-height: 1.1;
        color: var(--fb-text);
      }

      .fb-subtitle {
        color: var(--fb-muted);
        font-size: .84rem;
        margin-top: 2px;
      }

      .fb-badge {
        background: #E7F3FF;
        color: var(--fb-blue);
        border-radius: 999px;
        padding: 6px 10px;
        font-size: .78rem;
        font-weight: 700;
        white-space: nowrap;
      }

      /* Coluna de filtros no estilo "menu lateral" */
      .filter-title {
        font-size: 1.03rem;
        font-weight: 800;
        color: var(--fb-text);
        margin-bottom: .15rem;
      }

      .filter-note {
        color: var(--fb-muted);
        font-size: .82rem;
        margin-bottom: .5rem;
      }

      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF;
        border-color: var(--fb-border) !important;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,.06);
      }

      h1, h2, h3 {
        color: var(--fb-text);
      }

      h1 {
        font-size: 1.8rem !important;
        margin-bottom: .10rem !important;
      }

      [data-testid="stMetric"] {
        background: var(--fb-card);
        border: 1px solid var(--fb-border);
        padding: 14px 16px;
        border-radius: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,.08);
      }

      [data-testid="stMetricLabel"] {
        color: var(--fb-muted);
        font-weight: 600;
      }

      [data-testid="stMetricValue"] {
        color: var(--fb-blue);
        font-weight: 700;
      }

      .small-note {
        font-size: .90rem;
        color: var(--fb-muted);
        margin-top: .35rem;
      }

      .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--fb-text);
        margin-top: .15rem;
        margin-bottom: .25rem;
      }

      div[data-baseweb="tab-list"] {
        gap: .35rem;
      }

      button[data-baseweb="tab"] {
        background: #FFFFFF;
        border-radius: 8px 8px 0 0;
        padding-left: 1rem;
        padding-right: 1rem;
      }

      button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--fb-blue) !important;
        border-bottom-color: var(--fb-blue) !important;
        font-weight: 700;
      }

      .stButton > button,
      .stDownloadButton > button {
        border-radius: 8px;
        border: 1px solid var(--fb-blue);
        color: var(--fb-blue);
      }

      .stButton > button:hover,
      .stDownloadButton > button:hover {
        border-color: var(--fb-blue-dark);
        color: var(--fb-blue-dark);
      }

      hr {
        border-color: var(--fb-border);
      }

      @media (max-width: 900px) {
        .fb-topbar {
          align-items: flex-start;
          flex-direction: column;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

EXPECTED = [
    "#", "Clientes", "Atribuído a", "Projeto", "Tipo", "Estado", "Prioridade",
    "Assunto", "Data de fim", "Alterado", "Autor", "Data de início", "Criado", "Descrição"
]

WAITING_PREFIX = "Aguardando"
CRITICAL_PRIORITIES = {"Alta", "Urgente", "Prioritário"}

REDMINE_WEB_URL = os.getenv(
    "REDMINE_URL",
    "https://chamados.nteia.com"
).rstrip("/")


def preparar_tabela_com_link_redmine(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Converte a coluna de ID (#) em link clicável para o chamado no Redmine.

    O número continua sendo exibido como identificador do chamado,
    porém o clique abre diretamente a tela correspondente no Redmine.
    """
    tabela = frame.copy()
    configuracao = {}

    if "#" in tabela.columns:
        def montar_url(valor):
            if pd.isna(valor):
                return None

            texto = str(valor).strip()

            # Evita exibir IDs com ".0" quando o pandas inferiu float.
            if texto.endswith(".0"):
                texto = texto[:-2]

            return f"{REDMINE_WEB_URL}/issues/{texto}"

        tabela["#"] = tabela["#"].apply(montar_url)

        configuracao["#"] = st.column_config.LinkColumn(
            "Chamado",
            help="Clique no número para abrir o chamado no Redmine",
            display_text=r"issues/(\d+)$",
        )

    return tabela, configuracao



def ajustar_grafico(fig, altura=None):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#1C1E21"),
        margin=dict(l=20, r=20, t=35, b=20),
        hoverlabel=dict(bgcolor="#FFFFFF", font_color="#1C1E21"),
    )
    if altura:
        fig.update_layout(height=altura)
    fig.update_xaxes(gridcolor="#E4E6EB", zerolinecolor="#E4E6EB")
    fig.update_yaxes(gridcolor="#E4E6EB", zerolinecolor="#E4E6EB")
    return fig

def read_redmine_csv(source) -> pd.DataFrame:
    """Lê exportação do Redmine tentando os encodings mais comuns no Windows/BR."""
    raw = source.read() if hasattr(source, "read") else Path(source).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc, sep=None, engine="python")
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError("Não foi possível identificar o encoding/separador do CSV.")


def prepare(df: pd.DataFrame, origem: str = "csv") -> pd.DataFrame:
    """
    Normaliza os dados vindos da API ou do CSV.

    A API do Redmine retorna datas ISO 8601 com timezone, por exemplo:
    2026-08-25T10:13:32-03:00

    O CSV pode trazer datas no padrão brasileiro.

    Para evitar o erro:
    "Cannot subtract tz-naive and tz-aware datetime-like objects"

    todas as datas são convertidas para UTC e, em seguida, têm o timezone
    removido antes dos cálculos do painel.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    colunas_data = ["Criado", "Alterado", "Data de início", "Data de fim", "Fechado"]

    for col in colunas_data:
        if col not in df.columns:
            continue

        if origem == "api":
            # Redmine API: ISO 8601 / YYYY-MM-DD, normalmente com timezone.
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce",
                utc=True,
            ).dt.tz_convert(None)
        else:
            # Exportação CSV: normalmente utiliza formato brasileiro.
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce",
                dayfirst=True,
                utc=True,
            ).dt.tz_convert(None)

    if "Criado" not in df.columns:
        raise ValueError("Os dados precisam conter a coluna 'Criado'.")

    today = pd.Timestamp(date.today()).normalize()

    df["Tempo em aberto (dias)"] = (
        today - df["Criado"].dt.normalize()
    ).dt.days.clip(lower=0)

    estado = df.get("Estado", pd.Series("", index=df.index)).fillna("").astype(str)
    df["Responsabilidade atual"] = estado.str.startswith(WAITING_PREFIX).map(
        {True: "Aguardando terceiros", False: "Em atuação do EDI"}
    )

    prioridade = df.get("Prioridade", pd.Series("", index=df.index)).fillna("").astype(str)
    df["Prioridade crítica"] = prioridade.isin(CRITICAL_PRIORITIES)

    def bucket(v):
        if pd.isna(v): return "Sem data"
        if v <= 7: return "0–7 dias"
        if v <= 15: return "8–15 dias"
        if v <= 30: return "16–30 dias"
        if v <= 60: return "31–60 dias"
        if v <= 90: return "61–90 dias"
        if v <= 180: return "91–180 dias"
        if v <= 365: return "181–365 dias"
        return "+365 dias"

    df["Faixa de tempo em aberto"] = df["Tempo em aberto (dias)"].apply(bucket)

    if "Data de fim" in df.columns:
        df["Prazo vencido"] = df["Data de fim"].notna() & (df["Data de fim"].dt.normalize() < today.normalize())
    else:
        df["Prazo vencido"] = False

    return df


def multiselect_filter(frame: pd.DataFrame, label: str, col: str, container):
    if col not in frame.columns:
        return []
    values = sorted([x for x in frame[col].dropna().astype(str).unique() if x.strip()])
    return container.multiselect(label, values, placeholder="Selecione")


# -------------------------------------------------------------------------
# VISÃO PRINCIPAL — estilo Facebook
# -------------------------------------------------------------------------
st.markdown(
    """
    <div class="fb-topbar">
      <div class="fb-brand">
        <div class="fb-logo">EDI</div>
        <div>
          <div class="fb-title">Painel de Capacidade e Atendimento</div>
          <div class="fb-subtitle">Acompanhamento operacional dos chamados do Redmine</div>
        </div>
      </div>
      <div class="fb-badge">● Dados operacionais</div>
    </div>
    """,
    unsafe_allow_html=True,
)

filter_col, main_col = st.columns([1.08, 4.25], gap="large")

# -------------------------------------------------------------------------
# COLUNA ESQUERDA — filtros sempre visíveis
# -------------------------------------------------------------------------
with filter_col:
    with st.container(border=True):
        st.markdown('<div class="filter-title">Filtros</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="filter-note">Refine os chamados sem depender da barra lateral do navegador.</div>',
            unsafe_allow_html=True,
        )

        st.markdown("#### Fonte dos dados")
        fonte = st.radio(
            "Como deseja carregar os chamados?",
            ["API do Redmine", "Arquivo CSV"],
            index=0,
            label_visibility="collapsed",
        )

@st.cache_data(ttl=300, show_spinner=False)
def carregar_api_abertos() -> pd.DataFrame:
    chamados = buscar_chamados_projetos(status_id="open")
    return pd.DataFrame([issue_para_linha(c) for c in chamados])

# -------------------------------------------------------------------------
# CARGA DOS DADOS
# -------------------------------------------------------------------------
if fonte == "API do Redmine":
    with filter_col:
        st.caption("Atualização automática. Cache de 5 minutos.")
        if st.button("Atualizar dados agora", use_container_width=True):
            carregar_api_abertos.clear()

    try:
        with main_col:
            with st.spinner("Consultando os chamados no Redmine..."):
                raw_df = carregar_api_abertos()

        if raw_df.empty:
            with main_col:
                st.warning("A API não retornou chamados em aberto.")
            st.stop()

        df = prepare(raw_df, origem="api")

    except Exception as exc:
        with main_col:
            st.error(f"Não foi possível consultar a API do Redmine: {exc}")
            st.info(
                "Confira as variáveis REDMINE_API_KEY, REDMINE_AUTHORIZATION, "
                "REDMINE_URL e REDMINE_PROJECT_IDS no ambiente."
            )
        st.stop()

else:
    with filter_col:
        uploaded = st.file_uploader("CSV exportado do Redmine", type=["csv"])

    local_default = Path("issues.csv")

    if uploaded is None and not local_default.exists():
        with main_col:
            st.info(
                "Carregue o CSV no painel de filtros. Para uso local fixo, "
                "você também pode salvar o arquivo como `issues.csv` ao lado do `app.py`."
            )
        st.stop()

    try:
        raw_df = read_redmine_csv(uploaded if uploaded is not None else local_default)
        df = prepare(raw_df, origem="csv")
    except Exception as exc:
        with main_col:
            st.error(f"Erro ao carregar o CSV: {exc}")
        st.stop()

missing = [
    c for c in ["#", "Atribuído a", "Estado", "Prioridade", "Tipo", "Criado"]
    if c not in df.columns
]

if missing:
    with main_col:
        st.warning(
            "Algumas análises ficarão limitadas porque faltam estas colunas: "
            + ", ".join(missing)
        )

# -------------------------------------------------------------------------
# FILTROS
# -------------------------------------------------------------------------
with filter_col:
    with st.container(border=True):
        st.markdown("#### Chamados")

        assignees = multiselect_filter(df, "Atribuído a", "Atribuído a", st)
        statuses = multiselect_filter(df, "Estado", "Estado", st)
        priorities = multiselect_filter(df, "Prioridade", "Prioridade", st)
        types = multiselect_filter(df, "Tipo", "Tipo", st)
        projects = multiselect_filter(df, "Projeto", "Projeto", st)
        clients = multiselect_filter(df, "Cliente", "Clientes", st)

f = df.copy()

for col, vals in [
    ("Atribuído a", assignees),
    ("Estado", statuses),
    ("Prioridade", priorities),
    ("Tipo", types),
    ("Projeto", projects),
    ("Clientes", clients),
]:
    if vals and col in f.columns:
        f = f[f[col].astype(str).isin(vals)]

with filter_col:
    with st.container(border=True):
        st.markdown("#### Tempo em aberto")

        aging_min = int(f["Tempo em aberto (dias)"].min()) if len(f) else 0
        aging_max = int(f["Tempo em aberto (dias)"].max()) if len(f) else 0

        aging_range = st.slider(
            "Faixa de dias em aberto",
            0,
            max(aging_max, 1),
            (0, max(aging_max, 1)),
        )

f = f[f["Tempo em aberto (dias)"].between(*aging_range)]

with filter_col:
    st.caption(f"{len(f)} chamado(s) no filtro atual")

# -------------------------------------------------------------------------
# CONTEÚDO PRINCIPAL
# -------------------------------------------------------------------------
with main_col:
    st.title("Visão operacional")
    st.caption(
        "Chamados em aberto, distribuição da carga, tempo em aberto e dependências externas"
    )

    # KPIs
    backlog = len(f)
    sob_acao = int((f["Responsabilidade atual"] == "Em atuação do EDI").sum())
    aguardando = int((f["Responsabilidade atual"] == "Aguardando terceiros").sum())
    mais30 = int((f["Tempo em aberto (dias)"] > 30).sum())
    criticos = int(f["Prioridade crítica"].sum())
    vencidos = int(f["Prazo vencido"].sum())

    cols = st.columns(6)
    cols[0].metric("Chamados em aberto", f"{backlog:,}".replace(",", "."))
    cols[1].metric("Em atuação do EDI", f"{sob_acao:,}".replace(",", "."))
    cols[2].metric("Aguardando terceiros", f"{aguardando:,}".replace(",", "."))
    cols[3].metric("+30 dias", f"{mais30:,}".replace(",", "."))
    cols[4].metric("Alta / Urgente", f"{criticos:,}".replace(",", "."))
    cols[5].metric("Prazo vencido", f"{vencidos:,}".replace(",", "."))

    if backlog:
        pct_wait = aguardando / backlog * 100
        med = f["Tempo em aberto (dias)"].median()
        avg = f["Tempo em aberto (dias)"].mean()
        st.markdown(
            f"<div class='small-note'>No filtro atual, <b>{pct_wait:.1f}%</b> dos chamados estão aguardando terceiros. "
            f"Tempo mediano em aberto: <b>{med:.0f} dias</b> · tempo médio em aberto: <b>{avg:.0f} dias</b>.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    tab_exec, tab_team, tab_aging, tab_demand, tab_detail = st.tabs(
        ["Visão geral", "Equipe", "Tempo em aberto", "Tipos de demanda", "Lista de chamados"]
    )

    with tab_exec:
        evento_status = None
        c1, c2 = st.columns([1.15, 1])
        with c1:
            st.markdown("<div class='section-title'>Distribuição dos chamados por responsável</div>", unsafe_allow_html=True)
            if "Atribuído a" in f.columns and len(f):
                resp = f.groupby(["Atribuído a", "Responsabilidade atual"], dropna=False).size().reset_index(name="Chamados")
                fig = px.bar(resp, x="Atribuído a", y="Chamados", color="Responsabilidade atual", barmode="stack",
                             text_auto=True, color_discrete_sequence=FACEBOOK_COLORS, labels={"Atribuído a":"Responsável", "Responsabilidade atual":"Situação"})
                fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="Chamados", height=430)
                ajustar_grafico(fig)
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("<div class='section-title'>Chamados por situação</div>", unsafe_allow_html=True)
            if "Estado" in f.columns and len(f):
                s = f["Estado"].fillna("Sem status").value_counts().reset_index()
                s.columns = ["Estado", "Chamados"]

                fig = px.bar(
                    s.sort_values("Chamados"),
                    x="Chamados",
                    y="Estado",
                    orientation="h",
                    text_auto=True,
                    color_discrete_sequence=FACEBOOK_COLORS,
                )
                fig.update_layout(
                    xaxis_title="Chamados",
                    yaxis_title="",
                    height=430,
                    clickmode="event+select",
                )
                ajustar_grafico(fig)

                evento_status = st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="grafico_chamados_por_situacao",
                    on_select="rerun",
                    selection_mode="points",
                )

        # -----------------------------------------------------------------
        # DETALHAMENTO INTERATIVO DO GRÁFICO "CHAMADOS POR SITUAÇÃO"
        # -----------------------------------------------------------------
        estado_selecionado = None

        try:
            if evento_status and evento_status.selection.points:
                ponto = evento_status.selection.points[0]
                estado_selecionado = ponto.get("y")
        except (AttributeError, IndexError, TypeError):
            estado_selecionado = None

        if estado_selecionado:
            if estado_selecionado == "Sem status":
                chamados_status = f[
                    f["Estado"].isna() | (f["Estado"].astype(str).str.strip() == "")
                ].copy()
            else:
                chamados_status = f[
                    f["Estado"].fillna("Sem status").astype(str) == str(estado_selecionado)
                ].copy()

            st.markdown(
                f"<div class='section-title'>Chamados da situação: {estado_selecionado}</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"{len(chamados_status)} chamado(s) correspondente(s) ao item selecionado no gráfico."
            )

            colunas_status = [
                c for c in [
                    "#",
                    "Atribuído a",
                    "Clientes",
                    "Tipo",
                    "Estado",
                    "Prioridade",
                    "Assunto",
                    "Criado",
                    "Tempo em aberto (dias)",
                ]
                if c in chamados_status.columns
            ]

            chamados_status = chamados_status.sort_values(
                "Tempo em aberto (dias)",
                ascending=False,
            )

            tabela_status, config_status = preparar_tabela_com_link_redmine(
                chamados_status[colunas_status]
            )

            st.dataframe(
                tabela_status,
                use_container_width=True,
                hide_index=True,
                column_config=config_status,
            )

            st.caption(
                "Clique no número do chamado para abrir diretamente no Redmine. "
                "Para trocar a seleção, clique em outra barra do gráfico."
            )
            st.divider()

        st.markdown("<div class='section-title'>Origem dos chamados ainda em aberto</div>", unsafe_allow_html=True)
        monthly = f.dropna(subset=["Criado"]).copy()
        if len(monthly):
            monthly["Mês"] = monthly["Criado"].dt.to_period("M").dt.to_timestamp()
            monthly = monthly.groupby("Mês").size().reset_index(name="Chamados ainda abertos")
            fig = px.line(monthly, x="Mês", y="Chamados ainda abertos", markers=True, color_discrete_sequence=FACEBOOK_COLORS)
            fig.update_layout(xaxis_title="", yaxis_title="Chamados ainda abertos", height=360)
            ajustar_grafico(fig)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Este gráfico mostra em que meses foram criados os chamados que continuam abertos. Ele não representa todo o volume recebido em cada mês; essa visão será incluída quando adicionarmos os chamados fechados.")

    with tab_team:
        if "Atribuído a" in f.columns and len(f):
            summary = f.groupby("Atribuído a", dropna=False).agg(
                **{
                    "Total": ("#", "count") if "#" in f.columns else ("Criado", "count"),
                    "Em atuação": ("Responsabilidade atual", lambda s: (s == "Em atuação do EDI").sum()),
                    "Aguardando": ("Responsabilidade atual", lambda s: (s == "Aguardando terceiros").sum()),
                    "+30 dias": ("Tempo em aberto (dias)", lambda s: (s > 30).sum()),
                    "+60 dias": ("Tempo em aberto (dias)", lambda s: (s > 60).sum()),
                    "Alta/Urgente": ("Prioridade crítica", "sum"),
                    "Tempo mediano em aberto": ("Tempo em aberto (dias)", "median"),
                    "Tempo médio em aberto": ("Tempo em aberto (dias)", "mean"),
                }
            ).reset_index().sort_values("Total", ascending=False)
            summary["Tempo médio em aberto"] = summary["Tempo médio em aberto"].round(1)
            st.dataframe(summary, use_container_width=True, hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                mix = f.groupby(["Atribuído a", "Tipo"]).size().reset_index(name="Chamados")
                top_types = f["Tipo"].value_counts().head(7).index
                mix = mix[mix["Tipo"].isin(top_types)]
                fig = px.bar(mix, x="Atribuído a", y="Chamados", color="Tipo", barmode="stack", color_discrete_sequence=FACEBOOK_COLORS)
                fig.update_layout(xaxis_title="", yaxis_title="Chamados", legend_title_text="Tipo de chamado", height=450)
                ajustar_grafico(fig)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                ag = f.groupby("Atribuído a")["Tempo em aberto (dias)"].median().sort_values(ascending=False).reset_index()
                fig = px.bar(ag, x="Atribuído a", y="Tempo em aberto (dias)", text_auto=".0f", color_discrete_sequence=FACEBOOK_COLORS)
                fig.update_layout(xaxis_title="", yaxis_title="Tempo mediano em aberto (dias)", height=450)
                ajustar_grafico(fig)
                st.plotly_chart(fig, use_container_width=True)

    with tab_aging:
        order = ["0–7 dias", "8–15 dias", "16–30 dias", "31–60 dias", "61–90 dias", "91–180 dias", "181–365 dias", "+365 dias", "Sem data"]
        age = f["Faixa de tempo em aberto"].value_counts().reindex(order, fill_value=0).reset_index()
        age.columns = ["Faixa", "Chamados"]
        fig = px.bar(age, x="Faixa", y="Chamados", text_auto=True, color_discrete_sequence=FACEBOOK_COLORS)
        fig.update_layout(xaxis_title="", yaxis_title="Chamados", height=400)
        ajustar_grafico(fig)
        st.plotly_chart(fig, use_container_width=True)

        old = f.sort_values("Tempo em aberto (dias)", ascending=False).head(30)
        cols_show = [c for c in ["#", "Atribuído a", "Clientes", "Tipo", "Estado", "Prioridade", "Assunto", "Criado", "Tempo em aberto (dias)"] if c in old.columns]
        st.markdown("**30 chamados há mais tempo em aberto**")
        tabela_antigos, config_antigos = preparar_tabela_com_link_redmine(old[cols_show])
        st.dataframe(
            tabela_antigos,
            use_container_width=True,
            hide_index=True,
            column_config=config_antigos,
        )

    with tab_demand:
        c1, c2 = st.columns(2)
        with c1:
            if "Tipo" in f.columns:
                t = f["Tipo"].value_counts().reset_index()
                t.columns = ["Tipo", "Chamados"]
                fig = px.bar(t.sort_values("Chamados"), x="Chamados", y="Tipo", orientation="h", text_auto=True, color_discrete_sequence=FACEBOOK_COLORS)
                fig.update_layout(xaxis_title="Chamados", yaxis_title="", height=470)
                ajustar_grafico(fig)
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            if "Prioridade" in f.columns:
                p = f["Prioridade"].value_counts().reset_index()
                p.columns = ["Prioridade", "Chamados"]
                fig = px.pie(p, names="Prioridade", values="Chamados", hole=.45, color_discrete_sequence=FACEBOOK_COLORS)
                fig.update_layout(height=470, legend_title_text="")
                ajustar_grafico(fig)
                st.plotly_chart(fig, use_container_width=True)

        if "Clientes" in f.columns:
            top = f["Clientes"].fillna("Sem cliente").value_counts().head(15).reset_index()
            top.columns = ["Cliente", "Chamados"]
            fig = px.bar(top.sort_values("Chamados"), x="Chamados", y="Cliente", orientation="h", text_auto=True, color_discrete_sequence=FACEBOOK_COLORS)
            fig.update_layout(xaxis_title="Chamados", yaxis_title="", height=500)
            ajustar_grafico(fig)
            st.plotly_chart(fig, use_container_width=True)

    with tab_detail:
        q = st.text_input("Pesquisar por número, cliente ou assunto")
        detail = f.copy()
        if q.strip():
            mask = pd.Series(False, index=detail.index)
            for col in ["#", "Clientes", "Assunto", "Descrição"]:
                if col in detail.columns:
                    mask |= detail[col].astype(str).str.contains(q, case=False, na=False, regex=False)
            detail = detail[mask]

        visible = [c for c in ["#", "Atribuído a", "Clientes", "Projeto", "Tipo", "Estado", "Prioridade", "Assunto", "Criado", "Alterado", "Data de fim", "Tempo em aberto (dias)"] if c in detail.columns]

        detalhe_ordenado = detail[visible].sort_values(
            "Tempo em aberto (dias)",
            ascending=False
        )

        tabela_detalhe, config_detalhe = preparar_tabela_com_link_redmine(
            detalhe_ordenado
        )

        st.dataframe(
            tabela_detalhe,
            use_container_width=True,
            hide_index=True,
            column_config=config_detalhe,
        )

        # O CSV continua contendo o ID puro do chamado, sem transformar em URL.
        csv_out = detalhe_ordenado.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("Baixar chamados filtrados (CSV)", data=csv_out, file_name="edi_backlog_filtrado.csv", mime="text/csv")

    st.divider()
    st.caption(
        "Versão 3.2 — integração com a API do Redmine, acesso direto aos chamados pelo ID e detalhamento interativo por situação. O CSV permanece disponível como contingência."
    )
