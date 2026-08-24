from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0016 import combined_summary, validate_counterbalance, worker_summary


REPO = Path(__file__).resolve().parents[1]


def branch(prefix: str, stage: int, errors: int, *, same_as: str | None = None) -> dict:
    identity = same_as or prefix
    return {
        "selected_event_ids": [f"{identity}-{stage}-{index}" for index in range(6)],
        "predictions": [0] * 8,
        "errors": errors,
        "deterministic_replay": True,
    }


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

    committed_errors = [1, 0, 0, 0, 0, 0]
    unchanged_errors = [3, 2, 2, 4, 2, 1]
    parent_errors = [3, 2, 1, 1, 1, 1]
    records = []
    for stage in range(6):
        branches = {
            "committed-program": branch("committed", stage, committed_errors[stage]),
            "unchanged-current": branch("unchanged", stage, unchanged_errors[stage]),
        }
        for condition in (
            "fixed-most-recent",
            "fixed-first-seen-verbatim",
            "fixed-naive-nearest",
            "no-persistence",
        ):
            branches[condition] = branch(condition, stage, 3)
        records.append(
            {
                "stage": stage,
                "contact_comparison": {
                    "current": branch("contact-current", stage, 2),
                    "challenger": branch("contact-challenger", stage, 0),
                },
                "decision": {
                    "true_application": {
                        "choice": "challenger",
                        "deterministic_replay": True,
                    },
                    "credit_neutralized_application": {
                        "choice": "current",
                        "deterministic_replay": True,
                    },
                },
                "commit": {"changed": True},
                "preupdate_parent_branch": branch("parent", stage, parent_errors[stage]),
                "heldout_condition_order": task_order["phases"][stage]["condition_order"][
                    worker_id
                ],
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
        "proposals": [{} for _ in range(6)],
        "selector_snapshots": [{} for _ in range(7)],
        "decision_rule_snapshots": [{} for _ in range(7)],
        "identity_placebos": {
            "selector": {"selection": True, "prediction": True, "score": True},
            "decision_rule": {"choice": True, "comparison": True},
        },
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


class OT0016HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0016-acceptance.json")
        self.task_order = load_json(REPO / "fixtures/ot-0016/task-order.json")

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

    def test_complete_credit_causal_temporal_chain_promotes(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order),
        ]
        summary = combined_summary(self.raw(workers))
        self.assertEqual(summary["disposition"], "promoted")
        self.assertTrue(summary["workers"][0]["gates"]["temporal_corrigibility_chain"])

    def test_credit_neutralization_must_remove_commit_choice(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["stage_records"][2]["decision"]["credit_neutralized_application"][
            "choice"
        ] = "challenger"
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["gates"]["temporal_corrigibility_chain"])

    def test_harm_correction_and_canary_are_each_required(self) -> None:
        for mutation in ("harm", "correction", "canary"):
            worker = passing_worker("worker-1", self.acceptance, self.task_order)
            if mutation == "harm":
                worker["stage_records"][3]["preupdate_parent_branch"]["errors"] = 3
            elif mutation == "correction":
                worker["stage_records"][3]["branches"]["committed-program"]["errors"] = 2
            else:
                worker["stage_records"][4]["branches"]["unchanged-current"]["errors"] = 1
                worker["stage_records"][5]["branches"]["unchanged-current"]["errors"] = 1
            with self.subTest(mutation=mutation):
                summary = worker_summary(worker, self.acceptance, self.task_order)
                self.assertFalse(summary["gates"]["temporal_corrigibility_chain"])

    def test_identity_placebo_failure_rejects_behavior(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["identity_placebos"]["decision_rule"]["choice"] = False
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["gates"]["identity_placebos"])
        self.assertFalse(summary["behavioral_pass"])

    def test_model_specific_inventory_mismatch_invalidates(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["direct_inventory_by_model"]["gpt-5.6-terra"]["tool_count"] = 3
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["deployment_epoch"]["valid"])
        self.assertFalse(summary["scientific_pass"])

    def test_missing_model_inventory_receipt_invalidates(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["direct_inventory_by_model"]["gpt-5.6-luna"]["receipt_count"] = 5
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["deployment_epoch"]["valid"])

    def test_missing_turn_inventory_receipt_invalidates(self) -> None:
        worker = passing_worker("worker-1", self.acceptance, self.task_order)
        worker["actor_results"][0]["inventory_receipts"] = 0
        summary = worker_summary(worker, self.acceptance, self.task_order)
        self.assertFalse(summary["deployment_epoch"]["valid"])

    def test_epoch_change_invalidates_combined_result(self) -> None:
        workers = [
            passing_worker("worker-1", self.acceptance, self.task_order),
            passing_worker("worker-2", self.acceptance, self.task_order, etag="changed"),
        ]
        self.assertEqual(combined_summary(self.raw(workers))["disposition"], "invalidated")


if __name__ == "__main__":
    unittest.main()
