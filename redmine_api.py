from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
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
    return garantir_custom_fields(chamados) if completar_custom_fields else chamados


def issue_para_linha(chamado: dict) -> dict:
    clientes = pegar_custom_field(chamado, 1)
    origem = pegar_custom_field(chamado, 5)

    if isinstance(clientes, list):
        clientes = ", ".join(map(str, clientes))
    if isinstance(origem, list):
        origem = ", ".join(map(str, origem))

    return {
        "#": chamado.get("id"),
        "Clientes": clientes,
        "Origem": origem,
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
