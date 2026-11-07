"""Global EDDY configuration with backward-compatible VR01 aliases.

Explicit legacy values take precedence during migration; global defaults
apply to new rules without creating an environment variable per acquirer.
"""
from __future__ import annotations

import os

EDNNA_LEGACY_NAMES = (
    "ADMIN_EMAILS", "DB_PATH", "EDI_EMAILS", "EMAIL_FROM",
    "JOURNAL_COOLDOWN_SECONDS", "MAX_ERROS_CONSECUTIVOS",
    "MONITOR_EMAIL_ENABLED", "MONITOR_EMAIL_INITIAL_DELAY_SECONDS",
    "MONITOR_EMAIL_INTERVAL_SECONDS", "STATUS_RESPOSTA_RECEBIDA",
    "SYNC_INTERVAL_SECONDS",
)

ALIASES = {**{
    "EDDY_" + suffix: "EDNNA_" + suffix for suffix in EDNNA_LEGACY_NAMES
},
    "EDDY_VR01_EXTERNAL_ENABLED": "EDDY_EXTERNAL_ENABLED",
    "EDDY_VR01_INTERVAL_SECONDS": "EDDY_INTERVAL_SECONDS",
    "EDDY_VR01_TRANSPORT_MYSQL_READY": "EDDY_TRANSPORT_MYSQL_READY",
    "EDDY_VR01_RECIPIENT_RESOLVER_READY": "EDDY_RECIPIENT_RESOLVER_READY",
    "EDDY_VR01_REPLY_RECONCILIATION_READY": "EDDY_REPLY_RECONCILIATION_READY",
    "EDDY_VR01_REDMINE_MYSQL_AUDIT_READY": "EDDY_REDMINE_MYSQL_AUDIT_READY",
    "EDDY_VR01_PORTFOLIO_ENABLED": "EDDY_PORTFOLIO_ENABLED",
    "EDDY_VR01_PORTFOLIO_INTERNAL_ADVANCE": "EDDY_INTERNAL_ADVANCE_ENABLED",
    "EDDY_VR01_AUTO_SEND_PORTAL": "EDDY_AUTO_SEND_ENABLED",
}


def setting(name: str, default: str = "", environ=None) -> str:
    env = os.environ if environ is None else environ
    # EDNNA -> EDDY: new canonical name wins; deployed legacy values
    # remain valid until Azure is migrated.
    if name.startswith("EDNNA_") and name[6:] in EDNNA_LEGACY_NAMES:
        canonical = "EDDY_" + name[6:]
        if canonical in env:
            return str(env[canonical])
    if name in env:
        return str(env[name])
    alternate = ALIASES.get(name, name)
    return str(env.get(alternate, default))


def enabled(name: str, default: str = "false", environ=None) -> bool:
    return setting(name, default, environ).strip().lower() == "true"
