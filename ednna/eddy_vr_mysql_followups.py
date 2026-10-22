"""Read-only VR01 follow-up scheduler using confirmed MySQL dispatch evidence.

A 48-hour deadline is only meaningful after a Graph-confirmed send. Inbox
replies suspend follow-up. No outbound calls or Redmine writes are performed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ednna.mysql_storage import connect

def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def listar_followups_vr01(*, agora=None, limit=200) -> dict:
    now = _utc(agora) if agora is not None else datetime.now(timezone.utc)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT a.chamado_id, MAX(a.updated_at)
                   FROM eddy_vr01_dispatch_audit a
                   JOIN eddy_chamados c ON c.id=a.chamado_id
                   WHERE a.status='ENVIO_CONFIRMADO'
                     AND LOWER(COALESCE(c.estado,'')) NOT REGEXP
                         'conclu|fechad|rejeitad|cancelad'
                   GROUP BY a.chamado_id
                   ORDER BY MAX(a.updated_at) LIMIT %s""",
                (max(1, min(int(limit), 1000)),),
            )
            sent = list(cur.fetchall())
            results = []
            for cid, when in sent:
                # Inbox evidence is immutable. Without a trustworthy received
                # timestamp in this schema, any reply blocks an automated chase.
                cur.execute(
                    """SELECT COUNT(*) FROM eddy_external_evidence
                       WHERE chamado_id=%s AND source='GRAPH'
                         AND evidence_type='INBOX_REPLY'""",
                    (cid,),
                )
                reply_count = int(cur.fetchone()[0])
                if reply_count:
                    results.append({"chamado_id": int(cid), "situacao": "RESPOSTA_RECEBIDA"})
                    continue
                deadline = _utc(when) + timedelta(hours=48)
                results.append({"chamado_id": int(cid),
                                "situacao": "FOLLOWUP_VENCIDO" if now >= deadline else "AGUARDANDO_PRAZO",
                                "vencimento": deadline.isoformat(),
                                "execucao_externa": False})
    return {"estado": "FOLLOWUPS_PLANEJADOS_SEM_ENVIO",
            "avaliados": len(sent), "followups": results, "envios_realizados": 0}
