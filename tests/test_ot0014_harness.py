from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0014 import (
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
    results = []
    index = 0
    all_receipts = [{"kind": "models_etag", "value": etag}]
    for phase in task_order["phases"]:
        for condition in phase["condition_order"][worker_id]:
            score_kind = phase["score"]
            response_id = f"response-{worker_id}-{index}"
            deployment_receipts = [
                {"kind": "effective_model", "value": "gpt-5.6-luna"},
                {"kind": "response_id", "value": response_id},
            ]
            all_receipts.extend(deployment_receipts)
            results.append(
                {
                    "condition": condition,
                    "phase": phase["phase"],
                    "score_kind": score_kind,
                    "errors": 0 if condition == "candidate" else (2 if score_kind == "heldout" else 0),
                    "outcomes": [0, 1, 0, 1] if score_kind == "heldout" else [0] * 5,
                    "parse_error": None,
                    "tool_calls": 0,
                    "thread_id": f"thread-{worker_id}-{index}",
                    "workspace": f"workspace-{worker_id}-{index}",
                    "projection_bytes": 80,
                    "inventory_receipts": 1,
                    "substrate_project_operations": 30,
                    "substrate_observe_operations": 150,
                    "deployment_receipts": deployment_receipts,
                    "deployment_effective_models": ["gpt-5.6-luna"],
                    "deployment_response_ids": [response_id],
                }
            )
            index += 1
    for ablation in task_order["ablations"]:
        response_id = f"response-{worker_id}-{index}"
        deployment_receipts = [
            {"kind": "effective_model", "value": "gpt-5.6-luna"},
            {"kind": "response_id", "value": response_id},
        ]
        all_receipts.extend(deployment_receipts)
        results.append(
            {
                "condition": "candidate-ablation",
                "phase": ablation["phase"],
                "score_kind": "ablation",
                "errors": 2,
                "outcomes": [0, 1, 0, 1],
                "parse_error": None,
                "tool_calls": 0,
                "thread_id": f"thread-{worker_id}-{index}",
                "workspace": f"workspace-{worker_id}-{index}",
                "projection_bytes": 30,
                "inventory_receipts": 1,
                "substrate_project_operations": 0,
                "substrate_observe_operations": 0,
                "deployment_receipts": deployment_receipts,
                "deployment_effective_models": ["gpt-5.6-luna"],
                "deployment_response_ids": [response_id],
            }
        )
        index += 1
    catalog = [{"id": "gpt-5.6-luna"}]
    return {
        "worker_id": worker_id,
        "status": "completed",
        "results": results,
        "candidate_state": {"regime": 1, "matches_hidden_regime_b": True},
        "direct_inventory": {
            "sha256": acceptance["direct_inventory"]["sha256"],
            "tool_count": acceptance["direct_inventory"]["tool_count"],
            "receipt_count": 26,
            "stable": True,
        },
        "deployment": {
            "catalog_payload": catalog,
            "catalog_payload_sha256": sha256_bytes(canonical_json(catalog)),
            "receipts": all_receipts,
            "collector_errors": [],
            "diagnostics": {},
        },
        "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "elapsed_seconds": 10,
    }


class OT0014HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0014-acceptance.json")
        self.task_order = load_json(REPO / "fixtures/ot-0014/task-order.json")

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
        validate_counterbalance(self.task_order, expected_count=3)

    def test_matching_epoch_and_behavior_promote(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "promoted")
        self.assertTrue(summary["validity_gates"]["same_deployment_epoch"])
        self.assertTrue(all(worker["behavioral_pass"] for worker in summary["workers"]))

    def test_epoch_change_invalidates_before_behavioral_interpretation(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order, etag="changed-etag"),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "invalidated")
        self.assertFalse(summary["validity_gates"]["same_deployment_epoch"])

    def test_missing_turn_response_receipt_invalidates_worker(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["results"][0]["deployment_response_ids"] = []
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["deployment_epoch"]["gates"]["per_turn_receipts"])
        self.assertFalse(summary["scientific_pass"])


if __name__ == "__main__":
    unittest.main()
