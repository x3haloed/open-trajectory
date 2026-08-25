from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0048 import build_task, complete_contact, task_family
from open_trajectory_harness.ot0050 import reference_source
from open_trajectory_harness.ot0053 import (
    actor_surface_authority,
    active_source,
    commit_branch_set,
    evaluate_case,
    initial_snapshot,
    project_snapshot,
    provisional_projection,
    restore_snapshot,
    snapshot_selections,
    validate_branch_set,
)


class OT0053Tests(unittest.TestCase):
    def test_branching_case_has_exact_causal_paths(self) -> None:
        result = evaluate_case(0, task_family()[0])
        self.assertTrue(result["pass"])
        self.assertEqual(result["pre_update_errors"], [4, 8, 4])
        self.assertEqual(result["candidate_errors"], [0, 0, 0])

    def test_commit_reject_and_restore_are_distinct(self) -> None:
        task = build_task(task_family()[0])
        regime = task["regimes"][0]
        current = initial_snapshot()
        choices = snapshot_selections(current, regime["contact"])
        receipt = complete_contact(regime["contact"], choices)
        correct = reference_source(tuple(regime["relation"]), regime["polarity"])
        sources = ["x[0]", correct]
        validations = validate_branch_set(sources, regime["contact"], receipt)
        provisional = provisional_projection(current, sources, validations)
        self.assertEqual(len(provisional["branches"]), 2)
        successor = commit_branch_set(current, sources, validations, 1)
        self.assertNotEqual(successor.sha256, current.sha256)
        self.assertEqual(active_source(successor), correct)
        self.assertEqual(
            restore_snapshot(project_snapshot(successor)).sha256, successor.sha256
        )
        rejected = commit_branch_set(current, sources, validations, 0)
        self.assertEqual(rejected.sha256, current.sha256)

    def test_actor_surface_excludes_hidden_authority(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])


if __name__ == "__main__":
    unittest.main()
