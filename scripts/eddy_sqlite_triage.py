"""Non-destructive SQLite integrity triage for EDDY on Azure.

Usage: python -m scripts.eddy_sqlite_triage /home/data
Only opens databases read-only. Never deletes, repairs, checkpoints or migrates.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def inspect_database(path: Path) -> dict:
    report = {"arquivo": str(path), "tamanho_bytes": path.stat().st_size}
    try:
        # URI mode=ro prevents accidental modification and avoids creating missing DBs.
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            result = db.execute("PRAGMA integrity_check").fetchall()
            report["integridade"] = "ok" if result == [("ok",)] else "corrompido"
            report["detalhes"] = [str(row[0]) for row in result[:10]]
            if report["integridade"] == "ok":
                report["tabelas"] = [row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )]
    except (sqlite3.DatabaseError, OSError) as exc:
        report["integridade"] = "erro"
        report["erro"] = type(exc).__name__
    return report


def inspect_directory(directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("Diretório não existe")
    databases = sorted(p for p in directory.rglob("*.db") if p.is_file())
    return {
        "diretorio": str(directory),
        "quantidade": len(databases),
        "bancos": [inspect_database(p) for p in databases],
        "somente_leitura": True,
        "alerta": "Não remover ou recriar banco sem backup e validação da fonte autoritativa.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diretorio", type=Path, help="Diretório persistente a examinar")
    args = parser.parse_args()
    print(json.dumps(inspect_directory(args.diretorio), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
