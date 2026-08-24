from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0027_casebook import (
    casebook_mechanism_valid,
    evaluate_casebook_output,
    parse_casebook_output,
    rendered_casebook_prompt,
)
from open_trajectory_harness.ot0027_pilot import configure_protocol, fixed_input_paths


REPO = Path(__file__).resolve().parents[1]
ANCHORS = (0, 1, 2, 3, 4, 8)
VALID_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"prior7-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in ANCHORS
    ],
    "expected_effect": "retain a discriminating parity casebook",
    "cheapest_falsifier": "the corresponding future examples do not reduce error",
}


class OT0027CasebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0027/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0027-acceptance.json")

    def test_known_casebook_realizes_causal_selection(self) -> None:
        result = evaluate_casebook_output(self.task, VALID_OUTPUT)
        self.assertEqual(result["exemplar_count"], 6)
        self.assertEqual(result["selected_event_count"], 6)
        self.assertEqual(result["casebook_error_advantage"], 8)
        self.assertTrue(result["selection_changed"])
        self.assertTrue(result["prediction_changed"])
        self.assertTrue(
            casebook_mechanism_valid([result, result], self.acceptance)
        )

    def test_anchors_must_be_known_and_distinct(self) -> None:
        unknown = deepcopy(VALID_OUTPUT)
        unknown["exemplars"][0]["anchor_event_id"] = "prior7-event-unknown"
        with self.assertRaisesRegex(ValueError, "not in the prior"):
            parse_casebook_output(self.task, unknown)
        duplicate = deepcopy(VALID_OUTPUT)
        duplicate["exemplars"][1]["anchor_event_id"] = duplicate["exemplars"][0][
            "anchor_event_id"
        ]
        with self.assertRaisesRegex(ValueError, "not distinct"):
            parse_casebook_output(self.task, duplicate)

    def test_mask_radius_and_priority_are_exactly_bounded(self) -> None:
        malformed = deepcopy(VALID_OUTPUT)
        malformed["exemplars"][0]["mask"] = [True, False]
        with self.assertRaisesRegex(ValueError, "mask is invalid"):
            parse_casebook_output(self.task, malformed)
        malformed = deepcopy(VALID_OUTPUT)
        malformed["exemplars"][0]["radius"] = 5
        with self.assertRaisesRegex(ValueError, "radius"):
            parse_casebook_output(self.task, malformed)
        malformed = deepcopy(VALID_OUTPUT)
        malformed["exemplars"][0]["priority"] = 17
        with self.assertRaisesRegex(ValueError, "priority"):
            parse_casebook_output(self.task, malformed)

    def test_universal_casebook_does_not_bake_in_success(self) -> None:
        universal = {
            "exemplars": [
                {
                    "anchor_event_id": "prior7-event-0",
                    "mask": [False, False, False, False],
                    "radius": 4,
                    "priority": 1,
                }
            ],
            "expected_effect": "retain all events equally",
            "cheapest_falsifier": "stable ties do not improve prediction",
        }
        result = evaluate_casebook_output(self.task, universal)
        self.assertLess(result["casebook_error_advantage"], 4)
        self.assertFalse(
            casebook_mechanism_valid([result, result], self.acceptance)
        )

    def test_prompt_excludes_fresh_sealed_split(self) -> None:
        prompt, ledger = rendered_casebook_prompt(REPO, self.task)
        self.assertNotIn("sealed7-event-", prompt)
        self.assertIn("prior7-event-", prompt)
        self.assertEqual(len(ledger["entries"]), 1)

    def test_run_lock_covers_casebook_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0027_casebook.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0027_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0027/casebook-output.schema.json"), paths)
        self.assertIn(Path("fixtures/ot-0027/pilot-task.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0026/"
                "ot-0026-structured-score-pilot-001-controller-failure.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
