from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0051 import fixed_input_paths, run_calibration


class OT0051Tests(unittest.TestCase):
    def test_wrapper_preserves_calibration_and_advances_identity(self) -> None:
        summary = run_calibration(Path.cwd())
        self.assertEqual(summary["experiment_id"], "OT-0051")
        self.assertEqual(summary["future_candidate_experiment_id"], "OT-0052")
        self.assertEqual(summary["case_count"], 48)
        self.assertEqual(summary["passing_case_count"], 48)
        self.assertTrue(summary["pilot_pass"])

    def test_invalidated_predecessor_is_a_fixed_input(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(
            Path(
                "evidence/manifests/OT-0050/ot-0050-staged-operation-calibration-001-invalidated.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
