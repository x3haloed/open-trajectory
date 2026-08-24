from __future__ import annotations

import copy
import unittest

from open_trajectory_harness.ot0020_world import (
    EVALUATION_EPOCH,
    EXPERIMENT_ID,
    generate_task_manifest,
    validate_task_manifest,
)


class OT0020WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = generate_task_manifest("0123456789abcdef" * 2)

    def test_direct_e4_manifest_replays_exactly(self) -> None:
        validate_task_manifest(self.manifest)
        self.assertEqual(self.manifest["experiment_id"], EXPERIMENT_ID)
        receipt = self.manifest["e4_construction_receipt"]
        self.assertEqual(receipt["evaluation_epoch"], EVALUATION_EPOCH)
        self.assertTrue(receipt["planned_witness"]["passes"])
        self.assertTrue(receipt["exact_witness"]["passes"])
        self.assertTrue(receipt["split_queries_separated"])

    def test_task_mutation_breaks_seed_reconstruction(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["stages"][0]["events"][0]["event_id"] += "-tampered"
        with self.assertRaisesRegex(ValueError, "differs from its direct construction"):
            validate_task_manifest(changed)

    def test_receipt_mutation_breaks_exact_replay(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["e4_construction_receipt"]["semantic_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not replay exactly"):
            validate_task_manifest(changed)


if __name__ == "__main__":
    unittest.main()
