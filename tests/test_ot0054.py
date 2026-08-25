from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from open_trajectory_harness.ot0048 import complete_contact
from open_trajectory_harness.ot0053 import (
    initial_snapshot,
    project_snapshot,
    snapshot_selections,
)
from open_trajectory_harness.ot0050 import overfit_source, reference_source
from open_trajectory_harness.ot0054 import execute_worker
from open_trajectory_harness import ot0054
from open_trajectory_harness.ot0054 import (
    actor_surface_authority,
    actor_view,
    build_task,
    expected_task_seed,
    validate_task,
)


class OT0054Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("9" * 40))

    def test_task_and_surface_are_mechanical(self) -> None:
        validate_task(self.task)
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])

    def test_actor_view_has_only_public_contact_and_bounded_ledgers(self) -> None:
        regime = self.task["regimes"][0]
        current = initial_snapshot()
        choices = snapshot_selections(current, regime["contact"])
        receipt = complete_contact(regime["contact"], choices)
        view = actor_view(
            "proposal",
            regime["contact"],
            choices,
            receipt,
            project_snapshot(current),
            None,
        )
        self.assertNotIn("preferred_event_id", str(view))
        self.assertEqual(view["stage"], "proposal")

    def test_synthetic_branch_selection_realizes_endpoint(self) -> None:
        prior = "x[0]"

        def fake_turn(**kwargs):
            nonlocal prior
            regime = self.task["regimes"][kwargs["regime_index"] - 1]
            correct = reference_source(tuple(regime["relation"]), regime["polarity"])
            branches = [
                prior,
                overfit_source(
                    tuple(regime["relation"]),
                    regime["polarity"],
                    regime["contact_scale"],
                ),
                correct,
            ]
            active = 0 if kwargs["stage"] == "proposal" else 2
            if kwargs["stage"] == "adjudication":
                prior = correct
            return (
                {
                    "stage": kwargs["stage"],
                    "actor_output": {"branches": branches, "active_index": active},
                },
                {"branches": branches, "active_index": active},
                [],
            )

        with patch.object(ot0054, "run_actor_turn", side_effect=fake_turn):
            _, mechanism, _ = execute_worker(
                repo=Path.cwd(),
                task=self.task,
                worker="worker-1",
                client=object(),
                proxy=object(),
                model="synthetic",
                workspace_root=Path("unused"),
                prompt_template="unused",
                schema={},
            )
        self.assertEqual(mechanism["candidate_errors"], [0, 0, 0])
        self.assertEqual(mechanism["one_shot_errors"], [4, 8, 4])
        self.assertTrue(all(item["proposal_origin"] for item in mechanism["regimes"]))


if __name__ == "__main__":
    unittest.main()
