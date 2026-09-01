from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0100", ROOT / "experiments/ot_0100_threshold_corrected_allocation.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0100ThresholdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior92 = module.mechanism.load_prior(); _, _, _, cls.p82 = module.mechanism.prior_chain(prior92)
        cls.third, cls.receipt = module.load_third_revision(cls.p82, ROOT, ROOT / ".evidence")

    def test_exact_threshold_failures(self):
        self.assertEqual({row["fixture_id"] for row in self.receipt["fixture_rows"] if not row["passed"]},
                         {"boolean-threshold-a", "boolean-threshold-b"})

    def test_reference_passes_fifth_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fifth_stage_conformance(module.mechanism.REFERENCE_ALLOCATOR, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["fixture_rows"]), 8)

    def test_third_revision_fails_fifth_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fifth_stage_conformance(self.third["allocator_source"], Path(directory))
        self.assertFalse(result["passed"])


if __name__ == "__main__": unittest.main()
