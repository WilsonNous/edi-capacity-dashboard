import unittest

import importlib.util
from pathlib import Path

# Load pure homologation gate without importing legacy ednna package side effects.
module_path = Path(__file__).resolve().parents[1] / 'ednna' / 'eddy_vr01_homologation.py'
spec = importlib.util.spec_from_file_location('eddy_vr01_homologation_isolated', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
REQUIRED = module.REQUIRED
avaliar_homologacao_vr01 = module.avaliar_homologacao_vr01


class VR01HomologationTests(unittest.TestCase):
    def test_missing_evidence_fails_closed(self):
        result = avaliar_homologacao_vr01({"chamado_id": 49227})
        self.assertEqual(result["estado"], "HOMOLOGACAO_PENDENTE")
        self.assertEqual(set(result["pendencias"]), set(REQUIRED))
        self.assertFalse(result["homologada"])

    def test_other_issue_cannot_pass(self):
        result = avaliar_homologacao_vr01({"chamado_id": 1})
        self.assertEqual(result["estado"], "BLOQUEADO_ESCOPO")

    def test_complete_evidence_requires_review(self):
        data = {"chamado_id": 49227}
        data.update({name: {"confirmado": True, "referencia": "audit/123"} for name in REQUIRED})
        result = avaliar_homologacao_vr01(data)
        self.assertEqual(result["pendencias"], [])
        self.assertEqual(result["estado"], "EVIDENCIAS_COMPLETAS_PARA_REVISAO")
        self.assertFalse(result["homologada"])

    def test_boolean_without_reference_not_evidence(self):
        data = {"chamado_id": 49227, "redmine_snapshot_fresco": True}
        self.assertIn("redmine_snapshot_fresco", avaliar_homologacao_vr01(data)["pendencias"])


if __name__ == "__main__":
    unittest.main()
