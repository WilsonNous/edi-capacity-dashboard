from __future__ import annotations

"""Identidade institucional dos e-mails operacionais do EDDY.

O EDDY pode ser citado como camada de automação especializada em EDI, mas a
comunicação externa continua assinada institucionalmente pela Equipe EDI Netunna.

As variáveis EDNNA_EMAIL_* são preservadas por compatibilidade com o ambiente
Azure atual. Novas instalações podem usar EDDY_EMAIL_*; quando ambas existirem,
EDDY_EMAIL_* tem precedência.
"""
import os


def _env_identidade(novo: str, legado: str, padrao: str) -> str:
    return str(os.getenv(novo) or os.getenv(legado) or padrao or "").strip()


def assinatura_email() -> str:
    return _env_identidade(
        "EDDY_EMAIL_SIGNATURE",
        "EDNNA_EMAIL_SIGNATURE",
        "Atenciosamente,\nEquipe EDI Netunna",
    )


def rodape_automacao() -> str:
    habilitado = _env_identidade(
        "EDDY_EMAIL_AUTOMATION_FOOTER",
        "EDNNA_EMAIL_AUTOMATION_FOOTER",
        "true",
    ).casefold()
    if habilitado not in {"1", "true", "sim", "yes", "on"}:
        return ""
    return _env_identidade(
        "EDDY_EMAIL_AUTOMATION_FOOTER_TEXT",
        "EDNNA_EMAIL_AUTOMATION_FOOTER_TEXT",
        "Mensagem operacional preparada e acompanhada pelo EDDY — Automação EDI Netunna.",
    )


def finalizar_email(texto: str, *, citar_eddy: bool = True, citar_ednna: bool | None = None) -> str:
    """Finaliza o e-mail preservando compatibilidade com chamadas antigas.

    `citar_ednna` continua aceito temporariamente como alias técnico para não
    quebrar fluxos legados; nenhum texto externo volta a identificar a EDNNA.
    """
    if citar_ednna is not None:
        citar_eddy = bool(citar_ednna)
    partes = [str(texto or "").rstrip(), assinatura_email()]
    rodape = rodape_automacao() if citar_eddy else ""
    if rodape:
        partes.extend(["", rodape])
    return "\n\n".join(p for p in partes if p is not None).strip()
