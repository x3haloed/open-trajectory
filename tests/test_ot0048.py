from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0048 import (
    CANONICAL_POINTS,
    RELATIONS,
    actor_view,
    actor_surface_authority,
    build_split,
    complete_contact,
    evaluate_case,
    initial_reference_snapshot,
    neutralize_receipt,
    project_reference,
    public_contact,
    reference_selections,
    restore_reference,
    structural_certificate,
    task_family,
    update_reference,
    weighted_selections,
)


REPO = Path(__file__).resolve().parents[1]


class OT0048Tests(unittest.TestCase):
    def test_every_relation_has_exact_structural_incapacity_certificate(self) -> None:
        for relation in RELATIONS:
            for polarity in (-1, 1):
                certificate = structural_certificate(relation, polarity, 2)
                self.assertTrue(certificate["pass"])
                self.assertEqual(certificate["constant_sum"], 0)
                self.assertEqual(certificate["first_moments"], (0, 0, 0, 0))
                split = build_split("tie-check", relation, polarity, 2)
                errors = sum(
                    selected != pair["preferred_event_id"]
                    for selected, pair in zip(
                        weighted_selections((0, 0, 0, 0), split),
                        split["pairs"],
                        strict=True,
                    )
                )
                self.assertEqual(errors, 4)

    def test_reference_learns_only_from_completed_consequences(self) -> None:
        split = build_split("test-contact", RELATIONS[0], 1, 1)
        source = initial_reference_snapshot()
        selected = reference_selections(source, split)
        receipt = complete_contact(split, selected)
        self.assertEqual(
            update_reference(source, split, neutralize_receipt(receipt)).sha256,
            source.sha256,
        )
        learned = update_reference(source, split, receipt)
        canary = build_split("test-canary", RELATIONS[0], 1, 2)
        self.assertEqual(
            sum(
                selected != pair["preferred_event_id"]
                for selected, pair in zip(
                    reference_selections(learned, canary), canary["pairs"], strict=True
                )
            ),
            0,
        )
        self.assertEqual(restore_reference(project_reference(learned)).sha256, learned.sha256)

    def test_actor_surface_omits_controller_outcomes(self) -> None:
        split = build_split("test-surface", RELATIONS[0], 1, 1)
        contact = public_contact(split)
        self.assertNotIn("preferred_event_id", repr(contact))
        self.assertTrue(actor_surface_authority(REPO)["pass"])
        with self.assertRaises(ValueError):
            actor_view(contact, project_reference(initial_reference_snapshot()), [], None)

    def test_all_frozen_cases_pass(self) -> None:
        family = task_family()
        self.assertEqual(len(family), 48)
        for index, case in enumerate(family):
            result = evaluate_case(index, case)
            self.assertTrue(result["pass"])
            self.assertEqual(result["reference_errors"], [0, 0, 0])
            self.assertEqual(result["unchanged_errors"], [4, 8, 4])
            self.assertEqual(result["frozen_first_errors"], [0, 8, 4])
            self.assertEqual(result["projection_bytes_max"] <= 512, True)
            self.assertEqual(len(CANONICAL_POINTS), 8)


if __name__ == "__main__":
    unittest.main()
