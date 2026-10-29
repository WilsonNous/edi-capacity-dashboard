"""Explicitly synchronize Redmine field-option metadata to durable MySQL."""
import json
from ednna.mysql_redmine_catalog import sincronizar_catalogo


if __name__ == "__main__":
    print(json.dumps(sincronizar_catalogo(), ensure_ascii=False))
