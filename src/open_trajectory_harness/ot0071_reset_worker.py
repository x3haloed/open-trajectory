"""Fresh-process fixtures for OT-0071 trajectory practice calibration.

The worker has no trajectory-store loader or channel capability.  Each call
receives only canonical exact projections and small explicit literals on
standard input, then emits candidate-free actor-channel payload bytes.  It
does not append records, select a winner, or observe later world consequence.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


_RECORD_ID = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[0-9a-f]{32}")
_SOURCES = {"actor-channel", "controller-channel", "world-channel"}


class WorkerError(ValueError):
    """Raised when a reset envelope violates its frozen local contract."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise WorkerError(f"{label} keys differ from the frozen schema")
    return value


def _record_id(value: object, label: str) -> str:
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise WorkerError(f"{label} is not a lowercase record identity")
    return value


def _token(value: object, label: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise WorkerError(f"{label} is not a bounded opaque token")
    return value


def _validate_record(record_id: str, raw: object) -> dict[str, Any]:
    record = _exact(raw, {"parents", "payload", "source"}, "record")
    if record["source"] not in _SOURCES:
        raise WorkerError("record source is unavailable")
    parents = record["parents"]
    if type(parents) is not list:
        raise WorkerError("record parents are not a list")
    checked = [_record_id(item, "record parent") for item in parents]
    if checked != sorted(set(checked)):
        raise WorkerError("record parents are not sorted and unique")
    if type(record["payload"]) is not dict:
        raise WorkerError("record payload is not an object")
    if hashlib.sha256(canonical_json(record)).hexdigest() != record_id:
        raise WorkerError("record identity does not match canonical bytes")
    return record


def _projection(raw: object, label: str) -> dict[str, tuple[str, dict[str, Any]]]:
    projection = _exact(
        raw,
        {"external_parents", "record_ids", "records", "schema_version"},
        f"{label} projection",
    )
    if projection["schema_version"] != 1:
        raise WorkerError(f"{label} projection schema is unavailable")
    ids = projection["record_ids"]
    entries = projection["records"]
    external = projection["external_parents"]
    if type(ids) is not list or type(entries) is not list or type(external) is not list:
        raise WorkerError(f"{label} projection collections are malformed")
    checked_ids = [_record_id(item, f"{label} record identity") for item in ids]
    if checked_ids != sorted(set(checked_ids)) or len(entries) != len(checked_ids):
        raise WorkerError(f"{label} projection identities are not exact")
    records: dict[str, tuple[str, dict[str, Any]]] = {}
    local: dict[str, dict[str, Any]] = {}
    for expected_id, raw_entry in zip(checked_ids, entries, strict=True):
        entry = _exact(raw_entry, {"record", "record_id"}, f"{label} entry")
        entry_id = _record_id(entry["record_id"], f"{label} entry identity")
        if entry_id != expected_id:
            raise WorkerError(f"{label} projection order differs")
        record = _validate_record(entry_id, entry["record"])
        local[entry_id] = record
        marker = record["payload"].get("record")
        if type(marker) is not str or marker in records:
            raise WorkerError(f"{label} record markers are ambiguous")
        records[marker] = (entry_id, record)
    checked_external = [_record_id(item, f"{label} external parent") for item in external]
    expected_external = sorted(
        {
            parent
            for record in local.values()
            for parent in record["parents"]
            if parent not in local
        }
    )
    if checked_external != expected_external:
        raise WorkerError(f"{label} external-parent header differs")
    return records


def _only(records: dict[str, tuple[str, dict[str, Any]]], marker: str) -> tuple[str, dict[str, Any]]:
    try:
        return records[marker]
    except KeyError as error:
        raise WorkerError(f"required {marker} record is absent") from error


def _directory_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    payload = record["payload"]
    entries = payload.get("entries")
    if type(entries) is not list or len(entries) != 3:
        raise WorkerError("directory entries differ from the frozen schema")
    for raw in entries:
        entry = _exact(
            raw,
            {"address_handle", "locator_id", "proposal_id", "trial_id"},
            "directory entry",
        )
        _token(entry["address_handle"], "directory address")
        for key in ("locator_id", "proposal_id", "trial_id"):
            _record_id(entry[key], f"directory {key}")
    return entries


def _entry_for_handle(record: dict[str, Any], handle: str) -> dict[str, Any]:
    matches = [item for item in _directory_entries(record) if item["address_handle"] == handle]
    if len(matches) != 1:
        raise WorkerError("directory address does not resolve exactly once")
    return matches[0]


def _diagnostic(inputs: dict[str, Any]) -> dict[str, Any]:
    inputs = _exact(
        inputs,
        {
            "address_handle",
            "attempt_ordinal",
            "contact",
            "correction_consequence_id",
            "directory",
            "query_key",
        },
        "diagnostic inputs",
    )
    contact_id, contact = _only(_projection(inputs["contact"], "contact"), "contact")
    directory_id, directory = _only(
        _projection(inputs["directory"], "directory"), "directory"
    )
    payload = contact["payload"]
    handle = _token(inputs["address_handle"], "attempt address")
    query = _token(inputs["query_key"], "attempt query")
    if type(inputs["attempt_ordinal"]) is not int or inputs["attempt_ordinal"] not in range(3):
        raise WorkerError("attempt ordinal is unavailable")
    if query not in payload.get("query_keys", []):
        raise WorkerError("attempt query is absent from current contact")
    entry = _entry_for_handle(directory, handle)
    return {
        "address_handle": handle,
        "case_token": payload["case_token"],
        "contact_id": contact_id,
        "correction_consequence_id": _record_id(
            inputs["correction_consequence_id"], "correction consequence"
        ),
        "directory_id": directory_id,
        "expected_active_id": payload["active_proposal_id"],
        "expected_pointer_event_id": payload["pointer_event_id"],
        "locator_id": entry["locator_id"],
        "proposal_id": entry["proposal_id"],
        "query_key": query,
        "record": "diagnostic_request",
        "regime": payload["regime"],
        "schema_version": 1,
        "trial_id": entry["trial_id"],
    }


def _outcome_entry(raw_projection: object) -> tuple[str, dict[str, Any]]:
    outcome_id, outcome = _only(_projection(raw_projection, "outcome"), "attempt_outcome")
    payload = outcome["payload"]
    _exact(
        payload,
        {
            "address_handle",
            "case_token",
            "proposal_output",
            "query_key",
            "record",
            "request_id",
            "resolved_output",
            "schema_version",
            "world_receipt",
        },
        "outcome payload",
    )
    return outcome_id, payload


def _practice_fit(inputs: dict[str, Any]) -> dict[str, Any]:
    inputs = _exact(
        inputs,
        {
            "contact",
            "correction_consequence",
            "directory",
            "outcomes",
            "previous_practice",
        },
        "practice-fit inputs",
    )
    contact_id, contact = _only(_projection(inputs["contact"], "contact"), "contact")
    correction_id, correction = _only(
        _projection(inputs["correction_consequence"], "correction"),
        "correction_consequence",
    )
    directory_id, directory = _only(
        _projection(inputs["directory"], "directory"), "directory"
    )
    raw_outcomes = inputs["outcomes"]
    if type(raw_outcomes) is not list or len(raw_outcomes) != 6:
        raise WorkerError("practice fit requires six outcome projections")
    outcomes = [_outcome_entry(item) for item in raw_outcomes]
    outcome_ids = sorted(item[0] for item in outcomes)
    if len(set(outcome_ids)) != 6:
        raise WorkerError("practice support outcomes are not unique")
    contact_payload = contact["payload"]
    queries = contact_payload.get("query_keys")
    if type(queries) is not list or len(queries) != 3 or queries != sorted(set(queries)):
        raise WorkerError("contact queries differ from the frozen schema")
    grouped: dict[str, list[dict[str, Any]]] = {}
    handle_outputs: dict[str, str] = {}
    for _, outcome in outcomes:
        grouped.setdefault(outcome["query_key"], []).append(outcome)
        prior = handle_outputs.setdefault(outcome["address_handle"], outcome["proposal_output"])
        if prior != outcome["proposal_output"]:
            raise WorkerError("one address exposes inconsistent proposal outputs")
    if len(grouped) != 2 or any(len(rows) != 3 for rows in grouped.values()):
        raise WorkerError("practice support does not cover two exhaustive queries")
    directory_handles = {item["address_handle"] for item in _directory_entries(directory)}
    if set(handle_outputs) != directory_handles or len(set(handle_outputs.values())) != 3:
        raise WorkerError("practice support does not expose the complete directory relation")
    rows: list[dict[str, str]] = []
    used_outputs: set[str] = set()
    for query, items in grouped.items():
        matches = [item for item in items if item["proposal_output"] == item["resolved_output"]]
        if len(matches) != 1:
            raise WorkerError("diagnostic query does not identify one matching address")
        rows.append({"address_handle": matches[0]["address_handle"], "query_key": query})
        used_outputs.add(matches[0]["resolved_output"])
    heldout = [query for query in queries if query not in grouped]
    remaining_outputs = set(handle_outputs.values()) - used_outputs
    if len(heldout) != 1 or len(remaining_outputs) != 1:
        raise WorkerError("public bijection does not identify the heldout row")
    remaining = remaining_outputs.pop()
    remaining_handles = [handle for handle, output in handle_outputs.items() if output == remaining]
    if len(remaining_handles) != 1:
        raise WorkerError("heldout output does not identify one address")
    rows.append({"address_handle": remaining_handles[0], "query_key": heldout[0]})
    rows.sort(key=lambda row: row["query_key"])

    previous_id = contact_payload["active_practice_id"]
    previous_projection = inputs["previous_practice"]
    if previous_id is None:
        if previous_projection is not None:
            raise WorkerError("genesis contact unexpectedly receives prior practice")
    else:
        prior_id, _ = _only(_projection(previous_projection, "previous practice"), "practice")
        if prior_id != previous_id:
            raise WorkerError("previous compact practice identity differs from contact")
    receipt_payload = {
        "case_token": contact_payload["case_token"],
        "contact_id": contact_id,
        "correction_consequence_id": correction_id,
        "directory_id": directory_id,
        "expected_active_id": contact_payload["active_proposal_id"],
        "expected_pointer_event_id": contact_payload["pointer_event_id"],
        "previous_practice_id": previous_id,
        "record": "practice_receipt",
        "regime": contact_payload["regime"],
        "rows": rows,
        "schema_version": 1,
        "support_outcome_ids": outcome_ids,
    }
    receipt_parents = sorted(
        {contact_id, correction_id, directory_id, *outcome_ids}
        | ({previous_id} if previous_id is not None else set())
    )
    receipt_record = {
        "parents": receipt_parents,
        "payload": receipt_payload,
        "source": "actor-channel",
    }
    receipt_id = hashlib.sha256(canonical_json(receipt_record)).hexdigest()
    practice_payload = {
        "case_token": contact_payload["case_token"],
        "practice_receipt_id": receipt_id,
        "record": "practice",
        "rows": rows,
        "schema_version": 1,
    }
    return {
        "practice_payload": practice_payload,
        "practice_receipt_payload": receipt_payload,
    }


def _practice_execute(inputs: dict[str, Any]) -> dict[str, Any]:
    inputs = _exact(
        inputs,
        {"contact", "directory", "heldout_query_key", "practice"},
        "practice-execution inputs",
    )
    contact_id, contact = _only(_projection(inputs["contact"], "contact"), "contact")
    directory_id, directory = _only(
        _projection(inputs["directory"], "directory"), "directory"
    )
    practice_id, practice = _only(_projection(inputs["practice"], "practice"), "practice")
    query = _token(inputs["heldout_query_key"], "heldout query")
    rows = practice["payload"].get("rows")
    if type(rows) is not list:
        raise WorkerError("compact practice rows are unavailable")
    matches = [row for row in rows if row.get("query_key") == query]
    if len(matches) != 1:
        raise WorkerError("compact practice does not resolve the heldout query")
    handle = _token(matches[0].get("address_handle"), "practice address")
    entry = _entry_for_handle(directory, handle)
    contact_payload = contact["payload"]
    return {
        "address_handle": handle,
        "case_token": contact_payload["case_token"],
        "contact_id": contact_id,
        "directory_id": directory_id,
        "expected_active_id": contact_payload["active_proposal_id"],
        "expected_pointer_event_id": contact_payload["pointer_event_id"],
        "locator_id": entry["locator_id"],
        "practice_id": practice_id,
        "proposal_id": entry["proposal_id"],
        "query_key": query,
        "record": "projection_request",
        "regime": contact_payload["regime"],
        "schema_version": 1,
        "trial_id": entry["trial_id"],
    }


def _successor(inputs: dict[str, Any]) -> dict[str, Any]:
    inputs = _exact(
        inputs,
        {"contact", "locator", "projection_request", "selected_branch"},
        "successor inputs",
    )
    _, contact = _only(_projection(inputs["contact"], "contact"), "contact")
    request_id, request = _only(
        _projection(inputs["projection_request"], "projection request"),
        "projection_request",
    )
    locator_id, _ = _only(_projection(inputs["locator"], "locator"), "locator")
    selected = _projection(inputs["selected_branch"], "selected branch")
    proposal_id, proposal = _only(selected, "proposal")
    trial_id, _ = _only(selected, "trial")
    request_payload = request["payload"]
    if (
        request_payload["proposal_id"] != proposal_id
        or request_payload["trial_id"] != trial_id
        or request_payload["locator_id"] != locator_id
    ):
        raise WorkerError("successor inputs are not request-bound")
    coefficients = proposal["payload"].get("coefficients")
    if type(coefficients) is not list or len(coefficients) != 2 or any(type(x) is not int or x not in {0, 1} for x in coefficients):
        raise WorkerError("selected mechanism coefficients are invalid")
    return {
        "case_token": contact["payload"]["case_token"],
        "coefficients": list(coefficients),
        "note": "",
        "occurrence": "successor",
        "record": "proposal",
        "schema_version": 2,
        "source_context_id": None,
    }


def _decision(inputs: dict[str, Any]) -> dict[str, Any]:
    inputs = _exact(
        inputs,
        {
            "case_token",
            "decision_token",
            "expected_active_id",
            "expected_pointer_event_id",
            "requested_action",
            "rollback_target_id",
            "selected_branch",
        },
        "decision inputs",
    )
    action = inputs["requested_action"]
    if action not in {"adopt", "rollback", "set_down"}:
        raise WorkerError("requested action is unavailable")
    selected_id: str | None = None
    trial_id: str | None = None
    rollback_target = inputs["rollback_target_id"]
    selected_projection = inputs["selected_branch"]
    if action in {"adopt", "set_down"}:
        selected = _projection(selected_projection, "decision selected branch")
        selected_id, _ = _only(selected, "proposal")
        trial_id, _ = _only(selected, "trial")
        if rollback_target is not None:
            raise WorkerError("adopt/set-down input carries rollback target")
    else:
        if selected_projection is not None:
            raise WorkerError("rollback input carries selected branch")
        rollback_target = _record_id(rollback_target, "rollback target")
    return {
        "action": action,
        "case_token": _token(inputs["case_token"], "decision case token"),
        "decision_token": _token(inputs["decision_token"], "decision token"),
        "expected_active_id": _record_id(inputs["expected_active_id"], "expected active"),
        "expected_pointer_event_id": _record_id(
            inputs["expected_pointer_event_id"], "expected pointer"
        ),
        "record": "decision",
        "rollback_target_id": rollback_target,
        "schema_version": 1,
        "selected_proposal_id": selected_id,
        "trial_id": trial_id,
    }


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "decision": _decision,
    "diagnostic": _diagnostic,
    "practice_execute": _practice_execute,
    "practice_fit": _practice_fit,
    "successor": _successor,
}


def evaluate_envelope(raw: bytes) -> dict[str, Any]:
    try:
        envelope = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkerError("reset envelope is not canonical JSON") from error
    if raw != canonical_json(envelope):
        raise WorkerError("reset envelope bytes are not canonical")
    envelope = _exact(envelope, {"inputs", "kind", "schema_version"}, "reset envelope")
    if envelope["schema_version"] != 1 or envelope["kind"] not in _HANDLERS:
        raise WorkerError("reset envelope kind is unavailable")
    if type(envelope["inputs"]) is not dict:
        raise WorkerError("reset inputs are not an object")
    return {
        "kind": envelope["kind"],
        "payloads": _HANDLERS[envelope["kind"]](envelope["inputs"]),
        "schema_version": 1,
    }


def main() -> int:
    before = sorted(path.name for path in Path.cwd().iterdir())
    raw = sys.stdin.buffer.read(24577)
    try:
        result = evaluate_envelope(raw)
        after = sorted(path.name for path in Path.cwd().iterdir())
        result["workspace_empty_after"] = after == []
        result["workspace_empty_before"] = before == []
        sys.stdout.buffer.write(canonical_json(result))
        return 0 if result["workspace_empty_before"] and result["workspace_empty_after"] else 2
    except (OSError, TypeError, WorkerError, ValueError) as error:
        sys.stderr.write(f"reset rejected: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
