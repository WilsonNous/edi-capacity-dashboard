"""Global EDDY configuration with backward-compatible VR01 aliases.

Explicit legacy values take precedence during migration; global defaults
apply to new rules without creating an environment variable per acquirer.
"""
from __future__ import annotations

import os

ALIASES = {
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
    legacy = env.get(name)
    if legacy is not None:
        return str(legacy)
    global_name = ALIASES.get(name, name)
    return str(env.get(global_name, default))


def enabled(name: str, default: str = "false", environ=None) -> bool:
    return setting(name, default, environ).strip().lower() == "true"
