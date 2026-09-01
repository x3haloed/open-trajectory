from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0098", ROOT / "experiments/ot_0098_iterated_allocation_correction.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0098IterationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior92 = module.mechanism.load_prior(); _, _, _, cls.p82 = module.mechanism.prior_chain(prior92)
        failed = module.base.load_failed_aggregate(cls.p82, ROOT, ROOT / ".evidence")
        cls.shallow = module.load_shallow_candidate(cls.p82, ROOT, ROOT / ".evidence", failed)

    def test_shallow_candidate_is_exact_revision(self):
        self.assertTrue(self.shallow["revision_derived"])
        self.assertEqual(self.shallow["choice"]["contact_id"], "joint")

    def test_shallow_fails_second_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = module.seal_second_stage(self.p82, self.shallow, Path(directory))
        self.assertFalse(receipt["passed"])
        self.assertEqual({row["fixture_id"] for row in receipt["fixture_rows"] if not row["passed"]},
                         {"composition-over-gain", "composition-regret", "threshold-not-count"})

    def test_reference_passes_third_stage_and_shallow_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = module.third_stage_conformance(module.mechanism.REFERENCE_ALLOCATOR, root / "reference")
            shallow = module.third_stage_conformance(self.shallow["allocator_source"], root / "shallow")
        self.assertTrue(reference["passed"], reference)
        self.assertFalse(shallow["passed"])


if __name__ == "__main__": unittest.main()
