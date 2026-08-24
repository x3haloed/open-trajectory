from __future__ import annotations

import argparse
import copy
import json
import random
import secrets
from itertools import product
from pathlib import Path
from typing import Any

from .ot0004_world import (
    FEATURE_VECTORS,
    STAGE_KINDS,
    archive_through_stage,
    fixed_selection,
    rule_label,
    selected_events,
    validate_task_manifest,
)
from .ot0005_world import deterministic_predictions, generate_task_manifest
from .ot0016 import FIXED_CONDITIONS


EXPERIMENT_ID = "OT-0017"
SAMPLES = 256
INCIDENCE_GATE = {
    "minimum_exact_witness_fraction": 0.05,
    "minimum_unique_manifests": 256,
}
SCORING = {
    "useful_pre_harm_commits_required": 2,
    "committed_over_unchanged_error_advantage_per_revision": 2,
    "learned_selector_harm_over_protected_parent_required": 2,
    "correction_error_recovery_required": 3,
    "corrected_selector_errors_allowed": 1,
    "post_correction_canary_advantage_required": 2,
    "committed_lineage_errors_allowed": 8,
    "committed_lineage_advantage_over_each_fixed_control_required": 6,
}
SEED = "seed-no-persistence"
CONSTRUCTION_PLAN = (
    "fixed-first-seen-verbatim",
    "fixed-naive-nearest",
    "fixed-most-recent",
    "fixed-most-recent",
    "no-persistence",
    "fixed-most-recent",
)
CONSTRUCTION_TASKS = 16
CONSTRUCTION_MAX_EVALUATIONS = 20_000
CONSTRUCTION_GATE = {
    "required_successes": 16,
    "maximum_mean_evaluations": 5_000,
    "maximum_p95_evaluations": 10_000,
}


def control_tables(manifest: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for stage_index, stage in enumerate(manifest["stages"]):
        archive = archive_through_stage(manifest, stage_index)
        conditions: dict[str, dict[str, Any]] = {}
        for condition in FIXED_CONDITIONS:
            condition_record: dict[str, Any] = {}
            for split in ("contact", "heldout"):
                queries = stage[split]["queries"]
                outcomes = stage[split]["outcomes"]
                identities = fixed_selection(condition, archive, queries, limit)
                predictions = deterministic_predictions(
                    selected_events(archive, identities), queries
                )
                condition_record[split] = {
                    "selected_event_ids": identities,
                    "errors": sum(
                        prediction != outcome
                        for prediction, outcome in zip(predictions, outcomes)
                    ),
                }
            conditions[condition] = condition_record
        tables.append({"stage": stage_index, "conditions": conditions})
    return tables


def _mode_split(table: dict[str, Any], mode: str, split: str) -> dict[str, Any]:
    if mode == SEED:
        return table["conditions"]["no-persistence"][split]
    return table["conditions"][mode][split]


def _selection_changed(
    table: dict[str, Any], left: str, right: str, split: str
) -> bool:
    return (
        _mode_split(table, left, split)["selected_event_ids"]
        != _mode_split(table, right, split)["selected_event_ids"]
    )


def _evaluate_path(
    tables: list[dict[str, Any]], proposals: tuple[str, ...]
) -> dict[str, Any]:
    snapshots = [SEED]
    records: list[dict[str, Any]] = []
    for table, proposal in zip(tables, proposals):
        current = snapshots[-1]
        parent = snapshots[-2] if len(snapshots) > 1 else current
        current_contact = _mode_split(table, current, "contact")["errors"]
        challenger_contact = _mode_split(table, proposal, "contact")["errors"]
        contact_advantage = current_contact - challenger_contact
        changed = proposal != current and contact_advantage > 0
        committed = proposal if changed else current
        if changed:
            snapshots.append(committed)
        committed_heldout = _mode_split(table, committed, "heldout")["errors"]
        current_heldout = _mode_split(table, current, "heldout")["errors"]
        parent_heldout = _mode_split(table, parent, "heldout")["errors"]
        records.append(
            {
                "stage": table["stage"],
                "current": current,
                "parent": parent,
                "proposal": proposal,
                "committed": committed,
                "commit_changed": changed,
                "contact_advantage": contact_advantage,
                "heldout_advantage": current_heldout - committed_heldout,
                "harm_over_parent": current_heldout - parent_heldout,
                "committed_errors": committed_heldout,
                "current_errors": current_heldout,
                "parent_errors": parent_heldout,
                "selection_changed": _selection_changed(
                    table, committed, current, "heldout"
                ),
                "parent_selection_changed": _selection_changed(
                    table, current, parent, "heldout"
                ),
            }
        )
    return {"proposals": proposals, "snapshots": snapshots, "records": records}


def _path_summary(
    path: dict[str, Any], tables: list[dict[str, Any]], scoring: dict[str, int]
) -> dict[str, Any]:
    records = path["records"]
    useful = [
        record
        for record in records[1:]
        if record["commit_changed"]
        and record["selection_changed"]
        and record["contact_advantage"] > 0
        and record["heldout_advantage"]
        >= scoring["committed_over_unchanged_error_advantage_per_revision"]
    ]
    chains = []
    for correction in records[1:]:
        if not (
            correction["parent_selection_changed"]
            and correction["harm_over_parent"]
            >= scoring["learned_selector_harm_over_protected_parent_required"]
            and correction["commit_changed"]
            and correction["selection_changed"]
            and correction["contact_advantage"] > 0
            and correction["heldout_advantage"]
            >= scoring["correction_error_recovery_required"]
            and correction["committed_errors"]
            <= scoring["corrected_selector_errors_allowed"]
        ):
            continue
        useful_before = [
            record for record in useful if record["stage"] < correction["stage"]
        ]
        canaries = [
            record
            for record in useful
            if record["stage"] > correction["stage"]
            and record["heldout_advantage"]
            >= scoring["post_correction_canary_advantage_required"]
        ]
        if (
            len(useful_before) >= scoring["useful_pre_harm_commits_required"]
            and canaries
        ):
            chains.append(
                {
                    "harm_and_correction_stage": correction["stage"],
                    "useful_pre_harm_stages": [item["stage"] for item in useful_before],
                    "canary_stage": canaries[0]["stage"],
                }
            )
    lineage_errors = sum(record["committed_errors"] for record in records)
    fixed_totals = {
        condition: sum(
            table["conditions"][condition]["heldout"]["errors"] for table in tables
        )
        for condition in FIXED_CONDITIONS
    }
    gates = {
        "temporal_chain": bool(chains),
        "lineage_absolute": lineage_errors
        <= scoring["committed_lineage_errors_allowed"],
        "lineage_comparative": all(
            errors - lineage_errors
            >= scoring["committed_lineage_advantage_over_each_fixed_control_required"]
            for errors in fixed_totals.values()
        ),
    }
    return {
        **path,
        "chains": chains,
        "lineage_errors": lineage_errors,
        "fixed_totals": fixed_totals,
        "gates": gates,
        "passes": all(gates.values()),
    }


def find_exact_witness(
    tables: list[dict[str, Any]], scoring: dict[str, int] = SCORING
) -> dict[str, Any] | None:
    if len(tables) != 6:
        raise ValueError("the E4 opportunity oracle requires six stages")
    witnesses = []
    for proposals in product(FIXED_CONDITIONS, repeat=len(tables)):
        summary = _path_summary(_evaluate_path(tables, proposals), tables, scoring)
        if summary["passes"]:
            witnesses.append(summary)
    if not witnesses:
        return None
    return min(
        witnesses,
        key=lambda item: (
            item["lineage_errors"],
            len(item["snapshots"]),
            item["proposals"],
        ),
    )


def construction_penalty(tables: list[dict[str, Any]]) -> int:
    summary = _path_summary(
        _evaluate_path(tables, CONSTRUCTION_PLAN), tables, SCORING
    )
    records = summary["records"]
    penalty = 0
    expected_current = (SEED, *CONSTRUCTION_PLAN[:-1])
    for record, expected in zip(records, expected_current):
        penalty += 20 * (record["current"] != expected)
    for stage in (0, 1, 2, 4, 5):
        record = records[stage]
        penalty += 20 * (not record["commit_changed"])
        penalty += 10 * (not record["selection_changed"])
        penalty += max(0, 1 - record["contact_advantage"])
    for stage in (1, 2, 5):
        penalty += max(
            0,
            SCORING["committed_over_unchanged_error_advantage_per_revision"]
            - records[stage]["heldout_advantage"],
        )
    correction = records[4]
    penalty += 10 * (not correction["parent_selection_changed"])
    penalty += max(
        0,
        SCORING["learned_selector_harm_over_protected_parent_required"]
        - correction["harm_over_parent"],
    )
    penalty += max(
        0,
        SCORING["correction_error_recovery_required"]
        - correction["heldout_advantage"],
    )
    penalty += max(
        0,
        correction["committed_errors"] - SCORING["corrected_selector_errors_allowed"],
    )
    penalty += max(
        0,
        SCORING["post_correction_canary_advantage_required"]
        - records[5]["heldout_advantage"],
    )
    penalty += max(
        0, summary["lineage_errors"] - SCORING["committed_lineage_errors_allowed"]
    )
    penalty += sum(
        max(
            0,
            SCORING["committed_lineage_advantage_over_each_fixed_control_required"]
            - (errors - summary["lineage_errors"]),
        )
        for errors in summary["fixed_totals"].values()
    )
    if summary["passes"]:
        return 0
    return max(1, penalty)


def _renumber_events(manifest: dict[str, Any]) -> None:
    sequence = 0
    for stage in manifest["stages"]:
        for event in stage["events"]:
            event["sequence"] = sequence
            sequence += 1


def _stage_rule(manifest: dict[str, Any], stage_index: int) -> tuple[list[int], int, set[tuple[int, ...]]]:
    kind = STAGE_KINDS[stage_index]
    mask_index = 0 if stage_index < 2 else (1 if stage_index < 5 else 2)
    exceptions = (
        {tuple(value) for value in manifest["rules"]["exceptions"]}
        if kind == "exceptions"
        else set()
    )
    return (
        manifest["rules"]["masks"][mask_index],
        manifest["rules"]["biases"][mask_index],
        exceptions,
    )


def _outcomes(
    manifest: dict[str, Any], stage_index: int, queries: list[list[int]]
) -> list[int]:
    mask, bias, exceptions = _stage_rule(manifest, stage_index)
    return [
        rule_label(
            tuple(query),
            mask=tuple(mask),
            bias=bias,
            exceptions=exceptions,
        )
        for query in queries
    ]


def _mutate_manifest(
    manifest: dict[str, Any], rng: random.Random
) -> dict[str, Any]:
    changed = copy.deepcopy(manifest)
    stage_index = rng.randrange(6)
    stage = changed["stages"][stage_index]
    mutation = rng.choice(("events", "contact", "heldout"))
    if mutation == "events":
        mask, bias, exceptions = _stage_rule(changed, stage_index)
        features = list(FEATURE_VECTORS)
        features.extend(rng.choices(list(FEATURE_VECTORS), k=8))
        rng.shuffle(features)
        noisy = set(rng.sample(range(24), 9)) if stage_index == 4 else set()
        events = []
        for index, vector in enumerate(features):
            clean = rule_label(
                vector,
                mask=tuple(mask),
                bias=bias,
                exceptions=exceptions,
            )
            events.append(
                {
                    "event_id": f"event-{secrets.token_hex(6)}",
                    "sequence": 0,
                    "features": list(vector),
                    "label": 1 - clean if index in noisy else clean,
                }
            )
        stage["events"] = events
        _renumber_events(changed)
    else:
        queries = [list(value) for value in rng.sample(list(FEATURE_VECTORS), 8)]
        stage[mutation] = {
            "queries": queries,
            "outcomes": _outcomes(changed, stage_index, queries),
        }
    return changed


def construct_manifest(max_evaluations: int = CONSTRUCTION_MAX_EVALUATIONS) -> dict[str, Any]:
    if max_evaluations <= 0:
        raise ValueError("construction evaluation budget must be positive")
    seed = secrets.token_hex(16)
    rng = random.Random(int(seed, 16))
    population = [generate_task_manifest() for _ in range(32)]
    evaluations = 0
    best_penalty: int | None = None
    while evaluations < max_evaluations:
        scored = []
        for manifest in population:
            tables = control_tables(manifest)
            penalty = construction_penalty(tables)
            evaluations += 1
            scored.append((penalty, manifest, tables))
            if penalty == 0:
                inherited = dict(manifest)
                inherited["experiment_id"] = "OT-0004"
                validate_task_manifest(inherited)
                witness = find_exact_witness(tables)
                if witness is None:
                    raise RuntimeError("zero-penalty construction lacks exact witness")
                return {
                    "manifest": manifest,
                    "receipt": {
                        "success": True,
                        "constructor": "bounded-stage-mutation-v1",
                        "seed": seed,
                        "evaluations": evaluations,
                        "maximum_evaluations": max_evaluations,
                        "planned_modes": CONSTRUCTION_PLAN,
                        "exact_witness": witness,
                    },
                }
            if evaluations >= max_evaluations:
                break
        scored.sort(key=lambda item: item[0])
        best_penalty = scored[0][0] if scored else best_penalty
        elites = [item[1] for item in scored[:8]]
        population = [copy.deepcopy(item) for item in elites]
        while len(population) < 32:
            if rng.random() < 0.1:
                population.append(generate_task_manifest())
            else:
                candidate = copy.deepcopy(rng.choice(elites))
                for _ in range(1 if rng.random() < 0.8 else 2):
                    candidate = _mutate_manifest(candidate, rng)
                population.append(candidate)
    return {
        "manifest": None,
        "receipt": {
            "success": False,
            "constructor": "bounded-stage-mutation-v1",
            "seed": seed,
            "evaluations": max_evaluations,
            "maximum_evaluations": max_evaluations,
            "planned_modes": CONSTRUCTION_PLAN,
            "best_penalty": best_penalty,
            "exact_witness": None,
        },
    }


def summarize_construction(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    evaluations = sorted(receipt["evaluations"] for receipt in receipts)
    if not evaluations:
        raise ValueError("construction study requires receipts")
    p95_index = max(0, (95 * len(evaluations) + 99) // 100 - 1)
    mean_evaluations = sum(evaluations) / len(evaluations)
    identities = {
        json.dumps(receipt["manifest"], sort_keys=True, separators=(",", ":"))
        for receipt in receipts
        if receipt["manifest"] is not None
    }
    successes = [receipt for receipt in receipts if receipt["success"]]
    gates = {
        "trial_count": len(receipts) == CONSTRUCTION_TASKS,
        "success_count": len(successes) == CONSTRUCTION_GATE["required_successes"],
        "unique_manifests": len(identities) == len(successes),
        "exact_witnesses": all(
            receipt["exact_witness"]["passes"] for receipt in successes
        ),
        "mean_evaluations": mean_evaluations
        <= CONSTRUCTION_GATE["maximum_mean_evaluations"],
        "p95_evaluations": evaluations[p95_index]
        <= CONSTRUCTION_GATE["maximum_p95_evaluations"],
        "evaluation_budget": max(evaluations) <= CONSTRUCTION_MAX_EVALUATIONS,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "controller-only constructive exact-opportunity feasibility",
        "candidate_outputs_present": False,
        "construction_gate": CONSTRUCTION_GATE,
        "observations": {
            "success_count": len(successes),
            "completed_witnesses": len(successes),
            "mean_evaluations": mean_evaluations,
            "p95_evaluations": evaluations[p95_index],
            "maximum_evaluations": max(evaluations),
            "unique_manifests": len(identities),
        },
        "gates": gates,
        "viable": all(gates.values()),
    }


def run_construction_study(tasks: int = CONSTRUCTION_TASKS) -> dict[str, Any]:
    if tasks <= 0:
        raise ValueError("construction task count must be positive")
    receipts = [construct_manifest() for _ in range(tasks)]
    enriched = [
        {"manifest": item["manifest"], **item["receipt"]} for item in receipts
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "study": "bounded-stage-mutation-construction-v1",
        "candidate_outputs_present": False,
        "receipts": enriched,
        "summary": summarize_construction(enriched),
    }


def analyze_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    tables = control_tables(manifest)
    witness = find_exact_witness(tables)
    return {
        "exact_witness": witness is not None,
        "witness": witness,
    }


def summarize(analyses: list[dict[str, Any]], unique_manifests: int) -> dict[str, Any]:
    if not analyses:
        raise ValueError("E4 opportunity study requires at least one analysis")
    witness_count = sum(item["exact_witness"] for item in analyses)
    fraction = witness_count / len(analyses)
    gates = {
        "sample_count": len(analyses) == SAMPLES,
        "unique_manifests": unique_manifests
        >= INCIDENCE_GATE["minimum_unique_manifests"],
        "exact_witness_fraction": fraction
        >= INCIDENCE_GATE["minimum_exact_witness_fraction"],
        "all_reported_witnesses_pass": all(
            item["witness"] is None or item["witness"]["passes"] for item in analyses
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "controller-only E4 exact causal-opportunity incidence study",
        "candidate_outputs_present": False,
        "sample_count": len(analyses),
        "incidence_gate": INCIDENCE_GATE,
        "scoring_anchor": SCORING,
        "observations": {
            "exact_witness_count": witness_count,
            "exact_witness_fraction": fraction,
            "unique_manifests": unique_manifests,
        },
        "gates": gates,
        "viable": all(gates.values()),
    }


def run_study(samples: int = SAMPLES) -> dict[str, Any]:
    if samples <= 0:
        raise ValueError("sample count must be positive")
    manifests = [generate_task_manifest() for _ in range(samples)]
    analyses = [analyze_manifest(manifest) for manifest in manifests]
    identities = {
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        for manifest in manifests
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "study": "unconditioned-exact-causal-opportunity-incidence-v1",
        "candidate_outputs_present": False,
        "manifests": manifests,
        "analyses": analyses,
        "summary": summarize(analyses, len(identities)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("incidence", "construction"), default="incidence")
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (
        run_construction_study(args.samples)
        if args.mode == "construction"
        else run_study(args.samples)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
