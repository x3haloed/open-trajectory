from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from open_trajectory_harness.ot0038_e7_ot2_calibration import (
    oracle_contract,
    raw_packet_has_no_goal,
)
from open_trajectory_harness.ot0039 import (
    fixed_input_paths,
    substrate_authority,
    validate_counterbalance,
)
from open_trajectory_harness.ot0039_world import (
    DurableGoalContract,
    GoalObservation,
    GoalWorld,
    admission_score,
    build_task,
    expected_task_seed,
    hierarchy_correct,
    public_evaluator_task,
    selector_route_lineage,
    true_actions,
    unchanged_actions,
    validate_task,
)


IMPLEMENTATION_FIXTURE = "1" * 40


def fixture_task() -> dict:
    return build_task(expected_task_seed(IMPLEMENTATION_FIXTURE))


def admission_output(task: dict) -> dict:
    contract = oracle_contract(public_evaluator_task(task))
    return {
        "goal_contract": contract,
        "goal_id": contract["goal_id"],
        "goal_status": "active",
        "plan_version": 1,
        "experiment_id": "exp-123456789abc",
        "subtask_id": "sub-123456789abc",
        "action": "admit-contract",
        "completion_claim": False,
    }


class OT0039Tests(unittest.TestCase):
    def test_post_implementation_task_is_mechanical_and_goal_free(self) -> None:
        seed = expected_task_seed(IMPLEMENTATION_FIXTURE)
        task = build_task(seed)
        self.assertEqual(task, build_task(seed))
        validate_task(task)
        contract = oracle_contract(public_evaluator_task(task))
        self.assertTrue(raw_packet_has_no_goal(public_evaluator_task(task), contract))
        self.assertEqual(contract["value_thesis"]["minimum_gain"], 21)

    def test_promoted_selector_and_ledger_are_causal_to_routes(self) -> None:
        lineage = selector_route_lineage(fixture_task())
        self.assertTrue(lineage["pass"])
        self.assertEqual(lineage["candidate_route_errors"], [0, 0, 0])
        self.assertEqual(lineage["unchanged_route_errors"], [3, 3, 3])
        self.assertTrue(all(regime["changed"] for regime in lineage["regimes"]))
        self.assertTrue(
            all(not regime["neutralized_changed"] for regime in lineage["regimes"])
        )

    def test_controller_admits_oracle_quality_actor_contract(self) -> None:
        task = fixture_task()
        output = admission_output(task)
        score = admission_score(task, output)
        self.assertTrue(score["quality_pass"])
        self.assertTrue(score["ot2_admissible"])
        schema = json.loads(
            Path("fixtures/ot-0039/actor-output.schema.json").read_text()
        )
        jsonschema.validate(output, schema)

    def test_complete_candidate_path_survives_resets_and_delays_completion(self) -> None:
        task = fixture_task()
        lineage = selector_route_lineage(task)
        world = GoalWorld(task, lineage)
        substrate = DurableGoalContract(true_actions(task, lineage), True)
        initial = admission_output(task)
        packet = world.packet(0)
        receipt = world.apply(initial, True)
        substrate.observe(GoalObservation(packet, initial, receipt, True))
        self.assertEqual(world.step, 1)
        outputs = [initial]
        for encounter in range(1, 8):
            packet = world.packet(encounter)
            projection = json.loads(substrate.project(512))
            output = {
                "goal_contract": None,
                "goal_id": projection["goal_id"],
                "goal_status": projection["goal_status"],
                "plan_version": projection["plan_version"],
                "experiment_id": projection["experiment_id"],
                "subtask_id": projection["subtask_id"],
                "action": projection["required_action"],
                "completion_claim": projection["completion_claim"],
            }
            self.assertTrue(
                hierarchy_correct(
                    initial["goal_contract"],
                    initial["experiment_id"],
                    initial["subtask_id"],
                    world.step,
                    output,
                )
            )
            receipt = world.apply(output, False)
            substrate.observe(GoalObservation(packet, output, receipt, False))
            outputs.append(output)
        self.assertEqual(world.step, 8)
        self.assertEqual([item["plan_version"] for item in outputs], [1, 1, 2, 2, 3, 3, 3, 3])
        self.assertEqual([item["completion_claim"] for item in outputs], [False] * 7 + [True])

    def test_unchanged_selector_differs_on_first_repair(self) -> None:
        task = fixture_task()
        lineage = selector_route_lineage(task)
        self.assertNotEqual(true_actions(task, lineage)[1], unchanged_actions(task, lineage)[1])

    def test_hosted_order_is_exactly_counterbalanced(self) -> None:
        task_order = json.loads(Path("fixtures/ot-0039/task-order.json").read_text())
        validate_counterbalance(task_order, 4)

    def test_run_lock_will_bind_all_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0039-acceptance.json"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0039.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0039_world.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0038/"
                "ot-0038-e7-ot2-evaluator-calibration-001.json"
            ),
            paths,
        )

    def test_durable_substrate_has_no_world_or_evaluator_authority(self) -> None:
        authority = substrate_authority(Path.cwd())
        self.assertTrue(authority["pass"])
        self.assertEqual(authority["init_parameters"], ["self", "actions", "adaptive"])
        self.assertEqual(authority["project_parameters"], ["self", "byte_limit"])
        self.assertEqual(authority["forbidden_authority"], [])


if __name__ == "__main__":
    unittest.main()
