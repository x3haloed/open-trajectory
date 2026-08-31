from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0088", ROOT / "experiments/ot_0088_unseen_pursuit_selection.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0088Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior87 = module.load_prior(ROOT)
        cls.prior86 = cls.prior87.load_prior(ROOT)
        cls.prior85 = cls.prior86.load_prior(ROOT)
        cls.prior84 = cls.prior85.load_prior(ROOT)
        cls.prior83 = cls.prior84.load_prior(ROOT)
        cls.prior82 = cls.prior83.load_prior(ROOT)
        cls.parent = module.load_parent(cls.prior82, ROOT, ROOT / ".evidence")

    def test_balanced_world_and_all_reference_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior82, self.parent, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertEqual(set(result["references"]), set(module.TARGETS))
        for target in result["references"].values():
            self.assertEqual(target["hidden"]["gain"], 80.0)
            self.assertTrue(target["public"]["no_case_regression"])

    def test_pursuit_erasure_preserves_non_pursuit_projection(self):
        result = module.projection_conformance(self.prior82, self.parent)
        self.assertTrue(result["passed"], result)
        active = module.active_projection(self.parent)
        erased = module.erased_projection(self.prior82, self.parent)
        self.assertIn(module.INHERITED_OPENING, json.dumps(active))
        self.assertNotIn(module.INHERITED_OPENING, json.dumps(erased))

    def test_frozen_exact_count_gate(self):
        self.assertLessEqual(module.fisher_enrichment(5, 1), 0.05)
        self.assertGreater(module.fisher_enrichment(4, 1), 0.05)
        self.assertLess(module.fisher_enrichment(6, 0), module.fisher_enrichment(5, 1))

    def test_actor_schemas_use_supported_subset(self):
        for name in ("ot-0088-route.schema.json", "ot-0088-implementation.schema.json"):
            schema = json.loads((ROOT / "spec" / name).read_text())
            self.assertNotIn("uniqueItems", schema["properties"]["files_changed"])

    def test_parent_position(self):
        self.assertEqual(self.parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(self.parent["continuation"]["next_opening"], module.INHERITED_OPENING)


if __name__ == "__main__":
    unittest.main()
