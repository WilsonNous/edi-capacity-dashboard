"""Portão de aprovação de solicitações EDI, sem executar envios.

A autorização deve referenciar a minuta exata e ser confirmada por um
executor separado, com controle persistente de idempotência.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def avaliar_autorizacao_envio(minuta: dict[str, Any], aprovacao: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(minuta, dict):
        raise ValueError("minuta deve ser um objeto")
    payload = {
        "destinatario": str(minuta.get("destinatario") or "").strip().casefold(),
        "assunto": str(minuta.get("assunto") or ""),
        "corpo": str(minuta.get("corpo") or ""),
    }
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    pendencias = list(minuta.get("pendencias") or [])
    if not payload["destinatario"]:
        pendencias.append("destinatario_oficial")
    if not payload["assunto"] or not payload["corpo"]:
        pendencias.append("minuta_incompleta")
    aprovacao = aprovacao or {}
    autorizado = (
        aprovacao.get("aprovado") is True
        and str(aprovacao.get("digest") or "") == digest
        and bool(str(aprovacao.get("aprovador") or "").strip())
    )
    if not autorizado:
        pendencias.append("aprovacao_humana_da_versao_atual")
    pendencias = list(dict.fromkeys(pendencias))
    return {
        "digest_minuta": digest,
        "autorizacao_valida": autorizado and not pendencias,
        "pendencias": pendencias,
        "execucao": "NOT_PERFORMED",
        "envio_realizado": False,
        "redmine_atualizado": False,
        "proxima_acao": "Implementar executor com reserva persistente e evidência Graph" if not pendencias else "Resolver pendências antes do envio",
    }
