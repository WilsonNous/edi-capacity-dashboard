"""Regressões: persistência local, prazo estável e ausência de efeitos externos."""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from ednna import continuidade_decisoes as mod


class ContinuidadePersistidaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"EDNNA_DB_PATH": os.path.join(self.tmp.name, "ednna.db")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_idempotencia_e_prazo_nao_reinicia(self):
        item = {"chamado_id": 46312, "regra_id": "", "decisao": "MANTER_RESPONSAVEL_ATUAL",
                "motivo": "Aguardando terceiro", "responsavel_atual": {"id": 129, "nome": "Vitória"}}
        with patch.object(mod, "ultima_interpretacao_retorno", return_value={}):
            primeiro = mod.materializar_decisoes([item], agora=datetime(2026, 10, 8, 8, tzinfo=timezone.utc))
            prazo = mod.obter_decisao(46312)["prazo_revisao_em"]
            segundo = mod.materializar_decisoes([item], agora=datetime(2026, 10, 9, 8, tzinfo=timezone.utc))
        self.assertEqual(primeiro["novos"], 1)
        self.assertEqual(segundo["inalterados"], 1)
        self.assertEqual(mod.obter_decisao(46312)["prazo_revisao_em"], prazo)
        self.assertEqual(mod.obter_decisao(46312)["responsavel_id"], 129)

    def test_documentacao_impede_acao_externa(self):
        item = {"chamado_id": 49394, "decisao": "ACAO_EDDY_DUE", "motivo": "Retorno recebido"}
        interpretacao = {"classificacao": "PENDENCIA_DOCUMENTAL",
                        "evidencia": "Exigido termo assinado",
                        "proxima_acao": "Solicitar termo ao responsável legal",
                        "prazo_revisao_em": "2026-10-10T11:51:00-03:00"}
        with patch.object(mod, "ultima_interpretacao_retorno", return_value=interpretacao):
            mod.materializar_decisoes([item])
        r = mod.obter_decisao(49394)
        self.assertEqual(r["estado"], "AGUARDANDO_DOCUMENTACAO")
        self.assertEqual(r["decisao"], "VALIDACAO_HUMANA_DOCUMENTOS")
        self.assertIn("termo", r["evidencia"].lower())

    def test_sem_responsavel_nao_inventa_atribuicao(self):
        with patch.object(mod, "ultima_interpretacao_retorno", return_value={}):
            mod.materializar_decisoes([{"chamado_id": 38206, "decisao": "DECISAO_HUMANA"}])
        r = mod.obter_decisao(38206)
        self.assertIsNone(r["responsavel_id"])
        self.assertEqual(r["estado"], "REVISAO_HUMANA")


if __name__ == "__main__":
    unittest.main()
