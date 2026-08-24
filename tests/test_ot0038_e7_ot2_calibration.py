from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0038_e7_ot2_calibration import (
    build_task,
    criteria,
    evaluate_case,
    fixed_input_paths,
    mutated_contracts,
    oracle_contract,
    raw_packet_has_no_goal,
    rule_pairs,
    score_contract,
    temporal_path,
)


class OT0038E7OT2CalibrationTests(unittest.TestCase):
    def test_raw_packet_supplies_environment_not_concrete_goal(self) -> None:
        task = build_task(0, criteria()[0], 0, rule_pairs()[0])
        contract = oracle_contract(task)
        self.assertTrue(raw_packet_has_no_goal(task, contract))
        self.assertEqual(len(task["assets"]), 8)
        self.assertEqual(
            task["raw_packet"]["environment"]["intervention_budget"], 3
        )

    def test_contract_quality_and_authorship_are_separate(self) -> None:
        task = build_task(127, criteria()[127], 2, rule_pairs()[2])
        contract = oracle_contract(task)
        actor = score_contract(task, contract, "actor-output")
        supplied = score_contract(task, contract, "researcher-given")
        self.assertTrue(actor["quality_pass"])
        self.assertTrue(actor["ot2_admissible"])
        self.assertTrue(supplied["quality_pass"])
        self.assertFalse(supplied["ot2_admissible"])

    def test_each_counterfactual_has_one_decisive_contract_defect(self) -> None:
        task = build_task(255, criteria()[255], 3, rule_pairs()[3])
        for name, contract in mutated_contracts(task).items():
            with self.subTest(name=name):
                result = score_contract(task, contract, "actor-output")
                self.assertFalse(result["quality_pass"])
                self.assertEqual(
                    sum(not passed for passed in result["checks"].values()), 1
                )

    def test_excluded_development_cases_pass_complete_calibration(self) -> None:
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
                self.assertEqual(result["candidate_route_errors"], [0, 0, 0])
                self.assertEqual(result["unchanged_route_errors"], [3, 3, 3])

    def test_temporal_path_separates_admission_and_judgment(self) -> None:
        task = build_task(383, criteria()[383], 5, rule_pairs()[5])
        result = temporal_path(task, oracle_contract(task))
        self.assertTrue(result["pass"])
        self.assertEqual(result["candidate_hierarchy_matches"], 8)
        self.assertEqual(result["no_persistence_hierarchy_matches_after_admission"], 0)
        self.assertEqual(result["verbatim_hierarchy_matches_after_admission"], 0)
        self.assertEqual(result["plan_versions"], [1, 1, 2, 2, 3, 3, 3, 3])
        self.assertEqual(result["completion_claims"], [False] * 7 + [True])
        self.assertGreater(
            result["completion_claim_encounter"],
            result["verification_receipt_encounter"],
        )

    def test_run_lock_will_bind_every_causal_authority(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0038-acceptance.json"), paths)
        self.assertIn(
            Path("src/open_trajectory_harness/ot0038_e7_ot2_calibration.py"),
            paths,
        )
        self.assertIn(
            Path("src/open_trajectory_harness/ot0037_deterministic_candidate.py"),
            paths,
        )
        self.assertIn(
            Path(
                "evidence/manifests/OT-0037/"
                "ot-0037-e6-deterministic-ot1-candidate-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
