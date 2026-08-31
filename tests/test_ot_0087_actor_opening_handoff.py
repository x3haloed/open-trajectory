from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0087", ROOT / "experiments/ot_0087_actor_opening_handoff.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0087Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior86 = module.load_prior(ROOT)
        cls.prior85 = cls.prior86.load_prior(ROOT)
        cls.prior84 = cls.prior85.load_prior(ROOT)
        cls.prior83 = cls.prior84.load_prior(ROOT)
        cls.prior82 = cls.prior83.load_prior(ROOT)

    def test_complete_world_and_all_target_references(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior82, Path(directory))
        self.assertTrue(result["passed"], result)
        self.assertEqual(set(result["references"]), set(module.TARGETS))
        for target in result["references"].values():
            self.assertTrue(target["public"]["no_case_regression"])
            self.assertGreaterEqual(target["hidden"]["gain"], module.MIN_HIDDEN_GAIN)
            self.assertGreaterEqual(target["hidden"]["oracle_improvement_fraction"], module.MIN_ORACLE_FRACTION)

    def test_opening_contract_allows_choice_or_surrender(self):
        representative = {
            "status": "open",
            "next_opening": "Follow one observed discrepancy.",
            "chosen_target_path": "ensemble/mix.py",
            "target_symbol": "choose_mix",
            "observed_discrepancy": "The public mix policy leaves regret.",
            "world_contact": "Compare expected mix value.",
            "surrender_condition": "Stop if held-out value is not improved.",
            "continuation_after_contact": "Inspect what remains unresolved.",
        }
        self.assertTrue(module.valid_opening(representative))
        representative["status"] = "surrendered"
        representative["chosen_target_path"] = ""
        representative["target_symbol"] = ""
        self.assertTrue(module.valid_opening(representative))
        self.assertFalse(module.valid_opening(module.opening_template()))

    def test_parent_position(self):
        parent = module.load_parent(self.prior86, self.prior82, ROOT, ROOT / ".evidence")
        self.assertEqual(parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(parent["active_pursuit"]["next_pursuit"], "No further action required.")
        self.assertEqual(parent["continuation"]["next_opening"], "inspect-and-select-environmental-intervention")

    def test_successor_schema_uses_supported_exact_audit_subset(self):
        schema = json.loads((ROOT / "spec/ot-0087-successor.schema.json").read_text())
        files = schema["properties"]["files_changed"]
        self.assertNotIn("uniqueItems", files)
        self.assertEqual(files["minItems"], 2)
        self.assertEqual(files["maxItems"], 2)


if __name__ == "__main__":
    unittest.main()
