from __future__ import annotations

import unittest
from itertools import permutations, product
from pathlib import Path

from open_trajectory_harness.ot0033_weighted_selector import (
    build_split,
    build_task,
    complete_encounter,
    expected_task_seed,
    fixed_input_paths,
    initial_snapshot,
    learn,
    neutralize_outcome_credit,
    project,
    restore,
    run_protocol,
    score_snapshot,
    validate_run_lock,
)


DEVELOPMENT_SEED = "0" * 64


class OT0033WeightedSelectorTests(unittest.TestCase):
    def test_development_fixture_realizes_complete_learning_path(self) -> None:
        result = run_protocol(DEVELOPMENT_SEED)
        self.assertTrue(result["pilot_pass"])
        self.assertEqual(
            [regime["contact_score"]["errors"] for regime in result["regimes"]],
            [40, 80, 80],
        )
        self.assertEqual(
            [regime["canary_score"]["errors"] for regime in result["regimes"]],
            [0, 0, 0],
        )
        self.assertEqual(result["candidate_aggregate_errors"], 0)
        self.assertEqual(result["best_fixed_aggregate_errors"], 80)

    def test_outcome_credit_is_required_for_weight_change(self) -> None:
        source = initial_snapshot()
        task = build_task(DEVELOPMENT_SEED)
        completed = complete_encounter(source, task["regimes"][0]["contact"])
        learned, true_receipt = learn(source, completed)
        neutralized, neutralized_receipt = learn(
            source, neutralize_outcome_credit(completed)
        )
        self.assertNotEqual(learned.sha256, source.sha256)
        self.assertTrue(true_receipt["changed"])
        self.assertEqual(neutralized, source)
        self.assertFalse(neutralized_receipt["changed"])

    def test_development_seed_family_is_not_task_selected(self) -> None:
        for index in range(32):
            with self.subTest(index=index):
                result = run_protocol(f"{index:064x}")
                self.assertTrue(result["pilot_pass"])

    def test_every_controller_criterion_is_learnable_without_seed_selection(
        self,
    ) -> None:
        for magnitudes in permutations((1, 5, 25, 125)):
            for signs in product((-1, 1), repeat=4):
                hidden = tuple(
                    magnitude * sign
                    for magnitude, sign in zip(magnitudes, signs, strict=True)
                )
                current = initial_snapshot()
                for index, criterion in enumerate(
                    (hidden, tuple(-value for value in hidden), hidden),
                    start=1,
                ):
                    contact = build_split(f"exhaustive-{index}-contact", criterion)
                    canary = build_split(f"exhaustive-{index}-canary", criterion)
                    completed = complete_encounter(current, contact)
                    learned, _ = learn(current, completed)
                    self.assertEqual(score_snapshot(learned, canary)["errors"], 0)
                    current = learned

    def test_candidate_projection_omits_controller_authority(self) -> None:
        source = initial_snapshot()
        split = build_split("development", (1, 5, 25, 125))
        completed = complete_encounter(source, split)
        self.assertEqual(
            set(completed),
            {
                "source_snapshot_sha256",
                "outcome_credit",
                "archive",
                "outcomes",
                "decisions",
                "receipt_sha256",
            },
        )
        serialized = str(completed)
        self.assertNotIn("task_seed", serialized)
        self.assertNotIn("hidden", serialized)
        self.assertNotIn("canary", serialized)
        self.assertNotIn("control", serialized)
        neutralized = neutralize_outcome_credit(completed)
        self.assertNotIn("error", str(neutralized))
        self.assertEqual(neutralized["outcomes"], [])

    def test_restoration_accepts_only_exact_snapshot_projection(self) -> None:
        source = initial_snapshot()
        self.assertEqual(restore(project(source)), source)
        tampered = project(source)
        tampered["weights"][0] = 1
        with self.assertRaisesRegex(ValueError, "identity differs"):
            restore(tampered)

    def test_task_identity_is_post_implementation_and_seed_sensitive(self) -> None:
        implementation = "1" * 40
        seed = expected_task_seed(implementation)
        self.assertEqual(len(seed), 64)
        self.assertNotEqual(seed, expected_task_seed("2" * 40))
        self.assertNotEqual(
            build_task(seed)["task_sha256"],
            build_task(expected_task_seed("2" * 40))["task_sha256"],
        )

    def test_run_lock_covers_every_runtime_authority(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0033-acceptance.json"), paths)
        self.assertIn(
            Path("src/open_trajectory_harness/ot0033_weighted_selector.py"),
            paths,
        )
        self.assertIn(Path("experiments/ot_0033_harness.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0032/"
                "ot-0032-optimizer-walking-skeleton-001.json"
            ),
            paths,
        )

    def test_frozen_run_lock_reconstructs_the_post_implementation_task(
        self,
    ) -> None:
        implementation = "d40d2c6ce5616e4a5b3a643e2a6c93c9c197c5fd"
        lock = validate_run_lock(Path.cwd(), implementation)
        self.assertEqual(lock["implementation_git_commit"], implementation)
        self.assertEqual(lock["task_seed"], expected_task_seed(implementation))
        self.assertEqual(
            lock["task_sha256"], build_task(lock["task_seed"])["task_sha256"]
        )


if __name__ == "__main__":
    unittest.main()
