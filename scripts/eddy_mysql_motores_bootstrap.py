"""Provisiona as tabelas dos motores EDDY no MySQL 5.7.

Uso:
  python -m scripts.eddy_mysql_motores_bootstrap          # dry-run
  python -m scripts.eddy_mysql_motores_bootstrap --apply  # DDL idempotente
Nao acessa ednna.db, nao apaga tabelas e nao autoriza envios.
"""
from __future__ import annotations

import argparse
import json

from ednna.motores_mysql_repository import DDL
from ednna.mysql_storage import connect

TABLES = (
    "eddy_aprendizados_operacionais",
    "eddy_revisoes_regras_operacionais",
    "eddy_mineracao_aberturas",
    "eddy_homologacoes_regras",
    "eddy_autorizacoes_motor",
    "eddy_propostas_regras_abertura",
)


def executar(*, aplicar: bool = False) -> dict:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE(), VERSION()")
            database, version = cur.fetchone()
            if not str(version).startswith("5.7."):
                raise RuntimeError("Homologacao exigida: servidor nao e MySQL 5.7")
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=DATABASE() AND table_type='BASE TABLE'"
            )
            existentes = {str(row[0]) for row in cur.fetchall()}
            if aplicar:
                for statement in DDL:
                    cur.execute(statement)
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema=DATABASE() AND table_type='BASE TABLE'"
                )
                existentes = {str(row[0]) for row in cur.fetchall()}
            faltantes = sorted(set(TABLES) - existentes)
            if aplicar and faltantes:
                raise RuntimeError("Tabelas ausentes apos DDL: " + ", ".join(faltantes))
            contagens = {}
            if aplicar:
                for table in TABLES:
                    # Identificadores fixos, nunca fornecidos pelo usuario.
                    cur.execute("SELECT COUNT(*) FROM " + table)
                    contagens[table] = int(cur.fetchone()[0])
    return {
        "database": database,
        "version": version,
        "modo": "apply" if aplicar else "dry-run",
        "existentes": sorted(set(TABLES) & existentes),
        "faltantes": faltantes,
        "contagens": contagens,
        "aprendizado_executado": False,
        "envios_externos": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(executar(aplicar=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
