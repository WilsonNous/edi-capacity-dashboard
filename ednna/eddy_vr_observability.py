"""EDDY VR01 observability contract for the existing Operação dashboard.

Pure projection of verified batch results. Does not claim emails were sent.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

REVIEW_ACTIONS = frozenset({"VERIFICAR_PORTAL_E_CONTATO_CLIENTE", "PREPARAR_CONSULTA_VR"})
FOLLOWUP_REVIEW = frozenset({"VALIDAR_ENVIO", "FOLLOWUP_VENCIDO"})


def resumir_operacao_vr(batch: dict) -> dict:
    """Map VR assessment to EDDY's four operational queues, fail-closed."""
    if not isinstance(batch, dict) or not batch.get("somente_leitura"):
        raise ValueError("Resultado de avaliação não verificável")
    items = batch.get("chamados")
    if not isinstance(items, list):
        raise ValueError("Lista de chamados inválida")
    seen = set()
    rows = []
    for item in items:
        issue_id = int(item["chamado_id"])
        if issue_id in seen:
            raise ValueError(f"Chamado duplicado: {issue_id}")
        seen.add(issue_id)
        phase = item.get("fase_eddy")
        action = item.get("proxima_acao")
        followup = item.get("followup")
        if followup in FOLLOWUP_REVIEW or action in REVIEW_ACTIONS:
            queue = "voce"
        elif phase in ("CONCLUIDO", "NAO_ELEGIVEL") or action == "NENHUMA":
            queue = "excecoes"
        else:
            queue = "eddy"
        rows.append({
            "chamado_id": issue_id,
            "regra": "VR_BENEFICIOS",
            "fila": queue,
            "fase": phase,
            "proxima_acao": action,
            "followup": followup,
            "vencimento": item.get("vencimento"),
            "prazo_chamado": item.get("prazo_chamado"),
            "ultimo_envio_confirmado": bool(item.get("evidencia_envio_confirmada")),
            "acao_executada": False,
            "documentacao_redmine_confirmada": False,
        })
    counts = Counter(row["fila"] for row in rows)
    failures = batch.get("falhas") or []
    return {
        "regra": "VR_BENEFICIOS",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "modo": "avaliacao_somente_leitura",
        "indicadores": {
            "voce": counts["voce"],
            "eddy": counts["eddy"],
            "realizado": 0,
            "excecoes": counts["excecoes"] + len(failures),
        },
        "chamados": rows,
        "falhas": failures,
        "execucao_automatica_homologada": False,
    }
