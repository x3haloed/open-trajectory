from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .ot0002 import canonical_json, sha256_bytes


EXPERIMENT_ID = "OT-0016"
FIXED_CONDITIONS = (
    "fixed-most-recent",
    "fixed-first-seen-verbatim",
    "fixed-naive-nearest",
    "no-persistence",
)


def validate_counterbalance(task_order: dict[str, Any], expected_count: int) -> None:
    conditions = task_order.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 6 or len(set(conditions)) != 6:
        raise ValueError("OT-0016 requires six distinct scored conditions")
    counts = {condition: Counter() for condition in conditions}
    phases = task_order.get("phases")
    if not isinstance(phases, list) or len(phases) != 6:
        raise ValueError("OT-0016 requires six ordered stages")
    for phase in phases:
        orders = phase.get("condition_order") if isinstance(phase, dict) else None
        if not isinstance(orders, dict) or set(orders) != {"worker-1", "worker-2"}:
            raise ValueError("each OT-0016 stage requires two worker orders")
        for order in orders.values():
            if not isinstance(order, list) or len(order) != 6 or set(order) != set(conditions):
                raise ValueError("OT-0016 condition order is not an exact permutation")
            for position, condition in enumerate(order):
                counts[condition][position] += 1
    expected = Counter({position: expected_count for position in range(6)})
    if any(value != expected for value in counts.values()):
        raise ValueError("OT-0016 condition positions are not exactly counterbalanced")


def _all_true(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value) and all(_all_true(child) for child in value.values())
    return value is True


def behavioral_worker_summary(worker: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    scoring = acceptance["scoring"]
    comparisons: list[dict[str, Any]] = []
    for record in worker["stage_records"]:
        committed = record["branches"]["committed-program"]
        unchanged = record["branches"]["unchanged-current"]
        protected_parent = record["preupdate_parent_branch"]
        true_application = record["decision"]["true_application"]
        neutralized = record["decision"]["credit_neutralized_application"]
        comparisons.append(
            {
                "stage": record["stage"],
                "committed_errors": committed["errors"],
                "unchanged_errors": unchanged["errors"],
                "protected_parent_errors": protected_parent["errors"],
                "advantage": unchanged["errors"] - committed["errors"],
                "harm_over_parent": unchanged["errors"] - protected_parent["errors"],
                "selection_changed": committed["selected_event_ids"]
                != unchanged["selected_event_ids"],
                "preupdate_selection_changed": unchanged["selected_event_ids"]
                != protected_parent["selected_event_ids"],
                "commit_changed": record["commit"]["changed"],
                "credit_causal": true_application["choice"] == "challenger"
                and neutralized["choice"] == "current"
                and true_application["deterministic_replay"] is True
                and neutralized["deterministic_replay"] is True,
            }
        )

    useful = [
        item
        for item in comparisons[1:]
        if item["commit_changed"]
        and item["selection_changed"]
        and item["credit_causal"]
        and item["advantage"]
        >= scoring["committed_over_unchanged_error_advantage_per_revision"]
    ]
    chains: list[dict[str, Any]] = []
    for harm in comparisons[1:]:
        if not (
            harm["preupdate_selection_changed"]
            and harm["harm_over_parent"]
            >= scoring["learned_selector_harm_over_protected_parent_required"]
        ):
            continue
        useful_before = [item for item in useful if item["stage"] < harm["stage"]]
        correction_recovery = harm["unchanged_errors"] - harm["committed_errors"]
        if not (
            harm["commit_changed"]
            and harm["selection_changed"]
            and harm["credit_causal"]
            and correction_recovery >= scoring["correction_error_recovery_required"]
            and harm["committed_errors"] <= scoring["corrected_selector_errors_allowed"]
        ):
            continue
        canaries = [
            item
            for item in useful
            if item["stage"] > harm["stage"]
            and item["advantage"]
            >= scoring["post_correction_canary_advantage_required"]
        ]
        if canaries:
            chains.append(
                {
                    "harm_stage": harm["stage"],
                    "correction_stage": harm["stage"],
                    "canary_stage": canaries[0]["stage"],
                    "useful_before_harm": len(useful_before),
                    "correction_recovery": correction_recovery,
                }
            )

    lineage_errors = sum(item["committed_errors"] for item in comparisons)
    fixed_errors = {
        condition: sum(
            record["branches"][condition]["errors"] for record in worker["stage_records"]
        )
        for condition in FIXED_CONDITIONS
    }
    results = worker["actor_results"]
    freshness = {
        "threads": len({item["thread_id"] for item in results}) == len(results),
        "workspaces": len({item["workspace"] for item in results}) == len(results),
    }
    committed_count = sum(record["commit"]["changed"] for record in worker["stage_records"])
    deterministic_branches = [
        branch
        for record in worker["stage_records"]
        for branch in [
            record["contact_comparison"]["current"],
            record["contact_comparison"]["challenger"],
            record["preupdate_parent_branch"],
            *record["branches"].values(),
        ]
    ]
    gates = {
        "turn_count": len(results)
        == acceptance["resource_budget"]["actor_turns_total_per_worker"],
        "parse": sum(item.get("parse_error") is not None for item in results)
        <= scoring["actor_parse_failures_allowed"],
        "tools": sum(item.get("tool_calls", 0) for item in results)
        <= scoring["actor_tool_calls_allowed"],
        "freshness": all(freshness.values()),
        "proposal_count": len(worker["proposals"]) == acceptance["world"]["stages"],
        "selector_chain": len(worker["selector_snapshots"]) == committed_count + 1,
        "decision_rule_chain": len(worker["decision_rule_snapshots"])
        == acceptance["world"]["stages"] + 1,
        "deterministic_replay": all(
            branch.get("deterministic_replay") is True for branch in deterministic_branches
        ),
        "decision_replay": all(
            record["decision"][name].get("deterministic_replay") is True
            for record in worker["stage_records"]
            for name in ("true_application", "credit_neutralized_application")
        ),
        "identity_placebos": _all_true(worker["identity_placebos"]),
        "temporal_corrigibility_chain": any(
            chain["useful_before_harm"] >= scoring["useful_pre_harm_commits_required"]
            for chain in chains
        ),
        "novelty_unanimity": len(worker["reviews"])
        == acceptance["novelty_review"]["fresh_blinded_reviews_per_worker"]
        and all(review.get("pass") is True for review in worker["reviews"]),
        "lineage_absolute": lineage_errors <= scoring["committed_lineage_errors_allowed"],
        "lineage_comparative": all(
            errors - lineage_errors
            >= scoring["committed_lineage_advantage_over_each_fixed_control_required"]
            for errors in fixed_errors.values()
        ),
        "input_budget": worker["usage"]["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total_per_worker"],
        "output_budget": worker["usage"]["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total_per_worker"],
        "wall_budget": worker["elapsed_seconds"]
        <= acceptance["resource_budget"]["wall_seconds_per_worker"],
    }
    return {
        "worker_id": worker["worker_id"],
        "comparisons": comparisons,
        "corrigibility_chains": chains,
        "identity_placebos": worker["identity_placebos"],
        "committed_lineage_errors": lineage_errors,
        "fixed_control_errors": fixed_errors,
        "gates": gates,
        "behavioral_pass": all(gates.values()),
    }


def deployment_worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    results = worker["actor_results"]
    deployment = worker["deployment"]
    response_ids = [
        item["deployment_response_ids"][0]
        for item in results
        if item.get("deployment_response_ids")
    ]
    per_turn = all(
        item.get("deployment_effective_models") == [item.get("model")]
        and len(item.get("deployment_response_ids", [])) == 1
        for item in results
    )
    receipts = deployment["receipts"]
    effective_models = sorted(
        {item["value"] for item in receipts if item["kind"] == "effective_model"}
    )
    expected_models = sorted(acceptance["direct_inventory_by_model"])
    etags = sorted({item["value"] for item in receipts if item["kind"] == "models_etag"})
    observed_inventories = worker["direct_inventory_by_model"]
    expected_inventories = acceptance["direct_inventory_by_model"]
    inventory_valid = set(observed_inventories) == set(expected_inventories)
    if inventory_valid:
        for model, expected in expected_inventories.items():
            observed = observed_inventories[model]
            inventory_valid = inventory_valid and (
                observed["sha256"] == expected["sha256"]
                and observed["tool_count"] == expected["tool_count"]
                and observed["stable"] is True
            )
    epoch_fields = {
        "effective_models": effective_models,
        "catalog_payload_sha256": deployment["catalog_payload_sha256"],
        "models_etag_sha256": sha256_bytes(canonical_json(etags)) if etags else None,
    }
    gates = {
        "collector_integrity": deployment.get("collector_errors") == [],
        "effective_models": effective_models == expected_models,
        "catalog_payload": bool(
            re.fullmatch(r"[0-9a-f]{64}", deployment["catalog_payload_sha256"])
        ),
        "catalog_etag": len(etags) == 1,
        "per_turn_receipts": per_turn,
        "distinct_response_ids": len(response_ids)
        == len(set(response_ids))
        == acceptance["resource_budget"]["actor_turns_total_per_worker"],
        "counterbalanced_order": [
            record["heldout_condition_order"] for record in worker["stage_records"]
        ]
        == [phase["condition_order"][worker["worker_id"]] for phase in task_order["phases"]],
        "direct_inventory_by_model": inventory_valid,
    }
    return {
        **epoch_fields,
        "response_receipts_sha256": sha256_bytes(
            canonical_json([sha256_bytes(value.encode()) for value in response_ids])
        ),
        "response_count": len(response_ids),
        "epoch_identity_sha256": sha256_bytes(canonical_json(epoch_fields)),
        "gates": gates,
        "valid": all(gates.values()),
    }


def worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    summary = behavioral_worker_summary(worker, acceptance)
    deployment = deployment_worker_summary(worker, acceptance, task_order)
    summary["deployment_epoch"] = deployment
    summary["scientific_pass"] = summary["behavioral_pass"] and deployment["valid"]
    return summary


def combined_summary(raw: dict[str, Any]) -> dict[str, Any]:
    workers = [
        worker_summary(worker, raw["acceptance"], raw["task_order"])
        for worker in raw["workers"]
    ]
    validity = {
        "worker_deployment_receipts": len(workers) == 2
        and all(worker["deployment_epoch"]["valid"] for worker in workers),
        "same_deployment_epoch": len(workers) == 2
        and len({worker["deployment_epoch"]["epoch_identity_sha256"] for worker in workers})
        == 1,
        "same_task_manifest": raw.get("same_task_manifest", False),
        "two_worker_window": raw["two_worker_window_seconds"]
        <= raw["acceptance"]["deployment_epoch"]["maximum_two_worker_window_seconds"],
    }
    reproduction = len(workers) == 2 and all(worker["behavioral_pass"] for worker in workers)
    promotion = {
        "clean_predating_implementation": raw.get("implementation_clean", False),
        "original_behavioral_gates": bool(workers and workers[0]["behavioral_pass"]),
        "clean_behavioral_reproduction": reproduction,
        "deployment_epoch_validity": all(validity.values()),
        "audit_and_tests": raw.get("audit_and_tests", False),
    }
    if not all(validity.values()):
        disposition = "invalidated"
    elif not reproduction:
        disposition = "rejected"
    elif all(promotion.values()):
        disposition = "promoted"
    else:
        disposition = "conditional"
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_epoch": raw["acceptance"]["evaluation_epoch"],
        "run_id": raw["run_id"],
        "implementation_git_commit": raw["implementation_git_commit"],
        "task_manifest_sha256": raw["task_manifest_sha256"],
        "two_worker_window_seconds": raw["two_worker_window_seconds"],
        "workers": workers,
        "validity_gates": validity,
        "promotion_gates": promotion,
        "disposition": disposition,
        "evidence_horizon": "private, time-bounded, single constrained family OT-1 evidence only",
    }


__all__ = [
    "behavioral_worker_summary",
    "combined_summary",
    "deployment_worker_summary",
    "validate_counterbalance",
    "worker_summary",
]
