"""Explicit Blueprint migration. Source is never modified."""
import argparse
import json
from ednna.mysql_blueprint_participants import importar_participantes_sqlite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/home/data/ednna.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(importar_participantes_sqlite(args.source, aplicar=args.apply),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
