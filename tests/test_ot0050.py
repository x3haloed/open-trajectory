from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0048 import (
    complete_contact,
    score,
    task_family,
    build_task,
)
from open_trajectory_harness.ot0050 import (
    actor_surface_authority,
    commit_validated,
    evaluate_case,
    initial_snapshot,
    neutralize_validation,
    overfit_source,
    parse_staged_source,
    project_snapshot,
    reference_source,
    restore_snapshot,
    snapshot_selections,
    validate_proposal,
)


class OT0050Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = task_family()[0]
        self.task = build_task(self.case)

    def test_semantic_bound_accepts_compact_linear_but_rejects_bulk(self) -> None:
        parse_staged_source("x[0]+2*x[1]+4*x[2]+8*x[3]")
        with self.assertRaises(ValueError):
            parse_staged_source("+".join("x[0]" for _ in range(40)))

    def test_validation_separates_old_correct_and_contact_overfit(self) -> None:
        regime = self.task["regimes"][0]
        parent = initial_snapshot()
        receipt = complete_contact(
            regime["contact"], snapshot_selections(parent, regime["contact"])
        )
        old = validate_proposal("x[0]", regime["contact"], receipt)
        correct_source = reference_source(tuple(regime["relation"]), regime["polarity"])
        correct = validate_proposal(correct_source, regime["contact"], receipt)
        overfit = overfit_source(
            tuple(regime["relation"]), regime["polarity"], regime["contact_scale"]
        )
        overfit_receipt = validate_proposal(overfit, regime["contact"], receipt)
        self.assertEqual(old["error_count"], 4)
        self.assertEqual(correct["error_count"], 0)
        self.assertEqual(overfit_receipt["error_count"], 0)
        overfit_state = commit_validated(parent, overfit, overfit_receipt)
        self.assertEqual(
            score(
                regime["canary"], snapshot_selections(overfit_state, regime["canary"])
            ),
            8,
        )

    def test_no_credit_parent_and_restoration_are_exact(self) -> None:
        regime = self.task["regimes"][0]
        parent = initial_snapshot()
        receipt = complete_contact(
            regime["contact"], snapshot_selections(parent, regime["contact"])
        )
        source = reference_source(tuple(regime["relation"]), regime["polarity"])
        validation = validate_proposal(source, regime["contact"], receipt)
        self.assertEqual(
            commit_validated(parent, source, neutralize_validation(validation)), parent
        )
        child = commit_validated(parent, source, validation)
        self.assertEqual(restore_snapshot(project_snapshot(child)), child)

    def test_all_case_mechanics_and_actor_surface(self) -> None:
        self.assertTrue(evaluate_case(0, self.case)["pass"])
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])


if __name__ == "__main__":
    unittest.main()
