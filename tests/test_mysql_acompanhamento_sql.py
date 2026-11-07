"""Regression tests for MySQL SQL translation, atomic locks and send safety."""
import unittest
from unittest.mock import MagicMock, patch
from ednna import mysql_acompanhamento_acoes as mysql


class ActionSQLTest(unittest.TestCase):
    def setUp(self):
        self.raw = MagicMock()
        self.cursor = MagicMock()
        self.raw.cursor.return_value.__enter__.return_value = self.cursor
        self.cursor.description = None
        self.cursor.fetchall.return_value = []
        self.cursor.fetchone.return_value = (1,)
        self.ctx = MagicMock()
        self.ctx.__enter__.return_value = self.raw
        self.patcher = patch.object(mysql, "connect", return_value=self.ctx)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.db = mysql.Connection()

    def tearDown(self):
        self.db.close()

    def test_upsert_translates_to_mysql(self):
        self.db.execute("""INSERT INTO acoes_operacionais (chamado_id, regra_id, estado)
            VALUES (?, ?, 'ENVIANDO')
            ON CONFLICT(chamado_id, regra_id) DO UPDATE SET estado=excluded.estado""",
            (50318, "VR01"))
        sql = self.cursor.execute.call_args.args[0]
        self.assertIn("INSERT INTO eddy_acoes_operacionais", sql)
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertIn("VALUES(estado)", sql)
        self.assertNotIn("?", sql)
        self.raw.commit.assert_called()

    def test_lock_held_through_transaction_and_released_on_commit(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("SELECT * FROM acoes_operacionais WHERE chamado_id=? AND regra_id=?",
                        (50318, "VR01"))
        calls = [str(x) for x in self.cursor.execute.call_args_list]
        self.assertTrue(any("GET_LOCK" in x for x in calls))
        self.assertFalse(any("RELEASE_LOCK" in x for x in calls))
        self.db.execute("COMMIT")
        self.assertTrue(any("RELEASE_LOCK" in str(x) for x in self.cursor.execute.call_args_list))

    def test_lock_failure_blocks_send(self):
        self.cursor.fetchone.return_value = (0,)
        self.db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(RuntimeError, "MYSQL_ACTION_LOCK_TIMEOUT"):
            self.db.execute("SELECT * FROM acoes_operacionais WHERE chamado_id=? AND regra_id=?",
                            (50318, "VR01"))

    def test_abandoned_transaction_rolls_back_before_unlock(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("SELECT * FROM acoes_operacionais WHERE chamado_id=? AND regra_id=?",
                        (50318, "VR01"))
        self.db.close()
        self.raw.rollback.assert_called_once()
        self.assertTrue(any("RELEASE_LOCK" in str(x) for x in self.cursor.execute.call_args_list))

    def test_nested_transaction_fails_closed(self):
        self.db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(RuntimeError, "Nested operational transaction"):
            self.db.execute("BEGIN IMMEDIATE")

    def test_unknown_sql_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported operational SQL"):
            self.db.execute("DELETE FROM acoes_operacionais")

    def test_schema_has_unique_key_and_indexes(self):
        self.assertIn("PRIMARY KEY (chamado_id, regra_id)", mysql.DDL)
        self.assertIn("idx_eddy_acoes_estado", mysql.DDL)


if __name__ == "__main__":
    unittest.main()
