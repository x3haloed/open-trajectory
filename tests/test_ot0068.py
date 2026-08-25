from __future__ import annotations

import copy
import unittest
from pathlib import Path

from open_trajectory_harness.ot0068 import (
    INHERITANCE_LIMIT,
    PARTITION_HYPOTHESES,
    _overbudget_reference,
    actor_surface_authority,
    attempt_update,
    build_case,
    complete_contact,
    evaluate_case,
    initial_snapshot,
    project_snapshot,
    run_calibration,
)
from open_trajectory_harness.ot0067 import reference_partition
from open_trajectory_harness.ot0002 import canonical_json


class OT0068Tests(unittest.TestCase):
    def test_relational_world_is_identifiable_and_predecessor_wrong(self) -> None:
        task = build_case(0)
        self.assertEqual(len(PARTITION_HYPOTHESES), 4140)
        for regime in task["regimes"]:
            self.assertFalse(
                set(regime["diagnostic_pairs"]) & set(regime["heldout_pairs"])
            )
            self.assertEqual(
                [item["correct_side"] for item in regime["heldout"]].count("left"),
                4,
            )
        result = evaluate_case(0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["pre_update_errors"], [4, 8, 8])
        self.assertEqual(result["reference_errors"], [0, 0, 0])
        self.assertEqual(result["frozen_first_errors"], [0, 8, 4])
        self.assertEqual(result["frozen_second_errors"], [3, 0, 8])

    def test_every_raw_subset_is_measured_and_only_one_row_fits(self) -> None:
        result = evaluate_case(0)
        for regime in result["regimes"]:
            certificate = regime["compression_certificate"]
            self.assertTrue(certificate["pass"])
            self.assertEqual(certificate["evaluated_subset_count"], 32768)
            self.assertEqual(certificate["allowed_projection_count"], 16)
            self.assertEqual(certificate["maximum_allowed_rows"], 1)
            self.assertGreaterEqual(certificate["minimum_surviving_partitions"], 800)
            self.assertEqual(set(certificate["allowed_replay_errors"]), {4})

    def test_contact_perfect_padded_reference_fails_only_at_projection(self) -> None:
        regime = build_case(0)["regimes"][0]
        reference = reference_partition(regime)
        choices = ["left"] * len(regime["contact"]["bundles"])
        receipt = complete_contact(regime["contact"], choices)
        current = initial_snapshot()
        committed, reason = attempt_update(
            current, reference, receipt, regime["contact"]
        )
        self.assertEqual(reason, "committed")
        self.assertLessEqual(
            len(canonical_json(project_snapshot(committed))), INHERITANCE_LIMIT
        )
        padded = _overbudget_reference(reference)
        rejected, rejected_reason = attempt_update(
            current, padded, receipt, regime["contact"]
        )
        self.assertEqual(rejected_reason, "invalid")
        self.assertEqual(rejected.sha256, current.sha256)
        self.assertNotEqual(copy.deepcopy(padded), reference)
        self.assertEqual(INHERITANCE_LIMIT, 620)

    def test_all_cases_promote_without_candidate_output(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])
        result = run_calibration(Path.cwd())
        self.assertTrue(result["pilot_pass"])
        self.assertEqual(result["passing_case_count"], 16)
        self.assertEqual(result["future_candidate_authorization"], 1)
        self.assertFalse(result["candidate_outputs"])
        self.assertEqual(result["hosted_model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
