"""Configurable human routing suggestion; never overrides Redmine ownership evidence."""
from __future__ import annotations

import json
import os
import re
import unicodedata

DEFAULT_EXCEPTIONS = {
    "SIM REDE": "Wilson",
    "SANTA LUCIA": "Wilson",
    "SANDER": "Wilson",
    "MARTMINAS": "Wilson",
    "POSTOS ROTA": "Wilson",
    "MAMBO": "Wilson",
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\\s+", " ", value.upper().strip())


def sugerir_responsavel(cliente: str) -> dict:
    """Human-readable suggestion only; no Redmine ID, mutation or assignment."""
    name = _normalize(cliente)
    if not name:
        return {"responsavel": None, "criterio": "CLIENTE_AUSENTE"}
    try:
        configured = json.loads(os.getenv("EDDY_OWNER_ROUTING_JSON", "{}"))
        if not isinstance(configured, dict):
            raise ValueError("Routing config must be an object")
        exceptions = {**DEFAULT_EXCEPTIONS, **{
            _normalize(k): str(v).strip() for k, v in
            (configured.get("excecoes") or {}).items()
        }}
        alpha = configured.get("alfabetico") or {}
        first = str(alpha.get("A_M", "Vitória")).strip()
        second = str(alpha.get("N_Z", "Laura")).strip()
        if not first or not second or any(not v for v in exceptions.values()):
            raise ValueError("Routing config contains empty owner")
    except (ValueError, TypeError, AttributeError):
        return {"responsavel": None, "criterio": "CONFIGURACAO_INVALIDA"}
    if name in exceptions:
        return {"responsavel": exceptions[name], "criterio": "EXCECAO_CLIENTE"}
    if "A" <= name[0] <= "M":
        return {"responsavel": first, "criterio": "ALFABETICO_A_M"}
    if "N" <= name[0] <= "Z":
        return {"responsavel": second, "criterio": "ALFABETICO_N_Z"}
    return {"responsavel": None, "criterio": "CLIENTE_FORA_DA_FAIXA"}
