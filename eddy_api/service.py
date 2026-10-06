from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ednna.homologacao import estado_regra
from redmine_api import buscar_detalhes_chamado

CAPABILITIES = (
    "edi.status.get",
    "edi.issue.inspect",
    "edi.player.inspect",
    "edi.rule.list",
)

def _db_path(env_name: str, filename: str) -> Path:
    configured = str(os.getenv(env_name, "") or "").strip()
    if configured:
        return Path(configured)
    if os.getenv("WEBSITE_INSTANCE_ID"):
        return Path("/home/data") / filename
    return Path("data") / filename

def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

def _active_snapshot() -> tuple[list[dict], str | None]:
    path = _db_path("PAINEL_DB_PATH", "painel.db")
    if not path.exists():
        return [], None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT payload_json, atualizado_em FROM snapshots
               WHERE chave LIKE '%|status=open|%'
               ORDER BY atualizado_em DESC LIMIT 1"""
        ).fetchone()
        if not row:
            return [], None
        payload = json.loads(row["payload_json"] or "[]")
        return (payload if isinstance(payload, list) else []), row["atualizado_em"]
    finally:
        conn.close()

def _local_metrics() -> dict[str, int]:
    out = dict(rules=0, homologated_rules=0, human_decisions=0, automatic_rules=0,
               under_monitoring=0, executions=0, followups=0)
    path = _db_path("EDNNA_DB_PATH", "ednna.db")
    if not path.exists():
        return out
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        tables = _table_names(conn)
        if "aprendizados_operacionais" in tables:
            out["rules"] = int(conn.execute("SELECT COUNT(*) FROM aprendizados_operacionais").fetchone()[0] or 0)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(aprendizados_operacionais)").fetchall()}
            if "estado" in cols:
                out["human_decisions"] = int(conn.execute(
                    "SELECT COUNT(*) FROM aprendizados_operacionais WHERE estado='PRONTA_PARA_REVISAO'"
                ).fetchone()[0] or 0)
        if "revisoes_regras_operacionais" in tables:
            out["homologated_rules"] = int(conn.execute(
                "SELECT COUNT(*) FROM revisoes_regras_operacionais WHERE estado='HOMOLOGADA'"
            ).fetchone()[0] or 0)
        if "autorizacoes_motor" in tables:
            out["automatic_rules"] = int(conn.execute(
                "SELECT COUNT(*) FROM autorizacoes_motor WHERE modo='AUTOMATICA'"
            ).fetchone()[0] or 0)
        if "acoes_operacionais" in tables:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(acoes_operacionais)").fetchall()}
            proof = "COALESCE(graph_message_id,'')<>'' OR COALESCE(enviado_em,'')<>''"
            if "envio_confirmado" in cols:
                proof = "COALESCE(envio_confirmado,0)=1 OR " + proof
            out["executions"] = int(conn.execute(f"SELECT COUNT(*) FROM acoes_operacionais WHERE {proof}").fetchone()[0] or 0)
            out["under_monitoring"] = int(conn.execute(
                "SELECT COUNT(*) FROM acoes_operacionais WHERE estado IN ('AGUARDANDO_RESPOSTA','FOLLOWUP_ENVIADO','RESPOSTA_RECEBIDA')"
            ).fetchone()[0] or 0)
            if "followup_count" in cols:
                out["followups"] = int(conn.execute(
                    "SELECT COALESCE(SUM(followup_count),0) FROM acoes_operacionais"
                ).fetchone()[0] or 0)
        return out
    finally:
        conn.close()

def status_get(_: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    issues, updated_at = _active_snapshot()
    metrics = _local_metrics()
    awaiting = 0
    for issue in issues:
        status = str(((issue.get("status") or {}).get("name")) or "").casefold()
        if "terceir" in status or "aguard" in status:
            awaiting += 1
    output = {
        "active_issues": len(issues),
        "awaiting_third_parties": awaiting,
        **metrics,
        "snapshot_updated_at": updated_at,
    }
    warnings = [] if updated_at else ["Snapshot operacional não disponível."]
    confidence = 0.98 if updated_at else 0.60
    return output, confidence, [{"source": "eddy:sqlite-read-model", "snapshot_updated_at": updated_at}], warnings, not bool(updated_at)

def issue_inspect(data: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    issue_id = data.get("issue_id") or data.get("id")
    if not issue_id:
        raise ValueError("issue_id é obrigatório.")
    issue = buscar_detalhes_chamado(int(issue_id), incluir_journals=False, incluir_relacoes=False,
                                    incluir_anexos=False, consulta_pontual=False, tentativas=1) or {}
    issue = issue.get("issue", issue) if isinstance(issue, dict) else {}
    if not issue:
        raise LookupError("Chamado não encontrado.")
    safe = {k: issue.get(k) for k in ("id","subject","status","priority","project","assigned_to",
                                      "created_on","updated_on","closed_on") if k in issue}
    return safe, 0.97, [{"source": f"redmine:issue:{issue_id}"}], [], False

def player_inspect(data: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    player = str(data.get("player") or "").strip()
    if not player:
        raise ValueError("player é obrigatório.")
    return {"player": player, "message": "Consulta agregada de player ainda não materializada no contrato v1."}, 0.40, [], ["Evidência agregada insuficiente; requer análise humana."], True

def rule_list(data: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    rid = str(data.get("rule_id") or "").strip()
    if rid:
        state = estado_regra(rid)
        if state:
            return {"rules": [state]}, 0.99, [{"source": f"eddy:homologacao:{rid}"}], [], False
        return {"rules": []}, 0.80, [], ["Regra não encontrada entre as homologações."], True
    return {"rules": []}, 0.50, [], ["Listagem consolidada será ligada ao catálogo canônico em incremento posterior."], True

ROUTES = {
    "edi.status.get": status_get,
    "edi.issue.inspect": issue_inspect,
    "edi.player.inspect": player_inspect,
    "edi.rule.list": rule_list,
}
