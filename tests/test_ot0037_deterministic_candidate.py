from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0003_world import DiscrepancyGatedVersionLedger
from open_trajectory_harness.ot0036_e6_calibration import controller_predictions
from open_trajectory_harness.ot0037_deterministic_candidate import (
    build_task,
    expected_task_seed,
    fixed_input_paths,
    run_lineage,
    run_protocol,
    validate_run_lock,
)


DEVELOPMENT_SEED = "0" * 64


class OT0037DeterministicCandidateTests(unittest.TestCase):
    def test_development_lineage_realizes_complete_ot1_path(self) -> None:
        result = run_lineage(DEVELOPMENT_SEED)
        self.assertTrue(result["pass"])
        self.assertEqual(result["contact_errors"], [40, 80, 80])
        self.assertEqual(result["candidate_errors"], [0, 0, 0])
        self.assertEqual(result["unchanged_errors"], [4, 8, 8])
        self.assertEqual(result["best_fixed_aggregate_errors"], 8)
        self.assertTrue(all(result["gates"].values()))

    def test_two_fresh_reconstructions_are_receipt_identical(self) -> None:
        result = run_protocol(Path.cwd(), DEVELOPMENT_SEED)
        self.assertTrue(result["pilot_pass"])
        self.assertEqual(len(set(result["reconstruction_receipts"])), 1)
        self.assertTrue(result["gates"]["clean_reconstruction"])

    def test_excluded_development_seed_family_preserves_all_gates(self) -> None:
        for index in range(32):
            with self.subTest(index=index):
                result = run_lineage(f"{index:064x}")
                self.assertTrue(result["pass"])
                self.assertEqual(result["candidate_errors"], [0, 0, 0])
                self.assertEqual(result["unchanged_errors"], [4, 8, 8])
                self.assertEqual(result["best_fixed_aggregate_errors"], 8)

    def test_task_is_post_implementation_and_seed_sensitive(self) -> None:
        first = expected_task_seed("1" * 40)
        second = expected_task_seed("2" * 40)
        self.assertNotEqual(first, second)
        self.assertNotEqual(
            build_task(first)["task_sha256"], build_task(second)["task_sha256"]
        )

    def test_nonsingleton_controller_application_is_outcome_independent(self) -> None:
        ledger = DiscrepancyGatedVersionLedger()
        queries = ((1, 1, 0, 0), (0, 0, 1, 1))
        self.assertEqual(controller_predictions(ledger, queries), (0, 0))

    def test_run_lock_will_bind_candidate_and_evaluator_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0037-acceptance.json"), paths)
        self.assertIn(
            Path("src/open_trajectory_harness/ot0037_deterministic_candidate.py"),
            paths,
        )
        self.assertIn(
            Path("src/open_trajectory_harness/ot0033_weighted_selector.py"),
            paths,
        )
        self.assertIn(
            Path("src/open_trajectory_harness/ot0036_e6_calibration.py"),
            paths,
        )
        self.assertIn(
            Path(
                "evidence/manifests/OT-0036/"
                "ot-0036-e6-deterministic-integration-calibration-001.json"
            ),
            paths,
        )

    def test_frozen_run_lock_reconstructs_task_and_runtime_authorities(self) -> None:
        implementation = "5df5cab1877130fa6c2d0afb1a553cab7c67712d"
        lock = validate_run_lock(Path.cwd(), implementation)
        self.assertEqual(lock["implementation_git_commit"], implementation)
        self.assertEqual(lock["task_seed"], expected_task_seed(implementation))


if __name__ == "__main__":
    unittest.main()
