import unittest
from unittest.mock import patch, call
from scripts.eddy_vr01_controlled_pilot import executar_piloto


class VR01PilotTests(unittest.TestCase):
    @patch("scripts.eddy_vr01_controlled_pilot.registrar_decisao")
    @patch("scripts.eddy_vr01_controlled_pilot.importar_chamado_vr")
    def test_default_does_not_fetch_redmine(self, fetch, audit):
        audit.side_effect = lambda issue_id: {"chamado_id": issue_id}
        result = executar_piloto()
        fetch.assert_not_called()
        self.assertEqual(len(result), 2)
        audit.assert_has_calls([call(49227), call(49289)])

    @patch("scripts.eddy_vr01_controlled_pilot.registrar_decisao")
    @patch("scripts.eddy_vr01_controlled_pilot.importar_chamado_vr")
    def test_import_opt_in(self, fetch, audit):
        audit.return_value = {"execucao_externa": False}
        executar_piloto([49227], importar=True)
        fetch.assert_called_once_with(49227)
        audit.assert_called_once_with(49227)

    @patch("scripts.eddy_vr01_controlled_pilot.registrar_decisao")
    def test_other_issue_blocked(self, audit):
        with self.assertRaises(ValueError):
            executar_piloto([47173])
        audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
