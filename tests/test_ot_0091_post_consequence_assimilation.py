from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0091", ROOT / "experiments/ot_0091_post_consequence_assimilation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0091Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior90 = module.load_prior()
        cls.prior89 = cls.prior90.load_prior()
        cls.prior82 = cls.prior90.prior82(cls.prior89)
        cls.parent, cls.aggregate = module.load_inputs(cls.prior90, cls.prior82, ROOT, ROOT / ".evidence")
        cls.world = module.consequence(cls.aggregate)

    def test_exact_parent_and_receipt(self):
        self.assertEqual(self.parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(self.parent["continuation"]["next_opening"], module.INHERITED_OPENING)
        self.assertEqual(self.world["receipt_digest"], module.WORLD_RECEIPT_DIGEST)

    def test_erasure_preserves_identity_and_removes_outcomes(self):
        result = module.projection_conformance(self.prior82, self.parent, self.world)
        self.assertTrue(result["passed"], result)

    def test_reference_assimilation_passes_only_with_content(self):
        result = module.fixture_conformance(self.prior90, self.prior82, self.parent, self.world)
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["active_reference_passed"])
        self.assertTrue(result["erased_reference_rejected"])

    def test_assimilation_contract_exactness(self):
        self.assertEqual(set(module.assimilation_template()), module.ASSIMILATION_KEYS)
        self.assertFalse(module.valid_assimilation(module.assimilation_template()))


if __name__ == "__main__":
    unittest.main()
