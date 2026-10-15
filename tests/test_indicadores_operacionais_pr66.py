import unittest
from ednna.indicadores_operacionais import calcular_indicadores


class TestIndicadoresOperacionais(unittest.TestCase):
    def test_nao_contar_envio_sem_confirmacao(self):
        itens = [
            {"envio_confirmado": 1, "resposta_recebida_em": "2026-10-15", "followup_count": 2},
            {"envio_confirmado": 0, "enviado_em": "2026-10-15", "followup_count": 0},
            {"envio_confirmado": None, "redmine_erro": "timeout"},
        ]
        r = calcular_indicadores(itens)
        self.assertEqual(r["envios_iniciais_confirmados"], 1)
        self.assertEqual(r["respostas_registradas"], 1)
        self.assertEqual(r["followups_registrados"], 2)
        self.assertEqual(r["redmine_pendente"], 1)
        self.assertIsNone(r["tempo_economizado_minutos"])
        self.assertIsNone(r["intervencoes_humanas_evitadas"])

    def test_vazio(self):
        r = calcular_indicadores([])
        self.assertEqual(r["registros_transacionais"], 0)
        self.assertEqual(r["envios_iniciais_confirmados"], 0)


if __name__ == "__main__":
    unittest.main()
