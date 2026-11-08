"""Regression: migrate legacy BP evidence without touching the old database."""
import json
import sqlite3
from unittest.mock import Mock

from ednna.eddy_legacy_blueprint_backfill import (
    evidencias_legadas, importar_evidencias_legadas,
)


def test_legacy_bp_cnpj_migration_read_only(tmp_path):
    path = tmp_path / "ednna.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE blueprint_documentos (id INTEGER, cliente TEXT, chamado_id INTEGER)")
        db.execute("CREATE TABLE blueprint_linhas (documento_id INTEGER, dados_json TEXT)")
        db.executemany("INSERT INTO blueprint_documentos VALUES (?,?,?)", [
            (1, "CLIENTE A", 501), (2, "CLIENTE B", 502),
        ])
        db.executemany("INSERT INTO blueprint_linhas VALUES (?,?)", [
            (1, json.dumps({"CNPJ:": "12.345.678/0001-90"})),
            (1, json.dumps({"CNPJ": "12345678000190"})),
            (2, json.dumps({"CNPJ": "98765432000199"})),
        ])
    assert evidencias_legadas(path, clientes={"CLIENTE A"}) == {
        ("CLIENTE A", 501): {"12345678000190"}
    }
    registrar = Mock()
    stats = importar_evidencias_legadas(
        caminho=path, clientes={"CLIENTE A"}, registrar=registrar)
    assert stats == {"blueprints": 1, "conflitos": 0, "clientes": 1}
    registrar.assert_called_once_with(
        "CLIENTE A", 501, {"12345678000190"}, fonte="EDNNA_SQLITE_LEGADO")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM blueprint_linhas").fetchone()[0] == 3


def test_missing_legacy_db_is_not_an_error(tmp_path):
    assert evidencias_legadas(tmp_path / "missing.db") == {}


def test_unrelated_sqlite_is_not_modified(tmp_path):
    path = tmp_path / "empty.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE unrelated (id INTEGER)")
    assert evidencias_legadas(path) == {}
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='blueprint_documentos'").fetchone() is None
