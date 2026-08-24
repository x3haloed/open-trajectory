from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0036_e6_calibration import criteria, rule_pairs
from open_trajectory_harness.ot0044 import (
    evaluate_advantage_case,
    fixed_input_paths,
)


class OT0044Tests(unittest.TestCase):
    def acceptance(self) -> dict[str, int]:
        return {
            "old_advantage_threshold": 4,
            "new_advantage_threshold": 3,
            "candidate_action_successes": 8,
            "unchanged_control_action_successes": 5,
            "one_repair_defect_action_successes": 7,
        }

    def test_exact_causal_advantage_is_three(self) -> None:
        result = evaluate_advantage_case(
            0, criteria()[0], 0, rule_pairs()[0], self.acceptance()
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["candidate_actions"], 8)
        self.assertEqual(result["unchanged_actions"], 5)
        self.assertEqual(result["perfect_advantage"], 3)

    def test_old_threshold_rejects_perfection_and_new_rejects_defect(self) -> None:
        result = evaluate_advantage_case(
            383, criteria()[383], 5, rule_pairs()[5], self.acceptance()
        )
        self.assertTrue(result["checks"]["old_threshold_impossible"])
        self.assertTrue(result["checks"]["new_threshold_accepts"])
        self.assertTrue(result["checks"]["one_defect_rejected"])
        self.assertEqual(result["one_defect_advantage"], 2)

    def test_fixed_inputs_bind_e9_and_rejected_candidate(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0043.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0043/"
                "ot-0043-e9-split-interface-calibration-001.json"
            ),
            paths,
        )
        self.assertIn(
            Path(
                "evidence/manifests/OT-0042/"
                "ot-0042-e8b-self-authored-goal-candidate-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
