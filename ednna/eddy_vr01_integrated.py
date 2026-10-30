"""VR01 pilot orchestrator: MySQL ledger, BP, Redmine and Graph.

Execution is deliberately fail-closed. No action runs merely because this module
is imported or a scheduler is active. Each external action needs a specific
approval and production readiness; ambiguous replies never authorize handoff.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ednna.eddy_vr01_lifecycle import VR01Evidence, VR01State, next_transition
from ednna.eddy_vr_readiness import verificar_prontidao_vr01
from ednna.mysql_storage import connect

ISSUE_ID = 50318
ORIGINAL_OWNER_ID = 97
ESTABLISHMENT = "71676316003323"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHASES = tuple(s.value for s in VR01State)
DDL = """CREATE TABLE IF NOT EXISTS eddy_vr01_lifecycle_audit (
 chamado_id BIGINT NOT NULL PRIMARY KEY,
 fase VARCHAR(64) NOT NULL,
 original_owner_id BIGINT NOT NULL,
 eddy_owner_id BIGINT NOT NULL,
 destinatario VARCHAR(254) NULL,
 bp_source_id BIGINT NULL,
 autorizacao_confirmada TINYINT NOT NULL DEFAULT 0,
 confirmacao_evidence_id VARCHAR(191) NULL,
 evidencias_registradas TINYINT NOT NULL DEFAULT 0,
 envio_graph_confirmado TINYINT NOT NULL DEFAULT 0,
 notificado TINYINT NOT NULL DEFAULT 0,
 operacao_pendente VARCHAR(64) NULL,
 atualizado_em TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
 ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
EVENT_DDL = """CREATE TABLE IF NOT EXISTS eddy_vr01_lifecycle_events (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 chamado_id BIGINT NOT NULL,
 evento VARCHAR(64) NOT NULL,
 referencia VARCHAR(191) NULL,
 ocorrido_em TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_vr01_evento (chamado_id, evento, referencia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def _identity() -> int:
    raw = os.getenv("EDDY_REDMINE_USER_ID", "")
    if not raw.isdigit() or int(raw) in (0, ORIGINAL_OWNER_ID):
        raise ValueError("EDDY_REDMINE_USER_ID nao identificado/valido")
    return int(raw)


def _read_issue(chamado_id: int) -> dict:
    from ednna.status_guard import preflight_chamado_ativo
    result = preflight_chamado_ativo(chamado_id)
    if not result.get("ok") or result.get("bloquear") or not isinstance(result.get("issue"), dict):
        raise RuntimeError("Redmine preflight bloqueado")
    return result["issue"]


def _assignee(issue: dict) -> int:
    return int((issue.get("assigned_to") or {}).get("id") or 0)


def _valid_bp() -> dict | None:
    from ednna.mysql_blueprint_participants import selecionar_contatos_cliente_mysql
    # Exact verified label only: never infer a client from an issue subject.
    client = os.getenv("EDDY_VR01_MAMBO_BP_CLIENTE", "").strip()
    if not client:
        return None
    contacts = selecionar_contatos_cliente_mysql(client, limite=20)
    candidates = [r for r in contacts if EMAIL_RE.fullmatch(str(r.get("email") or ""))
                  and r.get("source_id") and r.get("documento_id") and r.get("chamado_id")]
    # Fail closed on ambiguity: the operator must approve one proven contact.
    approved = os.getenv("EDDY_VR01_MAMBO_BP_EMAIL", "").strip().lower()
    matches = [r for r in candidates if str(r["email"]).strip().lower() == approved]
    return matches[0] if len(matches) == 1 else None


def _load() -> dict | None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(EVENT_DDL)
            cur.execute("""SELECT fase, original_owner_id, eddy_owner_id,
                destinatario, bp_source_id, autorizacao_confirmada,
                confirmacao_evidence_id, evidencias_registradas,
                envio_graph_confirmado, notificado, operacao_pendente
                FROM eddy_vr01_lifecycle_audit WHERE chamado_id=%s""", (ISSUE_ID,))
            row = cur.fetchone()
    if not row:
        return None
    keys = ("fase", "original_owner_id", "eddy_owner_id", "destinatario",
            "bp_source_id", "autorizacao_confirmada", "confirmacao_evidence_id",
            "evidencias_registradas", "envio_graph_confirmado", "notificado",
            "operacao_pendente")
    return dict(zip(keys, row))


def _initialize(issue: dict, eddy_id: int) -> dict:
    if _assignee(issue) != ORIGINAL_OWNER_ID:
        raise RuntimeError("Responsavel original divergente: nao assumir")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("""INSERT IGNORE INTO eddy_vr01_lifecycle_audit
                (chamado_id, fase, original_owner_id, eddy_owner_id)
                VALUES (%s,%s,%s,%s)""",
                (ISSUE_ID, VR01State.PRONTO_PARA_ASSUMIR.value, ORIGINAL_OWNER_ID, eddy_id))
    return _load()


def _reserve(phase: str, operation: str) -> bool:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE eddy_vr01_lifecycle_audit SET operacao_pendente=%s
                WHERE chamado_id=%s AND fase=%s AND operacao_pendente IS NULL""",
                (operation, ISSUE_ID, phase))
            return cur.rowcount == 1


def _advance(phase: str, operation: str, target: str, **fields) -> None:
    permitted = {"destinatario", "bp_source_id", "envio_graph_confirmado",
                 "evidencias_registradas", "notificado"}
    if not set(fields) <= permitted:
        raise ValueError("Campo de auditoria nao permitido")
    assignments = ", ".join(f"{key}=%s" for key in fields)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE eddy_vr01_lifecycle_audit SET fase=%s,
                operacao_pendente=NULL""" + (", " + assignments if assignments else "") +
                """ WHERE chamado_id=%s AND fase=%s AND operacao_pendente=%s""",
                (target, *fields.values(), ISSUE_ID, phase, operation))
            if cur.rowcount != 1:
                raise RuntimeError("Transicao nao reconciliada")


def _event(name: str, reference: str) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(EVENT_DDL)
            cur.execute("""INSERT IGNORE INTO eddy_vr01_lifecycle_events
                (chamado_id, evento, referencia) VALUES (%s,%s,%s)""",
                (ISSUE_ID, name, reference[:191]))


def _redmine_update(assigned_to_id: int | None = None, notes: str = "") -> None:
    import requests
    from redmine_api import REDMINE_URL, _headers
    if assigned_to_id is None and not notes:
        raise ValueError("Atualizacao Redmine vazia")
    issue = {"assigned_to_id": assigned_to_id} if assigned_to_id is not None else {}
    if notes:
        issue["notes"] = notes
    response = requests.put(
        f"{REDMINE_URL}/issues/{ISSUE_ID}.json",
        headers={**_headers(), "Content-Type": "application/json"},
        json={"issue": issue}, timeout=(8, 20),
    )
    response.raise_for_status()


def _approval(operation: str, approvals: dict, issue: dict) -> None:
    approved = approvals.get(operation)
    if not isinstance(approved, dict) or approved.get("issue_id") != ISSUE_ID:
        raise PermissionError("Aprovacao especifica ausente")
    if approved.get("redmine_updated_on") != issue.get("updated_on"):
        raise PermissionError("Versao Redmine nao aprovada")


def registrar_confirmacao_revisada(*, message_id: str, revisado_por: str) -> dict:
    """Human-reviewed positive authorization evidence, never inferred from any reply.

    Only an actual Graph INBOX_REPLY evidence row for this issue is accepted.
    This is a MySQL evidence update, not a Redmine write or outgoing email.
    """
    if not message_id or not revisado_por or len(message_id) > 191:
        raise ValueError("Referencia de resposta e revisor obrigatorios")
    row = _load()
    if not row or row["fase"] != VR01State.AGUARDA_CONFIRMACAO_CLIENTE.value:
        raise RuntimeError("Chamado nao aguarda confirmacao")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) FROM eddy_external_evidence
                WHERE chamado_id=%s AND source='GRAPH'
                AND evidence_type='INBOX_REPLY' AND external_id=%s""",
                (ISSUE_ID, message_id))
            if not int(cur.fetchone()[0]):
                raise RuntimeError("Mensagem Graph nao conciliada; nao confirmar")
            cur.execute("""UPDATE eddy_vr01_lifecycle_audit
                SET autorizacao_confirmada=1, confirmacao_evidence_id=%s
                WHERE chamado_id=%s AND fase=%s AND autorizacao_confirmada=0""",
                (message_id, ISSUE_ID, VR01State.AGUARDA_CONFIRMACAO_CLIENTE.value))
            if cur.rowcount != 1:
                raise RuntimeError("Confirmacao ja registrada ou estado mudou")
    _event("AUTORIZACAO_CONFIRMADA", f"{message_id} revisado por {revisado_por}")
    return {"chamado_id": ISSUE_ID, "estado": "AUTORIZACAO_CONFIRMADA_REVISADA"}


def _timeline() -> str:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT evento, referencia, ocorrido_em
                FROM eddy_vr01_lifecycle_events WHERE chamado_id=%s
                ORDER BY ocorrido_em, id""", (ISSUE_ID,))
            rows = cur.fetchall()
    tz = ZoneInfo("America/Sao_Paulo")
    parts = []
    for name, ref, when in rows:
        dt = when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when
        parts.append(f"{dt.astimezone(tz):%d/%m/%Y as %H:%M} - {name}: {ref or ''}")
    return "\n".join(parts)


def planejar_vr01(*, approvals: dict | None = None, execute: bool = False) -> dict:
    """One pilot step per call. Default is read-only; never schedules itself.

    Confirmation must be persisted by a separate evidence-verification process.
    No email text alone can set autorizacao_confirmada.
    """
    eddy_id = _identity()
    issue = _read_issue(ISSUE_ID)
    row = _load()
    if row is None:
        if not execute:
            return {"estado": "AGUARDA_INICIALIZACAO_MYSQL", "externo": False}
        # Initial MySQL ledger write is not an external Redmine/Graph action.
        row = _initialize(issue, eddy_id)
    if row["original_owner_id"] != ORIGINAL_OWNER_ID or row["eddy_owner_id"] != eddy_id:
        return {"estado": "BLOQUEADO_IDENTIDADE", "externo": False}
    if row["operacao_pendente"]:
        return {"estado": "AGUARDA_RECONCILIACAO_MANUAL", "operacao": row["operacao_pendente"], "externo": False}
    phase = VR01State(row["fase"])
    bp = _valid_bp() if phase in (VR01State.AGUARDA_CONTATO_BP, VR01State.SOLICITACAO_ENVIADA) else None
    evidence = VR01Evidence(
        original_owner_id=ORIGINAL_OWNER_ID, eddy_owner_id=eddy_id,
        redmine_assignee_id=_assignee(issue), redmine_snapshot_fresh=True,
        original_owner_persisted=True, blueprint_recipient_verified=bool(bp),
        graph_send_confirmed=bool(row["envio_graph_confirmado"]),
        customer_portal_authorization_confirmed=bool(row["autorizacao_confirmada"] and row["confirmacao_evidence_id"]),
        redmine_evidence_recorded=bool(row["evidencias_registradas"]),
        internal_notification_confirmed=bool(row["notificado"]),
    )
    operation, target = next_transition(phase, evidence)
    report = {"chamado_id": ISSUE_ID, "fase": phase.value, "acao": operation,
              "proxima_fase": target.value, "externo": False}
    if not execute:
        return report
    if not verificar_prontidao_vr01()["pronto"]:
        return {**report, "estado": "BLOQUEADO_PRONTIDAO"}
    if operation not in {"ASSUMIR_REDMINE", "BUSCAR_CONTATO_BP",
                         "SOLICITAR_AUTORIZACAO_PORTAL", "MONITORAR_CLIENTE",
                         "CONFIRMACAO_VALIDADA", "REGISTRAR_EVIDENCIAS_REDMINE",
                         "DEVOLVER_AO_RESPONSAVEL_ORIGINAL",
                         "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA"}:
        return report
    # Pure state transitions need no external approval.
    if operation in {"BUSCAR_CONTATO_BP", "MONITORAR_CLIENTE", "CONFIRMACAO_VALIDADA"}:
        if not _reserve(phase.value, operation):
            return {**report, "estado": "RESERVADO"}
        _advance(phase.value, operation, target.value)
        return {**report, "estado": "TRANSICAO_CONFIRMADA"}
    _approval(operation, approvals or {}, issue)
    if not _reserve(phase.value, operation):
        return {**report, "estado": "RESERVADO"}
    # Reservation stays pending on errors: manual reconciliation prevents blind retries.
    if operation == "ASSUMIR_REDMINE":
        _redmine_update(assigned_to_id=eddy_id)
        if _assignee(_read_issue(ISSUE_ID)) != eddy_id:
            raise RuntimeError("Assuncao Redmine nao confirmada")
        _event("ASSUNCAO_EDDY", str(eddy_id))
    elif operation == "SOLICITAR_AUTORIZACAO_PORTAL":
        if not bp:
            raise RuntimeError("BP nao validado")
        from ednna.email_sender import enviar_email_graph, localizar_email_enviado
        subject = f"[EDDY VR01] #{ISSUE_ID} - Autorizacao VR Beneficios MAMBO"
        body = ("Solicitamos acessar o portal VR Beneficios e autorizar o envio "
                f"dos arquivos do estabelecimento {ESTABLISHMENT} a Netunna. "
                "Por favor, confirme quando a autorizacao estiver concluida.")
        sender = os.environ["EDNNA_EMAIL_FROM"]
        # An already sent message is ambiguous unless correlated to this reservation.
        if localizar_email_enviado(remetente=sender, assunto=subject):
            raise RuntimeError("Mensagem anterior detectada; reconciliar")
        enviar_email_graph(remetente=sender, para=[bp["email"]], cc=[],
                           assunto=subject, corpo=body, chamado_id=ISSUE_ID)
        sent = localizar_email_enviado(remetente=sender, assunto=subject)
        if not sent.get("sentDateTime") or not (sent.get("id") or sent.get("internetMessageId")):
            raise RuntimeError("Graph envio pendente de conciliacao")
        _event("SOLICITACAO_CLIENTE", str(sent.get("internetMessageId") or sent["id"]))
    elif operation == "REGISTRAR_EVIDENCIAS_REDMINE":
        _redmine_update(notes=("EDDY VR01: autorizacao no portal VR Beneficios "
            "confirmada pelo cliente. Evidencia: " + str(row["confirmacao_evidence_id"]) +
            ". Recebimento dos arquivos ainda nao validado; responsabilidade do analista."))
        _event("EVIDENCIAS_REDMINE", str(row["confirmacao_evidence_id"]))
    elif operation == "DEVOLVER_AO_RESPONSAVEL_ORIGINAL":
        _redmine_update(assigned_to_id=ORIGINAL_OWNER_ID)
        if _assignee(_read_issue(ISSUE_ID)) != ORIGINAL_OWNER_ID:
            raise RuntimeError("Devolucao Redmine nao confirmada")
        _event("DEVOLUCAO_ORIGEM", str(ORIGINAL_OWNER_ID))
    elif operation == "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA":
        # No inferred internal address. Approval explicitly supplies the verified owner mailbox.
        recipient = (approvals or {})[operation].get("to", "")
        if not EMAIL_RE.fullmatch(str(recipient)):
            raise PermissionError("Email interno do responsavel nao verificado")
        from ednna.email_sender import enviar_email_graph, localizar_email_enviado
        subject = f"[EDDY VR01] #{ISSUE_ID} - Autorizacao confirmada | MAMBO"
        sender = os.environ["EDNNA_EMAIL_FROM"]
        if localizar_email_enviado(remetente=sender, assunto=subject):
            raise RuntimeError("Notificacao anterior detectada; reconciliar")
        body = ("Historico EDDY VR01:\n" + _timeline() +
                "\n\nProxima acao humana: verificar recebimento dos arquivos pela Netunna."
                "\nAutorizacao no portal nao comprova recebimento.")
        enviar_email_graph(remetente=sender, para=[recipient], cc=[],
                           assunto=subject, corpo=body, chamado_id=ISSUE_ID)
        sent = localizar_email_enviado(remetente=sender, assunto=subject)
        if not sent.get("sentDateTime") or not (sent.get("id") or sent.get("internetMessageId")):
            raise RuntimeError("Notificacao pendente de conciliacao")
        _event("NOTIFICACAO_ORIGEM", str(sent.get("internetMessageId") or sent["id"]))
    fields = {}
    if operation == "SOLICITAR_AUTORIZACAO_PORTAL":
        fields = {"destinatario": bp["email"], "bp_source_id": bp["source_id"],
                  "envio_graph_confirmado": 1}
    if operation == "REGISTRAR_EVIDENCIAS_REDMINE":
        fields = {"evidencias_registradas": 1}
    if operation == "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA":
        fields = {"notificado": 1}
    _advance(phase.value, operation, target.value, **fields)
    return {**report, "estado": "TRANSICAO_CONFIRMADA"}
