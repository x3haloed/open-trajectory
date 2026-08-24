from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0021_pilot import evaluate_actor_output, rendered_prompt
from open_trajectory_harness.ot0022_pilot import configure_protocol, fixed_input_paths


REPO = Path(__file__).resolve().parents[1]
VALID_OUTPUT = {
    "selector_expression": '[e["event_id"] for e in events[:limit]]',
    "decision_expression": (
        '"challenger" if comparison["challenger_error_advantage"] > 0 '
        'else "current"'
    ),
    "expected_effect": "retain enough varied outcomes to fit the observations",
    "cheapest_falsifier": "paired error does not improve",
}


class OT0022PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def test_fresh_task_is_hidden_and_known_slice_is_realizable(self) -> None:
        task = load_json(REPO / "fixtures/ot-0022/pilot-task.json")
        prompt, _ = rendered_prompt(REPO, task)
        self.assertNotIn("sealed2-event-", prompt)
        result = evaluate_actor_output(task, VALID_OUTPUT)
        self.assertEqual(result["challenger_error_advantage"], 6)
        self.assertEqual(result["true_choice"], "challenger")
        self.assertEqual(result["neutralized_choice"], "current")

    def test_run_lock_covers_corrected_core_and_fresh_task(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0021_pilot.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0022_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0022/pilot-task.json"), paths)
        self.assertIn(
            Path("evidence/manifests/OT-0021/ot-0021-trace-pilot-001.json"),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
