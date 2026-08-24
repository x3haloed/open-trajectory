from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from typing import Any

from .ot0004_world import archive_through_stage, fixed_selection, selected_events
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
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_study(args.samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
