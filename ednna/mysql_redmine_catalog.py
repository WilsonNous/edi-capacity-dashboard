"""Durable Redmine custom-field catalog (all attributes and option labels)."""
from __future__ import annotations

import json

from ednna.mysql_storage import connect


def preparar_tabela():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS eddy_redmine_field_definitions (
                field_id INT NOT NULL PRIMARY KEY,
                field_name VARCHAR(255) NOT NULL,
                field_format VARCHAR(64) NULL,
                field_payload LONGTEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS eddy_redmine_field_options (
                field_id INT NOT NULL,
                option_value VARCHAR(191) NOT NULL,
                option_label VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (field_id, option_value)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")


def mapa_persistido(field_id=1):
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT option_value, option_label FROM eddy_redmine_field_options WHERE field_id=%s",
                (field_id,),
            )
            return {str(value): str(label) for value, label in cursor.fetchall()}


def definicoes_persistidas():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT field_payload FROM eddy_redmine_field_definitions ORDER BY field_id")
            return [json.loads(row[0]) for row in cursor.fetchall()]


def traduzir_valores(valor, field_id, *, mapa=None):
    """Return raw IDs and resolved labels; never present unknown IDs as names."""
    valores = valor if isinstance(valor, list) else [valor]
    mapa = mapa if mapa is not None else mapa_persistido(field_id)
    return [{"id": str(v), "nome": mapa.get(str(v)),
             "resolvido": str(v) in mapa} for v in valores if v not in (None, "")]


def sincronizar_catalogo():
    """Explicit GET Redmine and atomic MySQL upsert; no Redmine writes."""
    from redmine_api import _get
    fields = _get("custom_fields.json").get("custom_fields") or []
    if not isinstance(fields, list) or not fields:
        raise ValueError("Catálogo Redmine vazio ou inválido; nenhuma gravação")
    definitions, options = [], []
    seen = set()
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Definição Redmine inválida")
        field_id = int(field["id"])
        if field_id in seen:
            raise ValueError("IDs de atributos duplicados")
        seen.add(field_id)
        name = str(field.get("name") or "").strip()
        if not name:
            raise ValueError("Atributo sem nome")
        definitions.append((field_id, name, str(field.get("field_format") or ""),
                            json.dumps(field, ensure_ascii=False)))
        for item in field.get("possible_values") or []:
            if not isinstance(item, dict):
                raise ValueError("Opção de atributo inválida")
            key = str(item.get("value") or "").strip()
            label = str(item.get("label") or "").strip()
            if key and label:
                if len(key) > 191 or len(label) > 255:
                    raise ValueError("Opção maior que limite do schema")
                options.append((field_id, key, label))
    preparar_tabela()
    with connect() as conn:
        with conn.cursor() as cursor:
            for item in definitions:
                cursor.execute("""INSERT INTO eddy_redmine_field_definitions
                    (field_id, field_name, field_format, field_payload)
                    VALUES (%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE field_name=VALUES(field_name),
                    field_format=VALUES(field_format), field_payload=VALUES(field_payload)""", item)
            for item in options:
                cursor.execute("""INSERT INTO eddy_redmine_field_options
                    (field_id, option_value, option_label) VALUES (%s,%s,%s)
                    ON DUPLICATE KEY UPDATE option_label=VALUES(option_label)""", item)
    return {"fonte": "REDMINE_CUSTOM_FIELDS", "destino": "MYSQL",
            "atributos_sincronizados": len(definitions),
            "opcoes_sincronizadas": len(options),
            "envios_realizados": 0, "redmine_escritas": 0}
