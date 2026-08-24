from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0004_world import score_predictions, selected_events
from .ot0005_world import ProgramLedger, deterministic_predictions, deterministic_selection


EXPERIMENT_ID = "OT-0021"
LEDGER_SCHEMA_VERSION = 1
FORBIDDEN_TRACE_KEYS = {
    "construction_receipt",
    "exact_witness",
    "fixed_controls",
    "future_stage",
    "hidden_outcomes",
}


def _selector_branch(
    expression: str,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
) -> dict[str, Any]:
    snapshot = ProgramLedger(expression, iteration_depth_limit=8).current
    selected_ids = deterministic_selection(
        expression,
        archive,
        queries,
        limit,
        allow_empty=expression == "[]",
        iteration_depth_limit=8,
    )
    retained = selected_events(archive, selected_ids)
    predictions = deterministic_predictions(retained, queries)
    errors, parse_error = score_predictions(predictions, outcomes)
    if parse_error:
        raise RuntimeError("OT-0021 deterministic prediction replay failed")
    query_receipts = [
        {
            "query": list(query),
            "outcome": outcome,
            "prediction": prediction,
            "error": prediction != outcome,
        }
        for query, outcome, prediction in zip(queries, outcomes, predictions)
    ]
    return {
        "program": {"expression": expression, "sha256": snapshot.sha256},
        "selected_events": deepcopy(retained),
        "predictions": predictions,
        "query_receipts": query_receipts,
        "errors": errors,
        "deterministic_replay": True,
    }


def seed_consequence_entry(task: dict[str, Any]) -> dict[str, Any]:
    prior = task["prior_completed_encounter"]
    branch = _selector_branch(
        "[]",
        prior["archive"],
        prior["queries"],
        prior["outcomes"],
        task["selection_limit"],
    )
    body = {
        "source_stage": 0,
        "completed": True,
        "raw_encounter": {
            "archive": deepcopy(prior["archive"]),
            "queries": deepcopy(prior["queries"]),
            "outcomes": list(prior["outcomes"]),
        },
        "selector_consequences": {"current": branch},
        "decision": {
            "choice": "current",
            "committed_program_sha256": branch["program"]["sha256"],
        },
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def consequence_ledger(
    entries: list[dict[str, Any]], *, max_entries: int, max_bytes: int
) -> dict[str, Any]:
    ledger = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "entries": deepcopy(entries),
        "entry_limit": max_entries,
        "byte_limit": max_bytes,
    }
    validate_consequence_ledger(ledger)
    return ledger


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_walk_keys(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_walk_keys(child) for child in value), set())
    return set()


def validate_consequence_ledger(ledger: dict[str, Any]) -> None:
    if set(ledger) != {"schema_version", "entries", "entry_limit", "byte_limit"}:
        raise ValueError("OT-0021 consequence ledger has an invalid root schema")
    if ledger["schema_version"] != LEDGER_SCHEMA_VERSION:
        raise ValueError("OT-0021 consequence ledger has an invalid version")
    entries = ledger["entries"]
    if not isinstance(entries, list) or len(entries) > ledger["entry_limit"]:
        raise ValueError("OT-0021 consequence ledger exceeds its entry budget")
    if len(canonical_json(ledger)) > ledger["byte_limit"]:
        raise ValueError("OT-0021 consequence ledger exceeds its byte budget")
    if _walk_keys(ledger) & FORBIDDEN_TRACE_KEYS:
        raise ValueError("OT-0021 consequence ledger contains evaluator authority")
    expected_stages = list(range(len(entries)))
    if [entry.get("source_stage") for entry in entries] != expected_stages:
        raise ValueError("OT-0021 consequence ledger is not append-only and contiguous")
    for entry in entries:
        if entry.get("completed") is not True:
            raise ValueError("OT-0021 consequence ledger contains an incomplete stage")
        body = {key: value for key, value in entry.items() if key != "receipt_sha256"}
        if entry.get("receipt_sha256") != sha256_bytes(canonical_json(body)):
            raise ValueError("OT-0021 consequence receipt identity is invalid")


def validate_public_task(
    task: dict[str, Any], *, experiment_id: str = EXPERIMENT_ID
) -> None:
    if set(task) != {
        "schema_version",
        "experiment_id",
        "selection_limit",
        "prior_completed_encounter",
        "sealed_pilot_evaluation",
    }:
        raise ValueError("OT-0021 public pilot task has an invalid root schema")
    if task["schema_version"] != 1 or task["experiment_id"] != experiment_id:
        raise ValueError("OT-0021 public pilot task has an invalid identity")
    limit = task["selection_limit"]
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("OT-0021 selection limit is invalid")
    for split_name in ("prior_completed_encounter", "sealed_pilot_evaluation"):
        split = task[split_name]
        if set(split) != {"archive", "queries", "outcomes"}:
            raise ValueError(f"OT-0021 {split_name} has an invalid schema")
        archive = split["archive"]
        queries = split["queries"]
        outcomes = split["outcomes"]
        if len(archive) < limit or len(queries) != len(outcomes) or not queries:
            raise ValueError(f"OT-0021 {split_name} has invalid dimensions")
        event_ids = [event.get("event_id") for event in archive]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError(f"OT-0021 {split_name} has duplicate event identities")
        for event in archive:
            if set(event) != {"event_id", "sequence", "features", "label"}:
                raise ValueError(f"OT-0021 {split_name} has an invalid event")
    ledger = consequence_ledger(
        [seed_consequence_entry(task)], max_entries=5, max_bytes=49152
    )
    if ledger["entries"][0]["selector_consequences"]["current"]["errors"] < 2:
        raise ValueError("OT-0021 prior trace does not expose a useful discrepancy")


__all__ = [
    "EXPERIMENT_ID",
    "consequence_ledger",
    "seed_consequence_entry",
    "validate_consequence_ledger",
    "validate_public_task",
]
