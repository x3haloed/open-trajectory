from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0067 import (
    PARTITION_HYPOTHESES,
    actor_surface_authority,
    regime_three_impossibility_certificate,
    run_calibration,
)


class OT0067Tests(unittest.TestCase):
    def test_complete_partition_hypothesis_family(self) -> None:
        self.assertEqual(len(PARTITION_HYPOTHESES), 4140)
        self.assertEqual(len(set(PARTITION_HYPOTHESES)), 4140)

    def test_regime_three_gate_is_prospectively_impossible(self) -> None:
        certificate = regime_three_impossibility_certificate()
        self.assertTrue(certificate["pass"])
        self.assertEqual(certificate["target_same_changed_pair_count"], 4)
        self.assertEqual(certificate["balanced_all_wrong_heldout_count"], 495)
        self.assertTrue(certificate["required_hidden_equals_singleton_mismatches"])
        self.assertTrue(certificate["singleton_matches_every_available_pair"])

    def test_complete_family_rejects_without_candidate(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])
        result = run_calibration(Path.cwd())
        self.assertEqual(result["passing_case_count"], 0)
        self.assertEqual(result["disposition"], "rejected")
        self.assertFalse(result["pilot_pass"])
        self.assertEqual(result["future_candidate_authorization"], 0)
        self.assertEqual(result["partition_hypothesis_count"], 4140)


if __name__ == "__main__":
    unittest.main()
