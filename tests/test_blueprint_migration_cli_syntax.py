"""Regression guard: Blueprint CLI must remain parseable Python."""
import ast
from pathlib import Path


def test_blueprint_migration_cli_syntax():
    source = Path(__file__).resolve().parents[1] / "scripts" / "eddy_blueprint_mysql_migration.py"
    ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
