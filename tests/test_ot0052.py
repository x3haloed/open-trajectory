from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0048 import complete_contact
from open_trajectory_harness.ot0050 import (
    initial_snapshot,
    snapshot_selections,
    validate_proposal,
)
from open_trajectory_harness.ot0052 import (
    actor_surface_authority,
    actor_view,
    bounded_provisional,
    build_task,
    expected_task_seed,
    force_one_shot,
    validate_task,
)


class OT0052Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("9" * 40))

    def test_task_and_actor_surface_are_mechanical(self) -> None:
        validate_task(self.task)
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])

    def test_invalid_proposal_has_bounded_digest_projection(self) -> None:
        current = initial_snapshot()
        contact = self.task["regimes"][0]["contact"]
        choices = snapshot_selections(current, contact)
        receipt = complete_contact(contact, choices)
        source = "+".join("x[0]" for _ in range(80))
        validation = validate_proposal(source, contact, receipt)
        projection = bounded_provisional(current, source, validation)
        self.assertIsNone(projection["source"])
        self.assertLessEqual(
            len(__import__("json").dumps(projection, separators=(",", ":")).encode()),
            512,
        )

    def test_one_shot_uses_exact_admissible_proposal(self) -> None:
        current = initial_snapshot()
        contact = self.task["regimes"][0]["contact"]
        choices = snapshot_selections(current, contact)
        receipt = complete_contact(contact, choices)
        source = "x[0]+x[1]"
        validation = validate_proposal(source, contact, receipt)
        child = force_one_shot(current, source, validation)
        self.assertEqual(child.state["source"], source)
        view = actor_view("proposal", contact, choices, receipt, None, None)
        self.assertNotIn("preferred_event_id", str(view))


if __name__ == "__main__":
    unittest.main()
