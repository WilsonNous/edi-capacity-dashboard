"""Safety tests for Blueprint MySQL cutover."""
from unittest.mock import patch
import pytest
from ednna import mysql_blueprint_participants as module


def test_missing_sqlite_fails_without_writes(tmp_path):
    with pytest.raises(FileNotFoundError):
        module.importar_participantes_sqlite(tmp_path / "missing.db")


def test_corrupt_sqlite_fails_closed(tmp_path):
    path = tmp_path / "ednna.db"
    path.write_bytes(b"not a database")
    with pytest.raises(Exception):
        module.importar_participantes_sqlite(path, aplicar=True)


def test_mysql_selector_prioritizes_financeiro():
    class Cursor:
        description = [(name,) for name in (
            "cliente", "nome", "area", "email", "telefone", "andamento",
            "status_report", "documento_id", "chamado_id", "ativo",
            "fonte_arquivo", "attachment_id", "importado_em")]
        def execute(self, *args): pass
        def fetchall(self):
            return [
                ("A", "Gerente", "GERENTE/COORD. PROJETO", "g@example.org",
                 "", "", "", 1, 1, 1, "", None, ""),
                ("A", "Financeiro", "Financeiro", "f@example.org",
                 "", "", "", 1, 1, 1, "", None, ""),
            ]
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Conn:
        def cursor(self): return Cursor()
        def __enter__(self): return self
        def __exit__(self, *args): pass
    with patch.object(module, "connect", return_value=Conn()):
        rows = module.selecionar_contatos_cliente_mysql("A")
    assert [row["email"] for row in rows] == ["f@example.org", "g@example.org"]
