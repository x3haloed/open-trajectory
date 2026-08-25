from __future__ import annotations

import ast
import unittest
from pathlib import Path

from open_trajectory_harness.ot0059 import (
    actor_surface_authority,
    attempt_update,
    evaluate_case,
    evaluate_source,
    initial_snapshot,
    interpreter_rejection_receipt,
    parse_source,
    project_snapshot,
    reference_source,
    restore_snapshot,
    run_calibration,
)
from open_trajectory_harness.ot0048 import complete_contact
from open_trajectory_harness.ot0056 import build_case


class OT0059Tests(unittest.TestCase):
    def test_safe_interpreter_accepts_generic_predicates(self) -> None:
        event = {
            "event_id": "event-a",
            "selector_features": [0, 0, 0, 0],
            "on_flags": ["opaque"],
        }
        self.assertTrue(evaluate_source('"opaque" in event["on_flags"]', event))
        self.assertTrue(evaluate_source('event["event_id"] == "event-a"', event))
        self.assertTrue(interpreter_rejection_receipt()["pass"])

    def test_reference_update_is_contact_causal_and_restorable(self) -> None:
        regime = build_case(0)["regimes"][0]
        current = initial_snapshot()
        choices = [
            min(event["event_id"] for event in pair["events"])
            for pair in regime["contact"]["pairs"]
        ]
        receipt = complete_contact(regime["contact"], choices)
        source = reference_source(regime["target_flag"], regime["polarity"])
        updated, reason = attempt_update(current, source, receipt, regime["contact"])
        withheld, withheld_reason = attempt_update(
            current, source, None, regime["contact"]
        )
        type_invalid, type_invalid_reason = attempt_update(
            current, 'event["on_flags"] in "opaque"', receipt, regime["contact"]
        )
        self.assertEqual(reason, "committed")
        self.assertEqual(withheld_reason, "no-credit")
        self.assertEqual(withheld.sha256, current.sha256)
        self.assertEqual(type_invalid_reason, "invalid")
        self.assertEqual(type_invalid.sha256, current.sha256)
        self.assertEqual(
            restore_snapshot(project_snapshot(updated)).sha256, updated.sha256
        )
        self.assertLessEqual(len(source.encode()), 256)
        self.assertLessEqual(sum(1 for _ in ast.walk(parse_source(source))), 31)

    def test_case_realizes_all_causal_gates(self) -> None:
        result = evaluate_case(0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["reference_errors"], [0, 0, 0])
        self.assertEqual(result["no_state_errors"], [4, 4, 4])
        for regime in result["regimes"]:
            self.assertEqual(regime["constant_ast_ablation_errors"], 4)
            self.assertEqual(regime["literal_deletion_ablation_errors"], 4)
            self.assertTrue(regime["compression_certificate"]["pass"])

    def test_complete_family_and_surface_pass(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])
        result = run_calibration(Path.cwd())
        self.assertEqual(result["passing_case_count"], 32)
        self.assertTrue(result["reverse_order_placebo"])
        self.assertEqual(result["disposition"], "promoted")


if __name__ == "__main__":
    unittest.main()
