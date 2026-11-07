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


def resolver_identidade_cliente(issue, *, buscar=None, baixar=None):
    """Read-only resolution through Redmine relations and BP Excel attachments.

    Returns a single CNPJ only when exactly one distinct legal entity is proven.
    A multi-establishment BP remains explicit instead of silently choosing one.
    """
    from ednna.eddy_vr_mysql_sync import clientes_do_redmine
    from ednna.mysql_blueprint_participants import _descobrir_fontes_redmine
    from ednna.blueprint_knowledge import ler_excel, _eh_blueprint
    from redmine_api import buscar_detalhes_chamado, baixar_anexo_redmine

    clientes = clientes_do_redmine(issue)
    if len(clientes) != 1:
        return {"estado": "CLIENTE_AMBIGUO" if clientes else "CLIENTE_AUSENTE", "cnpj": None}
    buscar = buscar or (lambda iid: buscar_detalhes_chamado(
        int(iid), incluir_anexos=True, consulta_pontual=True))
    baixar = baixar or baixar_anexo_redmine
    try:
        _, bp_id = _descobrir_fontes_redmine(int(issue["id"]))
        if not bp_id:
            return {"estado": "BLUEPRINT_NAO_LOCALIZADO", "cnpj": None}
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
        if len(cnpjs) != 1:
            return {"estado": "CNPJ_AMBIGUO" if cnpjs else "CNPJ_NAO_LOCALIZADO_BP",
                    "cnpj": None, "blueprint_id": bp_id, "quantidade_cnpjs": len(cnpjs)}
        return {"estado": "RESOLVIDO", "cliente": clientes[0], "cnpj": next(iter(cnpjs)),
                "blueprint_id": bp_id}
    except Exception as exc:
        return {"estado": "FONTE_BP_INDISPONIVEL", "cnpj": None,
                "erro": type(exc).__name__}
