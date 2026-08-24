from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0004 import (
    combined_summary,
    validate_counterbalance,
    worker_summary,
)


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
    for index in range(acceptance["resource_budget"]["actor_turns_total_per_worker"]):
        model = "gpt-5.6-terra" if index >= 66 else "gpt-5.6-luna"
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
                "deployment_receipts": turn_receipts,
                "deployment_effective_models": [model],
                "deployment_response_ids": [response_id],
            }
        )
    pairs = [(0, 0), (0, 2), (0, 2), (4, 1), (0, 4), (0, 2)]
    stage_records = []
    for stage, (changed_errors, frozen_errors) in enumerate(pairs):
        changed_ids = [f"changed-{stage}-{index}" for index in range(6)]
        frozen_ids = (
            changed_ids if stage == 0 else [f"frozen-{stage}-{index}" for index in range(6)]
        )
        branches = {
            "changed-policy": {
                "errors": changed_errors,
                "selected_event_ids": changed_ids,
            },
            "frozen-predecessor": {
                "errors": frozen_errors,
                "selected_event_ids": frozen_ids,
            },
        }
        for condition in (
            "fixed-most-recent",
            "fixed-first-seen-verbatim",
            "fixed-naive-nearest",
            "no-persistence",
        ):
            branches[condition] = {"errors": 3, "selected_event_ids": []}
        stage_records.append(
            {
                "stage": stage,
                "heldout_condition_order": task_order["phases"][stage]["condition_order"][worker_id],
                "branches": branches,
            }
        )
    catalog = [{"id": "gpt-5.6-luna"}, {"id": "gpt-5.6-terra"}]
    return {
        "worker_id": worker_id,
        "status": "completed",
        "actor_results": actor_results,
        "stage_records": stage_records,
        "policy_snapshots": [{} for _ in range(7)],
        "reviews": [
            {"pass": True, "operation_summary": "new operation", "seed_overlap": "absent"},
            {"pass": True, "operation_summary": "new operation", "seed_overlap": "absent"},
        ],
        "direct_inventory": {
            "sha256": acceptance["direct_inventory"]["sha256"],
            "tool_count": acceptance["direct_inventory"]["tool_count"],
            "receipt_count": len(actor_results),
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
        "elapsed_seconds": 100,
    }


class OT0004HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0004-acceptance.json")
        self.task_order = load_json(REPO / "fixtures/ot-0004/task-order.json")

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

    def test_task_order_is_exactly_position_balanced(self) -> None:
        validate_counterbalance(self.task_order, expected_count=2)

    def test_complete_temporal_chain_and_epoch_promote(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "promoted")
        self.assertTrue(summary["workers"][0]["gates"]["temporal_corrigibility_chain"])
        self.assertEqual(
            summary["workers"][0]["corrigibility_chains"][0],
            {
                "harm_stage": 3,
                "correction_stage": 4,
                "canary_stage": 5,
                "useful_before_harm": 2,
            },
        )

    def test_epoch_change_invalidates_before_scientific_interpretation(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order, etag="changed"),
        ]
        self.assertEqual(combined_summary(self.raw(workers))["disposition"], "invalidated")

    def test_missing_response_receipt_invalidates_worker(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["actor_results"][0]["deployment_response_ids"] = []
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["deployment_epoch"]["valid"])
        self.assertFalse(summary["scientific_pass"])

    def test_policy_benefit_without_harm_correction_canary_is_rejected(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["stage_records"][3]["branches"]["changed-policy"]["errors"] = 0
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["gates"]["temporal_corrigibility_chain"])
        self.assertFalse(summary["behavioral_pass"])


if __name__ == "__main__":
    unittest.main()
