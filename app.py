from __future__ import annotations

import io
import os
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
from redmine_api import buscar_chamados_projetos, issue_para_linha, carregar_catalogos_redmine
from ednna.primeiro_combate import filtrar_estado_aberto_dataframe

try:
    from redmine_api import obter_diagnostico_redmine
except ImportError:
    def obter_diagnostico_redmine():
        return {
            "tempo_listagem_s": 0.0,
            "tempo_detalhes_s": 0.0,
            "tempo_total_s": 0.0,
            "chamados_encontrados": 0,
            "com_custom_fields": 0,
            "detalhes_consultados": 0,
            "modo_compatibilidade": True,
        }


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



def _normalizar_lista_clientes(valor) -> list[str]:
    """Converte o campo interno de clientes para uma lista limpa."""
    if isinstance(valor, (list, tuple, set)):
        return [str(x).strip() for x in valor if str(x).strip()]

    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return []

    texto = str(valor).strip()
    if not texto:
        return []

    # API V3.5 utiliza " / " para múltiplos clientes.
    return [x.strip() for x in texto.split(" / ") if x.strip()]


def lista_clientes_linha(row: pd.Series) -> list[str]:
    if "_Clientes_lista" in row.index:
        lista = _normalizar_lista_clientes(row.get("_Clientes_lista"))
        if lista:
            return lista
    return _normalizar_lista_clientes(row.get("Clientes"))


def todos_clientes(frame: pd.DataFrame) -> list[str]:
    valores: set[str] = set()
    for _, row in frame.iterrows():
        valores.update(lista_clientes_linha(row))
    return sorted(valores)


def filtrar_por_clientes(frame: pd.DataFrame, selecionados: list[str]) -> pd.DataFrame:
    if not selecionados:
        return frame

    alvo = set(map(str, selecionados))
    mascara = frame.apply(
        lambda row: bool(alvo.intersection(lista_clientes_linha(row))),
        axis=1,
    )
    return frame[mascara]


def mascara_cliente(frame: pd.DataFrame, cliente: str) -> pd.Series:
    cliente = str(cliente)
    return frame.apply(
        lambda row: cliente in lista_clientes_linha(row),
        axis=1,
    )


def ranking_clientes(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Conta cada cliente individualmente.

    Como o campo Clientes do Redmine aceita múltiplos valores, um chamado
    associado a dois clientes contribui uma vez para cada cliente.
    """
    valores: list[str] = []
    for _, row in frame.iterrows():
        clientes = lista_clientes_linha(row)
        valores.extend(clientes or ["Sem cliente"])

    if not valores:
        return pd.DataFrame(columns=["Cliente", "Chamados"])

    ranking = (
        pd.Series(valores, dtype="object")
        .value_counts()
        .rename_axis("Cliente")
        .reset_index(name="Chamados")
    )
    return ranking.sort_values(["Chamados", "Cliente"], ascending=[False, True])


def legenda_interativa(
    frame: pd.DataFrame,
    coluna: str,
    titulo: str,
    chave_estado: str,
    key_prefix: str,
    valores: list[str] | None = None,
    max_por_linha: int = 4,
):
    """
    Renderiza uma legenda clicável com botões.

    O Plotly usa o clique da legenda nativa para mostrar/ocultar séries.
    Estes botões funcionam como uma legenda de navegação: ao clicar,
    o painel abre os chamados daquela categoria.
    """
    if coluna not in frame.columns:
        return

    serie = frame[coluna].fillna("Sem informação").astype(str)
    contagens = serie.value_counts()

    categorias = valores or contagens.index.tolist()
    categorias = [str(v) for v in categorias if str(v) in contagens.index]

    if not categorias:
        return

    st.caption(titulo)

    for inicio in range(0, len(categorias), max_por_linha):
        grupo = categorias[inicio:inicio + max_por_linha]
        colunas = st.columns(len(grupo))

        for coluna_ui, valor in zip(colunas, grupo):
            quantidade = int(contagens.get(valor, 0))
            with coluna_ui:
                if st.button(
                    f"{valor} · {quantidade}",
                    key=f"{key_prefix}_{inicio}_{valor}",
                    width="stretch",
                ):
                    st.session_state[chave_estado] = valor


def registrar_selecao_status():
    """
    Captura a seleção do gráfico de status no momento do evento e salva
    a categoria escolhida em um estado próprio da sessão.

    Isso evita perder a seleção durante a reexecução automática do Streamlit.
    """
    estado_grafico = st.session_state.get("grafico_chamados_por_situacao", {})
    selecao = estado_grafico.get("selection", {}) if estado_grafico else {}
    pontos = selecao.get("points", []) if selecao else []

    if not pontos:
        return

    ponto = pontos[0]
    estado = ponto.get("y")

    if estado is not None:
        st.session_state["estado_status_selecionado"] = str(estado)


def registrar_selecao_generica(chave_grafico: str, chave_estado: str, campo: str):
    estado_grafico = st.session_state.get(chave_grafico, {})
    selecao = estado_grafico.get("selection", {}) if estado_grafico else {}
    pontos = selecao.get("points", []) if selecao else []
    if pontos:
        valor = pontos[0].get(campo)
        if valor is not None:
            st.session_state[chave_estado] = str(valor)


def mostrar_chamados_selecionados(
    frame: pd.DataFrame,
    titulo: str,
    chave_estado: str,
    coluna_filtro: str,
    valor: str | None = None,
    mascara=None,
    key_prefix: str = "detalhe",
):
    selecionado = valor if valor is not None else st.session_state.get(chave_estado)
    if not selecionado:
        return

    if mascara is not None:
        detalhe = frame[mascara(frame, selecionado)].copy()
    elif coluna_filtro in frame.columns:
        detalhe = frame[
            frame[coluna_filtro].fillna("Sem informação").astype(str) == str(selecionado)
        ].copy()
    else:
        return

    st.markdown(
        f"<div class='section-title'>{titulo}: {selecionado}</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"{len(detalhe)} chamado(s) correspondente(s) ao item selecionado.")

    colunas = [
        c for c in [
            "#", "Atribuído a", "Clientes", "Projeto", "Tipo", "Estado",
            "Prioridade", "Assunto", "Criado", "Tempo em aberto (dias)"
        ] if c in detalhe.columns
    ]

    if "Tempo em aberto (dias)" in detalhe.columns:
        detalhe = detalhe.sort_values("Tempo em aberto (dias)", ascending=False)

    tabela, config = preparar_tabela_com_link_redmine(detalhe[colunas])
    st.dataframe(tabela, width="stretch", hide_index=True, column_config=config)

    a1, a2 = st.columns([1, 4])
    with a1:
        if st.button("Fechar seleção", key=f"fechar_{key_prefix}", width="stretch"):
            st.session_state.pop(chave_estado, None)
            st.rerun()
    with a2:
        st.caption("Clique no número do chamado para abrir diretamente no Redmine.")


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
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <div class="fb-badge">● Dados operacionais</div>
        <div class="fb-badge">🤖 EDNNA ativa</div>
      </div>
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
def carregar_api_abertos():
    inicio = time.perf_counter()

    inicio_redmine = time.perf_counter()
    chamados = buscar_chamados_projetos(status_id="open")
    tempo_redmine_total = round(time.perf_counter() - inicio_redmine, 3)

    diagnostico_redmine = obter_diagnostico_redmine()
    if diagnostico_redmine.get("modo_compatibilidade"):
        diagnostico_redmine["tempo_total_s"] = tempo_redmine_total
        diagnostico_redmine["tempo_listagem_s"] = tempo_redmine_total
        diagnostico_redmine["chamados_encontrados"] = len(chamados)

    inicio_catalogo = time.perf_counter()
    catalogos = carregar_catalogos_redmine()
    tempo_catalogo = round(time.perf_counter() - inicio_catalogo, 3)

    inicio_dataframe = time.perf_counter()
    linhas = [
        issue_para_linha(
            chamado,
            mapa_clientes=catalogos.get("clientes", {}),
            mapa_origens=catalogos.get("origens", {}),
        )
        for chamado in chamados
    ]
    raw_df = pd.DataFrame(linhas)
    tempo_dataframe = round(time.perf_counter() - inicio_dataframe, 3)

    diagnostico = {
        **diagnostico_redmine,
        "tempo_catalogo_s": tempo_catalogo,
        "tempo_dataframe_s": tempo_dataframe,
        "tempo_backend_s": round(time.perf_counter() - inicio, 3),
        "catalogo_ok": catalogos.get("ok", False),
        "qtd_clientes": catalogos.get("qtd_clientes", 0),
        "qtd_origens": catalogos.get("qtd_origens", 0),
        "erro_catalogo": catalogos.get("erro"),
    }

    return raw_df, diagnostico


def classificar_erro_api(exc: Exception) -> tuple[str, str]:
    """
    Retorna título e orientação amigável conforme o tipo de falha.
    """
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return (
            "Tempo esgotado ao conectar com o Redmine",
            "O Azure não conseguiu estabelecer a conexão HTTPS com o Redmine "
            "mesmo após as tentativas automáticas. Isso normalmente indica "
            "indisponibilidade temporária, oscilação de rede, nginx/proxy ou rota.",
        )

    if isinstance(exc, requests.exceptions.ReadTimeout):
        return (
            "O Redmine demorou demais para responder",
            "A conexão foi estabelecida, mas a resposta não chegou dentro do tempo limite. "
            "Tente novamente em alguns instantes.",
        )

    if isinstance(exc, requests.exceptions.ConnectionError):
        return (
            "Falha de comunicação com o Redmine",
            "Não foi possível completar a comunicação entre o Azure e o Redmine. "
            "A aplicação continuará usando a última carga válida, quando disponível.",
        )

    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status in (401, 403):
            return (
                f"Redmine recusou a autenticação ({status})",
                "Nesse caso, confira REDMINE_API_KEY e REDMINE_AUTHORIZATION.",
            )
        return (
            f"Redmine retornou erro HTTP {status or ''}".strip(),
            "A conexão ocorreu, mas o servidor respondeu com erro HTTP.",
        )

    return (
        "Não foi possível consultar a API do Redmine",
        "Consulte o diagnóstico técnico abaixo. Se o erro for de autenticação, "
        "revise as variáveis do ambiente; se for de conexão, aguarde e tente novamente.",
    )


# -------------------------------------------------------------------------
# CARGA DOS DADOS
# -------------------------------------------------------------------------
diagnostico_catalogos = None

if fonte == "API do Redmine":
    with filter_col:
        st.caption("Atualização automática. Cache de 5 minutos.")
        if st.button("Atualizar dados agora", width="stretch"):
            carregar_api_abertos.clear()

    usando_ultima_carga = False
    erro_atualizacao = None

    try:
        with main_col:
            with st.spinner("Consultando os chamados no Redmine..."):
                raw_df, diagnostico_catalogos = carregar_api_abertos()

        if raw_df.empty:
            raise RuntimeError("A API não retornou chamados em aberto.")

        # Guarda a última carga válida desta sessão do navegador.
        st.session_state["ultima_carga_api_df"] = raw_df.copy()
        st.session_state["ultima_carga_api_diagnostico"] = diagnostico_catalogos
        st.session_state["ultima_carga_api_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    except Exception as exc:
        erro_atualizacao = exc
        ultima_df = st.session_state.get("ultima_carga_api_df")

        if isinstance(ultima_df, pd.DataFrame) and not ultima_df.empty:
            raw_df = ultima_df.copy()
            diagnostico_catalogos = st.session_state.get(
                "ultima_carga_api_diagnostico", {}
            )
            usando_ultima_carga = True
        else:
            titulo_erro, orientacao = classificar_erro_api(exc)
            with main_col:
                st.error(f"{titulo_erro}: {exc}")
                st.info(orientacao)
            st.stop()

    df = prepare(raw_df, origem="api")

    with main_col:
        if usando_ultima_carga:
            titulo_erro, orientacao = classificar_erro_api(erro_atualizacao)
            ultima_em = st.session_state.get("ultima_carga_api_em", "horário não informado")
            st.warning(
                f"⚠️ Atualização do Redmine falhou. Exibindo a última carga válida "
                f"desta sessão ({ultima_em})."
            )
            with st.expander("Detalhes da falha de atualização", expanded=False):
                st.write(f"**{titulo_erro}**")
                st.write(orientacao)
                st.code(str(erro_atualizacao))
        elif diagnostico_catalogos:
            if diagnostico_catalogos.get("catalogo_ok"):
                modo = "compatibilidade" if diagnostico_catalogos.get("modo_compatibilidade") else "otimizado"
                st.success(
                    "API Redmine: OK  •  "
                    f"{diagnostico_catalogos.get('chamados_encontrados', 0)} chamados  •  "
                    f"Backend: {diagnostico_catalogos.get('tempo_backend_s', 0):.2f}s  •  "
                    f"Modo: {modo}"
                )
            else:
                st.warning(
                    "Chamados carregados, mas o catálogo de nomes não foi carregado. "
                    f"Diagnóstico: {diagnostico_catalogos.get('erro_catalogo') or 'não informado'}"
                )

        if diagnostico_catalogos:
            with st.expander("Desempenho da carga", expanded=False):
                st.write({
                    "Chamados encontrados": diagnostico_catalogos.get("chamados_encontrados", 0),
                    "Chamados já com campos personalizados": diagnostico_catalogos.get("com_custom_fields", 0),
                    "Detalhes adicionais consultados": diagnostico_catalogos.get("detalhes_consultados", 0),
                    "Projetos consultados": diagnostico_catalogos.get("projetos_consultados", 0),
                    "Páginas consultadas": diagnostico_catalogos.get("paginas_consultadas", 0),
                    "Listagem Redmine (s)": diagnostico_catalogos.get("tempo_listagem_s", 0),
                    "Detalhes individuais (s)": diagnostico_catalogos.get("tempo_detalhes_s", 0),
                    "Catálogo Clientes/Origem (s)": diagnostico_catalogos.get("tempo_catalogo_s", 0),
                    "Montagem do DataFrame (s)": diagnostico_catalogos.get("tempo_dataframe_s", 0),
                    "Backend total (s)": diagnostico_catalogos.get("tempo_backend_s", 0),
                    "Modo compatibilidade": diagnostico_catalogos.get("modo_compatibilidade", False),
                    "Usando última carga válida": usando_ultima_carga,
                })

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
        clients = st.multiselect(
            "Cliente",
            todos_clientes(df),
            placeholder="Selecione",
        )

f = df.copy()

for col, vals in [
    ("Atribuído a", assignees),
    ("Estado", statuses),
    ("Prioridade", priorities),
    ("Tipo", types),
    ("Projeto", projects),
]:
    if vals and col in f.columns:
        f = f[f[col].astype(str).isin(vals)]

# O campo Clientes pode conter mais de um valor por chamado.
# O filtro considera cada cliente individualmente.
f = filtrar_por_clientes(f, clients)

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

    tab_exec, tab_ednna, tab_team, tab_aging, tab_demand, tab_detail = st.tabs(
        [
            "Visão geral",
            "🤖 EDNNA",
            "Equipe",
            "Tempo em aberto",
            "Tipos de demanda",
            "Lista de chamados",
        ]
    )

    with tab_exec:
        c1, c2 = st.columns([1.15, 1])
        with c1:
            st.markdown("<div class='section-title'>Distribuição dos chamados por responsável</div>", unsafe_allow_html=True)
            if "Atribuído a" in f.columns and len(f):
                resp = f.groupby(["Atribuído a", "Responsabilidade atual"], dropna=False).size().reset_index(name="Chamados")
                fig = px.bar(resp, x="Atribuído a", y="Chamados", color="Responsabilidade atual", barmode="stack",
                             text_auto=True, color_discrete_sequence=FACEBOOK_COLORS, labels={"Atribuído a":"Responsável", "Responsabilidade atual":"Situação"})
                fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="Chamados", height=430)
                ajustar_grafico(fig)
                st.caption("Clique em uma barra para abrir os chamados do responsável.")
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_responsavel",
                    on_select=lambda: registrar_selecao_generica(
                        "grafico_responsavel", "sel_responsavel", "x"
                    ),
                    selection_mode="points",
                )
                mostrar_chamados_selecionados(
                    f, "Chamados do responsável", "sel_responsavel",
                    "Atribuído a", key_prefix="responsavel"
                )
                legenda_interativa(
                    f,
                    "Responsabilidade atual",
                    "Legenda interativa — clique para abrir os chamados:",
                    "sel_responsabilidade_legenda",
                    "legenda_responsabilidade",
                    valores=["Em atuação do EDI", "Aguardando terceiros"],
                    max_por_linha=2,
                )
                mostrar_chamados_selecionados(
                    f,
                    "Chamados",
                    "sel_responsabilidade_legenda",
                    "Responsabilidade atual",
                    key_prefix="responsabilidade_legenda",
                )
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

                st.caption("Clique em uma barra para abrir os chamados daquela situação.")

                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_chamados_por_situacao",
                    on_select=registrar_selecao_status,
                    selection_mode="points",
                )

        # -----------------------------------------------------------------
        # DETALHAMENTO INTERATIVO DO GRÁFICO "CHAMADOS POR SITUAÇÃO"
        # -----------------------------------------------------------------
        estado_selecionado = st.session_state.get("estado_status_selecionado")

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
                width="stretch",
                hide_index=True,
                column_config=config_status,
            )

            acao1, acao2 = st.columns([1, 4])
            with acao1:
                if st.button(
                    "Fechar seleção",
                    key="fechar_selecao_status",
                    width="stretch",
                ):
                    st.session_state.pop("estado_status_selecionado", None)
                    st.rerun()

            with acao2:
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
            st.caption("Clique em um ponto para abrir os chamados ainda abertos criados naquele mês.")
            st.plotly_chart(
                fig,
                width="stretch",
                key="grafico_mes_origem",
                on_select=lambda: registrar_selecao_generica(
                    "grafico_mes_origem", "sel_mes_origem", "x"
                ),
                selection_mode="points",
            )

            mes_sel = st.session_state.get("sel_mes_origem")
            if mes_sel:
                try:
                    mes_ts = pd.to_datetime(mes_sel)
                    mascara_mes = (
                        (f["Criado"].dt.year == mes_ts.year) &
                        (f["Criado"].dt.month == mes_ts.month)
                    )
                    detalhe_mes = f[mascara_mes].copy()
                    rotulo_mes = mes_ts.strftime("%m/%Y")
                    st.markdown(
                        f"<div class='section-title'>Chamados criados em {rotulo_mes}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{len(detalhe_mes)} chamado(s) ainda aberto(s) criado(s) no mês selecionado.")
                    cols_mes = [c for c in ["#", "Atribuído a", "Clientes", "Tipo", "Estado", "Prioridade", "Assunto", "Criado", "Tempo em aberto (dias)"] if c in detalhe_mes.columns]
                    tabela_mes, config_mes = preparar_tabela_com_link_redmine(
                        detalhe_mes.sort_values("Tempo em aberto (dias)", ascending=False)[cols_mes]
                    )
                    st.dataframe(tabela_mes, width="stretch", hide_index=True, column_config=config_mes)
                    if st.button("Fechar seleção", key="fechar_mes_origem"):
                        st.session_state.pop("sel_mes_origem", None)
                        st.rerun()
                except Exception:
                    pass

            st.caption("Este gráfico mostra em que meses foram criados os chamados que continuam abertos. Ele não representa todo o volume recebido em cada mês; essa visão será incluída quando adicionarmos os chamados fechados.")


    with tab_ednna:
        st.markdown(
            "<div class='section-title'>EDNNA — Inteligência Operacional EDI</div>",
            unsafe_allow_html=True,
        )

        st.caption(
            "Primeiro combate dos chamados: identificação dos tickets que permanecem "
            "no estado Aberto e ainda precisam de análise operacional."
        )

        # Nesta primeira etapa, a EDNNA reaproveita os dados que o dashboard
        # já carregou do Redmine. Nenhuma nova consulta é feita aqui e nenhuma
        # alteração é realizada no chamado.
        ednna_abertos = filtrar_estado_aberto_dataframe(f)

        total_abertos_ednna = len(ednna_abertos)

        mais_1_dia = (
            int((ednna_abertos["Tempo em aberto (dias)"] >= 1).sum())
            if "Tempo em aberto (dias)" in ednna_abertos.columns
            else 0
        )

        criticos_ednna = (
            int(ednna_abertos["Prioridade crítica"].sum())
            if "Prioridade crítica" in ednna_abertos.columns
            else 0
        )

        sem_responsavel = (
            int(
                ednna_abertos["Atribuído a"]
                .fillna("")
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )
            if "Atribuído a" in ednna_abertos.columns
            else 0
        )

        k1, k2, k3, k4 = st.columns(4)

        k1.metric(
            "Aguardando análise EDNNA",
            f"{total_abertos_ednna:,}".replace(",", "."),
        )

        k2.metric(
            "Há 1 dia ou mais",
            f"{mais_1_dia:,}".replace(",", "."),
        )

        k3.metric(
            "Alta / Urgente",
            f"{criticos_ednna:,}".replace(",", "."),
        )

        k4.metric(
            "Sem responsável",
            f"{sem_responsavel:,}".replace(",", "."),
        )

        st.divider()

        if ednna_abertos.empty:
            st.success(
                "Não existem chamados no estado Aberto no filtro atual."
            )

        else:
            st.markdown(
                "<div class='section-title'>Fila de primeiro combate</div>",
                unsafe_allow_html=True,
            )

            st.caption(
                "A EDNNA ainda está em modo de observação. Nesta etapa ela apenas "
                "identifica os candidatos ao primeiro combate; nenhuma ação é "
                "realizada automaticamente no Redmine."
            )

            # Busca textual específica da EDNNA.
            pesquisa_ednna = st.text_input(
                "Pesquisar na fila EDNNA",
                placeholder="Número, cliente, origem ou assunto",
                key="pesquisa_fila_ednna",
            )

            fila_ednna = ednna_abertos.copy()

            if pesquisa_ednna.strip():
                termo = pesquisa_ednna.strip()
                mascara_busca = pd.Series(False, index=fila_ednna.index)

                for coluna in ["#", "Clientes", "Origem", "Tipo", "Assunto", "Descrição"]:
                    if coluna in fila_ednna.columns:
                        mascara_busca |= (
                            fila_ednna[coluna]
                            .astype(str)
                            .str.contains(
                                termo,
                                case=False,
                                na=False,
                                regex=False,
                            )
                        )

                fila_ednna = fila_ednna[mascara_busca]

            # Chamados críticos primeiro; depois os mais antigos.
            colunas_ordenacao = []
            ascending = []

            if "Prioridade crítica" in fila_ednna.columns:
                colunas_ordenacao.append("Prioridade crítica")
                ascending.append(False)

            if "Tempo em aberto (dias)" in fila_ednna.columns:
                colunas_ordenacao.append("Tempo em aberto (dias)")
                ascending.append(False)

            if colunas_ordenacao:
                fila_ednna = fila_ednna.sort_values(
                    colunas_ordenacao,
                    ascending=ascending,
                )

            colunas_ednna = [
                coluna
                for coluna in [
                    "#",
                    "Clientes",
                    "Origem",
                    "Atribuído a",
                    "Projeto",
                    "Tipo",
                    "Prioridade",
                    "Assunto",
                    "Criado",
                    "Tempo em aberto (dias)",
                ]
                if coluna in fila_ednna.columns
            ]

            tabela_ednna, config_ednna = preparar_tabela_com_link_redmine(
                fila_ednna[colunas_ednna]
            )

            st.dataframe(
                tabela_ednna,
                width="stretch",
                hide_index=True,
                column_config=config_ednna,
            )

            st.caption(
                f"{len(fila_ednna)} chamado(s) exibido(s) na fila atual. "
                "Clique no número para abrir diretamente no Redmine."
            )

            st.divider()

            st.markdown(
                "<div class='section-title'>Próxima evolução da EDNNA</div>",
                unsafe_allow_html=True,
            )

            st.info(
                "Na próxima etapa vamos analisar o histórico (journals) dos chamados "
                "para separar os que realmente ainda não tiveram primeiro combate. "
                "Depois disso entra o classificador de solicitações e o catálogo "
                "de automações por adquirente."
            )

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
            st.dataframe(summary, width="stretch", hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                mix = f.groupby(["Atribuído a", "Tipo"]).size().reset_index(name="Chamados")
                top_types = f["Tipo"].value_counts().head(7).index
                mix = mix[mix["Tipo"].isin(top_types)]
                fig = px.bar(mix, x="Atribuído a", y="Chamados", color="Tipo", barmode="stack", color_discrete_sequence=FACEBOOK_COLORS)
                fig.update_layout(xaxis_title="", yaxis_title="Chamados", legend_title_text="Tipo de chamado", height=450)
                ajustar_grafico(fig)
                st.caption("Clique em um segmento para abrir os chamados daquele responsável e tipo.")
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_equipe_tipo",
                    on_select=lambda: registrar_selecao_generica(
                        "grafico_equipe_tipo", "sel_equipe_resp", "x"
                    ),
                    selection_mode="points",
                )
                legenda_interativa(
                    f[f["Tipo"].isin(top_types)],
                    "Tipo",
                    "Legenda interativa — clique no tipo para abrir os chamados:",
                    "sel_tipo_legenda_equipe",
                    "legenda_tipo_equipe",
                    valores=[str(x) for x in top_types],
                    max_por_linha=3,
                )
                mostrar_chamados_selecionados(
                    f,
                    "Chamados do tipo",
                    "sel_tipo_legenda_equipe",
                    "Tipo",
                    key_prefix="tipo_legenda_equipe",
                )
                resp_sel = st.session_state.get("sel_equipe_resp")
                if resp_sel:
                    mostrar_chamados_selecionados(
                        f, "Chamados do responsável", "sel_equipe_resp",
                        "Atribuído a", key_prefix="equipe_resp"
                    )
            with c2:
                ag = f.groupby("Atribuído a")["Tempo em aberto (dias)"].median().sort_values(ascending=False).reset_index()
                fig = px.bar(ag, x="Atribuído a", y="Tempo em aberto (dias)", text_auto=".0f", color_discrete_sequence=FACEBOOK_COLORS)
                fig.update_layout(xaxis_title="", yaxis_title="Tempo mediano em aberto (dias)", height=450)
                ajustar_grafico(fig)
                st.caption("Clique em uma barra para abrir os chamados do responsável.")
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_tempo_mediano_responsavel",
                    on_select=lambda: registrar_selecao_generica(
                        "grafico_tempo_mediano_responsavel", "sel_mediana_resp", "x"
                    ),
                    selection_mode="points",
                )
                mostrar_chamados_selecionados(
                    f, "Chamados do responsável", "sel_mediana_resp",
                    "Atribuído a", key_prefix="mediana_resp"
                )

    with tab_aging:
        order = ["0–7 dias", "8–15 dias", "16–30 dias", "31–60 dias", "61–90 dias", "91–180 dias", "181–365 dias", "+365 dias", "Sem data"]
        age = f["Faixa de tempo em aberto"].value_counts().reindex(order, fill_value=0).reset_index()
        age.columns = ["Faixa", "Chamados"]
        fig = px.bar(age, x="Faixa", y="Chamados", text_auto=True, color_discrete_sequence=FACEBOOK_COLORS)
        fig.update_layout(xaxis_title="", yaxis_title="Chamados", height=400)
        ajustar_grafico(fig)
        st.caption("Clique em uma faixa para abrir os chamados correspondentes.")
        st.plotly_chart(
            fig,
            width="stretch",
            key="grafico_faixa_tempo",
            on_select=lambda: registrar_selecao_generica(
                "grafico_faixa_tempo", "sel_faixa_tempo", "x"
            ),
            selection_mode="points",
        )
        mostrar_chamados_selecionados(
            f, "Chamados na faixa", "sel_faixa_tempo",
            "Faixa de tempo em aberto", key_prefix="faixa_tempo"
        )

        old = f.sort_values("Tempo em aberto (dias)", ascending=False).head(30)
        cols_show = [c for c in ["#", "Atribuído a", "Clientes", "Tipo", "Estado", "Prioridade", "Assunto", "Criado", "Tempo em aberto (dias)"] if c in old.columns]
        st.markdown("**30 chamados há mais tempo em aberto**")
        tabela_antigos, config_antigos = preparar_tabela_com_link_redmine(old[cols_show])
        st.dataframe(
            tabela_antigos,
            width="stretch",
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
                st.caption("Clique em uma barra para abrir os chamados daquele tipo.")
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_tipo_demanda",
                    on_select=lambda: registrar_selecao_generica(
                        "grafico_tipo_demanda", "sel_tipo_demanda", "y"
                    ),
                    selection_mode="points",
                )
                mostrar_chamados_selecionados(
                    f, "Chamados do tipo", "sel_tipo_demanda",
                    "Tipo", key_prefix="tipo_demanda"
                )
        with c2:
            if "Prioridade" in f.columns:
                p = f["Prioridade"].value_counts().reset_index()
                p.columns = ["Prioridade", "Chamados"]
                fig = px.pie(
                    p,
                    names="Prioridade",
                    values="Chamados",
                    hole=.45,
                    color_discrete_sequence=FACEBOOK_COLORS,
                    custom_data=["Prioridade"],
                )
                fig.update_layout(height=470, legend_title_text="")
                ajustar_grafico(fig)
                st.caption("Clique em uma fatia para abrir os chamados daquela prioridade.")
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_prioridade",
                    on_select=lambda: registrar_selecao_generica(
                        "grafico_prioridade", "sel_prioridade", "label"
                    ),
                    selection_mode="points",
                )
                mostrar_chamados_selecionados(
                    f, "Chamados com prioridade", "sel_prioridade",
                    "Prioridade", key_prefix="prioridade"
                )
                legenda_interativa(
                    f,
                    "Prioridade",
                    "Legenda interativa — clique na prioridade para abrir os chamados:",
                    "sel_prioridade_legenda",
                    "legenda_prioridade",
                    valores=p["Prioridade"].astype(str).tolist(),
                    max_por_linha=3,
                )
                mostrar_chamados_selecionados(
                    f,
                    "Chamados com prioridade",
                    "sel_prioridade_legenda",
                    "Prioridade",
                    key_prefix="prioridade_legenda",
                )

        if "Clientes" in f.columns:
            st.markdown(
                "<div class='section-title'>Ranking de chamados por cliente</div>",
                unsafe_allow_html=True,
            )

            ranking = ranking_clientes(f)

            if len(ranking):
                # Mantemos o gráfico legível. A tabela abaixo preserva o ranking
                # completo para consulta.
                top = ranking.head(20).copy()

                # Ascendente no dataframe para que o maior apareça no topo
                # do gráfico horizontal do Plotly.
                grafico_clientes = top.sort_values(
                    ["Chamados", "Cliente"],
                    ascending=[True, False],
                )

                fig = px.bar(
                    grafico_clientes,
                    x="Chamados",
                    y="Cliente",
                    orientation="h",
                    text="Chamados",
                    color_discrete_sequence=FACEBOOK_COLORS,
                )
                fig.update_traces(
                    texttemplate="%{text} chamados",
                    textposition="outside",
                    cliponaxis=False,
                )
                fig.update_layout(
                    xaxis_title="Chamados",
                    yaxis_title="",
                    height=max(520, 32 * len(grafico_clientes)),
                    margin=dict(l=20, r=90, t=35, b=20),
                )
                ajustar_grafico(fig)

                st.caption(
                    "Ranking dos 20 clientes com mais chamados no filtro atual. "
                    "Clique em uma barra para abrir os chamados daquele cliente."
                )

                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="grafico_cliente",
                    on_select=lambda: registrar_selecao_generica(
                        "grafico_cliente", "sel_cliente", "y"
                    ),
                    selection_mode="points",
                )

                cliente_sel = st.session_state.get("sel_cliente")
                if cliente_sel:
                    mostrar_chamados_selecionados(
                        f,
                        "Chamados do cliente",
                        "sel_cliente",
                        "Clientes",
                        mascara=lambda frame, valor: mascara_cliente(frame, valor),
                        key_prefix="cliente",
                    )

                with st.expander("Ver ranking completo de clientes", expanded=False):
                    ranking_exibicao = ranking.copy()
                    ranking_exibicao.insert(
                        0,
                        "Posição",
                        range(1, len(ranking_exibicao) + 1),
                    )
                    st.dataframe(
                        ranking_exibicao,
                        width="stretch",
                        hide_index=True,
                    )
            else:
                st.info("Não há clientes disponíveis no filtro atual.")

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
            width="stretch",
            hide_index=True,
            column_config=config_detalhe,
        )

        # O CSV continua contendo o ID puro do chamado, sem transformar em URL.
        csv_out = detalhe_ordenado.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("Baixar chamados filtrados (CSV)", data=csv_out, file_name="edi_backlog_filtrado.csv", mime="text/csv")

    st.divider()
    st.caption(
        "Versão 3.6.0 — EDNNA integrada ao dashboard: fila inicial de primeiro combate, mantendo a consulta Redmine resiliente."
    )