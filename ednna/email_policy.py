from __future__ import annotations
"""Política global de destinatários dos e-mails operacionais da EDNNA."""
import os
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _lista_env(nome: str, padrao: str) -> list[str]:
    bruto = str(os.getenv(nome, padrao) or "")
    itens = re.split(r"[;,\n]+", bruto)
    return [x.strip().lower() for x in itens if _EMAIL_RE.match(x.strip())]


def cc_padrao_netunna() -> list[str]:
    """CC institucional: BPO + EDI + Consultores. Pode ser sobrescrito por env."""
    return _lista_env(
        "EDNNA_EMAIL_CC_PADRAO",
        "bpo@netunna.com.br;edi@netunna.com.br;consultores@netunna.com.br",
    )


def aplicar_cc_padrao(para: list[str] | None, cc: list[str] | None = None) -> list[str]:
    para_norm = {str(x).strip().lower() for x in (para or []) if str(x).strip()}
    saida: list[str] = []
    vistos: set[str] = set()
    for item in [*(cc or []), *cc_padrao_netunna()]:
        email = str(item or "").strip().lower()
        if not _EMAIL_RE.match(email) or email in para_norm or email in vistos:
            continue
        vistos.add(email)
        saida.append(email)
    return saida
