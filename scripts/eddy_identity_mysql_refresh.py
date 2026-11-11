"""Global, bounded Blueprint enrichment: Redmine sources, MySQL persistence.

Rotates through all known clients across cycles; never sends mail or writes Redmine.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone

from ednna.mysql_storage import connect

CURSOR_DDL = """CREATE TABLE IF NOT EXISTS eddy_blueprint_refresh_cursor (
    worker VARCHAR(64) NOT NULL PRIMARY KEY,
    last_cliente VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def _inventario():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, cliente, payload_json FROM eddy_chamados
                           WHERE cliente IS NOT NULL AND cliente <> ''
                           ORDER BY alterado_em DESC""")
            rows = cur.fetchall()
    chosen = {}
    for issue_id, cliente, payload in rows:
        try:
            issue = json.loads(payload) if isinstance(payload, str) else payload
            if not isinstance(issue, dict) or int(issue.get("id") or 0) != int(issue_id):
                continue
            status = issue.get("status") or {}
            status_name = str(status.get("name") or "").casefold()
            if (status.get("is_closed") or issue.get("closed_on")
                    or any(word in status_name for word in
                           ("conclu", "fechad", "cancelad", "rejeitad"))):
                continue
            chosen.setdefault(str(cliente).strip(), issue)
        except (TypeError, ValueError):
            continue
    return chosen


PENDING_DDL = """CREATE TABLE IF NOT EXISTS eddy_blueprint_refresh_pending (
    cliente VARCHAR(255) NOT NULL PRIMARY KEY,
    tentativas INT NOT NULL DEFAULT 0,
    proxima_tentativa DATETIME(6) NOT NULL,
    atualizado_em DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def _registrar_pendente(cliente):
    """Keep failed clients durable without pinning the fair scan cursor."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(PENDING_DDL)
            cur.execute("""INSERT INTO eddy_blueprint_refresh_pending
                (cliente, tentativas, proxima_tentativa, atualizado_em)
                VALUES (%s, 1, DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 60 SECOND), UTC_TIMESTAMP(6))
                ON DUPLICATE KEY UPDATE
                tentativas=tentativas+1,
                proxima_tentativa=DATE_ADD(UTC_TIMESTAMP(6),
                    INTERVAL LEAST(3600, 60 * POW(2, LEAST(tentativas, 6))) SECOND),
                atualizado_em=UTC_TIMESTAMP(6)""", (cliente,))


def _limpar_pendente(cliente):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(PENDING_DDL)
            cur.execute("DELETE FROM eddy_blueprint_refresh_pending WHERE cliente=%s", (cliente,))


def _pendentes_prontos(chosen, limite):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(PENDING_DDL)
            cur.execute("""SELECT cliente FROM eddy_blueprint_refresh_pending
                WHERE proxima_tentativa <= UTC_TIMESTAMP(6)
                ORDER BY proxima_tentativa, atualizado_em LIMIT %s""", (int(limite),))
            return [row[0] for row in cur.fetchall() if row[0] in chosen]


def _lote(chosen, limite):
    """Durable cursor: failure in one cycle cannot starve the other clients."""
    # Prioritize active VR, then rotate fairly across the entire inventory.
    from ednna.eddy_vr_origin import identificar_vr
    names = sorted(chosen, key=lambda name: (
        0 if identificar_vr(chosen[name]) else 1, name
    ))
    if not names:
        return []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(CURSOR_DDL)
            cur.execute("SELECT last_cliente FROM eddy_blueprint_refresh_cursor WHERE worker=%s",
                        ("GLOBAL_BP",))
            row = cur.fetchone()
            last = str(row[0]) if row else ""
            start = (names.index(last) + 1) % len(names) if last in names else 0
            batch = [names[(start + i) % len(names)]
                     for i in range(min(len(names), max(1, min(int(limite), 100))))]
    # Retry due failures first, while reserving at least half the batch for
    # circular inventory coverage so a sick customer cannot starve others.
    pending = _pendentes_prontos(chosen, max(1, len(batch) // 2))
    selected = list(dict.fromkeys(pending + batch))[:len(batch)]
    return [(name, chosen[name]) for name in selected]


def _confirmar_progresso(cliente):
    """Advance the scan cursor after an attempt, including a failed remote probe.

    This is a scan position, not a claim that the client has been resolved.
    The circular inventory revisits the client on a subsequent rotation.
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(CURSOR_DDL)
            cur.execute("""INSERT INTO eddy_blueprint_refresh_cursor (worker, last_cliente)
                           VALUES (%s,%s) ON DUPLICATE KEY UPDATE last_cliente=VALUES(last_cliente)""",
                        ("GLOBAL_BP", cliente))



def _retry_delay_seconds():
    try:
        return max(60, min(int(os.getenv("EDDY_BP_REDMINE_RETRY_SECONDS", "300")), 3600))
    except (ValueError, TypeError):
        return 300


def _cooldown_active():
    """Durable global Redmine cooldown, shared across all rules and workers."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS eddy_bp_redmine_cooldown (
                worker VARCHAR(64) NOT NULL PRIMARY KEY,
                retry_after DATETIME(6) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            cur.execute("SELECT retry_after FROM eddy_bp_redmine_cooldown WHERE worker=%s",
                        ("GLOBAL_BP",))
            row = cur.fetchone()
    if not row:
        return False
    retry_after = row[0]
    if isinstance(retry_after, str):
        retry_after = datetime.fromisoformat(retry_after)
    if retry_after.tzinfo:
        retry_after = retry_after.astimezone(timezone.utc).replace(tzinfo=None)
    return retry_after > datetime.now(timezone.utc).replace(tzinfo=None)


def _set_cooldown():
    retry_after = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        seconds=_retry_delay_seconds())
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_bp_redmine_cooldown(worker, retry_after)
                VALUES (%s,%s) ON DUPLICATE KEY UPDATE retry_after=VALUES(retry_after)""",
                ("GLOBAL_BP", retry_after))


def executar_uma_vez(limite=20):
    from ednna.eddy_client_identity import resolver_identidade_cliente
    from ednna.mysql_blueprint_participants import descobrir_e_sincronizar_participantes_mysql
    chosen = _inventario()
    if _cooldown_active():
        return {"clientes": len(chosen), "selecionados": 0, "estado": "REDMINE_COOLDOWN",
                "interrompido_por_redmine": True, "retry_seconds": _retry_delay_seconds()}
    batch = _lote(chosen, limite)
    stats = {"clientes": len(chosen), "selecionados": len(batch), "bp_sincronizados": 0,
             "consultados": 0, "resolvidos": 0, "indisponiveis": 0,
             "sem_bp": 0, "sem_blueprint": 0, "falhas_descoberta": 0,
             "falhas_anexo": 0, "interrompido_por_redmine": False,
             "ultimo_cliente_tentado": None, "cursor_avancado_apos_falha": False}
    for cliente, issue in batch:
        stats["ultimo_cliente_tentado"] = cliente
        discovery = descobrir_e_sincronizar_participantes_mysql(
            {int(issue["id"]): cliente}, aplicar=True, skip_imported=False)
        statuses = [row.get("status") for row in discovery.get("resultados", [])]
        contexts = [row.get("status") for row in discovery.get("descoberta", [])]
        stats["bp_sincronizados"] += statuses.count("IMPORTADO")
        stats["sem_blueprint"] += contexts.count("BLUEPRINT_NAO_LOCALIZADO")
        stats["falhas_descoberta"] += contexts.count("CONTEXTO_INDISPONIVEL")
        stats["falhas_anexo"] += statuses.count("ERRO_ANEXO") + statuses.count("ERRO_CHAMADO")
        # Avoid a second Redmine relation walk if the first has already failed.
        if "CONTEXTO_INDISPONIVEL" in contexts:
            stats["indisponiveis"] += 1
            stats["interrompido_por_redmine"] = True
            _registrar_pendente(cliente)
            _confirmar_progresso(cliente)
            stats["cursor_avancado_apos_falha"] = True
            _set_cooldown()
            break
        result = resolver_identidade_cliente(
            issue, allow_remote=False, cliente_override=cliente, refresh_mysql=True)
        stats["consultados"] += 1
        if result["estado"] == "RESOLVIDO":
            stats["resolvidos"] += 1
        elif result["estado"] == "IDENTIDADE_MYSQL_INDISPONIVEL":
            stats["indisponiveis"] += 1
            _registrar_pendente(cliente)
            break
        else:
            stats["sem_bp"] += 1
        _limpar_pendente(cliente)
        _confirmar_progresso(cliente)
    return stats


def main():
    interval = max(1800, int(os.getenv("EDDY_IDENTITY_REFRESH_INTERVAL_SECONDS", "1800")))
    while True:
        try:
            print("[EDDY-IDENTIDADE-MYSQL] " +
                  json.dumps(executar_uma_vez(), ensure_ascii=False), flush=True)
        except Exception as exc:
            print("[EDDY-IDENTIDADE-MYSQL] falha=" + type(exc).__name__, flush=True)
        time.sleep(min(interval, _retry_delay_seconds()))


if __name__ == "__main__":
    main()
