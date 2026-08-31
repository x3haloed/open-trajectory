from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0090", ROOT / "experiments/ot_0090_confirmation_renewal.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0090Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior89 = module.load_prior()
        cls.prior82 = module.prior82(cls.prior89)
        cls.parent = module.load_parent(cls.prior82, ROOT, ROOT / ".evidence")

    def test_exact_open_parent_and_capability(self):
        self.assertEqual(self.parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(self.parent["continuation"]["next_opening"], module.INHERITED_OPENING)
        self.assertEqual(module.retained_coverage(self.parent)["source_digest"], module.COVERAGE_SOURCE_DIGEST)

    def test_reference_generalizes_and_placeholder_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior89, self.prior82, self.parent, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["public_reference"]["valid"])
        self.assertTrue(result["hidden_reference"]["valid"])
        self.assertTrue(result["placeholder_rejected"])

    def test_hidden_cases_cover_ties_and_near_tie(self):
        ids = {case["case_id"] for case in module.HIDDEN_CASES}
        self.assertEqual(ids, {"hidden-two-way", "hidden-three-way", "hidden-near-tie", "hidden-cost-tie"})

    def test_successor_has_no_lifecycle_field(self):
        template = module.successor_template(self.prior89)
        self.assertNotIn("status", template)
        self.assertFalse(self.prior89.valid_successor(template))

    def test_actor_schema_has_exact_mutation_envelope(self):
        import json
        schema = json.loads(module.ACTOR_SCHEMA.read_text())
        self.assertEqual(set(schema["properties"]["files_changed"]["items"]["enum"]), {"verify_coverage.py", "successor-opening.json"})


if __name__ == "__main__":
    unittest.main()
