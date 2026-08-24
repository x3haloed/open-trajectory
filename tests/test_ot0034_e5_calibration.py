from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0034_e5_calibration import (
    candidate_authority,
    criteria,
    evaluate_criterion,
    fixed_input_paths,
    validate_run_lock,
)


class OT0034E5CalibrationTests(unittest.TestCase):
    def test_criterion_family_is_complete_and_unique(self) -> None:
        family = criteria()
        self.assertEqual(len(family), 384)
        self.assertEqual(len(set(family)), 384)

    def test_excluded_development_criteria_pass_every_controller_gate(self) -> None:
        family = criteria()
        for index in (0, 1, 127, 255, 383):
            with self.subTest(index=index):
                result = evaluate_criterion(index, family[index])
                self.assertTrue(result["pass"])
                self.assertTrue(all(result["checks"].values()))

    def test_candidate_reachability_excludes_world_and_dynamic_authority(self) -> None:
        authority = candidate_authority(Path.cwd())
        self.assertTrue(authority["pass"])
        self.assertEqual(authority["parameters"], ["current", "completed"])
        self.assertEqual(authority["forbidden_reachable"], [])
        self.assertNotIn("build_task", authority["reachable_functions"])
        self.assertNotIn("_hidden_weights", authority["reachable_functions"])

    def test_run_lock_covers_calibration_and_candidate_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0034-acceptance.json"), paths)
        self.assertIn(
            Path("src/open_trajectory_harness/ot0034_e5_calibration.py"),
            paths,
        )
        self.assertIn(
            Path("src/open_trajectory_harness/ot0033_weighted_selector.py"),
            paths,
        )
        self.assertIn(Path("experiments/ot_0034_harness.py"), paths)

    def test_frozen_run_lock_reconstructs_all_runtime_authorities(self) -> None:
        implementation = "00852ada0c1e3e64480e4f93518fc5b20b908d25"
        lock = validate_run_lock(Path.cwd(), implementation)
        self.assertEqual(lock["implementation_git_commit"], implementation)


if __name__ == "__main__":
    unittest.main()
