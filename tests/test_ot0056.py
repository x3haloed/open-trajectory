from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness.ot0056 import (
    INHERITANCE_LIMIT,
    all_real_weight_certificate,
    build_case,
    evaluate_case,
    initial_snapshot,
    project_snapshot,
    public_split,
    restore_snapshot,
    run_calibration,
)


class OT0056Tests(unittest.TestCase):
    def test_public_projection_removes_controller_answer_fields(self) -> None:
        regime = build_case(0)["regimes"][0]
        public = public_split(regime["contact"])
        self.assertNotIn("preferred_event_id", canonical_json(public).decode())
        self.assertNotIn("diagnostic_flag", canonical_json(public).decode())

    def test_all_real_weights_are_structurally_equivalent(self) -> None:
        canary = build_case(0)["regimes"][0]["canary"]
        certificate = all_real_weight_certificate(canary)
        self.assertTrue(certificate["pass"])
        self.assertTrue(certificate["all_real_weights_endpoint_equivalent"])
        self.assertEqual(certificate["tie_break_errors"], 4)

    def test_snapshot_round_trip_is_exact(self) -> None:
        snapshot = initial_snapshot()
        restored = restore_snapshot(project_snapshot(snapshot))
        self.assertEqual(restored.sha256, snapshot.sha256)

    def test_case_realizes_revision_and_compression_gates(self) -> None:
        result = evaluate_case(0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["pre_update_errors"][:2], [4, 8])
        self.assertEqual(result["reference_errors"], [0, 0, 0])
        for regime in result["regimes"]:
            certificate = regime["compression_certificate"]
            self.assertGreater(certificate["raw_bytes"], INHERITANCE_LIMIT)
            self.assertTrue(certificate["all_allowed_nonidentifying"])
            self.assertTrue(certificate["all_allowed_endpoint_divergent"])
            self.assertTrue(certificate["all_allowed_verbatim_errors_four"])
            self.assertEqual(set(regime["fixed_control_errors"].values()), {4})

    def test_complete_family_passes_in_both_orders(self) -> None:
        result = run_calibration(Path.cwd())
        self.assertEqual(result["case_count"], 32)
        self.assertEqual(result["passing_case_count"], 32)
        self.assertTrue(result["reverse_order_placebo"])
        self.assertEqual(result["disposition"], "promoted")


if __name__ == "__main__":
    unittest.main()
