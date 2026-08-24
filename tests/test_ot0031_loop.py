from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json
from open_trajectory_harness.ot0027_casebook import parse_casebook_output
from open_trajectory_harness.ot0030_further import evaluate_further_with_source
from open_trajectory_harness.ot0031_loop import (
    configure_protocol,
    evaluate_loop_branch,
    fixed_input_paths,
    loop_mechanism_valid,
    score_casebook,
    source_projection,
)


REPO = Path(__file__).resolve().parents[1]
PRIOR_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"shift9-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (0, 1, 2, 4, 8, 15)
    ],
    "expected_effect": "span feature dimensions",
    "cheapest_falsifier": "query errors remain high",
}
CURRENT_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"sealed9-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (1, 3, 5, 2, 6, 7)
    ],
    "expected_effect": "favor a different parity",
    "cheapest_falsifier": "canary errors remain high",
}
GOOD_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"sealed10-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (3, 5, 6, 7, 9, 10)
    ],
    "expected_effect": "retain outcome-consistent patterns",
    "cheapest_falsifier": "future errors remain high",
}
BAD_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"sealed10-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (1, 3, 5, 2, 6, 7)
    ],
    "expected_effect": "preserve the current selection",
    "cheapest_falsifier": "completed errors remain high",
}


class OT0031LoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0031/pilot-task.json")
        self.source_task = load_json(REPO / "fixtures/ot-0030/pilot-task.json")
        self.prior_task = load_json(REPO / "fixtures/ot-0029/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0031-acceptance.json")
        self.prior, _, _ = parse_casebook_output(self.prior_task, PRIOR_OUTPUT)
        self.current, _, _ = parse_casebook_output(
            self.source_task, CURRENT_OUTPUT
        )

    def synthetic_source_raw(self) -> dict:
        mechanism = evaluate_further_with_source(
            self.source_task, CURRENT_OUTPUT, self.prior
        )
        return {
            "experiment_id": "OT-0030",
            "actor_outputs": [deepcopy(CURRENT_OUTPUT), deepcopy(CURRENT_OUTPUT)],
            "summary": {"mechanisms": [deepcopy(mechanism), deepcopy(mechanism)]},
        }

    def test_bad_probe_then_good_revision_passes_loop(self) -> None:
        receipt, mechanism = evaluate_loop_branch(
            self.task, self.current, BAD_OUTPUT, GOOD_OUTPUT
        )
        self.assertEqual(receipt["errors"], 7)
        self.assertEqual(mechanism["final_completed_errors"], 0)
        self.assertEqual(mechanism["final_future_errors"], 0)
        self.assertTrue(mechanism["feedback_improved"])
        self.assertTrue(
            loop_mechanism_valid([mechanism, mechanism], self.acceptance)
        )

    def test_already_good_probe_may_be_preserved(self) -> None:
        _, mechanism = evaluate_loop_branch(
            self.task, self.current, GOOD_OUTPUT, GOOD_OUTPUT
        )
        self.assertTrue(mechanism["candidate_already_valid"])
        self.assertFalse(mechanism["feedback_improved"])
        self.assertTrue(mechanism["feedback_resolved"])

    def test_bad_probe_and_bad_revision_fail(self) -> None:
        _, mechanism = evaluate_loop_branch(
            self.task, self.current, BAD_OUTPUT, BAD_OUTPUT
        )
        self.assertFalse(mechanism["feedback_resolved"])
        self.assertFalse(
            loop_mechanism_valid([mechanism, mechanism], self.acceptance)
        )

    def test_candidate_receipt_is_deterministic(self) -> None:
        candidate, _, _ = parse_casebook_output(self.task, GOOD_OUTPUT)
        first = score_casebook(
            candidate, self.task["prior_completed_encounter"], 6
        )
        second = score_casebook(
            candidate, self.task["prior_completed_encounter"], 6
        )
        self.assertEqual(first, second)

    def test_source_projection_replays_and_excludes_future(self) -> None:
        _, projection = source_projection(
            REPO,
            self.task,
            self.synthetic_source_raw(),
            prior_state=self.prior,
        )
        self.assertEqual(projection["selection_consequences"]["errors"], 7)
        self.assertNotIn("sealed11-event-", canonical_json(projection).decode())

    def test_run_lock_covers_learning_loop_and_source_chain(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0031_loop.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0030_further.py"), paths)
        self.assertIn(Path("fixtures/ot-0030/pilot-task.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0030/"
                "ot-0030-further-correction-pilot-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
