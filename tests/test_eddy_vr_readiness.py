import unittest
from ednna.eddy_vr_readiness import verificar_prontidao_vr01

class TestVrReadiness(unittest.TestCase):
    def test_default_is_blocked(self):
        r = verificar_prontidao_vr01({})
        self.assertFalse(r["pronto"])
        self.assertIn("EXECUCAO_EXTERNA_DESABILITADA", r["bloqueios"])

    def test_mysql_alone_not_sufficient(self):
        r = verificar_prontidao_vr01({"EDDY_DB_ENGINE": "mysql"})
        self.assertFalse(r["pronto"])
        self.assertIn("TRANSPORTE_MYSQL_NAO_HOMOLOGADO", r["bloqueios"])

if __name__ == "__main__":
    unittest.main()
