from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0005_world import (
    archive_through_stage,
    deterministic_predictions,
    fixed_selection,
    generate_task_manifest,
    selected_events,
    validate_task_manifest,
)


EXPERIMENT_ID = "OT-0016"
CONDITIONS = (
    "fixed-most-recent",
    "fixed-first-seen-verbatim",
    "fixed-naive-nearest",
    "no-persistence",
)
SAMPLES = 256
VIABILITY_GATE = {
    "minimum_mean_dynamic_advantage": 2.0,
    "minimum_fraction_dynamic_advantage_at_least_two": 0.75,
    "maximum_single_static_winner_share": 0.75,
    "minimum_fraction_with_harm_and_contact_recovery": 0.65,
    "maximum_mean_contact_choice_regret": 2.0,
}
CONSTRAINED_SAMPLES = 64
CONSTRAINED_MAX_ATTEMPTS = 128
CONSTRAINED_MANIFEST_GATE = {
    "minimum_dynamic_advantage": 4,
    "maximum_contact_choice_regret": 2,
    "minimum_harm_and_contact_recovery_transitions": 1,
    "minimum_contact_advantage_over_best_static": 2,
}
CONSTRAINED_STUDY_GATE = {
    "maximum_p95_attempts": 40,
    "maximum_mean_attempts": 20,
}


def _errors(
    condition: str,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
) -> int:
    identities = fixed_selection(condition, archive, queries, limit)
    predictions = deterministic_predictions(selected_events(archive, identities), queries)
    return sum(prediction != outcome for prediction, outcome in zip(predictions, outcomes))


def analyze_manifest(manifest: dict[str, Any], *, limit: int = 6) -> dict[str, Any]:
    validate_task_manifest(manifest)
    stages: list[dict[str, Any]] = []
    fixed_totals = {condition: 0 for condition in CONDITIONS}
    prior_contact_choice: str | None = None
    harm_and_recovery = 0
    contact_selected_total = 0
    stage_oracle_total = 0

    for stage_index, stage in enumerate(manifest["stages"]):
        archive = archive_through_stage(manifest, stage_index)
        contact_errors = {
            condition: _errors(
                condition,
                archive,
                stage["contact"]["queries"],
                stage["contact"]["outcomes"],
                limit,
            )
            for condition in CONDITIONS
        }
        heldout_errors = {
            condition: _errors(
                condition,
                archive,
                stage["heldout"]["queries"],
                stage["heldout"]["outcomes"],
                limit,
            )
            for condition in CONDITIONS
        }
        for condition, errors in heldout_errors.items():
            fixed_totals[condition] += errors
        contact_choice = min(CONDITIONS, key=lambda item: (contact_errors[item], item))
        heldout_minimum = min(heldout_errors.values())
        heldout_winners = sorted(
            condition for condition, errors in heldout_errors.items() if errors == heldout_minimum
        )
        contact_selected_total += heldout_errors[contact_choice]
        stage_oracle_total += heldout_minimum
        prior_regret = None
        recovery = None
        if prior_contact_choice is not None:
            prior_regret = heldout_errors[prior_contact_choice] - heldout_minimum
            recovery = heldout_errors[prior_contact_choice] - heldout_errors[contact_choice]
            if prior_regret >= 2 and recovery >= 2:
                harm_and_recovery += 1
        stages.append(
            {
                "stage": stage_index,
                "contact_errors": contact_errors,
                "heldout_errors": heldout_errors,
                "contact_choice": contact_choice,
                "heldout_winners": heldout_winners,
                "prior_choice_regret": prior_regret,
                "contact_recovery": recovery,
            }
        )
        prior_contact_choice = contact_choice

    best_static_total = min(fixed_totals.values())
    best_static_conditions = sorted(
        condition for condition, errors in fixed_totals.items() if errors == best_static_total
    )
    return {
        "task_manifest_sha256": sha256_bytes(canonical_json(manifest)),
        "fixed_totals": fixed_totals,
        "best_static_total": best_static_total,
        "best_static_conditions": best_static_conditions,
        "stage_oracle_total": stage_oracle_total,
        "dynamic_advantage": best_static_total - stage_oracle_total,
        "contact_selected_total": contact_selected_total,
        "contact_choice_regret": contact_selected_total - stage_oracle_total,
        "harm_and_contact_recovery_transitions": harm_and_recovery,
        "stages": stages,
    }


def summarize(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    if not analyses:
        raise ValueError("power study requires at least one manifest")
    count = len(analyses)
    winner_counts: Counter[str] = Counter()
    for analysis in analyses:
        for condition in analysis["best_static_conditions"]:
            winner_counts[condition] += 1
    mean_dynamic_advantage = mean(item["dynamic_advantage"] for item in analyses)
    fraction_dynamic = sum(item["dynamic_advantage"] >= 2 for item in analyses) / count
    winner_shares = {
        condition: winner_counts[condition] / count for condition in CONDITIONS
    }
    maximum_winner_share = max(winner_shares.values())
    fraction_harm_recovery = sum(
        item["harm_and_contact_recovery_transitions"] >= 1 for item in analyses
    ) / count
    mean_contact_regret = mean(item["contact_choice_regret"] for item in analyses)
    gates = {
        "sample_count": count == SAMPLES,
        "dynamic_advantage_mean": mean_dynamic_advantage
        >= VIABILITY_GATE["minimum_mean_dynamic_advantage"],
        "dynamic_advantage_frequency": fraction_dynamic
        >= VIABILITY_GATE["minimum_fraction_dynamic_advantage_at_least_two"],
        "no_dominant_static_winner": maximum_winner_share
        <= VIABILITY_GATE["maximum_single_static_winner_share"],
        "harm_and_contact_recovery_frequency": fraction_harm_recovery
        >= VIABILITY_GATE["minimum_fraction_with_harm_and_contact_recovery"],
        "contact_choice_regret": mean_contact_regret
        <= VIABILITY_GATE["maximum_mean_contact_choice_regret"],
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "controller-only task-family viability; no candidate actor outputs",
        "sample_count": count,
        "viability_gate": VIABILITY_GATE,
        "observations": {
            "mean_dynamic_advantage": mean_dynamic_advantage,
            "fraction_dynamic_advantage_at_least_two": fraction_dynamic,
            "static_winner_shares": winner_shares,
            "maximum_static_winner_share": maximum_winner_share,
            "fraction_with_harm_and_contact_recovery": fraction_harm_recovery,
            "mean_contact_choice_regret": mean_contact_regret,
            "mean_fixed_total_errors": {
                condition: mean(item["fixed_totals"][condition] for item in analyses)
                for condition in CONDITIONS
            },
            "mean_stage_oracle_total": mean(item["stage_oracle_total"] for item in analyses),
            "mean_contact_selected_total": mean(
                item["contact_selected_total"] for item in analyses
            ),
        },
        "gates": gates,
        "viable": all(gates.values()),
    }


def constrained_manifest_gates(analysis: dict[str, Any]) -> dict[str, bool]:
    return {
        "dynamic_advantage": analysis["dynamic_advantage"]
        >= CONSTRAINED_MANIFEST_GATE["minimum_dynamic_advantage"],
        "contact_choice_regret": analysis["contact_choice_regret"]
        <= CONSTRAINED_MANIFEST_GATE["maximum_contact_choice_regret"],
        "harm_and_contact_recovery": analysis["harm_and_contact_recovery_transitions"]
        >= CONSTRAINED_MANIFEST_GATE["minimum_harm_and_contact_recovery_transitions"],
        "contact_advantage_over_best_static": analysis["best_static_total"]
        - analysis["contact_selected_total"]
        >= CONSTRAINED_MANIFEST_GATE["minimum_contact_advantage_over_best_static"],
    }


def generate_constrained_manifest(
    *, max_attempts: int = CONSTRAINED_MAX_ATTEMPTS
) -> dict[str, Any]:
    if max_attempts <= 0:
        raise ValueError("maximum attempts must be positive")
    rejected: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        manifest = generate_task_manifest()
        analysis = analyze_manifest(manifest)
        gates = constrained_manifest_gates(analysis)
        if all(gates.values()):
            return {
                "attempts": attempt,
                "manifest": manifest,
                "analysis": analysis,
                "gates": gates,
                "rejected": rejected,
            }
        rejected.append(
            {
                "task_manifest_sha256": analysis["task_manifest_sha256"],
                "dynamic_advantage": analysis["dynamic_advantage"],
                "contact_choice_regret": analysis["contact_choice_regret"],
                "harm_and_contact_recovery_transitions": analysis[
                    "harm_and_contact_recovery_transitions"
                ],
                "contact_advantage_over_best_static": analysis["best_static_total"]
                - analysis["contact_selected_total"],
                "gates": gates,
            }
        )
    raise RuntimeError("constrained world sampler exhausted its attempt budget")


def summarize_constrained(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    if not receipts:
        raise ValueError("constrained sampler study requires at least one receipt")
    attempts = sorted(receipt["attempts"] for receipt in receipts)
    p95_attempts = attempts[math.ceil(0.95 * len(attempts)) - 1]
    manifest_hashes = [receipt["analysis"]["task_manifest_sha256"] for receipt in receipts]
    all_manifest_gates = all(all(receipt["gates"].values()) for receipt in receipts)
    gates = {
        "sample_count": len(receipts) == CONSTRAINED_SAMPLES,
        "all_manifests_admissible": all_manifest_gates,
        "all_manifest_identities_unique": len(set(manifest_hashes)) == len(manifest_hashes),
        "p95_attempts": p95_attempts
        <= CONSTRAINED_STUDY_GATE["maximum_p95_attempts"],
        "mean_attempts": mean(attempts)
        <= CONSTRAINED_STUDY_GATE["maximum_mean_attempts"],
        "attempt_budget": max(attempts) <= CONSTRAINED_MAX_ATTEMPTS,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "controller-only constrained-world feasibility; no candidate actor outputs",
        "sample_count": len(receipts),
        "manifest_gate": CONSTRAINED_MANIFEST_GATE,
        "study_gate": CONSTRAINED_STUDY_GATE,
        "observations": {
            "mean_attempts": mean(attempts),
            "p95_attempts": p95_attempts,
            "maximum_attempts": max(attempts),
            "total_rejected_manifests": sum(len(receipt["rejected"]) for receipt in receipts),
            "mean_dynamic_advantage": mean(
                receipt["analysis"]["dynamic_advantage"] for receipt in receipts
            ),
            "mean_contact_choice_regret": mean(
                receipt["analysis"]["contact_choice_regret"] for receipt in receipts
            ),
            "mean_contact_advantage_over_best_static": mean(
                receipt["analysis"]["best_static_total"]
                - receipt["analysis"]["contact_selected_total"]
                for receipt in receipts
            ),
        },
        "gates": gates,
        "viable": all(gates.values()),
    }


def run_power_study(samples: int = SAMPLES) -> dict[str, Any]:
    if samples <= 0:
        raise ValueError("sample count must be positive")
    manifests = [generate_task_manifest() for _ in range(samples)]
    analyses = [analyze_manifest(manifest) for manifest in manifests]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "study": "inherited-world-fixed-control-power-v1",
        "candidate_outputs_present": False,
        "manifests": manifests,
        "analyses": analyses,
        "summary": summarize(analyses),
    }


def run_constrained_sampler_study(
    samples: int = CONSTRAINED_SAMPLES,
) -> dict[str, Any]:
    if samples <= 0:
        raise ValueError("sample count must be positive")
    receipts = [generate_constrained_manifest() for _ in range(samples)]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "study": "constrained-world-sampler-v1",
        "candidate_outputs_present": False,
        "receipts": receipts,
        "summary": summarize_constrained(receipts),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("unconditioned", "constrained"), default="unconditioned"
    )
    parser.add_argument("--samples", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "constrained":
        result = run_constrained_sampler_study(args.samples or CONSTRAINED_SAMPLES)
    else:
        result = run_power_study(args.samples or SAMPLES)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
