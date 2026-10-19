"""Explicit, bounded MySQL migration pilot from the current Redmine Panel snapshot."""
import argparse
import json

from ednna.mysql_panel_bridge import importar_snapshot_painel_mysql


def main():
    parser = argparse.ArgumentParser(description="EDDY: piloto de snapshot Redmine para MySQL")
    parser.add_argument("--painel", default="/home/data/painel.db")
    parser.add_argument("--limite", type=int, default=20)
    parser.add_argument("--apply", action="store_true", help="Grava no MySQL; padrão é dry-run")
    args = parser.parse_args()
    result = importar_snapshot_painel_mysql(args.painel, limite=args.limite, aplicar=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
