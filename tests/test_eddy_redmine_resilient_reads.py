import unittest
from unittest.mock import patch
from ednna.redmine_resilient_reads import listar_abertos_confirmados, detalhe_com_retomada


class ResilientRedmineTests(unittest.TestCase):
    @patch("ednna.redmine_resilient_reads.obter_diagnostico_redmine", return_value={"fonte_dados": "painel_sqlite_contingencia"})
    @patch("ednna.redmine_resilient_reads.buscar_chamados_projetos", return_value=[{"id": 1}])
    def test_stale_list_not_authoritative(self, *_):
        result = listar_abertos_confirmados()
        self.assertFalse(result["confirmado"])
        self.assertEqual(result["chamados"], [])

    @patch("ednna.redmine_resilient_reads.obter_diagnostico_redmine", return_value={"fonte_dados": "redmine"})
    @patch("ednna.redmine_resilient_reads.buscar_chamados_projetos", return_value=[{"id": 1}])
    def test_fresh_list(self, *_):
        self.assertTrue(listar_abertos_confirmados()["confirmado"])

    @patch("ednna.redmine_resilient_reads.buscar_detalhes_chamado")
    @patch("ednna.redmine_resilient_reads.carregar_snapshot")
    def test_reuses_unchanged_complete_journals(self, stored, fetch):
        stored.return_value = {"chamado": {
            "alterado_em": "2026-10-20T18:00:00",
            "payload_json": {"id": 47851, "_eddy_journals_completos": True},
        }, "journals": [{"id": 10, "criado_em": "2026-10-20T17:00:00", "notas": "evidencia", "detalhes_json": "[]"}]}
        result = detalhe_com_retomada({"id": 47851, "updated_on": "2026-10-20T18:00:00Z"})
        self.assertFalse(result["consultou_redmine"])
        self.assertEqual(result["detalhe"]["journals"][0]["notes"], "evidencia")
        fetch.assert_not_called()

    @patch("ednna.redmine_resilient_reads.buscar_detalhes_chamado")
    @patch("ednna.redmine_resilient_reads.carregar_snapshot")
    def test_changed_issue_fetches_fresh_journals(self, stored, fetch):
        stored.return_value = {"chamado": {
            "alterado_em": "2026-10-20T18:00:00",
            "payload_json": {"id": 47851, "journals": []},
        }}
        fetch.return_value = {"id": 47851, "journals": [{"id": 11}]}
        result = detalhe_com_retomada({"id": 47851, "updated_on": "2026-10-20T18:01:00Z"})
        self.assertTrue(result["consultou_redmine"])
        fetch.assert_called_once()

    @patch("ednna.redmine_resilient_reads.buscar_detalhes_chamado")
    @patch("ednna.redmine_resilient_reads.carregar_snapshot", return_value=None)
    def test_missing_journals_fails_closed(self, fetch, _):
        fetch.return_value = {"id": 47851}
        with self.assertRaises(ValueError):
            detalhe_com_retomada({"id": 47851})


if __name__ == "__main__":
    unittest.main()
