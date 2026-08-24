from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json
from open_trajectory_harness.ot0027_casebook import (
    evaluate_casebook_output,
    parse_casebook_output,
)
from open_trajectory_harness.ot0028_correction import (
    correction_mechanism_valid,
    evaluate_correction_with_source,
    source_projection,
)
from open_trajectory_harness.ot0028_pilot import configure_protocol, fixed_input_paths


REPO = Path(__file__).resolve().parents[1]
CURRENT_OUTPUT = {
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
REVISED_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"sealed7-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (0, 1, 2, 3, 4, 8)
    ],
    "expected_effect": "retain a discriminating parity casebook",
    "cheapest_falsifier": "future query errors do not fall",
}


def synthetic_source_raw(source_task: dict) -> dict:
    mechanism = evaluate_casebook_output(source_task, CURRENT_OUTPUT)
    return {
        "experiment_id": "OT-0027",
        "actor_outputs": [deepcopy(CURRENT_OUTPUT), deepcopy(CURRENT_OUTPUT)],
        "summary": {"mechanisms": [deepcopy(mechanism), deepcopy(mechanism)]},
    }


class OT0028CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol(REPO)

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0028/pilot-task.json")
        self.source_task = load_json(REPO / "fixtures/ot-0027/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0028-acceptance.json")
        self.current, _, _ = parse_casebook_output(
            self.source_task, CURRENT_OUTPUT
        )

    def test_known_revision_corrects_inherited_casebook(self) -> None:
        result = evaluate_correction_with_source(
            self.task, REVISED_OUTPUT, self.current
        )
        self.assertEqual(result["current_errors"], 8)
        self.assertEqual(result["revised_errors"], 0)
        self.assertEqual(result["revision_error_advantage"], 8)
        self.assertTrue(result["selection_changed"])
        self.assertTrue(result["prediction_changed"])
        self.assertTrue(
            correction_mechanism_valid([result, result], self.acceptance)
        )

    def test_unchanged_behavior_fails_correction_gate(self) -> None:
        universal_revision = deepcopy(CURRENT_OUTPUT)
        universal_revision["exemplars"][0][
            "anchor_event_id"
        ] = "sealed7-event-0"
        result = evaluate_correction_with_source(
            self.task, universal_revision, self.current
        )
        self.assertEqual(result["revision_error_advantage"], 0)
        self.assertFalse(result["selection_changed"])
        self.assertFalse(
            correction_mechanism_valid([result, result], self.acceptance)
        )

    def test_source_projection_replays_and_excludes_future(self) -> None:
        _, projection = source_projection(
            REPO, self.task, synthetic_source_raw(self.source_task)
        )
        self.assertEqual(projection["source_experiment_id"], "OT-0027")
        self.assertEqual(projection["selection_consequences"]["errors"], 8)
        self.assertNotIn("sealed8-event-", canonical_json(projection).decode())

    def test_source_projection_rejects_mechanism_mismatch(self) -> None:
        raw = synthetic_source_raw(self.source_task)
        raw["summary"]["mechanisms"][0]["casebook_errors"] = 0
        with self.assertRaisesRegex(ValueError, "does not replay"):
            source_projection(REPO, self.task, raw)

    def test_run_lock_covers_correction_and_source_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0028_correction.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0028_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0028/pilot-task.json"), paths)
        self.assertIn(Path("fixtures/ot-0027/pilot-task.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0027/"
                "ot-0027-casebook-pilot-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
