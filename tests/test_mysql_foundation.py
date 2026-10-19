"""Foundation regression tests; no live MySQL server needed."""
import os
import unittest
from unittest.mock import patch

from ednna import mysql_storage
from scripts.bootstrap_eddy_mysql import main


class TestMySQLFoundation(unittest.TestCase):
    def test_schema_uses_innodb_and_unique_evidence(self):
        ddl = "\n".join(mysql_storage.DDL)
        self.assertIn("ENGINE=InnoDB", ddl)
        self.assertIn("UNIQUE KEY uq_external_evidence", ddl)
        self.assertIn("idx_evidence_chamado", ddl)

    def test_operational_schema_is_indexed_and_referential(self):
        ddl = "\\n".join(mysql_storage.DDL)
        self.assertIn("CREATE TABLE IF NOT EXISTS eddy_chamados", ddl)
        self.assertIn("CREATE TABLE IF NOT EXISTS eddy_journals", ddl)
        self.assertIn("fk_eddy_journal_chamado", ddl)
        self.assertIn("ON DELETE CASCADE", ddl)
        self.assertIn("idx_eddy_chamados_estado", ddl)
        self.assertEqual(mysql_storage.SCHEMA_VERSION, 2)

    def test_missing_password_fails_closed(self):
        with patch.dict(os.environ, {
            "EDDY_DB_HOST": "example.invalid",
            "EDDY_DB_NAME": "eddy",
            "EDDY_DB_USER": "user",
            "EDDY_DB_PASSWORD": "",
        }):
            with self.assertRaises(ValueError):
                mysql_storage.connection_options()

    def test_verify_ca_requires_ca_file(self):
        env = {
            "EDDY_DB_HOST": "example.invalid",
            "EDDY_DB_NAME": "eddy",
            "EDDY_DB_USER": "user",
            "EDDY_DB_PASSWORD": "secret",
            "EDDY_DB_SSL_MODE": "VERIFY_CA",
            "EDDY_DB_SSL_CA": "",
        }
        with patch.dict(os.environ, env):
            with self.assertRaises(ValueError):
                mysql_storage.connection_options()

    def test_dry_run_never_bootstraps(self):
        with patch("scripts.bootstrap_eddy_mysql.bootstrap") as bootstrap:
            self.assertEqual(main([]), 0)
            bootstrap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
