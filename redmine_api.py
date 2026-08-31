from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import monotonic
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter

REDMINE_URL = os.getenv("REDMINE_URL", "https://chamados.nteia.com").rstrip("/")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY", "")
REDMINE_AUTHORIZATION = os.getenv("REDMINE_AUTHORIZATION", "")
REDMINE_PROJECT_IDS = [
    int(x.strip())
    for x in os.getenv("REDMINE_PROJECT_IDS", "5,42").split(",")
    if x.strip()
]

_CUSTOM_FIELDS_CACHE: list[dict] | None = None
_CUSTOM_FIELDS_CACHE_AT = 0.0
_CUSTOM_FIELDS_TTL_SECONDS = int(os.getenv("REDMINE_CUSTOM_FIELDS_TTL", "300"))

_SESSION = requests.Session()
_ADAPTER = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
_SESSION.mount("https://", _ADAPTER)
_SESSION.mount("http://", _ADAPTER)

_LAST_DIAGNOSTICO = {
    "tempo_listagem_s": 0.0,
    "tempo_detalhes_s": 0.0,
    "tempo_total_s": 0.0,
    "chamados_encontrados": 0,
    "com_custom_fields": 0,
    "detalhes_consultados": 0,
    "projetos_consultados": 0,
    "paginas_consultadas": 0,
}


def obter_diagnostico_redmine() -> dict:
    return dict(_LAST_DIAGNOSTICO)


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
    response = _SESSION.get(
        f"{REDMINE_URL}/{path.lstrip('/')}",
        headers=_headers(),
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def buscar_custom_fields(force: bool = False) -> list[dict]:
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
    for campo in buscar_custom_fields(force=force):
        if int(campo.get("id", -1)) != int(field_id):
            continue
        mapa = {}
        for item in campo.get("possible_values", []) or []:
            valor = item.get("value")
            label = item.get("label")
            if valor in (None, ""):
                continue
            chave = str(valor).strip()
            mapa[chave] = str(label).strip() if label not in (None, "") else chave
        return mapa
    return {}


def traduzir_custom_field(valor, field_id: int, *, retornar_lista: bool = False):
    if valor in (None, ""):
        return [] if retornar_lista else None
    valores = valor if isinstance(valor, list) else [valor]
    try:
        mapa = mapa_custom_field(field_id)
    except Exception:
        mapa = {}

    traduzidos = []
    for item in valores:
        if item in (None, ""):
            continue
        chave = str(item).strip()
        traduzidos.append(mapa.get(chave, chave))

    return traduzidos if retornar_lista else (" / ".join(traduzidos) if traduzidos else None)


def carregar_catalogos_redmine(force: bool = False) -> dict:
    try:
        campos = buscar_custom_fields(force=force)

        def montar(field_id: int) -> dict[str, str]:
            for campo in campos:
                if int(campo.get("id", -1)) == field_id:
                    mapa = {}
                    for item in campo.get("possible_values", []) or []:
                        valor = item.get("value")
                        label = item.get("label")
                        if valor in (None, ""):
                            continue
                        chave = str(valor).strip()
                        mapa[chave] = str(label).strip() if label not in (None, "") else chave
                    return mapa
            return {}

        clientes = montar(1)
        origens = montar(5)
        return {
            "ok": bool(clientes),
            "clientes": clientes,
            "origens": origens,
            "qtd_clientes": len(clientes),
            "qtd_origens": len(origens),
            "erro": None if clientes else "Campo Clientes (ID 1) sem valores.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "clientes": {},
            "origens": {},
            "qtd_clientes": 0,
            "qtd_origens": 0,
            "erro": f"{type(exc).__name__}: {exc}",
        }


def traduzir_valor_catalogo(valor, mapa: dict[str, str]):
    if valor in (None, ""):
        return None, []
    valores = valor if isinstance(valor, list) else [valor]
    nomes = []
    for item in valores:
        if item in (None, ""):
            continue
        chave = str(item).strip()
        nomes.append(mapa.get(chave, chave))
    return (" / ".join(nomes) if nomes else None), nomes


def buscar_chamados_projeto(
    project_id: int,
    status_id: str = "open",
    max_workers_paginas: int = 4,
) -> list[dict]:
    """
    Busca todos os chamados de um projeto.

    V3.5.4:
    - consulta a primeira página para descobrir total_count;
    - consulta páginas seguintes em paralelo;
    - preserva a ordem por offset.
    """
    limit = 100

    primeiro = _get(
        "issues.json",
        {
            "project_id": project_id,
            "status_id": status_id,
            "limit": limit,
            "offset": 0,
        },
    )

    primeira_pagina = primeiro.get("issues", [])
    total = int(primeiro.get("total_count", 0))

    if total <= limit or not primeira_pagina:
        return primeira_pagina

    offsets = list(range(limit, total, limit))
    paginas: dict[int, list[dict]] = {0: primeira_pagina}

    with ThreadPoolExecutor(max_workers=max_workers_paginas) as executor:
        futures = {
            executor.submit(
                _get,
                "issues.json",
                {
                    "project_id": project_id,
                    "status_id": status_id,
                    "limit": limit,
                    "offset": offset,
                },
            ): offset
            for offset in offsets
        }

        for future in as_completed(futures):
            offset = futures[future]
            try:
                dados = future.result()
                paginas[offset] = dados.get("issues", [])
            except Exception:
                paginas[offset] = []

    chamados: list[dict] = []
    for offset in sorted(paginas):
        chamados.extend(paginas[offset])

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
    global _LAST_DIAGNOSTICO

    if not chamados:
        return []

    com_campos = [c for c in chamados if "custom_fields" in c]
    sem_campos = [c for c in chamados if "custom_fields" not in c]

    _LAST_DIAGNOSTICO["com_custom_fields"] = len(com_campos)
    _LAST_DIAGNOSTICO["detalhes_consultados"] = len(sem_campos)

    if not sem_campos:
        return chamados

    inicio = monotonic()
    detalhes_por_id = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(buscar_detalhes_chamado, c["id"]): int(c["id"])
            for c in sem_campos
            if c.get("id") is not None
        }
        for future in as_completed(futures):
            chamado_id = futures[future]
            try:
                detalhes_por_id[chamado_id] = future.result()
            except Exception:
                pass

    _LAST_DIAGNOSTICO["tempo_detalhes_s"] = round(monotonic() - inicio, 3)

    resultado = []
    for chamado in chamados:
        chamado_id = int(chamado["id"]) if chamado.get("id") is not None else None
        resultado.append(detalhes_por_id.get(chamado_id, chamado))

    return resultado


def buscar_chamados_projetos(
    project_ids: Iterable[int] | None = None,
    status_id: str = "open",
    completar_custom_fields: bool = True,
) -> list[dict]:
    global _LAST_DIAGNOSTICO

    inicio_total = monotonic()
    inicio_listagem = monotonic()

    project_ids = list(project_ids or REDMINE_PROJECT_IDS)
    todos = []

    max_workers_projetos = min(
        max(1, int(os.getenv("REDMINE_PROJECT_WORKERS", "2"))),
        max(1, len(project_ids)),
    )
    max_workers_paginas = max(1, int(os.getenv("REDMINE_PAGE_WORKERS", "4")))

    with ThreadPoolExecutor(max_workers=max_workers_projetos) as executor:
        futures = {
            executor.submit(
                buscar_chamados_projeto,
                project_id,
                status_id,
                max_workers_paginas,
            ): project_id
            for project_id in project_ids
        }

        resultados_por_projeto: dict[int, list[dict]] = {}
        for future in as_completed(futures):
            project_id = futures[future]
            try:
                resultados_por_projeto[project_id] = future.result()
            except Exception:
                resultados_por_projeto[project_id] = []

    for project_id in project_ids:
        todos.extend(resultados_por_projeto.get(project_id, []))

    paginas_consultadas = 0
    for project_id in project_ids:
        qtd = len(resultados_por_projeto.get(project_id, []))
        paginas_consultadas += max(1, (qtd + 99) // 100)

    _LAST_DIAGNOSTICO = {
        "tempo_listagem_s": round(monotonic() - inicio_listagem, 3),
        "tempo_detalhes_s": 0.0,
        "tempo_total_s": 0.0,
        "chamados_encontrados": 0,
        "com_custom_fields": 0,
        "detalhes_consultados": 0,
        "projetos_consultados": len(project_ids),
        "paginas_consultadas": paginas_consultadas,
    }

    unicos = {int(c["id"]): c for c in todos if c.get("id") is not None}
    chamados = list(unicos.values())
    _LAST_DIAGNOSTICO["chamados_encontrados"] = len(chamados)

    try:
        buscar_custom_fields()
    except Exception:
        pass

    resultado = garantir_custom_fields(chamados) if completar_custom_fields else chamados

    if not completar_custom_fields:
        _LAST_DIAGNOSTICO["com_custom_fields"] = sum(
            1 for c in chamados if "custom_fields" in c
        )

    _LAST_DIAGNOSTICO["tempo_total_s"] = round(monotonic() - inicio_total, 3)
    return resultado


def issue_para_linha(
    chamado: dict,
    mapa_clientes: dict[str, str] | None = None,
    mapa_origens: dict[str, str] | None = None,
) -> dict:
    clientes_raw = pegar_custom_field(chamado, 1)
    origem_raw = pegar_custom_field(chamado, 5)

    if mapa_clientes is not None:
        clientes, clientes_lista = traduzir_valor_catalogo(clientes_raw, mapa_clientes)
    else:
        clientes_lista = traduzir_custom_field(clientes_raw, 1, retornar_lista=True)
        clientes = " / ".join(clientes_lista) if clientes_lista else None

    if mapa_origens is not None:
        origem, origem_lista = traduzir_valor_catalogo(origem_raw, mapa_origens)
    else:
        origem_lista = traduzir_custom_field(origem_raw, 5, retornar_lista=True)
        origem = " / ".join(origem_lista) if origem_lista else None

    return {
        "#": chamado.get("id"),
        "Clientes": clientes,
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
