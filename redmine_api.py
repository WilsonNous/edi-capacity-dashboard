from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from time import monotonic
from typing import Iterable

import requests


REDMINE_URL = os.getenv("REDMINE_URL", "https://chamados.nteia.com").rstrip("/")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY", "")
REDMINE_AUTHORIZATION = os.getenv("REDMINE_AUTHORIZATION", "")
REDMINE_PROJECT_IDS = [
    int(x.strip())
    for x in os.getenv("REDMINE_PROJECT_IDS", "5,42").split(",")
    if x.strip()
]

# Cache leve dos metadados dos campos personalizados.
# Mantém o dashboard rápido e permite que novos clientes cadastrados no
# Redmine apareçam automaticamente após alguns minutos.
_CUSTOM_FIELDS_CACHE: list[dict] | None = None
_CUSTOM_FIELDS_CACHE_AT = 0.0
_CUSTOM_FIELDS_TTL_SECONDS = int(os.getenv("REDMINE_CUSTOM_FIELDS_TTL", "300"))


def _headers() -> dict[str, str]:
    if not REDMINE_API_KEY:
        raise RuntimeError("A variável REDMINE_API_KEY não foi configurada.")

    headers = {
        "X-Redmine-API-Key": REDMINE_API_KEY,
        "Accept": "application/json",
    }
    if REDMINE_AUTHORIZATION:
        headers["Authorization"] = REDMINE_AUTHORIZATION
    return headers


def _get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
    response = requests.get(
        f"{REDMINE_URL}/{path.lstrip('/')}",
        headers=_headers(),
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()



def buscar_custom_fields(force: bool = False) -> list[dict]:
    """
    Retorna os campos personalizados cadastrados no Redmine.

    O endpoint /custom_fields.json contém os possíveis valores dos campos
    enumerados, permitindo traduzir IDs internos para os nomes exibidos
    no Redmine, por exemplo:
        243 -> SIM REDE
        338 -> VENTUNO
    """
    global _CUSTOM_FIELDS_CACHE, _CUSTOM_FIELDS_CACHE_AT

    agora = monotonic()
    cache_valido = (
        _CUSTOM_FIELDS_CACHE is not None
        and (agora - _CUSTOM_FIELDS_CACHE_AT) < _CUSTOM_FIELDS_TTL_SECONDS
    )

    if cache_valido and not force:
        return _CUSTOM_FIELDS_CACHE

    dados = _get("custom_fields.json")
    campos = dados.get("custom_fields", [])

    _CUSTOM_FIELDS_CACHE = campos
    _CUSTOM_FIELDS_CACHE_AT = agora
    return campos


def mapa_custom_field(field_id: int, force: bool = False) -> dict[str, str]:
    """Monta o mapa value -> label de um campo personalizado enumerado."""
    for campo in buscar_custom_fields(force=force):
        if int(campo.get("id", -1)) != int(field_id):
            continue

        mapa: dict[str, str] = {}
        for item in campo.get("possible_values", []) or []:
            valor = item.get("value")
            label = item.get("label")

            if valor in (None, ""):
                continue

            valor_texto = str(valor).strip()
            label_texto = str(label).strip() if label not in (None, "") else valor_texto
            mapa[valor_texto] = label_texto

        return mapa

    return {}


def traduzir_custom_field(
    valor,
    field_id: int,
    *,
    retornar_lista: bool = False,
):
    """
    Traduz um valor (ou lista de valores) usando os possible_values do Redmine.

    Se um ID ainda não existir no mapa, preservamos o valor original para
    não perder informação e para o painel continuar funcionando.
    """
    if valor in (None, ""):
        return [] if retornar_lista else None

    valores = valor if isinstance(valor, list) else [valor]

    try:
        mapa = mapa_custom_field(field_id)
    except Exception:
        # Falha na consulta de metadados não pode derrubar o dashboard.
        mapa = {}

    traduzidos: list[str] = []
    for item in valores:
        if item in (None, ""):
            continue
        chave = str(item).strip()
        traduzidos.append(mapa.get(chave, chave))

    if retornar_lista:
        return traduzidos

    return " / ".join(traduzidos) if traduzidos else None


def buscar_chamados_projeto(project_id: int, status_id: str = "open") -> list[dict]:
    """Busca todos os chamados de um projeto, vencendo o limite de paginação do Redmine."""
    chamados: list[dict] = []
    offset = 0
    limit = 100

    while True:
        dados = _get(
            "issues.json",
            {
                "project_id": project_id,
                "status_id": status_id,
                "limit": limit,
                "offset": offset,
            },
        )
        lote = dados.get("issues", [])
        chamados.extend(lote)
        total = int(dados.get("total_count", 0))
        offset += limit
        if offset >= total or not lote:
            break

    return chamados


def buscar_detalhes_chamado(chamado_id: int, incluir_journals: bool = False) -> dict:
    params = {"include": "journals"} if incluir_journals else None
    return _get(f"issues/{chamado_id}.json", params).get("issue", {})


def pegar_custom_field(chamado: dict, field_id: int):
    for campo in chamado.get("custom_fields", []):
        if campo.get("id") == field_id:
            value = campo.get("value")
            if isinstance(value, list):
                value = [v for v in value if v not in (None, "")]
                return value or None
            return value if value not in (None, "") else None
    return None


def garantir_custom_fields(chamados: list[dict], max_workers: int = 12) -> list[dict]:
    """Se a listagem não trouxer campos personalizados, busca detalhes em paralelo."""
    if not chamados:
        return []
    if all("custom_fields" in c for c in chamados[: min(10, len(chamados))]):
        return chamados

    completos: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(buscar_detalhes_chamado, c["id"]): c["id"]
            for c in chamados
        }
        for future in as_completed(futures):
            try:
                completos.append(future.result())
            except Exception:
                # Mantemos o dashboard disponível mesmo se um chamado isolado falhar.
                pass
    return completos


def buscar_chamados_projetos(
    project_ids: Iterable[int] | None = None,
    status_id: str = "open",
    completar_custom_fields: bool = True,
) -> list[dict]:
    project_ids = list(project_ids or REDMINE_PROJECT_IDS)
    todos: list[dict] = []
    for project_id in project_ids:
        todos.extend(buscar_chamados_projeto(project_id, status_id=status_id))

    # Proteção contra duplicidade caso um chamado apareça em mais de uma consulta.
    unicos = {int(c["id"]): c for c in todos if c.get("id") is not None}
    chamados = list(unicos.values())

    # Carrega o catálogo de campos enumerados uma única vez por ciclo de cache.
    # Se o usuário não tiver acesso ao endpoint, seguimos com os IDs originais.
    try:
        buscar_custom_fields()
    except Exception:
        pass

    return garantir_custom_fields(chamados) if completar_custom_fields else chamados


def issue_para_linha(chamado: dict) -> dict:
    clientes_raw = pegar_custom_field(chamado, 1)
    origem_raw = pegar_custom_field(chamado, 5)

    clientes_lista = traduzir_custom_field(
        clientes_raw,
        1,
        retornar_lista=True,
    )
    origem_lista = traduzir_custom_field(
        origem_raw,
        5,
        retornar_lista=True,
    )

    clientes = " / ".join(clientes_lista) if clientes_lista else None
    origem = " / ".join(origem_lista) if origem_lista else None

    return {
        "#": chamado.get("id"),

        # Campo exibido no painel.
        "Clientes": clientes,

        # Campo interno usado para ranking/filtro quando um chamado possui
        # mais de um cliente. O prefixo "_" evita confusão visual.
        "_Clientes_lista": clientes_lista,

        "Origem": origem,
        "_Origem_lista": origem_lista,

        "Atribuído a": (chamado.get("assigned_to") or {}).get("name"),
        "Projeto": (chamado.get("project") or {}).get("name"),
        "Tipo": (chamado.get("tracker") or {}).get("name"),
        "Estado": (chamado.get("status") or {}).get("name"),
        "Prioridade": (chamado.get("priority") or {}).get("name"),
        "Assunto": chamado.get("subject"),
        "Data de fim": chamado.get("due_date"),
        "Alterado": chamado.get("updated_on"),
        "Autor": (chamado.get("author") or {}).get("name"),
        "Data de início": chamado.get("start_date"),
        "Criado": chamado.get("created_on"),
        "Fechado": chamado.get("closed_on"),
        "Descrição": chamado.get("description"),
        "Tempo estimado": chamado.get("estimated_hours"),
        "% concluído": chamado.get("done_ratio"),
    }
