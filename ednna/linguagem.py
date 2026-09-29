"""Linguagem humana compartilhada da EDNNA."""
from __future__ import annotations

import re


def primeiro_nome_por_email(email: str, fallback: str = "") -> str:
    local = str(email or "").split("@", 1)[0].strip()
    if not local:
        return str(fallback or "").strip()
    token = re.split(r"[._\-]+", local)[0].strip()
    return token[:1].upper() + token[1:].lower() if token else str(fallback or "").strip()


def quantidade(n: int, singular: str, plural: str | None = None) -> str:
    n = int(n or 0)
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def verbo(n: int, singular: str, plural: str) -> str:
    return singular if int(n or 0) == 1 else plural
