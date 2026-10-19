import unittest
from unittest.mock import patch

import pandas as pd

from ednna import mysql_controlled_sync as sync


class ControlledSyncTests(unittest.TestCase):
    def test_only_requested_rows_are_written(self):
        frame = pd.DataFrame([
            {"#": 42, "Estado": "Aberto", "Alterado": "2026-10-19", "Clientes": "Cliente A"},
            {"#": 43, "Estado": "Fechado", "Alterado": "2026-10-19"},
        ])
        with patch.object(sync, "salvar_snapshot") as save:
            result = sync.sincronizar_dataframe_mysql(frame, limite=1)
        self.assertEqual(result["gravados"], 1)
        self.assertEqual(result["recebidos"], 1)
        self.assertEqual(save.call_count, 1)
        self.assertEqual(save.call_args.args[0]["id"], 42)
        self.assertEqual(save.call_args.args[0]["cliente"], "Cliente A")

    def test_bad_ids_do_not_write(self):
        frame = pd.DataFrame([{"#": "4.5"}, {"#": None}, {"#": -1}])
        with patch.object(sync, "salvar_snapshot") as save:
            result = sync.sincronizar_dataframe_mysql(frame)
        self.assertEqual(result["ignorados"], 3)
        save.assert_not_called()

    def test_database_errors_are_reported_not_hidden(self):
        frame = pd.DataFrame([{"#": 42}])
        with patch.object(sync, "salvar_snapshot", side_effect=RuntimeError("offline")):
            result = sync.sincronizar_dataframe_mysql(frame)
        self.assertEqual(result["erros"], 1)
        self.assertEqual(result["ids_erro"], [42])

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            sync.sincronizar_dataframe_mysql(pd.DataFrame({"#": [1]}), limite=0)


if __name__ == "__main__":
    unittest.main()
