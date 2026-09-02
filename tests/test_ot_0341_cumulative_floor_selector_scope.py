from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0341_cumulative_floor_selector_scope.py"
spec = importlib.util.spec_from_file_location("ot0341_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0341Tests(unittest.TestCase):
    def test_decision_combinations(self):
        for index, row in enumerate(module.DECISION_CONTRACT["allowed"]):
            decision = {
                "decision_id": f"decision-{index}",
                "global_stake_action": row[0],
                "world_policy_role": row[1],
                "next_operation": row[2],
                "rationale": "A grounded test decision.",
            }
            self.assertTrue(module.valid_decision(decision))

    def test_mixed_decision_rejected(self):
        decision = {
            "decision_id": "mixed-invalid",
            "global_stake_action": "revise",
            "world_policy_role": "post-contact-selector",
            "next_operation": "test-world-consequence-policy-reuse",
            "rationale": "Inconsistent roles.",
        }
        self.assertFalse(module.valid_decision(decision))

    def test_output_paths_follow_stake_change(self):
        base = {"action": "resolve-selector-scope", "note": "Done."}
        self.assertTrue(module.output_valid({**base, "files_changed": ["selector-scope-decision.json"]}, False))
        self.assertTrue(module.output_valid({**base, "files_changed": ["selector-scope-decision.json", "stake-revision.json"]}, True))
        self.assertFalse(module.output_valid({**base, "files_changed": ["selector-scope-decision.json"]}, True))


if __name__ == "__main__":
    unittest.main()
