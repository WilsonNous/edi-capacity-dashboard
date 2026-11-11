"""VR Beneficios portfolio lifecycle bridge, reusing the existing VR01 executor."""
from __future__ import annotations

import json
import re
import hashlib
from datetime import datetime, timezone
from ednna.eddy_vr01_offline_proposals import listar_chamados_vr_mysql
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.eddy_vr_mysql_sync import clientes_do_redmine
from ednna.eddy_vr_origin import identificar_vr


def _cnpj(issue: dict) -> str | None:
    """Accept only an explicit single CNPJ from the Redmine issue."""
    candidates = set()
    for field in issue.get("custom_fields") or []:
        if "cnpj" not in str(field.get("name") or "").casefold():
            continue
        value = field.get("value")
        for item in (value if isinstance(value, list) else [value]):
            digits = re.sub(r"\D", "", str(item or ""))
            if len(digits) == 14:
                candidates.add(digits)
    return next(iter(candidates)) if len(candidates) == 1 else None


def diagnosticar_identificacao_cliente(issue: dict) -> dict:
    """Explain VR01 identity failures without exposing CNPJ or client names.

    Keep the existing fail-closed rule: exactly one Clientes (field id 1)
    and exactly one explicit 14-digit CNPJ in a named custom field.
    """
    clients = clientes_do_redmine(issue)
    cnpjs = set()
    invalid_cnpj = False
    for field in issue.get("custom_fields") or []:
        if not isinstance(field, dict) or "cnpj" not in str(field.get("name") or "").casefold():
            continue
        value = field.get("value")
        for item in (value if isinstance(value, list) else [value]):
            raw = str(item or "").strip()
            if not raw:
                continue
            digits = re.sub(r"\D", "", raw)
            if len(digits) == 14:
                cnpjs.add(digits)
            else:
                invalid_cnpj = True
    reasons = []
    if not clients:
        reasons.append("CLIENTE_AUSENTE")
    elif len(clients) > 1:
        reasons.append("CLIENTE_AMBIGUO")
    if not cnpjs:
        reasons.append("CNPJ_INVALIDO" if invalid_cnpj else "CNPJ_AUSENTE")
    elif len(cnpjs) > 1:
        reasons.append("CNPJ_AMBIGUO")
    return {"motivos": reasons, "quantidade_clientes": len(clients),
            "quantidade_cnpjs_validos": len(cnpjs)}


def _recuperar_historico(issue_id: int, issue: dict) -> dict | None:
    """Recover a complete journal snapshot through the existing Redmine sync.

    Never infer completeness from the generic panel snapshot. Only the shared
    validated detail reader and transactional MySQL writer can mark it complete.
    """
    from ednna.redmine_resilient_reads import detalhe_com_retomada
    from ednna.eddy_vr_mysql_sync import _snapshot
    from ednna.mysql_snapshot_repository import salvar_snapshot
    leitura = detalhe_com_retomada(issue, force=True)
    detail = leitura["detalhe"]
    if int(detail.get("id") or 0) != issue_id:
        raise ValueError("Detalhe Redmine divergente")
    row, journals = _snapshot(detail, datetime.now(timezone.utc).replace(tzinfo=None))
    salvar_snapshot(row, journals)
    return carregar_snapshot(issue_id)


def _aprovacoes_automaticas_portal(issue_id: int, live: dict, ledger: dict | None,
                                  *, enabled_flag: bool) -> dict:
    """Approve only portal sends, scoped to one live Redmine version."""
    if not enabled_flag or not live.get("updated_on") or not ledger:
        return {}
    if ledger.get("fase") != "AGUARDA_CONTATO_BP" or ledger.get("operacao_pendente"):
        return {}
    if ledger.get("envio_graph_confirmado"):
        return {}
    return {"SOLICITAR_AUTORIZACAO_PORTAL": {
        "issue_id": issue_id, "redmine_updated_on": live["updated_on"]
    }}


def _reconciliar_solicitacao_existente(issue_id: int, live: dict, ledger: dict | None) -> dict:
    """Correlate the exact VR01 portal request to Graph before any new send.

    Never infer a portal authorization from an email, and never replay a send.
    Ambiguous historical messages stay blocked for review.
    """
    if not ledger or ledger.get("fase") != "AGUARDA_CONTATO_BP":
        return {"estado": "FORA_DA_ETAPA"}
    if ledger.get("envio_graph_confirmado"):
        return {"estado": "ENVIO_JA_CONFIRMADO"}
    from ednna.eddy_global_config import setting
    from ednna.email_sender import listar_emails_enviados_por_chamado
    from ednna.eddy_vr01_email_templates import assunto_vr01
    from ednna.eddy_vr01_integrated import (
        _context, _valid_bp, _bp_contacts, _advance, _event,
    )
    sender = setting("EDDY_EMAIL_FROM")
    bp = _valid_bp()
    if not sender or not bp or not live.get("updated_on"):
        return {"estado": "AGUARDA_EVIDENCIAS"}
    subject = assunto_vr01(issue_id, _context()["cliente"])
    items = listar_emails_enviados_por_chamado(remetente=sender, chamado_id=issue_id)
    verified = {str(row["email"]).strip().casefold() for row in _bp_contacts()}
    verified.add(str(bp["email"]).strip().casefold())
    matching = []
    for item in items:
        if str(item.get("subject") or "").strip() != subject:
            continue
        if not item.get("sentDateTime") or not (item.get("internetMessageId") or item.get("id")):
            continue
        recipients = {
            str((x.get("emailAddress") or {}).get("address") or "").strip().casefold()
            for x in (item.get("toRecipients") or [])
        }
        copied = {
            str((x.get("emailAddress") or {}).get("address") or "").strip().casefold()
            for x in (item.get("ccRecipients") or [])
        }
        # Historical deliveries may use an older primary and multiple CCs.
        # Never rewrite their real recipient headers.
        if not recipients or not recipients.issubset(verified) or not copied.issubset(verified):
            continue
        if not (item.get("body") or {}).get("content") and not item.get("bodyPreview"):
            continue
        matching.append(item)
    if len(matching) != 1:
        return {"estado": "ENVIO_AMBIGUO" if items else "ENVIO_NAO_LOCALIZADO"}
    if ledger.get("operacao_pendente") not in (None, "SOLICITAR_AUTORIZACAO_PORTAL"):
        return {"estado": "OPERACAO_DIVERGENTE"}
    from ednna.eddy_vr01_integrated import _reserve
    if ledger.get("operacao_pendente") is None and not _reserve(
        "AGUARDA_CONTATO_BP", "SOLICITAR_AUTORIZACAO_PORTAL"
    ):
        return {"estado": "RESERVA_CONCORRENTE"}
    message = matching[0]
    _event("SOLICITACAO_CLIENTE", str(message.get("internetMessageId") or message["id"]))
    # Reuse the existing Sent Items journal formatter and marker deduplication.
    from ednna.redmine_outbox import registrar_ou_enfileirar, _nota_sent_item
    from ednna.redmine_writer import nota_marcador_ja_existe
    nota, marcador = _nota_sent_item(message, 0)
    if nota_marcador_ja_existe(issue_id, marcador):
        result = {"ok": True, "ja_registrado": True}
    else:
        result = registrar_ou_enfileirar(
            chamado_id=issue_id, regra_id="VR01",
            nota=nota, status_nome="Aguardando Retorno Cliente",
        )
    if not (result.get("ok") or result.get("pendente")):
        return {"estado": "REDMINE_PENDENTE"}
    _advance("AGUARDA_CONTATO_BP", "SOLICITAR_AUTORIZACAO_PORTAL",
             "SOLICITACAO_ENVIADA", destinatario=str((message["toRecipients"][0]["emailAddress"])["address"]).strip().lower(),
             bp_source_id=bp["source_id"], envio_graph_confirmado=1)
    return {"estado": "ENVIO_EXISTENTE_RECONCILIADO", "envios_realizados": 0}



def _reservar_consulta_identidade(issue_id: int) -> bool:
    """MySQL-backed cooldown shared by scheduler replicas; no Redmine storm."""
    from ednna.mysql_storage import connect
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS eddy_vr01_identity_probe (
                chamado_id BIGINT NOT NULL PRIMARY KEY,
                ultima_tentativa DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            cur.execute("""INSERT IGNORE INTO eddy_vr01_identity_probe
                (chamado_id, ultima_tentativa) VALUES (%s, UTC_TIMESTAMP())""",
                (issue_id,))
            if cur.rowcount == 1:
                return True
            cur.execute("""UPDATE eddy_vr01_identity_probe
                SET ultima_tentativa=UTC_TIMESTAMP()
                WHERE chamado_id=%s
                AND ultima_tentativa <= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 30 MINUTE)""",
                (issue_id,))
            return cur.rowcount == 1


def _recuperar_contatos_bp_pendentes(issue_id: int, cliente: str) -> dict:
    """Delegate recovery to the shared Blueprint engine."""
    from ednna.mysql_blueprint_participants import recuperar_contatos_blueprint
    return recuperar_contatos_blueprint(issue_id, cliente)


def executar_carteira_vr01(*, ids=None, execute=False, approvals_by_issue=None) -> dict:
    from ednna.eddy_vr01_integrated import (
        _load, _identity, _read_issue, escopo_vr01, planejar_vr01,
    )
    from ednna.eddy_vr_inbox_reconciliation import reconciliar_respostas_vr01
    from ednna.eddy_global_config import enabled

    selected = tuple(dict.fromkeys(int(i) for i in (
        listar_chamados_vr_mysql() if ids is None else ids
    )))
    outcomes = []
    for issue_id in selected:
        etapa = "CARREGAR_SNAPSHOT"
        entry = {"chamado_id": issue_id, "execucao_externa": False}
        try:
            snapshot = carregar_snapshot(issue_id)
            if not snapshot:
                entry["estado"] = "SEM_SNAPSHOT"
                outcomes.append(entry)
                continue
            issue = snapshot["chamado"].get("payload_json") or {}
            if isinstance(issue, str):
                issue = json.loads(issue)
            if (not isinstance(issue, dict) or int(issue.get("id") or 0) != issue_id
                    or not identificar_vr(issue) or (issue.get("status") or {}).get("is_closed")
                    or issue.get("closed_on") or any(
                        word in str((issue.get("status") or {}).get("name") or "").casefold()
                        for word in ("conclu", "fechad", "cancelad", "rejeitad")
                    )):
                entry["estado"] = "NAO_ELEGIVEL"
                outcomes.append(entry)
                continue
            if issue.get("_eddy_journals_completos") is not True:
                if execute:
                    try:
                        recovered = _recuperar_historico(issue_id, issue)
                        if recovered:
                            snapshot = recovered
                            issue = snapshot["chamado"].get("payload_json") or {}
                            if isinstance(issue, str):
                                issue = json.loads(issue)
                            entry["historico_recuperado"] = (
                                isinstance(issue, dict)
                                and issue.get("_eddy_journals_completos") is True
                            )
                    except Exception as exc:
                        entry["recuperacao_erro"] = type(exc).__name__
                if not isinstance(issue, dict) or issue.get("_eddy_journals_completos") is not True:
                    entry["estado"] = "HISTORICO_INCOMPLETO"
                    outcomes.append(entry)
                    continue
            etapa = "RESOLVER_IDENTIDADE_CLIENTE"
            clients = clientes_do_redmine(issue)
            from ednna.eddy_client_identity import resolver_identidade_cliente
            cliente_mysql = str(snapshot["chamado"].get("cliente") or "").strip()
            identidade = resolver_identidade_cliente(issue, cliente_override=cliente_mysql) if len(clients) == 1 else {
                "estado": "CLIENTE_AMBIGUO" if clients else "CLIENTE_AUSENTE",
                "cnpj": None,
            }
            # A bounded, targeted recovery for an issue with confirmed customer reply.
            # Remote Blueprint reads are explicit; a failed probe cannot authorize
            # an external action or silently select one of multiple CNPJs.
            if (execute and issue_id == 50428 and len(clients) == 1
                    and not identidade.get("cnpj") and _reservar_consulta_identidade(issue_id)):
                try:
                    recovered_identity = resolver_identidade_cliente(
                        issue, cliente_override=cliente_mysql, allow_remote=True,
                    )
                    entry["identidade_consulta_pontual"] = recovered_identity.get("estado")
                    if recovered_identity.get("cnpj") and not recovered_identity.get("desatualizado"):
                        identidade = recovered_identity
                except Exception as exc:
                    entry["identidade_consulta_pontual"] = type(exc).__name__
            cnpj = identidade.get("cnpj")
            if execute and identidade.get("desatualizado"):
                entry["estado"] = "IDENTIDADE_DESATUALIZADA_EXECUCAO_SUSPENSA"
                outcomes.append(entry)
                continue
            if len(clients) != 1 or not cnpj:
                entry["estado"] = "IDENTIFICACAO_CLIENTE_PENDENTE"
                entry["diagnostico_identificacao"] = {"origem": "BLUEPRINT", "estado": identidade["estado"], **diagnosticar_identificacao_cliente(issue)}
                outcomes.append(entry)
                continue
            # Operational routing is a suggestion, never a substitute for a
            # verified Redmine assignee, complete journals or lifecycle ledger.
            from ednna.eddy_owner_routing import sugerir_responsavel
            entry["distribuicao_humana"] = sugerir_responsavel(clients[0])
            # The existing pilot ledger is authoritative about original ownership.
            # New issues use the current Redmine owner only when not already EDDY.
            etapa = "CARREGAR_LEDGER"
            with escopo_vr01(issue_id, 1, clients[0], cnpj):
                ledger = _load()
            original_owner = (int(ledger["original_owner_id"]) if ledger else
                              int((issue.get("assigned_to") or {}).get("id") or 0))
            if not original_owner or original_owner == _identity():
                from ednna.eddy_vr_original_owner import recuperar_responsavel_por_journals
                recovered_owner = recuperar_responsavel_por_journals(
                    issue, snapshot.get("journals") or [], _identity()
                )
                if recovered_owner:
                    original_owner = recovered_owner
                    entry["responsavel_original_fonte"] = "JOURNAL_REDMINE_MYSQL"
            if not original_owner or original_owner == _identity():
                entry["estado"] = "RESPONSAVEL_ORIGINAL_NAO_IDENTIFICADO"
                outcomes.append(entry)
                continue
            etapa = "PLANEJAR_OU_EXECUTAR"
            with escopo_vr01(issue_id, original_owner, clients[0], cnpj):
                # Waiting for a customer is not a Redmine mutation. The ledger
                # and verified snapshot remain authoritative for observation;
                # inbox reconciliation may detect new evidence independently.
                # A later actionable transition still requires fresh Redmine
                # preflight in the executor.
                if (execute and ledger
                        and ledger.get("fase") == "AGUARDA_CONFIRMACAO_CLIENTE"
                        and not ledger.get("autorizacao_confirmada")
                        and not ledger.get("operacao_pendente")
                        and ledger.get("envio_graph_confirmado")
                        and ledger.get("eddy_owner_id") == _identity()
                        and (issue.get("assigned_to") or {}).get("id") == _identity()):
                    etapa = "ACOMPANHAMENTO_LOCAL"
                    entry.update(planejar_vr01(execute=False))
                    entry["preflight_redmine"] = "DISPENSADO_AGUARDANDO_CLIENTE"
                    if enabled("EDDY_VR01_REPLY_RECONCILIATION_READY"):
                        etapa = "RECONCILIAR_INBOX"
                        entry["inbox"] = reconciliar_respostas_vr01([issue_id])
                    entry["cliente"] = clients[0]
                    outcomes.append(entry)
                    continue
                if not execute:
                    etapa = "OBSERVAR_ESTADO_MYSQL"
                    entry.update(planejar_vr01(execute=False))
                else:
                    # Never initiate a Redmine/Graph action from a stale snapshot.
                    etapa = "PREFLIGHT_REDMINE"
                    live = _read_issue(issue_id)
                    if live.get("updated_on") != issue.get("updated_on"):
                        entry["estado"] = "SNAPSHOT_DESATUALIZADO"
                    elif (len(clientes_do_redmine(live)) != 1 or clientes_do_redmine(live)[0] != clients[0] or (resolver_identidade_cliente(live, cliente_override=cliente_mysql, allow_remote=False).get("cnpj") not in (None, cnpj)) or (_cnpj(live) is not None and _cnpj(live) != cnpj)):
                        entry["estado"] = "DADOS_CLIENTE_DIVERGENTES"
                    else:
                        # Reconcile an existing Graph send before approving a new one.
                        # A Graph failure fails closed and cannot trigger dispatch.
                        if ledger and ledger.get("fase") == "AGUARDA_CONTATO_BP":
                            etapa = "RECUPERAR_CONTATOS_BP"
                            try:
                                entry["recuperacao_bp"] = _recuperar_contatos_bp_pendentes(
                                    issue_id, clients[0]
                                )
                            except Exception as exc:
                                entry["recuperacao_bp"] = {"estado": "FONTE_BP_INDISPONIVEL",
                                                         "erro": type(exc).__name__}
                            etapa = "RECONCILIAR_ENVIO_ANTERIOR"
                            try:
                                entry["envio_anterior"] = _reconciliar_solicitacao_existente(
                                    issue_id, live, ledger
                                )
                            except Exception as exc:
                                entry["estado"] = "RECONCILIACAO_INDISPONIVEL"
                                entry["erro_reconciliacao"] = type(exc).__name__
                                outcomes.append(entry)
                                continue
                            if entry["envio_anterior"]["estado"] == "ENVIO_EXISTENTE_RECONCILIADO":
                                entry["estado"] = "ENVIO_EXISTENTE_RECONCILIADO"
                                outcomes.append(entry)
                                continue
                            if entry["envio_anterior"]["estado"] in (
                                "ENVIO_AMBIGUO", "OPERACAO_DIVERGENTE", "RESERVA_CONCORRENTE",
                                "REDMINE_PENDENTE",
                            ):
                                entry["estado"] = "AGUARDA_REVISAO_ENVIO"
                                outcomes.append(entry)
                                continue
                        # Run the same audited executor for every eligible issue.
                        # Approval payloads are scoped to the issue; never reuse
                        # one customer's authorization for another ticket.
                        # Preserve explicit approvals; auto-authorize portal only.
                        approvals = dict((approvals_by_issue or {}).get(issue_id, {}))
                        if "SOLICITAR_AUTORIZACAO_PORTAL" not in approvals:
                            approvals.update(_aprovacoes_automaticas_portal(
                                issue_id, live, ledger,
                                enabled_flag=enabled("EDDY_VR01_AUTO_SEND_PORTAL"),
                            ))
                        try:
                            etapa = "EXECUTOR_VR01"
                            # Reconcile a legacy EDDY assignment only with complete journals
                            # from the exact live Redmine version and matching human owner.
                            recovered_owner_id = None
                            if ledger is None and (live.get("assigned_to") or {}).get("id") == _identity():
                                from ednna.eddy_vr_original_owner import recuperar_responsavel_por_journals
                                journal_issue = dict(issue)
                                journal_issue["_eddy_journals_completos"] = (
                                    issue.get("_eddy_journals_completos") is True
                                    and issue.get("updated_on") == live.get("updated_on")
                                )
                                candidate = recuperar_responsavel_por_journals(
                                    journal_issue, snapshot.get("journals") or [], _identity()
                                )
                                if candidate == original_owner:
                                    recovered_owner_id = candidate
                            result = planejar_vr01(
                                execute=True, approvals=approvals, verified_issue=live,
                                recovered_owner_id=recovered_owner_id,
                            )
                            entry.update(result)
                            entry["execucao_externa"] = bool(result.get("externo"))
                        except PermissionError:
                            entry["estado"] = "AGUARDA_APROVACAO_ACAO"
                        # Reply reconciliation is independent of dispatch.
                        ledger = _load()
                        if (ledger and ledger["fase"] == "AGUARDA_CONFIRMACAO_CLIENTE"
                                and not ledger["autorizacao_confirmada"]
                                and enabled("EDDY_VR01_REPLY_RECONCILIATION_READY")):
                            etapa = "RECONCILIAR_INBOX"
                            entry["inbox"] = reconciliar_respostas_vr01([issue_id])
            entry["cliente"] = clients[0]
        except Exception as exc:
            entry["estado"] = "FALHA_SEGURA"
            entry["erro"] = type(exc).__name__
            entry["etapa_falha"] = etapa
            # Keep logs actionable without leaking credentials, client data or raw URLs.
            # Fingerprints group recurring failures without persisting exception messages.
            origin = type(exc).__module__ + "." + type(exc).__qualname__
            entry["erro_fingerprint"] = hashlib.sha256(
                (etapa + ":" + origin).encode("utf-8")
            ).hexdigest()[:16]
            entry["erro_causa"] = (
                type(exc.__cause__).__name__ if exc.__cause__ else None
            )
            # Classify the known executor rejection without exposing exception
            # messages or customer details in production logs.
            if etapa == "EXECUTOR_VR01" and isinstance(exc, RuntimeError):
                reason = str(exc)
                entry["executor_diagnostico"] = {
                    "Responsavel original divergente: nao assumir": "RESPONSAVEL_ORIGINAL_DIVERGENTE",
                    "Transicao nao reconciliada": "TRANSICAO_MYSQL_NAO_RECONCILIADA",
                    "Redmine preflight bloqueado": "PREFLIGHT_INTERNO_BLOQUEADO",
                    "Blueprint sem destinatario com origem comprovada": "BLUEPRINT_DESTINATARIO_AUSENTE",
                }.get(reason, "EXECUTOR_RUNTIME_NAO_CLASSIFICADO")
            # Stable operational reason codes; never log raw exception text.
            if etapa == "PREFLIGHT_REDMINE" and isinstance(exc, RuntimeError):
                entry["motivo_operacional"] = "PREFLIGHT_REDMINE_INDISPONIVEL_OU_BLOQUEADO"
            elif etapa == "EXECUTOR_VR01" and isinstance(exc, RuntimeError):
                entry["motivo_operacional"] = "EXECUTOR_REJEITOU_TRANSICAO"
            elif etapa == "RECONCILIAR_INBOX":
                entry["motivo_operacional"] = "CONCILIACAO_RESPOSTAS_FALHOU"
        outcomes.append(entry)
    return {"estado": "CARTEIRA_VR01_PROCESSADA", "avaliados": len(outcomes),
            "chamados": outcomes, "execucao_externa": any(
                item.get("execucao_externa") for item in outcomes)}
