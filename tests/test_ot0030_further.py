from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json
from open_trajectory_harness.ot0027_casebook import parse_casebook_output
from open_trajectory_harness.ot0029_reversal import evaluate_reversal_with_source
from open_trajectory_harness.ot0030_further import (
    evaluate_further_with_source,
    further_mechanism_valid,
    source_projection,
)
from open_trajectory_harness.ot0030_pilot import configure_protocol, fixed_input_paths


REPO = Path(__file__).resolve().parents[1]
PRIOR_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"sealed7-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (0, 1, 2, 4, 8, 14)
    ],
    "expected_effect": "retain the earlier useful patterns",
    "cheapest_falsifier": "later errors rise",
}
CURRENT_OUTPUT = {
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
REVISED_OUTPUT = {
    "exemplars": [
        {
            "anchor_event_id": f"sealed9-event-{index}",
            "mask": [True, True, True, True],
            "radius": 0,
            "priority": 1,
        }
        for index in (3, 5, 6, 7, 9, 10)
    ],
    "expected_effect": "replace the remaining contradicted patterns",
    "cheapest_falsifier": "next canary errors remain high",
}


class OT0030FurtherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol(REPO)

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0030/pilot-task.json")
        self.source_task = load_json(REPO / "fixtures/ot-0029/pilot-task.json")
        self.prior_task = load_json(REPO / "fixtures/ot-0028/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0030-acceptance.json")
        self.prior, _, _ = parse_casebook_output(self.prior_task, PRIOR_OUTPUT)
        self.current, _, _ = parse_casebook_output(
            self.source_task, CURRENT_OUTPUT
        )

    def synthetic_source_raw(self) -> dict:
        mechanism = evaluate_reversal_with_source(
            self.source_task, CURRENT_OUTPUT, self.prior
        )
        return {
            "experiment_id": "OT-0029",
            "actor_outputs": [deepcopy(CURRENT_OUTPUT), deepcopy(CURRENT_OUTPUT)],
            "summary": {"mechanisms": [deepcopy(mechanism), deepcopy(mechanism)]},
        }

    def test_known_further_revision_restores_behavior(self) -> None:
        result = evaluate_further_with_source(
            self.task, REVISED_OUTPUT, self.current
        )
        self.assertEqual(result["inherited_errors"], 9)
        self.assertEqual(result["revised_errors"], 0)
        self.assertEqual(result["revision_error_advantage"], 9)
        self.assertTrue(result["selection_changed"])
        self.assertTrue(further_mechanism_valid([result, result], self.acceptance))

    def test_unchanged_behavior_fails_further_gate(self) -> None:
        unchanged = deepcopy(CURRENT_OUTPUT)
        for exemplar in unchanged["exemplars"]:
            exemplar["anchor_event_id"] = exemplar["anchor_event_id"].replace(
                "shift9", "sealed9"
            )
        result = evaluate_further_with_source(self.task, unchanged, self.current)
        self.assertEqual(result["inherited_errors"], 9)
        self.assertEqual(result["revised_errors"], 9)
        self.assertFalse(result["selection_changed"])
        self.assertFalse(further_mechanism_valid([result, result], self.acceptance))

    def test_source_projection_replays_and_excludes_next_canary(self) -> None:
        _, projection = source_projection(
            REPO,
            self.task,
            self.synthetic_source_raw(),
            prior_state=self.prior,
        )
        self.assertEqual(projection["selection_consequences"]["errors"], 9)
        self.assertNotIn("sealed10-event-", canonical_json(projection).decode())

    def test_source_projection_rejects_revision_mismatch(self) -> None:
        raw = self.synthetic_source_raw()
        raw["summary"]["mechanisms"][1]["revised_errors"] = 0
        with self.assertRaisesRegex(ValueError, "does not replay"):
            source_projection(REPO, self.task, raw, prior_state=self.prior)

    def test_run_lock_covers_full_source_chain(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0030_further.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0029_reversal.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0028_correction.py"), paths)
        self.assertIn(Path("fixtures/ot-0029/pilot-task.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0029/"
                "ot-0029-casebook-reversal-pilot-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
