import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from ednna import retry_continuidades as retry


class TestRetryContinuidades(unittest.TestCase):
    def test_pendente_vencido_tem_prioridade(self):
        agora = datetime(2026, 10, 15, tzinfo=timezone.utc)
        vencido = (agora - timedelta(minutes=1)).isoformat()
        futuro = (agora + timedelta(minutes=10)).isoformat()
        with patch.object(retry, "_ler", return_value={"20": vencido, "30": futuro}), patch.object(retry, "_agora", return_value=agora), patch("ednna.lotes_continuidade.selecionar_persistido", side_effect=lambda ids, limite, chave: ids[:limite]):
            self.assertEqual(retry.selecionar_com_pendencias([10, 20, 30], 2, "cursor"), [20, 10])

    def test_resultados_pendentes_e_sucesso(self):
        dados = {"10": "2026-10-01T00:00:00+00:00"}
        with patch.object(retry, "_ler", return_value=dados), patch("painel_cache.salvar_metadado_json") as salvar:
            resumo = retry.registrar_resultados([{"chamado_id": 10, "ok": True}, {"chamado_id": 20, "ok": False}])
        self.assertEqual(resumo["pendentes_persistidos"], 1)
        persistido = salvar.call_args.args[1]
        self.assertNotIn("10", persistido)
        self.assertIn("20", persistido)

    def test_sem_lote(self):
        self.assertEqual(retry.selecionar_com_pendencias([1], 0, "cursor"), [])


if __name__ == "__main__":
    unittest.main()
