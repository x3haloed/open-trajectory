from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0339_subject_authored_world_consequence_policy.py"
spec = importlib.util.spec_from_file_location("ot0339_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0339Tests(unittest.TestCase):
    def test_lexicographic_direction(self):
        policy = module.fixture_policy()
        rows = [
            {"world_id": "two", "admissible": True, "metrics": {"viable_contact_count": 2, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}},
            {"world_id": "three", "admissible": True, "metrics": {"viable_contact_count": 3, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}},
        ]
        self.assertEqual(module.choose(policy, rows)["selected_world_id"], "three")

    def test_floor_failure_is_inadmissible(self):
        policy = module.fixture_policy()
        rows = [
            {"world_id": "many-bad", "admissible": False, "metrics": {"viable_contact_count": 9, "mean_match_basis_points": 9000, "minimum_match_basis_points": 9000}},
            {"world_id": "two-good", "admissible": True, "metrics": {"viable_contact_count": 2, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}},
        ]
        self.assertEqual(module.choose(policy, rows)["selected_world_id"], "two-good")


if __name__ == "__main__":
    unittest.main()
