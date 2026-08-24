from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0041 import (
    fixed_input_paths,
    negative_turn_safe,
)


class OT0041Tests(unittest.TestCase):
    def test_negative_turn_allows_explicit_inventory_presence_or_absence(self) -> None:
        turn = {
            "turn_status": "failed",
            "error_message": "invalid_json_schema: uniqueItems is not permitted",
            "response_ids": [],
            "collector_errors": [],
        }
        self.assertTrue(negative_turn_safe(turn, None))
        self.assertTrue(negative_turn_safe(turn, [{"name": "tool"}]))

    def test_negative_turn_rejects_secondary_exception_or_transport_error(self) -> None:
        base = {
            "turn_status": "failed",
            "error_message": "invalid_json_schema: uniqueItems is not permitted",
            "response_ids": [],
            "collector_errors": [],
        }
        exception = {**base, "turn_status": "exception"}
        transport = {**base, "collector_errors": ["upstream forwarding failed"]}
        self.assertFalse(negative_turn_safe(exception, None))
        self.assertFalse(negative_turn_safe(transport, None))

    def test_run_lock_binds_paired_core_and_both_predecessors(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0040.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0040/"
                "ot-0040-e8-hosted-schema-calibration-001.json"
            ),
            paths,
        )
        self.assertIn(
            Path(
                "evidence/manifests/OT-0039/"
                "ot-0039-e7-self-authored-goal-candidate-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
