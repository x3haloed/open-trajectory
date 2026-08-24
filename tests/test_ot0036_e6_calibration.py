from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0036_e6_calibration import (
    criteria,
    evaluate_case,
    fixed_input_paths,
    integration_authority,
    rule_pairs,
    validate_run_lock,
)


class OT0036E6CalibrationTests(unittest.TestCase):
    def test_controller_family_exhausts_criteria_and_rule_pairs(self) -> None:
        family = criteria()
        pairs = rule_pairs()
        self.assertEqual(len(family), 384)
        self.assertEqual(len(set(family)), 384)
        self.assertEqual(len(pairs), 6)
        self.assertEqual(len({rule for pair in pairs for rule in pair}), 12)

    def test_excluded_development_cases_pass_every_integration_gate(self) -> None:
        family = criteria()
        pairs = rule_pairs()
        for criterion_index, pair_index in (
            (0, 0),
            (0, 5),
            (127, 2),
            (255, 3),
            (383, 5),
        ):
            with self.subTest(
                criterion_index=criterion_index, pair_index=pair_index
            ):
                result = evaluate_case(
                    criterion_index,
                    family[criterion_index],
                    pair_index,
                    pairs[pair_index],
                )
                self.assertTrue(result["pass"])
                self.assertTrue(all(result["checks"].values()))
                self.assertEqual(result["candidate_errors"], [0, 0, 0])
                self.assertEqual(result["unchanged_errors"], [4, 8, 8])
                self.assertEqual(result["best_fixed_aggregate_errors"], 8)

    def test_integration_adapter_has_no_task_or_execution_authority(self) -> None:
        authority = integration_authority(Path.cwd())
        self.assertTrue(authority["pass"])
        self.assertEqual(
            authority["parameters"],
            ["parent", "snapshot", "contact", "queries"],
        )
        self.assertEqual(
            authority["reachable_functions"],
            ["apply_to_ledger", "selected_observations"],
        )
        self.assertEqual(authority["forbidden_reachable"], [])

    def test_run_lock_will_bind_every_calibration_authority(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0036-acceptance.json"), paths)
        self.assertIn(
            Path("src/open_trajectory_harness/ot0036_e6_calibration.py"),
            paths,
        )
        self.assertIn(
            Path("src/open_trajectory_harness/ot0033_weighted_selector.py"),
            paths,
        )
        self.assertIn(
            Path("src/open_trajectory_harness/ot0035_integration.py"),
            paths,
        )
        self.assertIn(Path("src/open_trajectory_harness/ot0003_world.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0035/"
                "ot-0035-e5-ot0-ledger-integration-001.json"
            ),
            paths,
        )

    def test_frozen_run_lock_reconstructs_all_runtime_authorities(self) -> None:
        implementation = "9072074f317e7f83d9863daf5cbc05722d0da9d4"
        lock = validate_run_lock(Path.cwd(), implementation)
        self.assertEqual(lock["implementation_git_commit"], implementation)


if __name__ == "__main__":
    unittest.main()
