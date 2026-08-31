from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0092", ROOT / "experiments/ot_0092_actor_contact_renewal.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0092Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior91 = module.load_prior(); cls.prior90 = cls.prior91.load_prior(); cls.prior89 = cls.prior90.load_prior(); cls.prior82 = cls.prior90.prior82(cls.prior89)
        cls.parent = module.load_parent(cls.prior91, cls.prior82, ROOT, ROOT / ".evidence")

    def test_exact_parent_and_capabilities(self):
        self.assertEqual(self.parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(module.capability(self.parent, "verify_coverage.py")["source_digest"], module.VERIFIER_DIGEST)
        self.assertEqual(module.capability(self.parent, "studio/coverage.py")["source_digest"], module.COVERAGE_DIGEST)

    def test_structural_contact_requires_reorder_tie_and_unique_score(self):
        cases = [module.case("a", 2, module.FOUR_TIE), module.case("b", 2, list(reversed(module.FOUR_TIE))), module.case("c", 1, module.NEAR_TIE)]
        result = module.contact_conformance({"cases": cases})
        self.assertTrue(result["passed"], result)
        self.assertFalse(module.contact_conformance({"cases": cases[:2]})["passed"])

    def test_hidden_suite_and_reference_loop(self):
        self.assertTrue(module.REQUIRED_REORDERED.issubset({row["case_id"] for row in module.HIDDEN_CASES}))
        result = module.fixture_conformance(self.prior91, self.prior89, self.prior82, self.parent)
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["hidden_reference"]["valid"])
        self.assertTrue(result["active_assimilation_reference"]["passed"])
        self.assertTrue(result["erased_assimilation_rejected"])


if __name__ == "__main__": unittest.main()
