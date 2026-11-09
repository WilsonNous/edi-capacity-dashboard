from unittest.mock import patch

from scripts.eddy_mysql_motores_bootstrap import DDL, TABLES, executar


class Cursor:
    def __init__(self, state):
        self.state = state
        self.last = ""
        self.ddl_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query):
        self.last = query
        if query.startswith("CREATE TABLE"):
            self.ddl_calls += 1
            self.state["tables"].update(TABLES)

    def fetchone(self):
        if "DATABASE(), VERSION()" in self.last:
            return ("noust785_eddy_edi", "5.7.44-48")
        if "COUNT(*)" in self.last:
            return (0,)
        raise AssertionError(self.last)

    def fetchall(self):
        return [(name,) for name in sorted(self.state["tables"])]


class Connection:
    def __init__(self, state):
        self.cursor_obj = Cursor(state)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_obj


def test_dry_run_nao_cria_tabelas():
    state = {"tables": {"eddy_chamados"}}
    conn = Connection(state)
    with patch("scripts.eddy_mysql_motores_bootstrap.connect", return_value=conn):
        result = executar()
    assert result["faltantes"] == sorted(TABLES)
    assert conn.cursor_obj.ddl_calls == 0
    assert result["envios_externos"] is False


def test_apply_cria_tabelas_e_repeticao_e_segura():
    state = {"tables": {"eddy_chamados"}}
    for _ in range(2):
        conn = Connection(state)
        with patch("scripts.eddy_mysql_motores_bootstrap.connect", return_value=conn):
            result = executar(aplicar=True)
        assert conn.cursor_obj.ddl_calls == len(DDL)
        assert result["faltantes"] == []
        assert result["aprendizado_executado"] is False
    assert "eddy_chamados" in state["tables"]
