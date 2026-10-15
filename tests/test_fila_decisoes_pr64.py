import unittest
from datetime import datetime, timezone
from ednna.fila_decisoes_continuidade import organizar_fila


class TestFilaAssistida(unittest.TestCase):
    def test_filtra_e_prioriza_prazo_vencido(self):
        dados = [
            {"chamado_id": 1, "estado": "ACOMPANHAMENTO_HUMANO"},
            {"chamado_id": 2, "estado": "REVISAO_HUMANA", "prazo_revisao_em": "2026-10-14T00:00:00+00:00", "decisao": "DECISAO_HUMANA"},
            {"chamado_id": 3, "estado": "REVISAO_HUMANA", "prazo_revisao_em": "2026-10-20T00:00:00+00:00", "responsavel_id": 97},
        ]
        fila = organizar_fila(dados, agora=datetime(2026, 10, 15, tzinfo=timezone.utc))
        self.assertEqual(fila["total"], 2)
        self.assertEqual(fila["vencidos"], 1)
        self.assertEqual(fila["sem_responsavel"], 1)
        self.assertEqual(fila["itens"][0]["chamado_id"], 2)
        self.assertTrue(all(not x["executavel_automaticamente"] for x in fila["itens"]))

    def test_limite_nao_altera_total(self):
        dados = [{"chamado_id": i, "estado": "REVISAO_HUMANA"} for i in range(1, 5)]
        fila = organizar_fila(dados, limite=2)
        self.assertEqual(fila["total"], 4)
        self.assertEqual(len(fila["itens"]), 2)


if __name__ == "__main__":
    unittest.main()
