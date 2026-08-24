from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0005 import combined_summary, validate_counterbalance, worker_summary


REPO = Path(__file__).resolve().parents[1]


def passing_worker(
    worker_id: str,
    acceptance: dict,
    task_order: dict,
    *,
    etag: str = "epoch-etag",
) -> dict:
    actor_results = []
    receipts = [{"kind": "models_etag", "value": etag}]
    for index in range(8):
        model = "gpt-5.6-luna" if index < 6 else "gpt-5.6-terra"
        response_id = f"response-{worker_id}-{index}"
        turn_receipts = [
            {"kind": "effective_model", "value": model},
            {"kind": "response_id", "value": response_id},
        ]
        receipts.extend(turn_receipts)
        actor_results.append(
            {
                "role": f"role-{index}",
                "model": model,
                "workspace": f"workspace-{worker_id}-{index}",
                "thread_id": f"thread-{worker_id}-{index}",
                "parse_error": None,
                "tool_calls": 0,
                "inventory_receipts": 1,
                "deployment_effective_models": [model],
                "deployment_response_ids": [response_id],
            }
        )
    pairs = [(0, 0), (0, 2), (0, 2), (4, 1), (0, 4), (0, 2)]
    records = []
    for stage, (changed_errors, parent_errors) in enumerate(pairs):
        changed_ids = [] if stage == 0 else [f"changed-{stage}-{index}" for index in range(6)]
        parent_ids = changed_ids if stage == 0 else [f"parent-{stage}-{index}" for index in range(6)]
        branches = {
            "changed-program": {
                "selected_event_ids": changed_ids,
                "predictions": [0] * 8,
                "errors": changed_errors,
                "deterministic_replay": True,
            },
            "frozen-parent": {
                "selected_event_ids": parent_ids,
                "predictions": [0] * 8,
                "errors": parent_errors,
                "deterministic_replay": True,
            },
        }
        for condition in (
            "fixed-most-recent",
            "fixed-first-seen-verbatim",
            "fixed-naive-nearest",
            "no-persistence",
        ):
            branches[condition] = {
                "selected_event_ids": [],
                "predictions": [1] * 8,
                "errors": 3,
                "deterministic_replay": True,
            }
        records.append(
            {
                "stage": stage,
                "contact": {"deterministic_replay": True},
                "heldout_condition_order": task_order["phases"][stage]["condition_order"][worker_id],
                "branches": branches,
            }
        )
    catalog = [{"id": "gpt-5.6-luna"}, {"id": "gpt-5.6-terra"}]
    inventory = {
        model: {
            **identity,
            "receipt_count": 6 if model == "gpt-5.6-luna" else 2,
            "stable": True,
        }
        for model, identity in acceptance["direct_inventory_by_model"].items()
    }
    return {
        "worker_id": worker_id,
        "actor_results": actor_results,
        "stage_records": records,
        "program_snapshots": [{} for _ in range(7)],
        "reviews": [
            {"pass": True, "operation_summary": "new", "seed_overlap": "absent"},
            {"pass": True, "operation_summary": "new", "seed_overlap": "absent"},
        ],
        "direct_inventory_by_model": inventory,
        "deployment": {
            "catalog_payload": catalog,
            "catalog_payload_sha256": sha256_bytes(canonical_json(catalog)),
            "receipts": receipts,
            "collector_errors": [],
        },
        "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "elapsed_seconds": 30,
    }


class OT0005HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0005-acceptance.json")
        self.task_order = load_json(REPO / "fixtures/ot-0005/task-order.json")

    def raw(self, workers: list[dict]) -> dict:
        return {
            "run_id": "test-run",
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

    def test_counterbalance_is_exact(self) -> None:
        validate_counterbalance(self.task_order, 2)

    def test_complete_deterministic_temporal_chain_promotes(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "promoted")
        self.assertTrue(summary["workers"][0]["gates"]["identity_placebo"])

    def test_identity_placebo_failure_rejects_behavior(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["stage_records"][0]["branches"]["frozen-parent"]["predictions"] = [1] * 8
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["gates"]["identity_placebo"])
        self.assertFalse(summary["behavioral_pass"])

    def test_model_specific_inventory_mismatch_invalidates(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["direct_inventory_by_model"]["gpt-5.6-terra"]["tool_count"] = 3
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["deployment_epoch"]["valid"])
        self.assertFalse(summary["scientific_pass"])

    def test_epoch_change_invalidates_combined_result(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order, etag="changed"),
        ]
        self.assertEqual(combined_summary(self.raw(workers))["disposition"], "invalidated")


if __name__ == "__main__":
    unittest.main()
