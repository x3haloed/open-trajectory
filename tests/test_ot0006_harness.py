from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0006 import combined_summary, validate_counterbalance
from open_trajectory_harness.ot0006_world import (
    DurableGoalContract,
    GoalObservation,
    GoalWorld,
    STEP_ACTIONS,
    generate_task_manifest,
    validate_task_manifest,
)


REPO = Path(__file__).resolve().parents[1]


def passing_worker(worker_id: str, acceptance: dict, task_order: dict, *, etag: str = "etag") -> dict:
    results = []
    receipts = [{"kind": "models_etag", "value": etag}]
    condition_steps = {condition: 0 for condition in task_order["conditions"]}
    turn_index = 0
    for encounter_index, phase in enumerate(task_order["phases"]):
        for condition in phase["condition_order"][worker_id]:
            before = condition_steps[condition]
            advanced = condition == "goal-contract" or encounter_index < 2
            after = before + int(advanced)
            condition_steps[condition] = after
            response_id = f"response-{worker_id}-{turn_index}"
            turn_receipts = [
                {"kind": "effective_model", "value": "gpt-5.6-luna"},
                {"kind": "response_id", "value": response_id},
            ]
            receipts.extend(turn_receipts)
            candidate = condition == "goal-contract"
            plan = 1 if encounter_index < 3 else (2 if encounter_index < 6 else 3)
            output = {
                "goal_id": "goal" if candidate else None,
                "goal_status": "completed" if candidate and encounter_index == 8 else ("active" if candidate else "unknown"),
                "plan_version": plan if candidate else None,
                "experiment_id": f"exp-{encounter_index}" if candidate else None,
                "subtask_id": f"sub-{encounter_index}" if candidate else None,
                "action": f"action-{encounter_index}",
                "completion_claim": candidate and encounter_index == 8,
            }
            results.append(
                {
                    "condition": condition,
                    "phase": phase["phase"],
                    "encounter_index": encounter_index,
                    "workspace": f"workspace-{worker_id}-{turn_index}",
                    "thread_id": f"thread-{worker_id}-{turn_index}",
                    "projection_bytes": 200,
                    "actor_output": output,
                    "parse_error": None,
                    "tool_calls": 0,
                    "inventory_receipts": 1,
                    "deployment_effective_models": ["gpt-5.6-luna"],
                    "deployment_response_ids": [response_id],
                    "world_step_before": before,
                    "world_step_after": after,
                    "world_receipt": {
                        "advanced": advanced,
                        "goal_complete": candidate and encounter_index == 8,
                    },
                    "hierarchy_correct": candidate,
                }
            )
            turn_index += 1
    catalog = [{"id": "gpt-5.6-luna"}]
    return {
        "worker_id": worker_id,
        "status": "completed",
        "results": results,
        "direct_inventory": {
            "sha256": acceptance["direct_inventory"]["sha256"],
            "tool_count": acceptance["direct_inventory"]["tool_count"],
            "receipt_count": 27,
            "stable": True,
        },
        "deployment": {
            "catalog_payload": catalog,
            "catalog_payload_sha256": sha256_bytes(canonical_json(catalog)),
            "receipts": receipts,
            "collector_errors": [],
            "diagnostics": {},
        },
        "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "elapsed_seconds": 20,
    }


class OT0006HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0006-acceptance.json")
        self.task_order = load_json(REPO / "fixtures/ot-0006/task-order.json")

    def raw(self, workers: list[dict]) -> dict:
        return {
            "run_id": "test",
            "implementation_git_commit": "a" * 40,
            "task_manifest_sha256": "b" * 64,
            "same_task_manifest": True,
            "implementation_clean": True,
            "audit_and_tests": True,
            "acceptance": self.acceptance,
            "task_order": self.task_order,
            "workers": workers,
            "two_worker_window_seconds": 100,
        }

    def test_task_generation_and_contract_causal_path(self) -> None:
        manifest = generate_task_manifest()
        validate_task_manifest(manifest)
        world = GoalWorld(manifest)
        substrate = DurableGoalContract(manifest)
        for encounter in range(9):
            packet = world.packet(encounter)
            projection = substrate.project(384)
            if encounter:
                self.assertIn(manifest["goal"]["id"], projection)
            output = {"action": manifest["actions"][STEP_ACTIONS[world.step]]}
            receipt = world.apply(output)
            substrate.observe(GoalObservation(packet, output, receipt))
        self.assertEqual(world.step, 9)

    def test_counterbalance(self) -> None:
        validate_counterbalance(self.task_order, 6)

    def test_matching_workers_promote_infrastructure(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "promoted-infrastructure")
        self.assertTrue(all(worker["scientific_pass"] for worker in summary["workers"]))

    def test_epoch_change_invalidates(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order, etag="changed"),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "invalidated")

    def test_premature_completion_rejects(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order),
        ]
        candidate = next(
            item
            for item in workers[0]["results"]
            if item["condition"] == "goal-contract" and item["encounter_index"] == 2
        )
        candidate["actor_output"]["completion_claim"] = True
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "rejected")


if __name__ == "__main__":
    unittest.main()
