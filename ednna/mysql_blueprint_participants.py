"""MySQL read model for Blueprint participants; no SQLite on VR01 read path.

Migration is explicit, read-only on source and atomic on destination.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

from ednna.mysql_storage import connect


DDL = """CREATE TABLE IF NOT EXISTS eddy_blueprint_participants (
    source_id BIGINT NOT NULL PRIMARY KEY,
    cliente VARCHAR(255) NOT NULL,
    nome TEXT NULL,
    area VARCHAR(255) NULL,
    email VARCHAR(320) NULL,
    telefone TEXT NULL,
    andamento VARCHAR(32) NULL,
    status_report VARCHAR(32) NULL,
    documento_id BIGINT NOT NULL,
    chamado_id BIGINT NOT NULL,
    ativo TINYINT NOT NULL,
    fonte_arquivo TEXT NULL,
    attachment_id BIGINT NULL,
    importado_em VARCHAR(64) NULL,
    KEY idx_bp_cliente_ativo (cliente, ativo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def preparar():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)


def selecionar_contatos_cliente_mysql(cliente, limite=10, area_preferida="FINANCEIRO"):
    def _norm(value):
        text = unicodedata.normalize("NFKD", str(value or "").strip().upper())
        return "".join(ch for ch in text if not unicodedata.combining(ch))
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT source_id, cliente, nome, area, email, telefone, andamento,
                status_report, documento_id, chamado_id, ativo, fonte_arquivo,
                attachment_id, importado_em
                FROM eddy_blueprint_participants
                WHERE cliente=%s AND ativo=1
                ORDER BY importado_em DESC, source_id ASC""", (cliente,))
            columns = [x[0] for x in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    unique, seen = [], set()
    for row in rows:
        email = str(row.get("email") or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(row)
    pref = _norm(area_preferida)
    def score(row):
        area = _norm(row.get("area"))
        andamento = _norm(row.get("andamento")) in {"SIM", "S", "YES", "TRUE", "1"}
        status = _norm(row.get("status_report")) in {"SIM", "S", "YES", "TRUE", "1"}
        return (0 if area == pref else (1 if "GERENTE/COORD" in area else 2),
                0 if andamento else 1, 0 if status else 1)
    unique.sort(key=score)
    return unique[:max(1, int(limite or 1))]


def importar_participantes_sqlite(caminho, *, aplicar=False):
    """Only import a fully readable source; never overwrite or repair SQLite."""
    path = Path(caminho)
    if not path.is_file():
        raise FileNotFoundError("Arquivo SQLite de origem inexistente")
    uri = path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as source:
        check = source.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise ValueError("SQLite corrompido: preservar arquivo e recuperar de backup")
        rows = source.execute("""SELECT p.id, p.cliente, p.nome, p.area, p.email,
            p.telefone, p.andamento, p.status_report, p.documento_id,
            p.chamado_id, p.ativo, d.nome_arquivo, d.attachment_id,
            d.importado_em
            FROM blueprint_participantes p JOIN blueprint_documentos d
            ON d.id=p.documento_id ORDER BY p.id""").fetchall()
    if not aplicar:
        return {"modo": "DRY_RUN", "participantes": len(rows), "mysql_escritas": 0}
    preparar()
    with connect() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute("""INSERT INTO eddy_blueprint_participants
                    (source_id, cliente, nome, area, email, telefone, andamento,
                     status_report, documento_id, chamado_id, ativo, fonte_arquivo,
                     attachment_id, importado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE cliente=VALUES(cliente),
                    nome=VALUES(nome), area=VALUES(area), email=VALUES(email),
                    telefone=VALUES(telefone), andamento=VALUES(andamento),
                    status_report=VALUES(status_report), ativo=VALUES(ativo),
                    fonte_arquivo=VALUES(fonte_arquivo),
                    attachment_id=VALUES(attachment_id),
                    importado_em=VALUES(importado_em)""", row)
    return {"modo": "IMPORTADO", "participantes": len(rows), "mysql_escritas": len(rows)}


def sincronizar_blueprints_redmine_mysql(pilotos, *, aplicar=False, skip_imported=False):
    """Read Redmine attachments and reuse Blueprint parsers; never open SQLite.

    pilotos: mapping issue_id -> verified client label. Read-only unless aplicar.
    """
    import hashlib
    from pathlib import Path
    from ednna.blueprint_knowledge import (
        ler_excel, _eh_blueprint, _norm, _dict_rows, _valor,
        _email_valido, _participantes_legado_id_projeto,
    )
    from redmine_api import buscar_detalhes_chamado, baixar_anexo_redmine
    from ednna.eddy_client_identity import cnpjs_blueprint
    from ednna.eddy_blueprint_identity_evidence import registrar_bp

    def stable_id(*parts):
        digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)

    results = []
    for issue_id, cliente in pilotos.items():
        issue_id = int(issue_id)
        cliente = str(cliente or "").strip()
        if not cliente:
            results.append({"chamado_id": issue_id, "status": "CLIENTE_NAO_RESOLVIDO"})
            continue
        try:
            issue = buscar_detalhes_chamado(issue_id, incluir_anexos=True, consulta_pontual=True)
            attachments = issue.get("attachments", []) or []
            if not attachments:
                results.append({"chamado_id": issue_id, "cliente": cliente,
                                "status": "SEM_ANEXOS_REDMINE", "participantes": 0})
            excel_found = False
            cnpjs_bp = set()
            blueprint_verificado = False
            for attachment in attachments:
                filename = str(attachment.get("filename") or "")
                if Path(filename).suffix.lower() not in (".xls", ".xlsx"):
                    continue
                excel_found = True
                attachment_id = int(attachment.get("id") or 0)
                try:
                    if aplicar and skip_imported and attachment_id:
                        with connect() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "SELECT COUNT(*) FROM eddy_blueprint_participants "
                                    "WHERE attachment_id=%s AND chamado_id=%s "
                                    "AND cliente=%s AND ativo=1",
                                    (attachment_id, issue_id, cliente),
                                )
                                existing = int(cur.fetchone()[0])
                        if existing:
                            results.append({
                                "chamado_id": issue_id, "cliente": cliente,
                                "attachment_id": attachment_id,
                                "status": "JA_IMPORTADO",
                                "participantes": existing,
                            })
                            continue
                    data = baixar_anexo_redmine(str(attachment.get("content_url") or ""))
                    abas = ler_excel(data, filename)
                    if not _eh_blueprint(filename, list(abas)):
                        continue
                    blueprint_verificado = True
                    cnpjs_bp.update(cnpjs_blueprint(issue, abas))
                    part_name = next((a for a in abas if _norm(a) == "PARTICIPANTES"), None)
                    participantes = []
                    if part_name:
                        for item in _dict_rows(abas[part_name]):
                            norm = {_norm(k): _valor(v) for k, v in item.items()}
                            email = _email_valido(norm.get("E-MAIL") or norm.get("EMAIL"))
                            if email:
                                participantes.append({
                                    "nome": norm.get("NOME", ""), "area": norm.get("AREA", ""),
                                    "email": email, "telefone": norm.get("TELEFONE WAPP") or norm.get("TELEFONE") or "",
                                    "andamento": norm.get("ANDAMENTO", ""),
                                    "status_report": norm.get("STATUS REPORT", ""),
                                })
                    layout = "MODERNO" if participantes else "ID_PROJETO_LEGADO"
                    if not participantes:
                        participantes = _participantes_legado_id_projeto(abas)
                    dedup = {p["email"].lower(): p for p in participantes if p.get("email")}
                    digest = hashlib.sha256(data).hexdigest()
                    documento_id = stable_id("documento", digest)
                    rows = []
                    for email, p in dedup.items():
                        rows.append((
                            stable_id("redmine", issue_id, attachment_id or digest, email),
                            cliente, p.get("nome", ""), p.get("area", ""), email,
                            p.get("telefone", ""), p.get("andamento", ""),
                            p.get("status_report", ""), documento_id, issue_id, 1,
                            filename, attachment_id or None,
                        ))
                    if aplicar and rows:
                        preparar()
                        with connect() as conn:
                            with conn.cursor() as cur:
                                cur.executemany("""
                                    INSERT INTO eddy_blueprint_participants
                                    (source_id, cliente, nome, area, email, telefone,
                                     andamento, status_report, documento_id, chamado_id,
                                     ativo, fonte_arquivo, attachment_id, importado_em)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP())
                                    ON DUPLICATE KEY UPDATE
                                    cliente=VALUES(cliente), nome=VALUES(nome),
                                    area=VALUES(area), email=VALUES(email),
                                    telefone=VALUES(telefone),
                                    andamento=VALUES(andamento),
                                    status_report=VALUES(status_report),
                                    ativo=VALUES(ativo),
                                    fonte_arquivo=VALUES(fonte_arquivo),
                                    attachment_id=VALUES(attachment_id)
                                """, rows)
                    results.append({
                        "chamado_id": issue_id, "cliente": cliente,
                        "attachment_id": attachment_id, "arquivo": filename,
                        "layout": layout, "participantes": len(rows),
                        "status": "IMPORTADO" if aplicar else "DRY_RUN",
                    })
                except Exception as exc:
                    results.append({"chamado_id": issue_id, "attachment_id": attachment_id,
                                    "status": "ERRO_ANEXO", "erro": type(exc).__name__})
            if aplicar and blueprint_verificado:
                # Evidence belongs to the actual Blueprint issue, not the operational ticket.
                from ednna.eddy_client_identity import cnpjs_blueprint
                cnpjs_bp.update(cnpjs_blueprint(issue))
                registrar_bp(cliente, issue_id, cnpjs_bp)
            if attachments and not excel_found:
                results.append({"chamado_id": issue_id, "cliente": cliente,
                                "status": "SEM_ANEXOS_EXCEL", "participantes": 0})
        except Exception as exc:
            results.append({"chamado_id": issue_id, "status": "ERRO_CHAMADO",
                            "erro": type(exc).__name__})
    return {
        "modo": "APPLY" if aplicar else "DRY_RUN",
        "mysql_escritas_habilitadas": bool(aplicar),
        "participantes_processados": sum(r.get("participantes", 0) for r in results if r.get("status") != "JA_IMPORTADO"),
        "participantes_reutilizados": sum(r.get("participantes", 0) for r in results if r.get("status") == "JA_IMPORTADO"),
        "resultados": results,
        "redmine_escritas": 0,
        "emails_enviados": 0,
    }


def _ids_relacoes_redmine(issue):
    """IDs de relações Redmine sem consultar cache ou SQLite."""
    atual = int(issue.get("id") or 0)
    ids = set()
    for rel in issue.get("relations", []) or []:
        origem = int(rel.get("issue_id") or 0)
        destino = int(rel.get("issue_to_id") or 0)
        outro = destino if origem == atual else origem if destino == atual else 0
        if outro > 0:
            ids.add(outro)
    return ids


def _eh_bp_redmine(issue):
    """Identifica a raiz BP/Novo Cliente sem dependências de persistência."""
    def norm(value):
        texto = unicodedata.normalize("NFKD", str(value or "").upper())
        return "".join(c for c in texto if not unicodedata.combining(c))
    tracker = norm((issue.get("tracker") or {}).get("name"))
    assunto = norm(issue.get("subject"))
    return "NOVO CLIENTE" in tracker or "NOVO CLIENTE" in assunto


def _descobrir_fontes_redmine(chamado_id):
    """Consulta raiz, relações diretas e relações do BP; falha fechada.

    Não usa ednna.contexto_relacionamentos (cache SQLite). Não interpreta
    eventos de negócio: qualquer anexo Excel relacionado pode conter BP.
    """
    from redmine_api import buscar_detalhes_chamado

    def buscar(iid):
        return buscar_detalhes_chamado(
            int(iid), incluir_relacoes=True, consulta_pontual=False,
            timeout=(4, 8), tentativas=1,
        )

    raiz = buscar(chamado_id)
    if int(raiz.get("id") or 0) != int(chamado_id):
        raise ValueError("REDMINE_ID_INCONSISTENTE")
    ids = {int(chamado_id)}
    bp = raiz if _eh_bp_redmine(raiz) else None
    diretos = _ids_relacoes_redmine(raiz)
    ids.update(diretos)
    for rid in sorted(diretos):
        relacionado = buscar(rid)
        if int(relacionado.get("id") or 0) != rid:
            raise ValueError("REDMINE_RELACAO_INCONSISTENTE")
        if bp is None and _eh_bp_redmine(relacionado):
            bp = relacionado
    if bp:
        ids.update(_ids_relacoes_redmine(bp))
    return ids, int(bp["id"]) if bp else None


def descobrir_e_sincronizar_participantes_mysql(chamados, *, aplicar=False, skip_imported=True):
    """Descoberta Redmine sem SQLite; MySQL apenas na importação autorizada.

    Os clientes são rótulos verificados pelo chamador. Falha em uma relação
    impede importação parcial daquele chamado. Não envia emails nem escreve
    no Redmine. Não habilita execução externa.
    """
    fontes = {}
    conflitos = set()
    diagnosticos = []
    for chamado_id, cliente_esperado in chamados.items():
        chamado_id = int(chamado_id)
        cliente = str(cliente_esperado or "").strip()
        if not cliente:
            diagnosticos.append({"chamado_id": chamado_id, "status": "SEM_CLIENTE"})
            continue
        try:
            ids, bp_id = _descobrir_fontes_redmine(chamado_id)
            if not bp_id:
                diagnosticos.append({"chamado_id": chamado_id, "status": "BLUEPRINT_NAO_LOCALIZADO", "fontes_inspecionadas": len(ids)})
                continue
            # Import only verified BP roots. Related operational issues may have
            # unrelated Excel files and must not become identity evidence.
            for origem_id in (bp_id,):
                anterior = fontes.get(origem_id)
                if anterior and anterior != cliente:
                    conflitos.add(origem_id)
                    diagnosticos.append({"chamado_id": origem_id, "status": "CLIENTE_CONFLITANTE"})
                else:
                    fontes[origem_id] = cliente
            diagnosticos.append({"chamado_id": chamado_id, "status": "CONTEXTO_RESOLVIDO",
                                 "blueprint_id": bp_id, "fontes": len(ids)})
        except Exception as exc:
            diagnosticos.append({"chamado_id": chamado_id, "status": "CONTEXTO_INDISPONIVEL",
                                 "erro": type(exc).__name__})
    for origem_id in conflitos:
        fontes.pop(origem_id, None)
    resultado = sincronizar_blueprints_redmine_mysql(
        fontes, aplicar=aplicar, skip_imported=skip_imported
    ) if fontes else {"modo": "SEM_FONTES", "resultados": [],
                      "participantes_processados": 0, "participantes_reutilizados": 0,
                      "redmine_escritas": 0, "emails_enviados": 0}
    resultado["descoberta"] = diagnosticos
    resultado["fontes_descobertas"] = len(fontes)
    return resultado
