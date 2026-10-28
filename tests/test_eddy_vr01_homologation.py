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
homologar_observacao_vr01 = module.homologar_observacao_vr01


class VR01HomologationTests(unittest.TestCase):
    def test_explicit_pilot_observation_approval_preserves_external_blocks(self):
        result = homologar_observacao_vr01({"chamado_id": 50318}, autorizacao_explicita=True)
        self.assertTrue(result["homologada"])
        self.assertEqual(result["estado"], "HOMOLOGADA_SOMENTE_OBSERVACAO")
        self.assertFalse(result["envios_autorizados"])
        self.assertFalse(result["redmine_escritas_autorizadas"])
        self.assertEqual(set(result["pendencias_execucao_externa"]), set(REQUIRED))

    def test_observation_requires_explicit_authorization(self):
        result = homologar_observacao_vr01({"chamado_id": 50318})
        self.assertFalse(result["homologada"])

    def test_closed_previous_pilot_cannot_be_approved(self):
        result = homologar_observacao_vr01({"chamado_id": 49227}, autorizacao_explicita=True)
        self.assertFalse(result["homologada"])
        self.assertFalse(result["envios_autorizados"])

    def test_observation_cannot_approve_another_issue(self):
        result = homologar_observacao_vr01({"chamado_id": 123}, autorizacao_explicita=True)
        self.assertFalse(result["homologada"])

    def test_missing_evidence_fails_closed(self):
        result = avaliar_homologacao_vr01({"chamado_id": 50318})
        self.assertEqual(result["estado"], "HOMOLOGACAO_PENDENTE")
        self.assertEqual(set(result["pendencias"]), set(REQUIRED))
        self.assertFalse(result["homologada"])

    def test_other_issue_cannot_pass(self):
        result = avaliar_homologacao_vr01({"chamado_id": 1})
        self.assertEqual(result["estado"], "BLOQUEADO_ESCOPO")

    def test_complete_evidence_requires_review(self):
        data = {"chamado_id": 50318}
        data.update({name: {"confirmado": True, "referencia": "audit/123"} for name in REQUIRED})
        result = avaliar_homologacao_vr01(data)
        self.assertEqual(result["pendencias"], [])
        self.assertEqual(result["estado"], "EVIDENCIAS_COMPLETAS_PARA_REVISAO")
        self.assertFalse(result["homologada"])

    def test_boolean_without_reference_not_evidence(self):
        data = {"chamado_id": 50318, "redmine_snapshot_fresco": True}
        self.assertIn("redmine_snapshot_fresco", avaliar_homologacao_vr01(data)["pendencias"])


if __name__ == "__main__":
    unittest.main()
