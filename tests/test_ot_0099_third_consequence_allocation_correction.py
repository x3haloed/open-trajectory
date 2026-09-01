from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0099", ROOT / "experiments/ot_0099_third_consequence_allocation_correction.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0099ThirdCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior92 = module.mechanism.load_prior(); _, _, _, cls.p82 = module.mechanism.prior_chain(prior92)
        cls.second, cls.receipt = module.load_second_revision(cls.p82, ROOT, ROOT / ".evidence")

    def test_exact_two_failure_receipt(self):
        self.assertEqual({row["fixture_id"] for row in self.receipt["fixture_rows"] if not row["passed"]},
                         {"threshold-regret", "threshold-equality"})

    def test_reference_passes_fourth_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fourth_stage_conformance(module.mechanism.REFERENCE_ALLOCATOR, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["fixture_rows"]), 9)

    def test_second_revision_fails_fourth_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fourth_stage_conformance(self.second["allocator_source"], Path(directory))
        self.assertFalse(result["passed"])


if __name__ == "__main__": unittest.main()
