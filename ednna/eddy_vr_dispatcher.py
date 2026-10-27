"""VR01 durable dispatcher. Explicit approval, no guessed addresses or unsafe retries.

An attempt is committed BEFORE Graph is invoked. A timeout/202 without
Sent Items proof is never retried automatically: reconciliation is required.
"""
from __future__ import annotations

import json
import os
import re
from ednna.mysql_storage import connect
from ednna.eddy_vr_readiness import verificar_prontidao_vr01
from ednna.central_envios import exigir_janela_externa
from ednna.status_guard import preflight_chamado_ativo
from ednna.email_sender import enviar_email_graph, localizar_email_enviado

DDL = """CREATE TABLE IF NOT EXISTS eddy_vr01_dispatch_audit (
 action_key CHAR(64) NOT NULL PRIMARY KEY,
 chamado_id BIGINT NOT NULL,
 status VARCHAR(48) NOT NULL,
 recipient VARCHAR(254) NOT NULL,
 subject VARCHAR(255) NOT NULL,
 provider_message_id VARCHAR(191) NULL,
 updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 KEY idx_dispatch_issue (chamado_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""

# Only a versioned, operator-approved action-specific mapping is accepted.
# No address is ever inferred from a journal or from the action's destination label.
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def _approved_message(action: dict, approvals: dict) -> dict | None:
    item = approvals.get(str(action["action_key"]))
    if not isinstance(item, dict):
        return None
    if item.get("redmine_updated_on") != action["redmine_updated_on"]:
        return None
    if item.get("acao") != action["acao"]:
        return None
    # Human handoff: the approved original owner must be explicit and verified\n    # against the live Redmine assignee before any notification is sent.\n    owner_id = item.get("original_owner_id")\n    if type(owner_id) is not int or owner_id <= 0:\n        return None\n    to = item.get("to")
    if not isinstance(to, str) or not EMAIL.fullmatch(to) or len(to) > 254:
        return None
    subject = str(item.get("subject") or "").strip()
    body = str(item.get("body") or "").strip()
    if not subject or not body or f"#{action['chamado_id']}" not in subject:
        return None
    # The action approval may carry verified Blueprint participants and the
    # ticket owner's confirmed address. No addresses are inferred from names.
    cc = item.get("cc", [])
    if not isinstance(cc, list) or any(not isinstance(e, str) or not EMAIL.fullmatch(e) or len(e) > 254 for e in cc):
        return None
    from ednna.email_policy import aplicar_cc_padrao
    return {"to": to, "original_owner_id": owner_id, "cc": aplicar_cc_padrao([to], cc),
            "subject": subject[:255], "body": body}

def _claim(action: dict, msg: dict) -> bool:
    # MySQL uniqueness serializes competing workers. The audit row is permanent,
    # including on Graph exceptions: never send a second time blindly.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(
                """INSERT IGNORE INTO eddy_vr01_dispatch_audit
                   (action_key, chamado_id, status, recipient, subject)
                   VALUES (%s,%s,'INICIADO',%s,%s)""",
                (action["action_key"], action["chamado_id"], msg["to"], msg["subject"]),
            )
            if cur.rowcount != 1:
                return False
            cur.execute(
                """UPDATE eddy_vr01_action_queue SET situacao='EM_EXECUCAO'
                   WHERE action_key=%s AND situacao='PENDENTE'
                     AND redmine_updated_on=%s""",
                (action["action_key"], action["redmine_updated_on"]),
            )
            if cur.rowcount != 1:
                # Commit the audit row as blocked, not as permission to send.
                cur.execute("UPDATE eddy_vr01_dispatch_audit SET status='BLOQUEADO_FILA' WHERE action_key=%s",
                            (action["action_key"],))
                return False
    return True

def _finish(key: str, status: str, provider_id: str = "") -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE eddy_vr01_dispatch_audit SET status=%s, provider_message_id=%s WHERE action_key=%s",
                (status, provider_id[:191], key),
            )
            cur.execute(
                "UPDATE eddy_vr01_action_queue SET situacao=%s WHERE action_key=%s AND situacao='EM_EXECUCAO'",
                (status, key),
            )

def executar_fila_vr01(*, approvals: dict | None = None, limit: int = 25,
                      preflight=None, send=None, lookup=None) -> dict:
    readiness = verificar_prontidao_vr01()
    if not readiness["pronto"]:
        return {"estado": "BLOQUEADO_PRONTIDAO", "bloqueios": readiness["bloqueios"],
                "envios_confirmados": 0}
    # Window check precedes claims, so an after-hours run cannot consume actions.
    exigir_janela_externa()
    if approvals is None:
        raw = os.getenv("EDDY_VR01_APPROVED_MESSAGES_JSON", "")
        try:
            approvals = json.loads(raw)
        except (ValueError, TypeError):
            approvals = {}
    if not isinstance(approvals, dict):
        approvals = {}
    preflight = preflight or preflight_chamado_ativo
    send = send or enviar_email_graph
    lookup = lookup or localizar_email_enviado
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(
                """SELECT action_key, chamado_id, redmine_updated_on, etapa, acao, destino
                   FROM eddy_vr01_action_queue WHERE situacao='PENDENTE'
                   ORDER BY criado_em LIMIT %s""", (max(1, min(int(limit), 100)),),
            )
            columns = ("action_key", "chamado_id", "redmine_updated_on", "etapa", "acao", "destino")
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    results = []
    for action in rows:
        key = action["action_key"]
        cid = int(action["chamado_id"])
        msg = _approved_message(action, approvals)
        if not msg:
            results.append({"chamado_id": cid, "estado": "AGUARDA_MENSAGEM_APROVADA"})
            continue
        # The latest Redmine version and status must match the queued snapshot.
        try:
            fresh = preflight(cid)
            issue = fresh.get("issue") or {}
            # The generic status preflight does not fetch journals or set
            # _eddy_journals_completos. Verify the current version against a
            # complete, persisted Redmine snapshot before authorizing dispatch.
            from ednna.mysql_snapshot_repository import carregar_snapshot
            stored = carregar_snapshot(cid)
            snapshot = (stored or {}).get("chamado") or {}
            payload = snapshot.get("payload_json")
            if isinstance(payload, str):
                payload = json.loads(payload)
            journals_complete = (
                isinstance(payload, dict)
                and payload.get("_eddy_journals_completos") is True
                and isinstance((stored or {}).get("journals"), list)
                and str(payload.get("updated_on") or "") == action["redmine_updated_on"]
            )
            if (not fresh.get("ok") or fresh.get("bloquear")
                    or str(issue.get("updated_on") or "") != action["redmine_updated_on"]
                    or not journals_complete):
                results.append({"chamado_id": cid, "estado": "BLOQUEADO_PREFLIGHT_OU_VERSAO"})
                continue
            # Do not notify a human while the ticket is still assigned to EDNNA.\n            # A verified Redmine handoff is mandatory, not merely an intent.\n            assigned = issue.get("assigned_to") or {}\n            if not isinstance(assigned, dict) or assigned.get("id") != msg["original_owner_id"]:\n                results.append({"chamado_id": cid, "estado": "AGUARDA_DEVOLUCAO_REDMINE"})\n                continue\n            # Before claiming, check for any already-sent message with the
            # action-specific subject. Lookup failure is not proof of absence.
            previous = lookup(remetente=os.environ["EDNNA_EMAIL_FROM"], assunto=msg["subject"])
            if previous:
                results.append({"chamado_id": cid, "estado": "REVISAR_ENVIO_EXISTENTE"})
                continue
        except Exception as exc:
            results.append({"chamado_id": cid, "estado": "BLOQUEADO_CONSULTA", "erro": type(exc).__name__})
            continue
        if not _claim(action, msg):
            results.append({"chamado_id": cid, "estado": "JA_RESERVADO_OU_SUPERADO"})
            continue
        try:
            send(remetente=os.environ["EDNNA_EMAIL_FROM"], para=[msg["to"]],
                          cc=msg["cc"], assunto=msg["subject"], corpo=msg["body"], chamado_id=cid)
            # HTTP 202 is only accepted by Graph, not a durable send receipt.
            provider = lookup(remetente=os.environ["EDNNA_EMAIL_FROM"], assunto=msg["subject"])
            if provider and provider.get("sentDateTime") and (provider.get("internetMessageId") or provider.get("id")):
                _finish(key, "ENVIO_CONFIRMADO", str(provider.get("internetMessageId") or provider["id"]))
                results.append({"chamado_id": cid, "estado": "ENVIO_CONFIRMADO"})
            else:
                _finish(key, "AGUARDA_CONCILIACAO")
                results.append({"chamado_id": cid, "estado": "AGUARDA_CONCILIACAO"})
        except Exception as exc:
            _finish(key, "AGUARDA_CONCILIACAO")
            results.append({"chamado_id": cid, "estado": "AGUARDA_CONCILIACAO", "erro": type(exc).__name__})
    return {"estado": "CICLO_EXECUTOR_CONCLUIDO", "avaliados": len(rows),
            "envios_confirmados": sum(r["estado"] == "ENVIO_CONFIRMADO" for r in results),
            "resultados": results}
