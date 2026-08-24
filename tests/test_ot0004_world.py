from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0004_world import (
    PolicyLedger,
    archive_through_stage,
    fixed_selection,
    generate_task_manifest,
    protected_consequence_receipt,
    score_predictions,
    selected_events,
    validate_task_manifest,
)


REPO = Path(__file__).resolve().parents[1]


class OT0004WorldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = generate_task_manifest()
        validate_task_manifest(self.manifest)

    def test_generated_world_has_six_sealed_stages_and_unique_events(self) -> None:
        stages = self.manifest["stages"]
        self.assertEqual(len(stages), 6)
        events = [event for stage in stages for event in stage["events"]]
        self.assertEqual(len(events), 144)
        self.assertEqual(len({event["event_id"] for event in events}), 144)
        self.assertEqual(sum(stage["kind"] == "noisy-contact" for stage in stages), 1)

    def test_fixed_selectors_are_bounded_and_controller_deterministic(self) -> None:
        archive = archive_through_stage(self.manifest, 3)
        queries = self.manifest["stages"][3]["heldout"]["queries"]
        recent = fixed_selection("fixed-most-recent", archive, queries, 6)
        first = fixed_selection("fixed-first-seen-verbatim", archive, queries, 6)
        nearest = fixed_selection("fixed-naive-nearest", archive, queries, 6)
        self.assertEqual(len(recent), 6)
        self.assertEqual(len(first), 6)
        self.assertEqual(len(nearest), 6)
        self.assertNotEqual(recent, first)
        self.assertEqual(
            nearest,
            fixed_selection("fixed-naive-nearest", archive, queries, 6),
        )
        self.assertEqual(fixed_selection("no-persistence", archive, queries, 6), [])

    def test_selection_rejects_unknown_or_duplicate_identities(self) -> None:
        archive = archive_through_stage(self.manifest, 0)
        event_id = archive[0]["event_id"]
        with self.assertRaises(ValueError):
            selected_events(archive, [event_id, event_id])
        with self.assertRaises(ValueError):
            selected_events(archive, ["event-unknown"])

    def test_controller_commits_immutable_policy_chain(self) -> None:
        ledger = PolicyLedger("Choose a bounded useful subset.", byte_limit=512)
        seed = ledger.current
        proposal = {
            "policy": "Prefer contacts whose observed utility is supported by the protected receipt.",
            "expected_effect": "Fewer future errors.",
            "cheapest_falsifier": "The frozen predecessor makes no more errors.",
        }
        changed = ledger.commit(proposal)
        self.assertEqual(changed.revision, 1)
        self.assertEqual(changed.parent_sha256, seed.sha256)
        self.assertNotEqual(changed.sha256, seed.sha256)
        self.assertEqual(ledger.snapshots[0], seed)
        with self.assertRaises(ValueError):
            ledger.commit({"policy": "incomplete"})

    def test_protected_receipt_includes_selected_and_rejected_evidence(self) -> None:
        archive = archive_through_stage(self.manifest, 0)
        split = self.manifest["stages"][0]["contact"]
        selected = fixed_selection(
            "fixed-most-recent", archive, split["queries"], 6
        )
        receipt = protected_consequence_receipt(
            stage_index=0,
            policy_sha256="a" * 64,
            archive=archive,
            selected_ids=selected,
            queries=split["queries"],
            predictions=split["outcomes"],
            outcomes=split["outcomes"],
        )
        self.assertEqual(receipt["errors"], 0)
        self.assertEqual(len(receipt["selected_events"]), 6)
        self.assertEqual(len(receipt["rejected_event_sample"]), 6)
        self.assertFalse(
            set(receipt["selected_event_ids"])
            & {event["event_id"] for event in receipt["rejected_event_sample"]}
        )

    def test_malformed_prediction_is_scored_as_all_errors(self) -> None:
        errors, reason = score_predictions([0], [0] * 8)
        self.assertEqual(errors, 8)
        self.assertIsNotNone(reason)


if __name__ == "__main__":
    unittest.main()
