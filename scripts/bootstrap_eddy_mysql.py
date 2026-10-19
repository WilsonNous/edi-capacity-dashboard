"""Opt-in MySQL schema bootstrap; does not activate MySQL as operational backend."""
from __future__ import annotations

import argparse
import sys

from ednna.mysql_storage import bootstrap, record_storage_health


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Create foundation tables")
    args = parser.parse_args(argv)
    if not args.apply:
        print("DRY_RUN: no tables created. Pass --apply after connection validation.")
        return 0
    try:
        bootstrap()
        health = record_storage_health()
    except Exception as exc:
        print("MYSQL_BOOTSTRAP_FAILED:", type(exc).__name__)
        return 1
    print("MYSQL_BOOTSTRAP_OK")
    print("TABLE_COUNT:", health["table_count"])
    print("DATABASE_BYTES:", health["database_bytes"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
