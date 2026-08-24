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
    ANCHOR_MAX_ABLATION_WITNESS_FRACTION,
    ANCHOR_TASKS,
    CONSTRUCTION_PLAN,
    DIRECT_CONSTRUCTION_GATE,
    DIRECT_CONSTRUCTION_MAX_EVALUATIONS,
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


EXPERIMENT_ID = "OT-0018"
EXCLUSION_ARTIFACTS_REQUIRED = 2


def _path_complete_canary_deletion(
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    deleted = copy.deepcopy(manifest)
    archive = archive_through_stage(deleted, 5)
    queries = [list(value) for value in FEATURE_VECTORS]
    first_ids = fixed_selection("fixed-first-seen-verbatim", archive, queries, 6)
    first_predictions = deterministic_predictions(
        selected_events(archive, first_ids), queries
    )
    truth = _outcomes(deleted, 5, queries)
    common_zeros = [
        value
        for value, prediction, outcome in zip(FEATURE_VECTORS, first_predictions, truth)
        if prediction == 0 and outcome == 0
    ]
    if len(common_zeros) < 2:
        raise ValueError("path-complete canary deletion needs two common zeros")
    rng = random.Random(
        int(hashlib.sha256(f"{deleted['salt']}:canary-delete".encode()).hexdigest(), 16)
    )
    rng.shuffle(common_zeros)
    repeated, second = common_zeros[:2]
    missing = [value for value in FEATURE_VECTORS if value != repeated]
    fillers = [*missing, *rng.choices(list(FEATURE_VECTORS), k=3)]
    rng.shuffle(fillers)
    feature_sequence = [*fillers, *([repeated] * 6)]
    stage = deleted["stages"][5]
    labels = _outcomes(deleted, 5, [list(value) for value in feature_sequence])
    for event, features, label in zip(stage["events"], feature_sequence, labels):
        event["features"] = list(features)
        event["label"] = label
    contact_queries = [list(repeated) for _ in range(8)]
    heldout_queries = [list(repeated) for _ in range(7)] + [list(second)]
    stage["contact"] = {
        "queries": contact_queries,
        "outcomes": _outcomes(deleted, 5, contact_queries),
    }
    stage["heldout"] = {
        "queries": heldout_queries,
        "outcomes": _outcomes(deleted, 5, heldout_queries),
    }
    _validate_inherited(deleted)
    return deleted, {
        "repeated_common_zero": list(repeated),
        "second_common_zero": list(second),
    }


def _paired_canary_rescue(
    deleted: dict[str, Any], base: dict[str, Any]
) -> dict[str, Any]:
    rescued = copy.deepcopy(deleted)
    rescued["stages"][5] = copy.deepcopy(base["stages"][5])
    _validate_inherited(rescued)
    return rescued


def analyze_calibration_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
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

    deleted, intervention = _path_complete_canary_deletion(manifest)
    deleted_tables = control_tables(deleted)
    deleted_stage_five = _error_grid(deleted_tables)[5]
    deleted_planned = _path_summary(
        _evaluate_path(deleted_tables, CONSTRUCTION_PLAN), deleted_tables, SCORING
    )
    deleted_witness = find_exact_witness(deleted_tables)
    route_complete = all(
        deleted_stage_five[condition][split] == 0
        for condition in FIXED_CONDITIONS
        for split in ("contact", "heldout")
    )

    rescued = _paired_canary_rescue(deleted, manifest)
    rescued_tables = control_tables(rescued)
    rescued_witness = find_exact_witness(rescued_tables)
    return {
        "base_exact_witness": base_witness is not None,
        "base_witness_signature": base_signature,
        "placebos": placebos,
        "replicated_ablations": replicated_ablations,
        "canary_deletion": {
            "schema_valid": True,
            "intervention": intervention,
            "stage_5_error_grid": deleted_stage_five,
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


def summarize_calibration(
    receipts: list[dict[str, Any]], exclusion_artifact_count: int
) -> dict[str, Any]:
    if not receipts:
        raise ValueError("path-complete calibration requires receipts")
    successes = [receipt for receipt in receipts if receipt["success"]]
    analyses = [receipt["calibration_analysis"] for receipt in successes]
    evaluations = sorted(receipt["evaluations"] for receipt in receipts)
    p95_index = max(0, (95 * len(evaluations) + 99) // 100 - 1)
    mean_evaluations = sum(evaluations) / len(evaluations)
    semantic = {receipt["semantic_fingerprint"] for receipt in successes}
    rules = {receipt["rule_profile"] for receipt in successes}
    ablation_names = ("stage_2_pre_harm", "stage_4_harm_correction")
    ablation_survivors = {
        name: sum(
            analysis["replicated_ablations"][name]["exact_witness"]
            for analysis in analyses
        )
        for name in ablation_names
    }
    denominator = len(analyses) or 1
    ablation_fractions = {
        name: survivors / denominator for name, survivors in ablation_survivors.items()
    }
    gates = {
        "exclusion_artifact_count": exclusion_artifact_count
        == EXCLUSION_ARTIFACTS_REQUIRED,
        "task_count": len(receipts) == ANCHOR_TASKS,
        "base_success_count": len(successes) == ANCHOR_TASKS,
        "no_prior_semantic_reuse": all(
            not receipt["excluded_semantic_collision"] for receipt in successes
        ),
        "no_prior_rule_reuse": all(
            not receipt["excluded_rule_collision"] for receipt in successes
        ),
        "unique_semantic_manifests": len(semantic) == len(successes),
        "unique_rule_profiles": len(rules) == len(successes),
        "split_query_separation": all(
            receipt["split_queries_separated"] for receipt in successes
        ),
        "inherited_schema": all(receipt["schema_valid"] for receipt in successes),
        "planned_witnesses": all(
            receipt["planned_witness"]["passes"] for receipt in successes
        ),
        "exact_witnesses": all(analysis["base_exact_witness"] for analysis in analyses),
        "mean_evaluations": mean_evaluations
        <= DIRECT_CONSTRUCTION_GATE["maximum_mean_evaluations"],
        "p95_evaluations": evaluations[p95_index]
        <= DIRECT_CONSTRUCTION_GATE["maximum_p95_evaluations"],
        "evaluation_budget": max(evaluations) <= DIRECT_CONSTRUCTION_MAX_EVALUATIONS,
        "event_identity_placebo": all(
            analysis["placebos"]["event_identity"]["schema_valid"]
            and analysis["placebos"]["event_identity"]["error_grid_invariant"]
            and analysis["placebos"]["event_identity"]["witness_invariant"]
            for analysis in analyses
        ),
        "query_order_placebo": all(
            analysis["placebos"]["query_order"]["schema_valid"]
            and analysis["placebos"]["query_order"]["error_grid_invariant"]
            and analysis["placebos"]["query_order"]["witness_invariant"]
            for analysis in analyses
        ),
        "replicated_ablation_schema": all(
            analysis["replicated_ablations"][name]["schema_valid"]
            for analysis in analyses
            for name in ablation_names
        ),
        **{
            f"{name}_exact_sensitivity": fraction
            <= ANCHOR_MAX_ABLATION_WITNESS_FRACTION
            for name, fraction in ablation_fractions.items()
        },
        "canary_deletion_schema": all(
            analysis["canary_deletion"]["schema_valid"] for analysis in analyses
        ),
        "canary_route_completeness": all(
            analysis["canary_deletion"]["route_complete"] for analysis in analyses
        ),
        "canary_planned_path_removed": all(
            not analysis["canary_deletion"]["planned_path_passes"]
            for analysis in analyses
        ),
        "canary_exact_witness_removed": all(
            not analysis["canary_deletion"]["exact_witness"] for analysis in analyses
        ),
        "canary_rescue": all(
            analysis["canary_rescue"]["schema_valid"]
            and analysis["canary_rescue"]["error_grid_invariant"]
            and analysis["canary_rescue"]["witness_invariant"]
            for analysis in analyses
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "controller-only path-complete E4 calibration",
        "candidate_outputs_present": False,
        "promotion_gate": {
            "tasks": ANCHOR_TASKS,
            "exclusion_artifacts": EXCLUSION_ARTIFACTS_REQUIRED,
            "maximum_ablation_witness_fraction": ANCHOR_MAX_ABLATION_WITNESS_FRACTION,
            "construction": DIRECT_CONSTRUCTION_GATE,
        },
        "observations": {
            "base_success_count": len(successes),
            "mean_evaluations": mean_evaluations,
            "p95_evaluations": evaluations[p95_index],
            "maximum_evaluations": max(evaluations),
            "unique_semantic_manifests": len(semantic),
            "unique_rule_profiles": len(rules),
            "replicated_ablation_exact_witness_survivors": ablation_survivors,
            "replicated_ablation_exact_witness_fractions": ablation_fractions,
            "canary_deletion_exact_witness_survivors": sum(
                analysis["canary_deletion"]["exact_witness"] for analysis in analyses
            ),
            "canary_rescue_count": sum(
                analysis["canary_rescue"]["witness_invariant"] for analysis in analyses
            ),
        },
        "gates": gates,
        "promote_e4": all(gates.values()),
    }


def load_exclusions(paths: list[Path]) -> tuple[set[str], set[str]]:
    semantic: set[str] = set()
    rules: set[str] = set()
    for path in paths:
        study = json.loads(path.read_text(encoding="utf-8"))
        receipts = study.get("receipts")
        if not isinstance(receipts, list) or not receipts:
            raise ValueError("exclusion artifact has no receipts")
        successful = [receipt for receipt in receipts if receipt.get("success")]
        semantic.update(receipt["semantic_fingerprint"] for receipt in successful)
        rules.update(receipt["rule_profile"] for receipt in successful)
    if not semantic or not rules:
        raise ValueError("exclusion artifacts have no successful identities")
    return semantic, rules


def run_calibration(
    *,
    tasks: int = ANCHOR_TASKS,
    master_seed: str | None = None,
    excluded_semantic: set[str],
    excluded_rules: set[str],
    exclusion_artifact_count: int,
) -> dict[str, Any]:
    if tasks <= 0:
        raise ValueError("calibration task count must be positive")
    master_seed = master_seed or secrets.token_hex(16)
    task_seeds = [
        hashlib.sha256(f"{master_seed}:ot0018:{index}".encode()).hexdigest()[:32]
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
            analyze_calibration_manifest(receipt["manifest"])
            if receipt["success"]
            else None
        )
        receipts.append(receipt)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "study": "path-complete-e4-calibration-v1",
        "candidate_outputs_present": False,
        "master_seed": master_seed,
        "excluded_prior_counts": {
            "artifacts": exclusion_artifact_count,
            "semantic_fingerprints": len(excluded_semantic),
            "rule_profiles": len(excluded_rules),
        },
        "receipts": receipts,
        "summary": summarize_calibration(receipts, exclusion_artifact_count),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=ANCHOR_TASKS)
    parser.add_argument("--seed")
    parser.add_argument("--exclude", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    semantic, rules = load_exclusions(args.exclude)
    result = run_calibration(
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
