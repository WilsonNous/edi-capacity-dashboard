"""Durable Redmine custom-field option catalog in MySQL (no SQLite).

Only an explicit sync fetches Redmine; normal VR01 drafts read MySQL only.
"""
from __future__ import annotations

from ednna.mysql_storage import connect


def preparar_tabela():
    with connect() as conn:
        with conn.cursor() as cursor:
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


def sincronizar_catalogo():
    """Explicit Redmine read and MySQL write; never touches Redmine issues."""
    from redmine_api import buscar_custom_fields
    fields = buscar_custom_fields(force=True)
    options = []
    for field in fields:
        if str(field.get("id")) not in ("1", "5"):
            continue
        for item in field.get("possible_values") or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("value") or "").strip()
            label = str(item.get("label") or "").strip()
            if key and label and key != label and len(key) <= 191 and len(label) <= 255:
                options.append((int(field["id"]), key, label))
    if not any(field_id == 1 for field_id, _, _ in options):
        raise ValueError("Catálogo Clientes Redmine sem opções válidas; nenhuma gravação")
    preparar_tabela()
    with connect() as conn:
        with conn.cursor() as cursor:
            for field_id, key, label in options:
                cursor.execute(
                    """INSERT INTO eddy_redmine_field_options
                       (field_id, option_value, option_label) VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE option_label=VALUES(option_label)""",
                    (field_id, key, label),
                )
    return {"fonte": "REDMINE_CUSTOM_FIELDS", "destino": "MYSQL",
            "opcoes_sincronizadas": len(options), "envios_realizados": 0,
            "redmine_escritas": 0}
