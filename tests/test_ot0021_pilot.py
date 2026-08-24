from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0021_pilot import (
    _summary,
    evaluate_actor_output,
    fixed_input_paths,
)


REPO = Path(__file__).resolve().parents[1]
VALID_OUTPUT = {
    "selector_expression": '[e["event_id"] for e in events[:limit]]',
    "decision_expression": (
        '"challenger" if comparison["challenger_error_advantage"] > 0 '
        'else "current"'
    ),
    "expected_effect": "retain a label-diverse bounded sample",
    "cheapest_falsifier": "paired error does not improve",
}


class OT0021PilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0021/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0021-acceptance.json")

    def test_known_valid_challenger_realizes_public_slice(self) -> None:
        result = evaluate_actor_output(self.task, VALID_OUTPUT)
        self.assertTrue(result["selection_changed"])
        self.assertTrue(result["prediction_changed"])
        self.assertEqual(result["challenger_error_advantage"], 6)
        self.assertEqual(result["true_choice"], "challenger")
        self.assertEqual(result["neutralized_choice"], "current")
        self.assertTrue(result["commit_changed"])

    def test_summary_requires_two_independent_complete_encounters(self) -> None:
        mechanism = evaluate_actor_output(self.task, VALID_OUTPUT)
        inventory = [{"name": "one"}, {"name": "two"}, {"name": "three"}]
        acceptance = dict(self.acceptance)
        acceptance["direct_inventory"] = {
            "sha256": sha256_bytes(canonical_json(inventory)),
            "tool_count": 3,
        }
        actors = [
            {
                "thread_id": f"thread-{index}",
                "workspace": f"workspace-{index}",
                "parse_error": None,
                "tool_calls": 0,
                "inventory_receipts": 1,
            }
            for index in range(2)
        ]
        receipts = [
            {"kind": "effective_model", "value": "gpt-5.6-luna"},
            {"kind": "models_etag", "value": "etag"},
            {"kind": "response_id", "value": "response-1"},
            {"kind": "response_id", "value": "response-2"},
        ]
        summary = _summary(
            acceptance=acceptance,
            actor_results=actors,
            mechanisms=[mechanism, mechanism],
            direct_inventories=[inventory, inventory],
            proxy_receipts=receipts,
            collector_errors=[],
            usage={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            elapsed_seconds=1,
            failure_type=None,
            verification={"tests_returncode": 0, "audit_returncode": 0},
        )
        self.assertTrue(summary["pilot_pass"])
        failed = _summary(
            acceptance=acceptance,
            actor_results=actors[:1],
            mechanisms=[mechanism],
            direct_inventories=[inventory],
            proxy_receipts=receipts[:3],
            collector_errors=[],
            usage={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            elapsed_seconds=1,
            failure_type="TimeoutError",
            verification={"tests_returncode": 0, "audit_returncode": 0},
        )
        self.assertFalse(failed["pilot_pass"])

    def test_run_lock_covers_every_trace_authority(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0021_trace.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0021_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0021/pilot-task.json"), paths)
        self.assertIn(Path("fixtures/ot-0021/trace-prompt.txt"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0020/ot-0020-hosted-epoch-001-invalidated.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
