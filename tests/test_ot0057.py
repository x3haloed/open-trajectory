from __future__ import annotations

import unittest
import json
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness.ot0057 import (
    actor_surface_authority,
    build_task,
    equal_state_projections,
    expected_task_seed,
    structural_calibration,
    validate_task,
)
from open_trajectory_harness.ot0048 import complete_contact
from open_trajectory_harness.ot0056 import (
    exact_rows,
    initial_snapshot,
    snapshot_selections,
)


class OT0057Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("7" * 40))

    def test_private_task_is_mechanical_and_structurally_valid(self) -> None:
        validate_task(self.task)
        result = structural_calibration(self.task)
        self.assertTrue(result["pass"])
        self.assertEqual(result["reference_errors"], [0, 0, 0])
        self.assertEqual(result["no_state_errors"], [4, 4, 4])
        self.assertEqual(result["maximum_allowed_rows"], 1)
        self.assertGreaterEqual(result["minimum_surviving_hypotheses"], 15)

    def test_equal_projections_fit_one_exact_row(self) -> None:
        regime = self.task["regimes"][0]
        contact = regime["contact"]
        choices = snapshot_selections(initial_snapshot(), contact)
        receipt = complete_contact(contact, choices)
        rows = exact_rows(contact, choices, receipt)
        projections, row_index = equal_state_projections(
            task_seed=self.task["task_seed"],
            worker="worker-1",
            regime_index=1,
            target_flag=regime["target_flag"],
            polarity=regime["polarity"],
            rows=rows,
            byte_limit=1024,
        )
        self.assertIn(row_index, range(15))
        self.assertEqual(
            len({len(canonical_json(value)) for value in projections.values()}), 1
        )
        self.assertLessEqual(len(canonical_json(projections["reference"])), 1024)
        self.assertEqual(len(json.loads(projections["verbatim"]["content"])["rows"]), 1)

    def test_actor_surface_excludes_controller_answer_fields(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])


if __name__ == "__main__":
    unittest.main()
