from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0089", ROOT / "experiments/ot_0089_derived_liveness.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0089Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior87 = module.load_prior(ROOT)
        cls.prior86 = cls.prior87.load_prior(ROOT)
        cls.prior85 = cls.prior86.load_prior(ROOT)
        cls.prior84 = cls.prior85.load_prior(ROOT)
        cls.prior83 = cls.prior84.load_prior(ROOT)
        cls.prior82 = cls.prior83.load_prior(ROOT)
        cls.parent = module.load_parent(cls.prior82, ROOT, ROOT / ".evidence")

    def test_exact_ot0088_apparatus_identity(self):
        self.assertEqual(module.BASE_SHA256, "65a9cb562fd0d1f95166a4012c2a758b04aa28e902a4ab7fca1553024fd9dce1")

    def test_substantive_opening_excludes_lifecycle_authority(self):
        opening = module.representative_successor()
        self.assertTrue(module.valid_successor(opening))
        self.assertFalse(module.valid_successor({**opening, "status": "open"}))
        opening.pop("unresolved")
        self.assertFalse(module.valid_successor(opening))

    def test_template_and_contract_match_exactly(self):
        self.assertEqual(set(module.successor_template()), module.SUCCESSOR_KEYS)
        self.assertEqual(set(module.successor_contract()["exact_keys"]), module.SUCCESSOR_KEYS)
        self.assertIn("derives canonical open", module.successor_contract()["lifecycle_authority"])

    def test_full_conformance_preserves_balanced_world(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior82, self.parent, Path(directory))
        self.assertTrue(result["passed"], json.dumps(result, sort_keys=True))
        self.assertTrue(result["actor_lifecycle_rejected"])
        self.assertEqual({row["hidden"]["gain"] for row in result["references"].values()}, {80.0})

    def test_parent_and_projection_are_unchanged(self):
        self.assertEqual(self.parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(self.parent["continuation"]["next_opening"], module.INHERITED_OPENING)
        self.assertTrue(module.projection_conformance(self.prior82, self.parent)["passed"])

    def test_frozen_causal_gate(self):
        self.assertLessEqual(module.fisher_enrichment(5, 1), 0.05)
        self.assertGreater(module.fisher_enrichment(4, 1), 0.05)


if __name__ == "__main__":
    unittest.main()
