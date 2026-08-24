from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import secrets
from pathlib import Path
from typing import Any

from .ot0004_world import (
    FEATURE_VECTORS,
    archive_through_stage,
    fixed_selection,
    selected_events,
)
from .ot0005_world import deterministic_predictions
from .ot0016 import FIXED_CONDITIONS
from .ot0017_regime import (
    ANCHOR_TASKS,
    CONSTRUCTION_PLAN,
    SCORING,
    _error_grid,
    _evaluate_path,
    _identity_placebo,
    _outcomes,
    _path_summary,
    _query_order_placebo,
    _swap_stage_blocks,
    _validate_inherited,
    _witness_signature,
    construct_direct_manifest,
    control_tables,
    find_exact_witness,
)
from .ot0018_regime import load_exclusions, summarize_calibration


EXPERIMENT_ID = "OT-0019"
EXCLUSION_ARTIFACTS_REQUIRED = 3


def _neutralize_stage(deleted: dict[str, Any], stage_index: int) -> dict[str, Any]:
    archive = archive_through_stage(deleted, stage_index)
    queries = [list(value) for value in FEATURE_VECTORS]
    first_ids = fixed_selection("fixed-first-seen-verbatim", archive, queries, 6)
    first_predictions = deterministic_predictions(
        selected_events(archive, first_ids), queries
    )
    truth = _outcomes(deleted, stage_index, queries)
    common_zeros = [
        value
        for value, prediction, outcome in zip(FEATURE_VECTORS, first_predictions, truth)
        if prediction == 0 and outcome == 0
    ]
    if len(common_zeros) < 2:
        raise ValueError("full-suffix neutralization needs two common zeros")
    rng = random.Random(
        int(
            hashlib.sha256(
                f"{deleted['salt']}:suffix-neutral:{stage_index}".encode()
            ).hexdigest(),
            16,
        )
    )
    rng.shuffle(common_zeros)
    repeated, second = common_zeros[:2]
    missing = [value for value in FEATURE_VECTORS if value != repeated]
    fillers = [*missing, *rng.choices(list(FEATURE_VECTORS), k=3)]
    rng.shuffle(fillers)
    feature_sequence = [*fillers, *([repeated] * 6)]
    clean_labels = _outcomes(
        deleted, stage_index, [list(value) for value in feature_sequence]
    )
    labels = [
        1 - label if stage_index == 4 and index < 9 else label
        for index, label in enumerate(clean_labels)
    ]
    stage = deleted["stages"][stage_index]
    for event, features, label in zip(stage["events"], feature_sequence, labels):
        event["features"] = list(features)
        event["label"] = label
    contact_queries = [list(repeated) for _ in range(8)]
    heldout_queries = [list(repeated) for _ in range(7)] + [list(second)]
    stage["contact"] = {
        "queries": contact_queries,
        "outcomes": _outcomes(deleted, stage_index, contact_queries),
    }
    stage["heldout"] = {
        "queries": heldout_queries,
        "outcomes": _outcomes(deleted, stage_index, heldout_queries),
    }
    return {
        "stage": stage_index,
        "repeated_common_zero": list(repeated),
        "second_common_zero": list(second),
        "noise_count": 9 if stage_index == 4 else 0,
    }


def _full_suffix_deletion(
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deleted = copy.deepcopy(manifest)
    interventions = [_neutralize_stage(deleted, stage_index) for stage_index in (4, 5)]
    _validate_inherited(deleted)
    return deleted, interventions


def _full_suffix_rescue(
    deleted: dict[str, Any], base: dict[str, Any]
) -> dict[str, Any]:
    rescued = copy.deepcopy(deleted)
    for stage_index in (4, 5):
        rescued["stages"][stage_index] = copy.deepcopy(base["stages"][stage_index])
    _validate_inherited(rescued)
    return rescued


def analyze_full_suffix_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    _validate_inherited(manifest)
    base_tables = control_tables(manifest)
    base_grid = _error_grid(base_tables)
    base_witness = find_exact_witness(base_tables)
    base_signature = _witness_signature(base_witness)

    placebos = {}
    for name, placebo in (
        ("event_identity", _identity_placebo(manifest)),
        ("query_order", _query_order_placebo(manifest)),
    ):
        _validate_inherited(placebo)
        tables = control_tables(placebo)
        placebos[name] = {
            "schema_valid": True,
            "error_grid_invariant": _error_grid(tables) == base_grid,
            "witness_invariant": _witness_signature(find_exact_witness(tables))
            == base_signature,
        }

    replicated_ablations = {}
    for name, ablated in (
        ("stage_2_pre_harm", _swap_stage_blocks(manifest, 2, 12, 18)),
        ("stage_4_harm_correction", _swap_stage_blocks(manifest, 4, 12, 18)),
    ):
        _validate_inherited(ablated)
        tables = control_tables(ablated)
        replicated_ablations[name] = {
            "schema_valid": True,
            "exact_witness": find_exact_witness(tables) is not None,
        }

    deleted, interventions = _full_suffix_deletion(manifest)
    deleted_tables = control_tables(deleted)
    deleted_grid = _error_grid(deleted_tables)
    deleted_planned = _path_summary(
        _evaluate_path(deleted_tables, CONSTRUCTION_PLAN), deleted_tables, SCORING
    )
    deleted_witness = find_exact_witness(deleted_tables)
    route_complete = all(
        deleted_grid[stage_index][condition][split] == 0
        for stage_index in (4, 5)
        for condition in FIXED_CONDITIONS
        for split in ("contact", "heldout")
    )

    rescued = _full_suffix_rescue(deleted, manifest)
    rescued_tables = control_tables(rescued)
    rescued_witness = find_exact_witness(rescued_tables)
    return {
        "base_exact_witness": base_witness is not None,
        "base_witness_signature": base_signature,
        "placebos": placebos,
        "replicated_ablations": replicated_ablations,
        "canary_deletion": {
            "schema_valid": True,
            "interventions": interventions,
            "suffix_error_grids": {
                str(stage_index): deleted_grid[stage_index] for stage_index in (4, 5)
            },
            "route_complete": route_complete,
            "planned_path_passes": deleted_planned["passes"],
            "exact_witness": deleted_witness is not None,
        },
        "canary_rescue": {
            "schema_valid": True,
            "error_grid_invariant": _error_grid(rescued_tables) == base_grid,
            "witness_invariant": _witness_signature(rescued_witness) == base_signature,
        },
    }


def summarize_full_suffix(
    receipts: list[dict[str, Any]], exclusion_artifact_count: int
) -> dict[str, Any]:
    summary = summarize_calibration(receipts, exclusion_artifact_count=2)
    summary["experiment_id"] = EXPERIMENT_ID
    summary["purpose"] = "controller-only full-suffix E4 calibration"
    summary["promotion_gate"]["exclusion_artifacts"] = EXCLUSION_ARTIFACTS_REQUIRED
    summary["gates"]["exclusion_artifact_count"] = (
        exclusion_artifact_count == EXCLUSION_ARTIFACTS_REQUIRED
    )
    gate_renames = {
        "canary_deletion_schema": "full_suffix_deletion_schema",
        "canary_route_completeness": "full_suffix_route_completeness",
        "canary_planned_path_removed": "full_suffix_planned_path_removed",
        "canary_exact_witness_removed": "full_suffix_exact_witness_removed",
        "canary_rescue": "full_suffix_rescue",
    }
    for old, new in gate_renames.items():
        summary["gates"][new] = summary["gates"].pop(old)
    observations = summary["observations"]
    observations["full_suffix_deletion_exact_witness_survivors"] = observations.pop(
        "canary_deletion_exact_witness_survivors"
    )
    observations["full_suffix_rescue_count"] = observations.pop("canary_rescue_count")
    summary["promote_e4"] = all(summary["gates"].values())
    return summary


def run_full_suffix_calibration(
    *,
    tasks: int = ANCHOR_TASKS,
    master_seed: str | None = None,
    excluded_semantic: set[str],
    excluded_rules: set[str],
    exclusion_artifact_count: int,
) -> dict[str, Any]:
    if tasks <= 0:
        raise ValueError("full-suffix task count must be positive")
    master_seed = master_seed or secrets.token_hex(16)
    task_seeds = [
        hashlib.sha256(f"{master_seed}:ot0019:{index}".encode()).hexdigest()[:32]
        for index in range(tasks)
    ]
    receipts = []
    for seed in task_seeds:
        item = construct_direct_manifest(seed)
        receipt = {"manifest": item["manifest"], **item["receipt"]}
        receipt["excluded_semantic_collision"] = (
            receipt["semantic_fingerprint"] in excluded_semantic
            if receipt["success"]
            else False
        )
        receipt["excluded_rule_collision"] = (
            receipt["rule_profile"] in excluded_rules if receipt["success"] else False
        )
        receipt["calibration_analysis"] = (
            analyze_full_suffix_manifest(receipt["manifest"])
            if receipt["success"]
            else None
        )
        receipts.append(receipt)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "study": "full-suffix-e4-calibration-v1",
        "candidate_outputs_present": False,
        "master_seed": master_seed,
        "excluded_prior_counts": {
            "artifacts": exclusion_artifact_count,
            "semantic_fingerprints": len(excluded_semantic),
            "rule_profiles": len(excluded_rules),
        },
        "receipts": receipts,
        "summary": summarize_full_suffix(receipts, exclusion_artifact_count),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=ANCHOR_TASKS)
    parser.add_argument("--seed")
    parser.add_argument("--exclude", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    semantic, rules = load_exclusions(args.exclude)
    result = run_full_suffix_calibration(
        tasks=args.samples,
        master_seed=args.seed,
        excluded_semantic=semantic,
        excluded_rules=rules,
        exclusion_artifact_count=len(args.exclude),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
