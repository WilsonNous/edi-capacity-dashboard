from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable

from redmine_api import (
    buscar_chamados_projetos,
    buscar_detalhes_chamado,
    issue_para_linha,
)


# ============================================================
# CONFIGURAÇÃO EDNNA
# ============================================================

EDNNA_STATUS_PRIMEIRO_COMBATE = os.getenv(
    "EDNNA_STATUS_PRIMEIRO_COMBATE",
    "Aberto",
).strip()

EDNNA_MAX_WORKERS = max(
    1,
    int(os.getenv("EDNNA_MAX_WORKERS", "4")),
)

# Opcional:
#
# Quando esta variável estiver preenchida, somente journals
# feitos por esses usuários serão considerados "atuação EDI".
#
# Exemplo:
#
# EDNNA_AUTORES_EDI=Will Martins,Fulano de Tal,Equipe EDI
#
# Se ficar vazia, qualquer journal com atuação relevante será
# considerado uma atuação.
EDNNA_AUTORES_EDI = {
    nome.strip().lower()
    for nome in os.getenv("EDNNA_AUTORES_EDI", "").split(",")
    if nome.strip()
}

# Usuários/bots que não devem ser considerados atuação humana.
#
# Exemplo:
#
# EDNNA_IGNORAR_AUTORES=EDNNA,Bot Redmine
EDNNA_IGNORAR_AUTORES = {
    nome.strip().lower()
    for nome in os.getenv(
        "EDNNA_IGNORAR_AUTORES",
        "ednna",
    ).split(",")
    if nome.strip()
}


# ============================================================
# MODELO DE RETORNO
# ============================================================

@dataclass
class ResultadoPrimeiroCombate:
    chamado_id: int
    candidato: bool

    motivo: str

    status: str | None = None
    assunto: str | None = None
    descricao: str | None = None

    cliente: str | None = None
    origem: str | None = None
    projeto: str | None = None
    tipo: str | None = None
    prioridade: str | None = None

    autor: str | None = None
    atribuido_a: str | None = None

    criado_em: str | None = None
    alterado_em: str | None = None

    idade_minutos: int | None = None

    quantidade_journals: int = 0

    houve_atuacao: bool = False
    autor_primeira_atuacao: str | None = None
    data_primeira_atuacao: str | None = None
    resumo_primeira_atuacao: str | None = None

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# UTILITÁRIOS
# ============================================================

def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _nome_entidade(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None

    valor = obj.get("name")

    if valor in (None, ""):
        return None

    return str(valor).strip()


def _parse_data_redmine(valor: str | None) -> datetime | None:
    if not valor:
        return None

    texto = valor.strip()

    if not texto:
        return None

    # Redmine normalmente retorna:
    # 2026-09-03T12:34:56Z
    try:
        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"

        return datetime.fromisoformat(texto)

    except (TypeError, ValueError):
        return None


def _idade_minutos(created_on: str | None) -> int | None:
    criado = _parse_data_redmine(created_on)

    if criado is None:
        return None

    if criado.tzinfo is None:
        criado = criado.replace(tzinfo=timezone.utc)

    agora = datetime.now(timezone.utc)

    segundos = (agora - criado.astimezone(timezone.utc)).total_seconds()

    if segundos < 0:
        return 0

    return int(segundos // 60)


# ============================================================
# STATUS
# ============================================================

def status_real(chamado: dict) -> str:
    return _texto(
        (chamado.get("status") or {}).get("name")
    )


def eh_status_primeiro_combate(
    chamado: dict,
    status_alvo: str | None = None,
) -> bool:
    alvo = (
        status_alvo
        or EDNNA_STATUS_PRIMEIRO_COMBATE
    ).strip().lower()

    atual = status_real(chamado).lower()

    return atual == alvo


# ============================================================
# JOURNALS / HISTÓRICO
# ============================================================

def _autor_journal(journal: dict) -> str:
    usuario = journal.get("user") or {}

    if not isinstance(usuario, dict):
        return ""

    return _texto(usuario.get("name"))


def _journal_tem_nota(journal: dict) -> bool:
    return bool(_texto(journal.get("notes")))


def _journal_tem_alteracao_relevante(journal: dict) -> bool:
    """
    Decide se houve uma alteração que pode representar atuação
    operacional sobre o chamado.

    Neste primeiro MVP consideramos relevantes principalmente:
    - mudança de status;
    - mudança de responsável;
    - mudança de prioridade;
    - mudança de percentual concluído;
    - mudança de data prevista.

    Alterações puramente administrativas em outros campos não
    bloqueiam automaticamente a EDNNA.
    """

    campos_relevantes = {
        "status_id",
        "assigned_to_id",
        "priority_id",
        "done_ratio",
        "due_date",
    }

    for detalhe in journal.get("details", []) or []:
        if not isinstance(detalhe, dict):
            continue

        propriedade = _texto(detalhe.get("property")).lower()
        nome = _texto(detalhe.get("name")).lower()

        # Alterações normais de atributos do chamado.
        if propriedade == "attr" and nome in campos_relevantes:
            return True

    return False


def _journal_representa_atuacao(journal: dict) -> bool:
    autor = _autor_journal(journal)
    autor_normalizado = autor.lower()

    # Ignora journals sem autor.
    if not autor_normalizado:
        return False

    # Ignora EDNNA ou bots configurados.
    if autor_normalizado in EDNNA_IGNORAR_AUTORES:
        return False

    # Se cadastrarmos explicitamente os membros EDI,
    # apenas eles serão considerados atuação operacional.
    if EDNNA_AUTORES_EDI:
        if autor_normalizado not in EDNNA_AUTORES_EDI:
            return False

    if _journal_tem_nota(journal):
        return True

    if _journal_tem_alteracao_relevante(journal):
        return True

    return False


def localizar_primeira_atuacao(
    chamado: dict,
) -> dict | None:
    """
    Retorna o primeiro journal que representa atuação.

    None significa que, pelos critérios atuais, não encontramos
    primeiro combate no histórico.
    """

    journals = chamado.get("journals", []) or []

    candidatos = []

    for journal in journals:
        if not isinstance(journal, dict):
            continue

        if not _journal_representa_atuacao(journal):
            continue

        candidatos.append(journal)

    if not candidatos:
        return None

    def chave(journal: dict):
        data = _parse_data_redmine(journal.get("created_on"))

        if data is None:
            return datetime.max.replace(tzinfo=timezone.utc)

        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)

        return data

    candidatos.sort(key=chave)

    return candidatos[0]


def _resumir_journal(journal: dict) -> str | None:
    notas = _texto(journal.get("notes"))

    if notas:
        notas = " ".join(notas.split())

        if len(notas) > 250:
            return notas[:247] + "..."

        return notas

    alteracoes = []

    for detalhe in journal.get("details", []) or []:
        if not isinstance(detalhe, dict):
            continue

        propriedade = _texto(detalhe.get("property"))
        nome = _texto(detalhe.get("name"))
        antigo = _texto(detalhe.get("old_value"))
        novo = _texto(detalhe.get("new_value"))

        if propriedade == "attr":
            alteracoes.append(
                f"{nome}: {antigo or '-'} -> {novo or '-'}"
            )

    if not alteracoes:
        return None

    return "; ".join(alteracoes[:5])


# ============================================================
# ANÁLISE INDIVIDUAL
# ============================================================

def analisar_chamado(
    chamado: dict,
    *,
    buscar_historico: bool = True,
) -> ResultadoPrimeiroCombate:
    chamado_id = chamado.get("id")

    if chamado_id is None:
        raise ValueError(
            "Chamado recebido sem ID."
        )

    chamado_id = int(chamado_id)

    # --------------------------------------------------------
    # Primeiro filtro: estado real
    # --------------------------------------------------------

    if not eh_status_primeiro_combate(chamado):
        return ResultadoPrimeiroCombate(
            chamado_id=chamado_id,
            candidato=False,
            motivo=(
                f"Estado atual '{status_real(chamado)}' "
                f"não corresponde a "
                f"'{EDNNA_STATUS_PRIMEIRO_COMBATE}'."
            ),
            status=status_real(chamado),
            assunto=chamado.get("subject"),
        )

    # --------------------------------------------------------
    # Busca os detalhes completos + journals
    # --------------------------------------------------------

    detalhe = chamado

    if buscar_historico:
        detalhe = buscar_detalhes_chamado(
            chamado_id,
            incluir_journals=True,
        )

    # --------------------------------------------------------
    # Normaliza informações já conhecidas do dashboard
    # --------------------------------------------------------

    linha = issue_para_linha(detalhe)

    journals = detalhe.get("journals", []) or []

    primeira_atuacao = localizar_primeira_atuacao(
        detalhe
    )

    houve_atuacao = primeira_atuacao is not None

    # --------------------------------------------------------
    # Resultado
    # --------------------------------------------------------

    if houve_atuacao:
        motivo = (
            "Chamado continua em Aberto, porém já existe "
            "atuação registrada no histórico."
        )

    else:
        motivo = (
            "Chamado está em Aberto e não foi encontrada "
            "atuação operacional no histórico."
        )

    return ResultadoPrimeiroCombate(
        chamado_id=chamado_id,

        candidato=not houve_atuacao,
        motivo=motivo,

        status=linha.get("Estado"),
        assunto=linha.get("Assunto"),
        descricao=linha.get("Descrição"),

        cliente=linha.get("Clientes"),
        origem=linha.get("Origem"),
        projeto=linha.get("Projeto"),
        tipo=linha.get("Tipo"),
        prioridade=linha.get("Prioridade"),

        autor=linha.get("Autor"),
        atribuido_a=linha.get("Atribuído a"),

        criado_em=linha.get("Criado"),
        alterado_em=linha.get("Alterado"),

        idade_minutos=_idade_minutos(
            linha.get("Criado")
        ),

        quantidade_journals=len(journals),

        houve_atuacao=houve_atuacao,

        autor_primeira_atuacao=(
            _autor_journal(primeira_atuacao)
            if primeira_atuacao
            else None
        ),

        data_primeira_atuacao=(
            primeira_atuacao.get("created_on")
            if primeira_atuacao
            else None
        ),

        resumo_primeira_atuacao=(
            _resumir_journal(primeira_atuacao)
            if primeira_atuacao
            else None
        ),
    )


# ============================================================
# CONSULTA GERAL EDNNA
# ============================================================

def buscar_candidatos_primeiro_combate(
    project_ids: Iterable[int] | None = None,
    *,
    max_workers: int | None = None,
) -> list[ResultadoPrimeiroCombate]:
    """
    Fluxo principal da EDNNA.

    1. Busca chamados abertos no Redmine.
    2. Mantém somente aqueles cujo Estado real é "Aberto".
    3. Consulta journals.
    4. Identifica se houve primeira atuação.
    5. Retorna apenas candidatos ao primeiro combate.

    IMPORTANTE:
    Esta função SOMENTE LÊ dados.
    Não modifica absolutamente nada no Redmine.
    """

    chamados = buscar_chamados_projetos(
        project_ids=project_ids,
        status_id="open",
        completar_custom_fields=True,
    )

    # status_id=open do Redmine significa "todos os não fechados".
    # Aqui fazemos a filtragem específica da EDNNA.
    chamados_abertos = [
        chamado
        for chamado in chamados
        if eh_status_primeiro_combate(chamado)
    ]

    if not chamados_abertos:
        return []

    workers = (
        max_workers
        if max_workers is not None
        else EDNNA_MAX_WORKERS
    )

    workers = max(1, int(workers))

    resultados: list[ResultadoPrimeiroCombate] = []

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = {
            executor.submit(
                analisar_chamado,
                chamado,
                buscar_historico=True,
            ): int(chamado["id"])
            for chamado in chamados_abertos
        }

        for future in as_completed(futures):
            chamado_id = futures[future]

            try:
                resultado = future.result()

            except Exception as exc:
                print(
                    f"[EDNNA] Erro ao analisar chamado "
                    f"#{chamado_id}: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                continue

            if resultado.candidato:
                resultados.append(resultado)

    # Chamados mais antigos primeiro.
    resultados.sort(
        key=lambda item: (
            item.criado_em or "",
            item.chamado_id,
        )
    )

    return resultados


def buscar_diagnostico_primeiro_combate(
    project_ids: Iterable[int] | None = None,
) -> dict:
    """
    Versão de diagnóstico.

    Além dos candidatos, mostra também chamados em Aberto que
    foram descartados por já possuírem atuação.
    """

    chamados = buscar_chamados_projetos(
        project_ids=project_ids,
        status_id="open",
        completar_custom_fields=True,
    )

    chamados_abertos = [
        chamado
        for chamado in chamados
        if eh_status_primeiro_combate(chamado)
    ]

    resultados: list[ResultadoPrimeiroCombate] = []

    if chamados_abertos:
        with ThreadPoolExecutor(
            max_workers=EDNNA_MAX_WORKERS
        ) as executor:

            futures = {
                executor.submit(
                    analisar_chamado,
                    chamado,
                    buscar_historico=True,
                ): int(chamado["id"])
                for chamado in chamados_abertos
            }

            for future in as_completed(futures):
                chamado_id = futures[future]

                try:
                    resultados.append(
                        future.result()
                    )

                except Exception as exc:
                    print(
                        f"[EDNNA] Erro no diagnóstico "
                        f"do chamado #{chamado_id}: "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

    candidatos = [
        r for r in resultados
        if r.candidato
    ]

    ja_atendidos = [
        r for r in resultados
        if not r.candidato
    ]

    candidatos.sort(
        key=lambda item: (
            item.criado_em or "",
            item.chamado_id,
        )
    )

    ja_atendidos.sort(
        key=lambda item: (
            item.criado_em or "",
            item.chamado_id,
        )
    )

    return {
        "total_redmine_open": len(chamados),
        "total_estado_aberto": len(chamados_abertos),

        "aguardando_primeiro_combate": len(
            candidatos
        ),

        "com_atuacao_identificada": len(
            ja_atendidos
        ),

        "candidatos": [
            item.para_dict()
            for item in candidatos
        ],

        "ja_atendidos": [
            item.para_dict()
            for item in ja_atendidos
        ],
    }


# ============================================================
# TESTE MANUAL
# ============================================================

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("EDNNA - INTELIGÊNCIA OPERACIONAL EDI")
    print("Diagnóstico de Primeiro Combate")
    print("=" * 70)

    diagnostico = buscar_diagnostico_primeiro_combate()

    print()
    print(
        "Chamados retornados pelo Redmine como open:",
        diagnostico["total_redmine_open"],
    )

    print(
        "Chamados realmente no Estado Aberto:",
        diagnostico["total_estado_aberto"],
    )

    print(
        "Aguardando primeiro combate:",
        diagnostico["aguardando_primeiro_combate"],
    )

    print(
        "Já possuem atuação:",
        diagnostico["com_atuacao_identificada"],
    )

    print()
    print("-" * 70)
    print("CANDIDATOS")
    print("-" * 70)

    for chamado in diagnostico["candidatos"]:
        print()
        print(
            f"#{chamado['chamado_id']} | "
            f"{chamado['assunto']}"
        )

        print(
            f"Cliente: {chamado['cliente'] or '-'}"
        )

        print(
            f"Origem: {chamado['origem'] or '-'}"
        )

        print(
            f"Prioridade: "
            f"{chamado['prioridade'] or '-'}"
        )

        print(
            f"Criado: {chamado['criado_em'] or '-'}"
        )

        print(
            f"Idade: "
            f"{chamado['idade_minutos']} min"
        )

        print(
            f"Motivo: {chamado['motivo']}"
        )

    print()
    print("=" * 70)
