"""Shared EDDY client identity resolver. EDNNA is the historical package name.

Resolve CNPJ from the verified Blueprint, never require it on operational issues.
No SQLite, no external writes and no arbitrary choice among establishments.
"""
from __future__ import annotations

import re
import unicodedata


def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or "").upper())
    return "".join(c for c in value if not unicodedata.combining(c))


def _cnpj_values(value):
    values = value if isinstance(value, list) else [value]
    result = set()
    for item in values:
        for match in re.findall(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)", str(item or "")):
            digits = re.sub(r"\D", "", match)
            if len(digits) == 14:
                result.add(digits)
    return result


def cnpjs_blueprint(blueprint, abas=None):
    """Extract identified legal entities from BP custom fields and identification tabs."""
    found = set()
    for field in blueprint.get("custom_fields") or []:
        if isinstance(field, dict) and "CNPJ" in _norm(field.get("name")):
            found.update(_cnpj_values(field.get("value")))
    for name, rows in (abas or {}).items():
        if _norm(name).strip() not in ("IDENTIFICACAO", "ID PROJETO"):
            continue
        for row in rows:
            cells = [str(v or "").strip() for v in row]
            for index, cell in enumerate(cells):
                if "CNPJ" in _norm(cell):
                    found.update(_cnpj_values(cell))
                    if index + 1 < len(cells):
                        found.update(_cnpj_values(cells[index + 1]))
    return found


def resolver_identidade_cliente(issue, *, buscar=None, baixar=None, allow_remote=False, cliente_override=None):
    """Read-only resolution through Redmine relations and BP Excel attachments.

    Returns a single CNPJ only when exactly one distinct legal entity is proven.
    A multi-establishment BP remains explicit instead of silently choosing one.
    """
    from ednna.eddy_client_identity_store import consultar, registrar
    from ednna.eddy_blueprint_identity_evidence import registrar_bp
    from ednna.eddy_blueprint_mysql_evidence import identidade_de_bp_mysql, candidatos_bp_mysql
    from ednna.eddy_vr_mysql_sync import clientes_do_redmine
    from ednna.mysql_blueprint_participants import _descobrir_fontes_redmine
    from ednna.blueprint_knowledge import ler_excel, _eh_blueprint
    from redmine_api import buscar_detalhes_chamado, baixar_anexo_redmine

    clientes = clientes_do_redmine(issue)
    # A caller-supplied client label is trusted only for the separate MySQL
    # inventory worker; operational paths without override still validate fields.
    if not cliente_override and len(clientes) != 1:
        return {"estado": "CLIENTE_AMBIGUO" if clientes else "CLIENTE_AUSENTE", "cnpj": None}
    cliente = str(cliente_override or clientes[0]).strip()
    # A cached identity avoids Redmine requests on every five-minute VR01 cycle.
    # Store outages fail closed instead of creating a Redmine request storm.
    try:
        cached = consultar(cliente)
    except Exception as exc:
        return {"estado": "IDENTIDADE_MYSQL_INDISPONIVEL", "cnpj": None,
                "erro": type(exc).__name__}
    # Re-evaluate fresh MySQL Blueprint evidence before accepting cached CNPJ.
    # A new BP may add a second entity and invalidate a previous single CNPJ.
    # Negative cache entries from PR #211 are not proof of BP absence.
    # Use already synchronized MySQL evidence before considering any API call.
    try:
        mysql_bp = identidade_de_bp_mysql(cliente)
    except Exception as exc:
        return {"estado": "IDENTIDADE_MYSQL_INDISPONIVEL", "cnpj": None,
                "erro": type(exc).__name__}
    if mysql_bp["estado"] == "RESOLVIDO":
        registrar(cliente, mysql_bp)
        return mysql_bp
    if cached is not None and cached.get("estado") == "RESOLVIDO":
        if mysql_bp["estado"] in ("CNPJ_AMBIGUO", "BP_MYSQL_SEM_IDENTIFICACAO"):
            return {"estado": mysql_bp["estado"], "cnpj": None, "origem": "MYSQL_BP"}
        return cached
    if not allow_remote:
        if cached is not None and cached.get("estado") == "RESOLVIDO":
            return cached
        return {"estado": mysql_bp["estado"], "cnpj": None,
                "origem": "MYSQL", "consulta_redmine": False}
    buscar = buscar or (lambda iid: buscar_detalhes_chamado(
        int(iid), incluir_anexos=True, consulta_pontual=True))
    baixar = baixar or baixar_anexo_redmine
    try:
        ids_mysql, _ = candidatos_bp_mysql(cliente)
        # A unique BP already indexed in MySQL avoids a relation walk.
        if len(ids_mysql) == 1:
            bp_id = next(iter(ids_mysql))
        else:
            _, bp_id = _descobrir_fontes_redmine(int(issue["id"]))
        if not bp_id:
            result = {"estado": "BLUEPRINT_NAO_LOCALIZADO", "cnpj": None}
            return result
        bp = buscar(bp_id)
        if int(bp.get("id") or 0) != bp_id:
            return {"estado": "BLUEPRINT_DIVERGENTE", "cnpj": None}
        cnpjs = cnpjs_blueprint(bp)
        for attachment in bp.get("attachments") or []:
            filename = str(attachment.get("filename") or "")
            if not filename.lower().endswith((".xls", ".xlsx")):
                continue
            abas = ler_excel(baixar(str(attachment.get("content_url") or "")), filename)
            if _eh_blueprint(filename, list(abas)):
                cnpjs.update(cnpjs_blueprint(bp, abas))
        registrar_bp(cliente, bp_id, cnpjs)
        if len(cnpjs) != 1:
            result = {"estado": "CNPJ_AMBIGUO" if cnpjs else "CNPJ_NAO_LOCALIZADO_BP",
                      "cnpj": None, "blueprint_id": bp_id, "quantidade_cnpjs": len(cnpjs)}
            registrar(cliente, result)
            return result
        result = {"estado": "RESOLVIDO", "cliente": cliente, "cnpj": next(iter(cnpjs)),
                  "blueprint_id": bp_id, "quantidade_cnpjs": 1}
        registrar(cliente, result)
        return result
    except Exception as exc:
        # Existing identity can support offline planning, never external writes.
        try:
            stale = consultar(cliente, allow_stale=True)
            if stale is not None:
                stale["desatualizado"] = True
                return stale
        except Exception:
            pass
        return {"estado": "FONTE_BP_INDISPONIVEL", "cnpj": None,
                "erro": type(exc).__name__}
