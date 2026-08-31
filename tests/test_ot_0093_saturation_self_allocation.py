from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0093", ROOT / "experiments/ot_0093_saturation_self_allocation.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0093WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior92 = module.load_prior(); _, _, _, cls.prior82 = module.prior_chain(cls.prior92)
        cls.parent = module.load_parent(cls.prior82, ROOT, ROOT / ".evidence")

    def test_exact_parent_selector_and_saturation(self):
        self.assertEqual(self.parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(self.parent["developmental_selector"]["selector_digest"], module.SELECTOR_DIGEST)
        certificate = module.saturation_certificate(self.parent)
        self.assertTrue(certificate["all_cases_passed"])
        self.assertEqual(certificate["next_same_domain_case"], "held_repeat")

    def test_balanced_world_frontier_and_allocator(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior92, self.prior82, self.parent, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["balanced_public_gain"])
        self.assertTrue(result["balanced_hidden_gain"])
        self.assertTrue(result["frontier_reference"]["passed"])
        self.assertTrue(result["allocator_reference"]["passed"])

    def test_allocator_source_is_path_and_id_agnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.allocator_conformance(module.REFERENCE_ALLOCATOR, Path(directory))
        self.assertTrue(result["generic_source"])
        self.assertTrue(result["passed"])


if __name__ == "__main__": unittest.main()
