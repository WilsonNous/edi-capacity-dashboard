"""Explicit Blueprint migration: SQLite source or direct Redmine attachments."""
import argparse
import json
from ednna.mysql_blueprint_participants import (
    importar_participantes_sqlite, sincronizar_blueprints_redmine_mysql,
)

PILOTOS = {
    48786: "POSTOS ANDREAZZA",
    49119: "POSTOS ROTA",
    50120: "REDE SANDER",
    50318: "SUPERMERCADOS MAMBO",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/home/data/ednna.db")
    parser.add_argument("--redmine-pilots", action="store_true",
                        help="Read four verified Redmine pilot issues without SQLite")
    parser.add_argument("--apply", action="store_true",
                        help="Write extracted participants to MySQL")
    args = parser.parse_args()
    if args.redmine_pilots:
        result = sincronizar_blueprints_redmine_mysql(PILOTOS, aplicar=args.apply)
    else:
        result = importar_participantes_sqlite(args.source, aplicar=args.apply)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
