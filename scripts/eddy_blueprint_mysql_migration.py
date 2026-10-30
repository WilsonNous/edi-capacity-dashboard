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
    parser.add_argument("--issue", type=int, action="append",
                        help="Restrict direct Redmine mode to specified pilot issue ID; repeatable")
    parser.add_argument("--skip-imported", action="store_true",
                        help="Skip attachments with active participants already in MySQL (apply only)")
    parser.add_argument("--apply", action="store_true",
                        help="Write extracted participants to MySQL")
    args = parser.parse_args()
    if args.redmine_pilots:
        unknown = set(args.issue or []) - set(PILOTOS)
        if unknown:
            parser.error("Issue ID fora dos pilotos verificados: " + str(sorted(unknown)))
        selecionados = {i: c for i, c in PILOTOS.items() if not args.issue or i in args.issue}
        result = sincronizar_blueprints_redmine_mysql(
            selecionados, aplicar=args.apply, skip_imported=args.skip_imported)
    else:
        result = importar_participantes_sqlite(args.source, aplicar=args.apply)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
