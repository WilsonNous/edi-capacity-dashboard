"""Versão central da aplicação.

Altere somente este arquivo a cada release. A UI e os logs devem consumir
essas constantes para evitar divergência de versão.
"""

APP_VERSION = "3.28.13"
APP_RELEASE = "EDNNA Player Alvo e Aprendizado de Inclusões"

def version_label() -> str:
    return f"{APP_VERSION} — {APP_RELEASE}"
