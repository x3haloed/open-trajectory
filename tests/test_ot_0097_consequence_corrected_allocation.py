from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0097", ROOT / "experiments/ot_0097_consequence_corrected_allocation.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0097CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior92 = module.mechanism.load_prior(); _, _, _, cls.p82 = module.mechanism.prior_chain(prior92)
        cls.failed = module.load_failed_aggregate(cls.p82, ROOT, ROOT / ".evidence")

    def test_exact_failed_event_and_erasure(self):
        receipt = module.named_receipt(self.failed); erased = module.erased_receipt(self.p82, receipt)
        self.assertEqual([row["fixture_id"] for row in receipt["fixture_rows"] if not row["passed"]],
                         ["real-order", "real-reversed", "renamed"])
        self.assertTrue(module.projection_conformance(self.p82, receipt, erased)["passed"])

    def test_disjoint_reference_generalizes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.second_stage_conformance(module.mechanism.REFERENCE_ALLOCATOR, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["fixture_rows"]), 7)

    def test_failed_allocator_does_not_generalize(self):
        source = self.failed["active_allocation"]["binding"]["allocator_source"]
        with tempfile.TemporaryDirectory() as directory:
            result = module.second_stage_conformance(source, Path(directory))
        self.assertFalse(result["passed"])


if __name__ == "__main__": unittest.main()
