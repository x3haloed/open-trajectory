from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0340_priority_causal_interpretation_correction.py"
spec = importlib.util.spec_from_file_location("ot0340_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0340Tests(unittest.TestCase):
    def test_policy_projection_ignores_labels(self):
        a = {"policy_id": "a", "rationale": "first", "requirements": ["x"], "priority_order": ["m"], "directions": {"m": "higher"}, "on_tie": "retain-open"}
        b = {**a, "policy_id": "b", "rationale": "second"}
        self.assertEqual(module.operative_policy(a), module.operative_policy(b))

    def test_policy_projection_detects_direction(self):
        a = {"policy_id": "a", "rationale": "first", "requirements": ["x"], "priority_order": ["m"], "directions": {"m": "higher"}, "on_tie": "retain-open"}
        b = {**a, "directions": {"m": "lower"}}
        self.assertNotEqual(module.operative_policy(a), module.operative_policy(b))


if __name__ == "__main__":
    unittest.main()
