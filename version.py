"""Versão central da aplicação."""
APP_VERSION = "3.28.31"
APP_RELEASE = "Reconciliação de Status Redmine"
def version_label() -> str:
    return f"{APP_VERSION} — {APP_RELEASE}"
