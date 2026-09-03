from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


# ============================================================
# EDNNA — INTELIGÊNCIA OPERACIONAL EDI
# Módulo: Armazenamento
#
# Responsabilidades:
#
# - manter a memória operacional da EDNNA;
# - armazenar snapshot dos chamados;
# - armazenar journals;
# - armazenar análises de primeiro combate;
# - fornecer contingência quando o Redmine estiver indisponível.
#
# Azure App Service:
# banco persistente em /home/data/ednna.db
# ============================================================


FUSO_BRASIL = ZoneInfo(
    "America/Sao_Paulo"
)


# ============================================================
# DATA / HORA
# ============================================================

def agora_brasil_iso() -> str:
    """
    Retorna data/hora atual de São Paulo
    no padrão ISO 8601.
    """

    return datetime.now(
        FUSO_BRASIL
    ).isoformat(
        timespec="seconds"
    )


# ============================================================
# CAMINHO DO BANCO
# ============================================================
#
# Azure App Service Linux:
#
# somente /home é persistente.
#
# Local:
#
# ./data/ednna.db
#
# Pode ser sobrescrito pela variável:
#
# EDNNA_DB_PATH=/home/data/ednna.db
# ============================================================

def obter_caminho_banco() -> Path:
    """
    Define o local do banco SQLite da EDNNA.

    Ordem de prioridade:

    1. EDNNA_DB_PATH
    2. Azure App Service -> /home/data/ednna.db
    3. Ambiente local -> data/ednna.db
    """

    caminho_configurado = os.getenv(
        "EDNNA_DB_PATH",
        "",
    ).strip()

    if caminho_configurado:

        caminho = Path(
            caminho_configurado
        )

    elif os.getenv(
        "WEBSITE_INSTANCE_ID"
    ):

        caminho = Path(
            "/home/data/ednna.db"
        )

    else:

        caminho = Path(
            "data/ednna.db"
        )

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return caminho


DB_PATH = obter_caminho_banco()


# ============================================================
# CONEXÃO
# ============================================================

@contextmanager
def conectar() -> Iterator[
    sqlite3.Connection
]:
    """
    Abre uma conexão SQLite controlada.

    Para este MVP não utilizamos WAL.

    No Azure App Service o banco ficará em /home,
    utilizando armazenamento persistente.

    busy_timeout evita falhas imediatas caso duas
    operações tentem acessar o SQLite ao mesmo tempo.
    """

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )

        yield conn

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# CRIAÇÃO DAS TABELAS
# ============================================================

def inicializar_banco() -> None:
    """
    Cria as tabelas da EDNNA caso
    ainda não existam.

    CREATE TABLE IF NOT EXISTS permite executar
    esta função em todo início da aplicação sem
    perder os dados existentes.
    """

    with conectar() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chamados (
                id INTEGER PRIMARY KEY,

                cliente TEXT,
                origem TEXT,
                responsavel TEXT,
                projeto TEXT,
                tipo TEXT,
                estado TEXT,
                prioridade TEXT,
                assunto TEXT,

                criado_em TEXT,
                alterado_em TEXT,

                tempo_aberto_dias REAL,

                payload_json TEXT,

                sincronizado_em TEXT NOT NULL
            );


            CREATE INDEX IF NOT EXISTS idx_chamados_estado
            ON chamados (estado);


            CREATE INDEX IF NOT EXISTS idx_chamados_alterado
            ON chamados (alterado_em);


            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY,

                chamado_id INTEGER NOT NULL,

                autor TEXT,
                criado_em TEXT,
                notas TEXT,

                detalhes_json TEXT,

                sincronizado_em TEXT NOT NULL,

                FOREIGN KEY (chamado_id)
                    REFERENCES chamados(id)
                    ON DELETE CASCADE
            );


            CREATE INDEX IF NOT EXISTS idx_journals_chamado
            ON journals (chamado_id);


            CREATE TABLE IF NOT EXISTS analises_primeiro_combate (
                chamado_id INTEGER PRIMARY KEY,

                alterado_em_redmine TEXT,

                situacao TEXT NOT NULL,

                teve_atuacao INTEGER
                    NOT NULL
                    DEFAULT 0,

                autor_primeira_atuacao TEXT,
                data_primeira_atuacao TEXT,
                tipo_primeira_atuacao TEXT,

                erro TEXT,

                analisado_em TEXT NOT NULL,

                FOREIGN KEY (chamado_id)
                    REFERENCES chamados(id)
                    ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS classificacoes_demandas (
                chamado_id INTEGER PRIMARY KEY,

                alterado_em_redmine TEXT,

                intencao TEXT NOT NULL,

                confianca REAL NOT NULL DEFAULT 0,

                regra_candidata TEXT,

                acao_sugerida TEXT,

                executavel INTEGER NOT NULL DEFAULT 0,

                evidencias_json TEXT,

                classificado_em TEXT NOT NULL,

                FOREIGN KEY (chamado_id)
                    REFERENCES chamados(id)
                    ON DELETE CASCADE
            );


            CREATE INDEX IF NOT EXISTS idx_classificacoes_intencao
            ON classificacoes_demandas (intencao);


            CREATE TABLE IF NOT EXISTS metadados (
                chave TEXT PRIMARY KEY,

                valor TEXT,

                atualizado_em TEXT NOT NULL
            );
            """
        )


# ============================================================
# UTILIDADES
# ============================================================

def _texto(
    valor: Any,
) -> str:
    """
    Converte valores diversos para texto.

    Também trata objetos de data/hora
    que possuem método isoformat().
    """

    if valor is None:
        return ""

    try:

        if hasattr(
            valor,
            "isoformat",
        ):

            return valor.isoformat()

    except Exception:

        pass

    return str(
        valor
    ).strip()


def _float(
    valor: Any,
) -> float | None:
    """
    Converte um valor para float.

    Retorna None quando não for possível.
    """

    if valor is None:
        return None

    try:

        return float(
            valor
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


def _json_seguro(
    valor: Any,
) -> str:
    """
    Serializa estruturas Python/Pandas.

    default=str evita erros com:
    - Timestamp
    - datetime
    - tipos especiais do Pandas
    - objetos desconhecidos
    """

    return json.dumps(
        valor,
        ensure_ascii=False,
        default=str,
    )


# ============================================================
# CHAMADOS
# ============================================================

def salvar_chamado(
    chamado_id: int,
    dados: dict,
) -> None:
    """
    Insere ou atualiza um chamado
    na memória operacional da EDNNA.

    O payload completo da linha também é
    armazenado em JSON.

    Isso permitirá reconstruir o DataFrame
    quando o Redmine estiver indisponível.
    """

    agora = (
        agora_brasil_iso()
    )

    with conectar() as conn:

        conn.execute(
            """
            INSERT INTO chamados (
                id,
                cliente,
                origem,
                responsavel,
                projeto,
                tipo,
                estado,
                prioridade,
                assunto,
                criado_em,
                alterado_em,
                tempo_aberto_dias,
                payload_json,
                sincronizado_em
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )

            ON CONFLICT(id) DO UPDATE SET

                cliente =
                    excluded.cliente,

                origem =
                    excluded.origem,

                responsavel =
                    excluded.responsavel,

                projeto =
                    excluded.projeto,

                tipo =
                    excluded.tipo,

                estado =
                    excluded.estado,

                prioridade =
                    excluded.prioridade,

                assunto =
                    excluded.assunto,

                criado_em =
                    excluded.criado_em,

                alterado_em =
                    excluded.alterado_em,

                tempo_aberto_dias =
                    excluded.tempo_aberto_dias,

                payload_json =
                    excluded.payload_json,

                sincronizado_em =
                    excluded.sincronizado_em
            """,
            (
                chamado_id,

                _texto(
                    dados.get(
                        "Clientes"
                    )
                ),

                _texto(
                    dados.get(
                        "Origem"
                    )
                ),

                _texto(
                    dados.get(
                        "Atribuído a"
                    )
                ),

                _texto(
                    dados.get(
                        "Projeto"
                    )
                ),

                _texto(
                    dados.get(
                        "Tipo"
                    )
                ),

                _texto(
                    dados.get(
                        "Estado"
                    )
                ),

                _texto(
                    dados.get(
                        "Prioridade"
                    )
                ),

                _texto(
                    dados.get(
                        "Assunto"
                    )
                ),

                _texto(
                    dados.get(
                        "Criado"
                    )
                ),

                _texto(
                    dados.get(
                        "Alterado"
                    )
                ),

                _float(
                    dados.get(
                        "Tempo em aberto (dias)"
                    )
                ),

                _json_seguro(
                    dados
                ),

                agora,
            ),
        )


def obter_chamado(
    chamado_id: int,
) -> dict | None:
    """
    Retorna um chamado armazenado
    na memória da EDNNA.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT *
            FROM chamados
            WHERE id = ?
            """,
            (
                chamado_id,
            ),
        ).fetchone()

    if linha is None:
        return None

    return dict(
        linha
    )


def listar_chamados(
    estado: str | None = None,
) -> list[dict]:
    """
    Lista chamados armazenados.

    Opcionalmente filtra pelo estado.
    """

    with conectar() as conn:

        if estado:

            linhas = conn.execute(
                """
                SELECT *
                FROM chamados

                WHERE
                    LOWER(TRIM(estado))
                    =
                    LOWER(TRIM(?))

                ORDER BY id DESC
                """,
                (
                    estado,
                ),
            ).fetchall()

        else:

            linhas = conn.execute(
                """
                SELECT *
                FROM chamados
                ORDER BY id DESC
                """
            ).fetchall()

    return [
        dict(
            linha
        )
        for linha in linhas
    ]


def obter_alterado_em(
    chamado_id: int,
) -> str:
    """
    Retorna o valor Alterado armazenado
    para determinado chamado.

    Utilizado para identificar se houve
    mudança desde a última sincronização.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT alterado_em
            FROM chamados
            WHERE id = ?
            """,
            (
                chamado_id,
            ),
        ).fetchone()

    if not linha:

        return ""

    return _texto(
        linha[
            "alterado_em"
        ]
    )


# ============================================================
# SNAPSHOT / CONTINGÊNCIA
# ============================================================

def carregar_snapshot_chamados() -> list[dict]:
    """
    Recupera o último snapshot completo conhecido
    dos chamados armazenados pela EDNNA.

    Esta função é utilizada pelo app.py quando:

        Redmine falha
            ↓
        session_state não possui carga
            ↓
        SQLite assume como contingência

    O retorno possui o mesmo formato de linhas utilizado
    para reconstruir um DataFrame Pandas.
    """

    inicializar_banco()

    with conectar() as conn:

        linhas = conn.execute(
            """
            SELECT
                id,
                payload_json

            FROM chamados

            WHERE
                payload_json IS NOT NULL

                AND TRIM(
                    payload_json
                ) <> ''

            ORDER BY id
            """
        ).fetchall()

    resultado: list[dict] = []

    for linha in linhas:

        try:

            payload = json.loads(
                linha[
                    "payload_json"
                ]
            )

            if not isinstance(
                payload,
                dict,
            ):
                continue

            # Segurança:
            # garante que o ID exista mesmo
            # em um payload antigo/incompleto.
            if "#" not in payload:

                payload["#"] = (
                    linha[
                        "id"
                    ]
                )

            resultado.append(
                payload
            )

        except Exception as exc:

            print(
                "[EDNNA] Payload inválido "
                "no SQLite | "
                f"chamado={linha['id']} | "
                f"erro={exc}"
            )

    return resultado


# ============================================================
# JOURNALS
# ============================================================

def salvar_journals(
    chamado_id: int,
    journals: list[dict],
) -> int:
    """
    Armazena os journals de um chamado.

    Journals já existentes são atualizados.

    Retorna a quantidade de journals processados.
    """

    agora = (
        agora_brasil_iso()
    )

    quantidade = 0

    with conectar() as conn:

        for journal in journals:

            journal_id = (
                journal.get(
                    "id"
                )
            )

            if journal_id is None:
                continue

            usuario = (
                journal.get(
                    "user"
                )
                or {}
            )

            autor = _texto(
                usuario.get(
                    "name"
                )
            )

            criado_em = _texto(
                journal.get(
                    "created_on"
                )
            )

            notas = _texto(
                journal.get(
                    "notes"
                )
            )

            detalhes = (
                journal.get(
                    "details"
                )
                or []
            )

            conn.execute(
                """
                INSERT INTO journals (
                    id,
                    chamado_id,
                    autor,
                    criado_em,
                    notas,
                    detalhes_json,
                    sincronizado_em
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?
                )

                ON CONFLICT(id) DO UPDATE SET

                    chamado_id =
                        excluded.chamado_id,

                    autor =
                        excluded.autor,

                    criado_em =
                        excluded.criado_em,

                    notas =
                        excluded.notas,

                    detalhes_json =
                        excluded.detalhes_json,

                    sincronizado_em =
                        excluded.sincronizado_em
                """,
                (
                    int(
                        journal_id
                    ),

                    chamado_id,

                    autor,

                    criado_em,

                    notas,

                    _json_seguro(
                        detalhes
                    ),

                    agora,
                ),
            )

            quantidade += 1

    return quantidade


def listar_journals(
    chamado_id: int,
) -> list[dict]:
    """
    Retorna journals armazenados
    para determinado chamado.
    """

    with conectar() as conn:

        linhas = conn.execute(
            """
            SELECT *
            FROM journals

            WHERE chamado_id = ?

            ORDER BY
                criado_em,
                id
            """,
            (
                chamado_id,
            ),
        ).fetchall()

    return [
        dict(
            linha
        )
        for linha in linhas
    ]


# ============================================================
# ANÁLISE DE PRIMEIRO COMBATE
# ============================================================

def salvar_analise_primeiro_combate(
    chamado_id: int,
    alterado_em_redmine: str,
    situacao: str,
    teve_atuacao: bool,
    autor_primeira_atuacao: str = "",
    data_primeira_atuacao: str = "",
    tipo_primeira_atuacao: str = "",
    erro: str = "",
) -> None:
    """
    Persiste o resultado da análise
    de primeiro combate.

    alterado_em_redmine será utilizado para saber
    se a análise armazenada ainda é válida.

    Se o chamado tiver sido alterado depois da análise,
    a EDNNA poderá buscar novamente seus journals.
    """

    with conectar() as conn:

        conn.execute(
            """
            INSERT INTO analises_primeiro_combate (
                chamado_id,
                alterado_em_redmine,
                situacao,
                teve_atuacao,
                autor_primeira_atuacao,
                data_primeira_atuacao,
                tipo_primeira_atuacao,
                erro,
                analisado_em
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )

            ON CONFLICT(chamado_id) DO UPDATE SET

                alterado_em_redmine =
                    excluded.alterado_em_redmine,

                situacao =
                    excluded.situacao,

                teve_atuacao =
                    excluded.teve_atuacao,

                autor_primeira_atuacao =
                    excluded.autor_primeira_atuacao,

                data_primeira_atuacao =
                    excluded.data_primeira_atuacao,

                tipo_primeira_atuacao =
                    excluded.tipo_primeira_atuacao,

                erro =
                    excluded.erro,

                analisado_em =
                    excluded.analisado_em
            """,
            (
                chamado_id,

                _texto(
                    alterado_em_redmine
                ),

                _texto(
                    situacao
                ),

                int(
                    bool(
                        teve_atuacao
                    )
                ),

                _texto(
                    autor_primeira_atuacao
                ),

                _texto(
                    data_primeira_atuacao
                ),

                _texto(
                    tipo_primeira_atuacao
                ),

                _texto(
                    erro
                ),

                agora_brasil_iso(),
            ),
        )


def obter_analise_primeiro_combate(
    chamado_id: int,
) -> dict | None:
    """
    Obtém a última análise conhecida
    de determinado chamado.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT *
            FROM analises_primeiro_combate

            WHERE chamado_id = ?
            """,
            (
                chamado_id,
            ),
        ).fetchone()

    if linha is None:

        return None

    return dict(
        linha
    )


def listar_analises_primeiro_combate() -> list[dict]:
    """
    Retorna todas as análises de primeiro combate armazenadas.

    Utilizado pelo dashboard para montar a Central Operacional
    da EDNNA sem abrir uma conexão SQLite para cada chamado.
    """
    with conectar() as conn:
        linhas = conn.execute(
            """
            SELECT *
            FROM analises_primeiro_combate
            ORDER BY chamado_id
            """
        ).fetchall()

    return [dict(linha) for linha in linhas]


# ============================================================
# CLASSIFICAÇÃO DE DEMANDAS
# ============================================================

def salvar_classificacao_demanda(
    chamado_id: int,
    alterado_em_redmine: str,
    intencao: str,
    confianca: float,
    regra_candidata: str = "",
    acao_sugerida: str = "",
    executavel: bool = False,
    evidencias: list[str] | None = None,
) -> None:
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO classificacoes_demandas (
                chamado_id,
                alterado_em_redmine,
                intencao,
                confianca,
                regra_candidata,
                acao_sugerida,
                executavel,
                evidencias_json,
                classificado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(chamado_id) DO UPDATE SET
                alterado_em_redmine = excluded.alterado_em_redmine,
                intencao = excluded.intencao,
                confianca = excluded.confianca,
                regra_candidata = excluded.regra_candidata,
                acao_sugerida = excluded.acao_sugerida,
                executavel = excluded.executavel,
                evidencias_json = excluded.evidencias_json,
                classificado_em = excluded.classificado_em
            """,
            (
                int(chamado_id),
                _texto(alterado_em_redmine),
                _texto(intencao),
                float(confianca or 0),
                _texto(regra_candidata),
                _texto(acao_sugerida),
                1 if executavel else 0,
                _json_seguro(evidencias or []),
                agora_brasil_iso(),
            ),
        )


def obter_classificacao_demanda(
    chamado_id: int,
) -> dict | None:
    with conectar() as conn:
        linha = conn.execute(
            """
            SELECT *
            FROM classificacoes_demandas
            WHERE chamado_id = ?
            """,
            (int(chamado_id),),
        ).fetchone()

    if linha is None:
        return None

    item = dict(linha)

    try:
        item["evidencias"] = json.loads(
            item.get("evidencias_json") or "[]"
        )
    except Exception:
        item["evidencias"] = []

    item["executavel"] = bool(
        item.get("executavel")
    )

    return item


def listar_classificacoes_demandas() -> list[dict]:
    with conectar() as conn:
        linhas = conn.execute(
            """
            SELECT *
            FROM classificacoes_demandas
            ORDER BY intencao, confianca DESC, chamado_id
            """
        ).fetchall()

    resultado = []

    for linha in linhas:
        item = dict(linha)

        try:
            item["evidencias"] = json.loads(
                item.get("evidencias_json") or "[]"
            )
        except Exception:
            item["evidencias"] = []

        item["executavel"] = bool(
            item.get("executavel")
        )

        resultado.append(item)

    return resultado


# ============================================================
# METADADOS
# ============================================================

def salvar_metadado(
    chave: str,
    valor: str,
) -> None:
    """
    Salva informação auxiliar da EDNNA.

    Exemplos:

    ultima_sincronizacao_snapshot
    ultima_sincronizacao_journals
    """

    with conectar() as conn:

        conn.execute(
            """
            INSERT INTO metadados (
                chave,
                valor,
                atualizado_em
            )

            VALUES (
                ?, ?, ?
            )

            ON CONFLICT(chave) DO UPDATE SET

                valor =
                    excluded.valor,

                atualizado_em =
                    excluded.atualizado_em
            """,
            (
                chave,
                valor,
                agora_brasil_iso(),
            ),
        )


def obter_metadado(
    chave: str,
) -> str:
    """
    Retorna um metadado armazenado
    pela EDNNA.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT valor
            FROM metadados

            WHERE chave = ?
            """,
            (
                chave,
            ),
        ).fetchone()

    if linha is None:

        return ""

    return _texto(
        linha[
            "valor"
        ]
    )


# ============================================================
# DIAGNÓSTICO
# ============================================================

def obter_diagnostico_banco() -> dict:
    """
    Retorna informações básicas
    sobre a memória SQLite da EDNNA.
    """

    inicializar_banco()

    with conectar() as conn:

        chamados = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM chamados
            """
        ).fetchone()[
            "total"
        ]

        journals = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM journals
            """
        ).fetchone()[
            "total"
        ]

        analises = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM analises_primeiro_combate
            """
        ).fetchone()[
            "total"
        ]

        snapshots_validos = conn.execute(
            """
            SELECT COUNT(*) AS total

            FROM chamados

            WHERE
                payload_json IS NOT NULL

                AND TRIM(
                    payload_json
                ) <> ''
            """
        ).fetchone()[
            "total"
        ]

    return {
        "arquivo": str(
            DB_PATH
        ),

        "existe":
            DB_PATH.exists(),

        "chamados":
            chamados,

        "snapshots_validos":
            snapshots_validos,

        "journals":
            journals,

        "analises_primeiro_combate":
            analises,
    }


# ============================================================
# INICIALIZAÇÃO AUTOMÁTICA
# ============================================================

inicializar_banco()


print(
    "[EDNNA] SQLite inicializado | "
    f"arquivo={DB_PATH}"
)
