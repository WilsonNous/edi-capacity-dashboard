import unittest
from unittest.mock import patch
from ednna.interpretacao_retorno import interpretar_retorno


class IntegracaoInterpretacaoTest(unittest.TestCase):
    def test_documentacao_greencard_nao_autoriza_cobranca(self):
        r = interpretar_retorno(
            "Somente serão realizadas mediante o envio do termo devidamente preenchido e assinado. "
            "Preferencialmente enviar documento com foto. Protocolo de atendimento: 70706.",
            assunto="GREENCARD POSTOS ROTA #49394",
            recebido_em="2026-10-01T11:51:00-03:00",
        )
        self.assertEqual(r["estado_sugerido"], "AGUARDANDO_DOCUMENTACAO")
        self.assertFalse(r["followup_externo_permitido"])
        self.assertEqual(r["protocolo"], "70706")

    def test_cache_terminal_eh_permanente(self):
        from ednna import contexto_relacionamentos as ctx
        import inspect
        fonte = inspect.getsource(ctx._cache_obter)
        self.assertIn('estado not in {"CONCLUIDO"', fonte)

    def test_monitor_persiste_interpretacao_antes_do_redmine(self):
        from pathlib import Path
        texto = Path("ednna/monitor_respostas.py").read_text(encoding="utf-8")
        self.assertLess(texto.index("interpretacao = registrar_interpretacao_retorno("),
                        texto.index("registrar_resposta_pendente_redmine(\n                chamado_id, regra_id,"))


if __name__ == "__main__":
    unittest.main()
