"""VR01 identification by Redmine origin code OR description.

A known origin is authoritative. Subject is a fallback only when origin is absent;
an unknown code must not be guessed from subject text.
"""
from __future__ import annotations

import json
import re
import unicodedata


def _normalize(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _is_vr_description(value) -> bool:
    return _normalize(value).startswith("vrbeneficio")


def identificar_vr(issue: dict, *, origem=None) -> bool:
    """Return True only for identifiable VR origins or subject fallback."""
    payload = issue.get("payload_json")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            payload = None
    if isinstance(payload, dict):
        issue = {**payload, **{k: v for k, v in issue.items() if v is not None}}
    explicit = origem if origem is not None else issue.get("origem")
    fields = issue.get("custom_fields") or []
    field = next((f for f in fields if str(f.get("id")) == "5"), None)
    if field is not None and field.get("value") not in (None, ""):
        explicit = field["value"]
    if explicit not in (None, ""):
        if _is_vr_description(explicit):
            return True
        # Numeric code: resolve only through Redmine's official mapping.
        try:
            from redmine_api import traduzir_custom_field
            translated = traduzir_custom_field(explicit, 5)
            return _is_vr_description(translated)
        except (ValueError, TypeError, KeyError):
            return False
    return _is_vr_description(issue.get("subject")) or (
        "vrbeneficio" in _normalize(issue.get("subject"))
    )
