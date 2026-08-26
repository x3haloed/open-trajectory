"""Fresh-process validator for an exact OT-0070 branch projection.

The worker deliberately has no trajectory-store loader.  Its entire inherited
data surface is one canonical projection on standard input.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


_RECORD_ID = re.compile(r"[0-9a-f]{64}")
_OPAQUE_TOKEN = re.compile(r"[0-9a-f]{16}")
_SOURCES = {"actor-channel", "controller-channel", "world-channel"}


class ProjectionError(ValueError):
    """Raised when inherited projection bytes violate the frozen contract."""


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ProjectionError(f"{label} keys differ from the frozen schema")
    return value


def _record_id(value: object, label: str) -> str:
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise ProjectionError(f"{label} is not a lowercase record identity")
    return value


def _token(value: object, label: str) -> str:
    if type(value) is not str or _OPAQUE_TOKEN.fullmatch(value) is None:
        raise ProjectionError(f"{label} is not a bounded opaque token")
    return value


def _validate_record(record_id: str, value: object) -> dict[str, Any]:
    record = _exact_keys(value, {"source", "parents", "payload"}, "record")
    if record["source"] not in _SOURCES:
        raise ProjectionError("record source is unavailable")
    parents = record["parents"]
    if type(parents) is not list:
        raise ProjectionError("record parents are not a list")
    checked_parents = [_record_id(item, "parent") for item in parents]
    if checked_parents != sorted(set(checked_parents)):
        raise ProjectionError("record parents are not sorted and unique")
    if type(record["payload"]) is not dict:
        raise ProjectionError("record payload is not an object")
    observed_id = hashlib.sha256(_canonical_json(record)).hexdigest()
    if observed_id != record_id:
        raise ProjectionError("record identity does not match canonical bytes")
    return record


def _validate_proposal(record: dict[str, Any]) -> dict[str, Any]:
    if record["source"] != "actor-channel":
        raise ProjectionError("projected proposal lacks actor-channel provenance")
    payload = _exact_keys(
        record["payload"],
        {"case_token", "occurrence", "record", "schema_version", "state"},
        "proposal payload",
    )
    if payload["record"] != "proposal" or payload["schema_version"] != 1:
        raise ProjectionError("projected proposal marker is invalid")
    _token(payload["case_token"], "proposal case token")
    if type(payload["occurrence"]) is not int or payload["occurrence"] < 0:
        raise ProjectionError("proposal occurrence is invalid")
    state = _exact_keys(payload["state"], {"output"}, "proposal state")
    _token(state["output"], "proposal output")
    if len(record["parents"]) != 1:
        raise ProjectionError("projected proposal is not a provisional child")
    return payload


def _validate_trial(record: dict[str, Any]) -> dict[str, Any]:
    if record["source"] != "world-channel":
        raise ProjectionError("projected trial lacks world-channel provenance")
    payload = _exact_keys(
        record["payload"],
        {
            "case_token",
            "executor_receipt",
            "proposal_id",
            "record",
            "schema_version",
            "trace",
        },
        "trial payload",
    )
    if payload["record"] != "trial" or payload["schema_version"] != 1:
        raise ProjectionError("projected trial marker is invalid")
    _token(payload["case_token"], "trial case token")
    _token(payload["executor_receipt"], "executor receipt")
    _record_id(payload["proposal_id"], "trial proposal identity")
    trace = payload["trace"]
    if type(trace) is not list or len(trace) != 3:
        raise ProjectionError("trial trace length differs from the frozen schema")
    for index, raw_row in enumerate(trace):
        row = _exact_keys(
            raw_row,
            {"input", "proposal_output", "resolved_output", "trial_id"},
            f"trial row {index}",
        )
        for key in ("input", "proposal_output", "resolved_output", "trial_id"):
            _token(row[key], f"trial row {index} {key}")
    return payload


def validate_projection_bytes(raw: bytes) -> dict[str, Any]:
    """Validate exactly two projected branch records without outside lookup."""

    if len(raw) > 2048:
        raise ProjectionError("projection exceeds 2048 canonical bytes")
    try:
        projection = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProjectionError("projection is not UTF-8 canonical JSON") from error
    if raw != _canonical_json(projection):
        raise ProjectionError("projection bytes are not canonical")
    projection = _exact_keys(
        projection,
        {"external_parents", "record_ids", "records", "schema_version"},
        "projection",
    )
    if projection["schema_version"] != 1:
        raise ProjectionError("projection schema version is unavailable")
    record_ids = projection["record_ids"]
    if type(record_ids) is not list:
        raise ProjectionError("projection record identities are not a list")
    checked_ids = [_record_id(item, "projected record identity") for item in record_ids]
    if checked_ids != sorted(set(checked_ids)) or len(checked_ids) != 2:
        raise ProjectionError("branch projection must name two sorted unique records")
    entries = projection["records"]
    if type(entries) is not list or len(entries) != 2:
        raise ProjectionError("branch projection must contain exactly two records")

    local_records: dict[str, dict[str, Any]] = {}
    for raw_entry, expected_id in zip(entries, checked_ids, strict=True):
        entry = _exact_keys(raw_entry, {"record", "record_id"}, "projection entry")
        entry_id = _record_id(entry["record_id"], "projection entry identity")
        if entry_id != expected_id:
            raise ProjectionError("projection records are not sorted by identity")
        local_records[entry_id] = _validate_record(entry_id, entry["record"])

    external_parents = projection["external_parents"]
    if type(external_parents) is not list:
        raise ProjectionError("external parents are not a list")
    checked_external = [_record_id(item, "external parent") for item in external_parents]
    expected_external = sorted(
        {
            parent
            for record in local_records.values()
            for parent in record["parents"]
            if parent not in local_records
        }
    )
    if checked_external != expected_external:
        raise ProjectionError("external-parent header is not exact")

    proposal_items = [
        (record_id, record)
        for record_id, record in local_records.items()
        if record["source"] == "actor-channel"
        and record["payload"].get("record") == "proposal"
    ]
    trial_items = [
        (record_id, record)
        for record_id, record in local_records.items()
        if record["source"] == "world-channel"
        and record["payload"].get("record") == "trial"
    ]
    if len(proposal_items) != 1 or len(trial_items) != 1:
        raise ProjectionError("projection does not contain one proposal and one trial")
    proposal_id, proposal_record = proposal_items[0]
    trial_id, trial_record = trial_items[0]
    proposal_payload = _validate_proposal(proposal_record)
    trial_payload = _validate_trial(trial_record)
    if trial_record["parents"] != [proposal_id] or trial_payload["proposal_id"] != proposal_id:
        raise ProjectionError("trial parent and payload do not bind the same proposal")
    if trial_payload["case_token"] != proposal_payload["case_token"]:
        raise ProjectionError("proposal and trial case tokens differ")

    unrelated_id = hashlib.sha256(b"ot-0070:unrelated-record").hexdigest()
    return {
        "schema_version": 1,
        "pass": True,
        "projection_bytes": len(raw),
        "projected_record_count": len(local_records),
        "proposal_id": proposal_id,
        "trial_id": trial_id,
        "external_parent_count": len(checked_external),
        "external_parent_lookup": any(item in local_records for item in checked_external),
        "unrelated_lookup": unrelated_id in local_records,
        "controller_store_serialized": False,
    }


def main() -> int:
    before = sorted(path.name for path in Path.cwd().iterdir())
    raw = sys.stdin.buffer.read(2049)
    try:
        result = validate_projection_bytes(raw)
        after = sorted(path.name for path in Path.cwd().iterdir())
        result.update(
            {
                "workspace_empty_before": before == [],
                "workspace_empty_after": after == [],
            }
        )
        result["pass"] = (
            result["pass"]
            and not result["external_parent_lookup"]
            and not result["unrelated_lookup"]
            and not result["controller_store_serialized"]
            and result["workspace_empty_before"]
            and result["workspace_empty_after"]
        )
        sys.stdout.buffer.write(_canonical_json(result))
        return 0 if result["pass"] else 2
    except (OSError, ProjectionError, TypeError, ValueError) as error:
        sys.stderr.write(f"projection rejected: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
