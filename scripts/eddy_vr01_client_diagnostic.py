"""Read-only diagnosis of VR01 client identification from persisted MySQL.

No Redmine/Graph calls, no database writes, no journal contents or emails.
"""
from __future__ import annotations

import json

from ednna.mysql_snapshot_repository import carregar_snapshot

PILOTS = (50318, 48786)


def diagnosticar(ids=PILOTS):
    saida = []
    for chamado_id in ids:
        item = {"chamado_id": chamado_id}
        try:
            stored = carregar_snapshot(chamado_id)
            if not stored:
                item["estado"] = "SNAPSHOT_AUSENTE"
                saida.append(item)
                continue
            row = stored.get("chamado") or {}
            raw = row.get("payload_json")
            issue = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(issue, dict):
                item["estado"] = "PAYLOAD_INVALIDO"
                saida.append(item)
                continue
            fields = issue.get("custom_fields")
            item["estado"] = "DIAGNOSTICO_DISPONIVEL"
            item["cliente_coluna_mysql"] = str(row.get("cliente") or "")
            item["cliente_campo_1"] = ""
            item["custom_fields_tipo"] = type(fields).__name__
            item["custom_fields"] = []
            if isinstance(fields, list):
                for field in fields:
                    if not isinstance(field, dict):
                        continue
                    field_id = str(field.get("id") or "")
                    value = field.get("value")
                    item["custom_fields"].append({
                        "id": field_id,
                        "nome": str(field.get("name") or ""),
                        "tipo_valor": type(value).__name__,
                        "preenchido": value not in (None, "", []),
                    })
                    if field_id == "1" and isinstance(value, str):
                        item["cliente_campo_1"] = value.strip()
            item["chaves_payload"] = sorted(str(k) for k in issue.keys())
            item["projeto"] = str((issue.get("project") or {}).get("name") or "")
            item["tracker"] = str((issue.get("tracker") or {}).get("name") or "")
        except Exception as exc:
            item["estado"] = "ERRO_LEITURA"
            item["erro_tipo"] = type(exc).__name__
        saida.append(item)
    return {"modo": "SOMENTE_LEITURA", "chamados": saida,
            "envios_realizados": 0, "redmine_escritas": 0, "mysql_escritas": 0}


def main():
    print(json.dumps(diagnosticar(), ensure_ascii=False))


if __name__ == "__main__":
    main()
