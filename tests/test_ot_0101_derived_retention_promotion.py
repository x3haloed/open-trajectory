from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0101", ROOT / "experiments/ot_0101_derived_retention_promotion.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0101PromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior92 = module.mechanism.load_prior(); _, _, _, cls.p82 = module.mechanism.prior_chain(prior92)
        cls.aggregate, cls.corrected, cls.implementation = module.load_admitted_chain(cls.p82, ROOT, ROOT / ".evidence")

    def test_exact_chain_is_admitted(self):
        self.assertTrue(self.implementation["world"]["developmentally_admitted"])
        self.assertTrue(self.aggregate["active_fourth_correction"]["score"]["correction_gate_passed"])

    def test_complete_receipt_has_public_and_hidden_rows(self):
        self.assertEqual(len(self.implementation["world"]["public"]["rows"]), 2)
        self.assertEqual(len(self.implementation["world"]["hidden"]["rows"]), 4)

    def test_retention_is_not_actor_authored(self):
        self.assertNotIn("allocator_disposition", module.ASSIMILATION_KEYS)


if __name__ == "__main__": unittest.main()
