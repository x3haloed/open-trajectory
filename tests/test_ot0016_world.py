from __future__ import annotations

import copy
import unittest

from open_trajectory_harness.ot0016_credit import CounterfactualSelectorLedger
from open_trajectory_harness.ot0016_world import generate_task_manifest, validate_task_manifest


DEEP_EXPRESSION = (
    '[e["event_id"] for e in events[:limit] if True or '
    'any(a for a in events for b in events for c in events for d in events)]'
)


class OT0016WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = generate_task_manifest()

    def test_generated_manifest_is_admissible_and_receipted(self) -> None:
        validate_task_manifest(self.manifest)
        receipt = self.manifest["sampling_receipt"]
        self.assertTrue(all(receipt["gates"].values()))
        self.assertEqual(len(receipt["rejected_manifest_sha256"]), receipt["attempts"] - 1)

    def test_tampered_sampling_receipt_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["sampling_receipt"]["observed"]["dynamic_advantage"] += 1
        with self.assertRaises(ValueError):
            validate_task_manifest(tampered)

    def test_frozen_depth_eight_is_honored_during_comparison(self) -> None:
        archive = self.manifest["stages"][0]["events"]
        stage = self.manifest["stages"][0]
        ledger = CounterfactualSelectorLedger(iteration_depth_limit=8)
        challenger = ledger.propose(
            {
                "expression": DEEP_EXPRESSION,
                "expected_effect": "Exercise the frozen carrier depth.",
                "cheapest_falsifier": "Comparison rejects an expression accepted at proposal.",
            }
        )
        receipt = ledger.compare(
            challenger,
            archive=archive,
            queries=stage["contact"]["queries"],
            outcomes=stage["contact"]["outcomes"],
            limit=6,
            stage=0,
            split_identity="depth-eight-test",
        )
        self.assertTrue(receipt["challenger"]["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
