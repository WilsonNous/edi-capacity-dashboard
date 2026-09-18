from __future__ import annotations

"""Identidade institucional dos e-mails operacionais da EDNNA.

A EDNNA pode ser citada como camada de automação, mas a comunicação externa
é assinada institucionalmente pela Equipe EDI Netunna.
"""
import os


def assinatura_email() -> str:
    return str(
        os.getenv(
            "EDNNA_EMAIL_SIGNATURE",
            "Atenciosamente,\nEquipe EDI Netunna",
        )
        or "Atenciosamente,\nEquipe EDI Netunna"
    ).strip()


def rodape_automacao() -> str:
    habilitado = str(os.getenv("EDNNA_EMAIL_AUTOMATION_FOOTER", "true") or "true").strip().casefold()
    if habilitado not in {"1", "true", "sim", "yes", "on"}:
        return ""
    return str(
        os.getenv(
            "EDNNA_EMAIL_AUTOMATION_FOOTER_TEXT",
            "Mensagem operacional preparada e acompanhada pela EDNNA — Automação EDI Netunna.",
        )
        or ""
    ).strip()


def finalizar_email(texto: str, *, citar_ednna: bool = True) -> str:
    partes = [str(texto or "").rstrip(), assinatura_email()]
    rodape = rodape_automacao() if citar_ednna else ""
    if rodape:
        partes.extend(["", rodape])
    return "\n\n".join(p for p in partes if p is not None).strip()
