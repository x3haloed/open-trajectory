from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0094", ROOT / "experiments/ot_0094_live_frontier_self_allocation.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0094LiveFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior92 = module.base.load_prior(); _, _, _, cls.prior82 = module.base.prior_chain(cls.prior92)
        cls.parent = module.base.load_parent(cls.prior82, ROOT, ROOT / ".evidence")

    def test_exact_parent_and_frozen_base(self):
        self.assertEqual(self.parent["artifact_digest"], module.base.PARENT_DIGEST)
        self.assertEqual(module.hashlib.sha256(module.BASE_PATH.read_bytes()).hexdigest(), module.BASE_SHA256)

    def test_live_frontier_excludes_saturated_pursuit(self):
        rows = module.live_reference_frontier()
        self.assertEqual({row["target_path"] for row in rows}, {"operations/recovery.py", "operations/joint.py"})
        self.assertTrue(all(not row["held_repeat"] for row in rows))
        result = module.validate_live_frontier(
            {"contacts": rows}, module.base.saturation_certificate(self.parent)
        )
        self.assertTrue(result["passed"], result)

    def test_preflight_preserves_hidden_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior92, self.prior82, self.parent, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["allocator_reference"]["passed"])
        self.assertTrue(result["live_frontier_reference"]["passed"])

    def test_established_disposition_vocabulary(self):
        contacts = module.live_reference_frontier()
        choice = {key: "grounded" for key in module.base.CHOICE_KEYS}
        choice["contact_id"] = contacts[0]["id"]
        choice["current_opening_disposition"] = "retire"
        self.assertTrue(module.valid_choice(choice, contacts))
        choice["current_opening_disposition"] = "deprioritize"
        self.assertFalse(module.valid_choice(choice, contacts))


if __name__ == "__main__":
    unittest.main()
