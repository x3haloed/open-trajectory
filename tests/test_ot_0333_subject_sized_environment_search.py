from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0333_subject_sized_environment_search.py"
spec = importlib.util.spec_from_file_location("ot0333_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0333Tests(unittest.TestCase):
    def test_frozen_bounds(self):
        self.assertEqual(module.OBSERVER_PROVIDER_CEILING, 4)
        self.assertEqual(module.SUBJECT_PROVIDER_CEILING, 3)
        self.assertEqual(module.MINIMUM_PROVIDER_COUNT, 2)

    def test_policy_interpreter_requires_stable_support(self):
        policy = module.fixture_policy()
        self.assertEqual(module.policy_action(policy, [], 0), "request-world")
        history = [
            {"supported": True, "selected_world_id": "a"},
            {"supported": True, "selected_world_id": "a"},
        ]
        self.assertEqual(module.policy_action(policy, history, 2), "offer-world")
        history[-1]["selected_world_id"] = "b"
        self.assertEqual(module.policy_action(policy, history, 2), "request-world")
        self.assertEqual(module.policy_action(policy, history, 3), "revise-stake")


if __name__ == "__main__":
    unittest.main()
