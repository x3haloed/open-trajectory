from __future__ import annotations

import argparse
import copy
import itertools
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import (
    canonical_json,
    child_environment,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
)
from .ot0003 import write_sealed_json
from .ot0040 import unsupported_keywords


EXPERIMENT_ID = "OT-0067"
ACCEPTANCE_PATH = Path("spec/ot-0067-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0067-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0067/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0067/actor-output.schema.json")
OT66_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0066/ot-0066-disjoint-temporal-topology-candidate-001.json"
)
OT65_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0065/ot-0065-temporal-state-topology-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0067-equivalence-partition-calibration-001"
SIDES = ("left", "right")
SYMBOL_COUNT = 8
INHERITANCE_LIMIT = 1024
MAX_GROUPS = 8
MAX_IDENTIFIER_BYTES = 40


@dataclass(frozen=True)
class PartitionSnapshot:
    revision: int
    parent_sha256: str | None
    outcome_receipt_sha256: str
    state: dict[str, Any]
    sha256: str


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0067.py"),
        "entrypoint_sha256": Path("experiments/ot_0067_harness.py"),
        "test_sha256": Path("tests/test_ot0067.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0066_manifest_sha256": OT66_MANIFEST_PATH,
        "ot0065_manifest_sha256": OT65_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def all_partition_labels(size: int = SYMBOL_COUNT) -> list[tuple[int, ...]]:
    if size < 1:
        raise ValueError("OT-0067 partition size is unavailable")
    values: list[tuple[int, ...]] = []

    def extend(prefix: tuple[int, ...]) -> None:
        if len(prefix) == size:
            values.append(prefix)
            return
        for label in range(max(prefix) + 2):
            extend((*prefix, label))

    extend((0,))
    return values


PARTITION_HYPOTHESES = tuple(all_partition_labels())
TARGET_LABELS = (
    (0, 1, 0, 1, 0, 1, 0, 1),
    (0, 0, 0, 0, 1, 1, 1, 1),
    (0, 1, 2, 3, 0, 1, 2, 3),
)
ALL_PAIRS = tuple(itertools.combinations(range(SYMBOL_COUNT), 2))


def same_group(labels: tuple[int, ...] | list[int], pair: tuple[int, int]) -> bool:
    return labels[pair[0]] == labels[pair[1]]


def resolved_side(labels: tuple[int, ...] | list[int], pair: tuple[int, int]) -> str:
    return "left" if same_group(labels, pair) else "right"


def heldout_pairs(regime_index: int) -> list[tuple[int, int]]:
    target = TARGET_LABELS[regime_index - 1]
    if regime_index == 1:
        same = [pair for pair in ALL_PAIRS if same_group(target, pair)]
        different = [pair for pair in ALL_PAIRS if not same_group(target, pair)]
    else:
        previous = TARGET_LABELS[regime_index - 2]
        changed = [
            pair
            for pair in ALL_PAIRS
            if same_group(target, pair) != same_group(previous, pair)
        ]
        same = [pair for pair in changed if same_group(target, pair)]
        different = [pair for pair in changed if not same_group(target, pair)]
    if len(same) < 4 or len(different) < 4:
        raise ValueError("OT-0067 heldout family is not balanced")
    return same[:4] + different[:4]


def consistent_partitions(
    target: tuple[int, ...], observations: list[tuple[int, int]]
) -> list[tuple[int, ...]]:
    return [
        labels
        for labels in PARTITION_HYPOTHESES
        if all(
            same_group(labels, pair) == same_group(target, pair)
            for pair in observations
        )
    ]


def diagnostic_pairs(
    target: tuple[int, ...], heldout: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    heldout_set = set(heldout)

    def allowed(pair: tuple[int, int]) -> bool:
        surviving = consistent_partitions(target, [pair])
        behaviors = {
            tuple(same_group(labels, query) for query in heldout)
            for labels in surviving
        }
        return len(surviving) >= 2 and len(behaviors) >= 2

    pool = [pair for pair in ALL_PAIRS if pair not in heldout_set and allowed(pair)]
    selected: list[tuple[int, int]] = []
    remaining = list(PARTITION_HYPOTHESES)
    while len(remaining) > 1:
        choices = []
        for pair in pool:
            if pair in selected:
                continue
            narrowed = [
                labels
                for labels in remaining
                if same_group(labels, pair) == same_group(target, pair)
            ]
            if 0 < len(narrowed) < len(remaining):
                choices.append((len(narrowed), pair, narrowed))
        if not choices:
            raise ValueError("OT-0067 diagnostics cannot identify the target")
        _, chosen, remaining = min(choices, key=lambda value: value[:2])
        selected.append(chosen)
    for pair in pool:
        if pair not in selected:
            selected.append(pair)
        if len(selected) == 15:
            break
    if len(selected) != 15 or consistent_partitions(target, selected) != [target]:
        raise ValueError("OT-0067 diagnostic set is incomplete")
    return selected


def symbol_tokens(case_index: int) -> tuple[str, ...]:
    tokens = [
        "symbol-" + sha256_bytes(f"ot-0067:{case_index}:{index}".encode())[:12]
        for index in range(SYMBOL_COUNT)
    ]
    return tuple(
        sorted(
            tokens,
            key=lambda token: sha256_bytes(
                f"ot-0067-order:{case_index}:{token}".encode()
            ),
        )
    )


def _events(case_index: int, bundle_index: int, trial: int) -> list[dict[str, Any]]:
    order = SIDES if (case_index + bundle_index + trial) % 2 == 0 else tuple(reversed(SIDES))
    return [
        {
            "event_id": side,
            "selector_features": [0, 0, 0, 0],
            "on_flags": [f"side-{side}"],
        }
        for side in order
    ]


def _encode_pair(pair: tuple[int, int], symbols: tuple[str, ...]) -> list[str]:
    return [symbols[pair[0]], symbols[pair[1]]]


def _bundle(
    case_index: int,
    regime_index: int,
    bundle_index: int,
    pair: tuple[int, int],
    symbols: tuple[str, ...],
    target: tuple[int, ...],
) -> dict[str, Any]:
    correct = resolved_side(target, pair)
    return {
        "bundle_id": f"bundle-{regime_index}-{bundle_index:02d}",
        "query_symbols": _encode_pair(pair, symbols),
        "presentations": [
            {
                "presentation_id": sha256_bytes(
                    f"ot-0067:{case_index}:{regime_index}:{bundle_index}:{trial}".encode()
                )[:20],
                "events": _events(case_index, bundle_index, trial),
                "correct_side": correct,
            }
            for trial in range(4)
        ],
    }


def public_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbols": list(contact["symbols"]),
        "bundles": [
            {
                "bundle_id": bundle["bundle_id"],
                "query_symbols": bundle["query_symbols"],
                "presentations": [
                    {
                        "presentation_id": item["presentation_id"],
                        "events": item["events"],
                    }
                    for item in bundle["presentations"]
                ],
            }
            for bundle in contact["bundles"]
        ],
    }


def complete_contact(contact: dict[str, Any], choices: list[str]) -> dict[str, Any]:
    if len(choices) != len(contact["bundles"]) or any(choice not in SIDES for choice in choices):
        raise ValueError("OT-0067 contact choices are malformed")
    outcomes = []
    for bundle, choice in zip(contact["bundles"], choices, strict=True):
        correct = bundle["presentations"][0]["correct_side"]
        outcomes.append(
            {
                "bundle_id": bundle["bundle_id"],
                "selected_side": choice,
                "resolved_side": correct,
                "success": choice == correct,
            }
        )
    body = {"kind": "ot-0067-completed-contact", "outcomes": outcomes}
    return {**body, "sha256": sha256_bytes(canonical_json(body))}


def build_regime(case_index: int, regime_index: int) -> dict[str, Any]:
    symbols = symbol_tokens(case_index)
    target = TARGET_LABELS[regime_index - 1]
    heldout = heldout_pairs(regime_index)
    diagnostics = diagnostic_pairs(target, heldout)
    rotation = (case_index * 5 + regime_index) % len(diagnostics)
    diagnostics = diagnostics[rotation:] + diagnostics[:rotation]
    if case_index % 2:
        heldout = list(reversed(heldout))
    return {
        "index": regime_index,
        "symbols": symbols,
        "target_labels": target,
        "contact": {
            "symbols": symbols,
            "bundles": [
                _bundle(case_index, regime_index, index, pair, symbols, target)
                for index, pair in enumerate(diagnostics)
            ],
        },
        "diagnostic_pairs": diagnostics,
        "heldout": [
            {
                "query_symbols": _encode_pair(pair, symbols),
                "correct_side": resolved_side(target, pair),
            }
            for pair in heldout
        ],
        "heldout_pairs": heldout,
    }


def build_case(case_index: int) -> dict[str, Any]:
    if not 0 <= case_index < 16:
        raise ValueError("OT-0067 case index is unavailable")
    return {
        "case_index": case_index,
        "regimes": [build_regime(case_index, index) for index in (1, 2, 3)],
    }


def reference_partition(regime: dict[str, Any]) -> dict[str, Any]:
    groups: dict[int, list[str]] = {}
    for symbol, label in zip(regime["symbols"], regime["target_labels"], strict=True):
        groups.setdefault(label, []).append(symbol)
    return {
        "groups": [
            {"id": f"group-{index}", "members": members}
            for index, members in sorted(groups.items())
        ],
        "within_output": "left",
        "across_output": "right",
    }


def validate_partition(partition: dict[str, Any], symbols: tuple[str, ...] | list[str]) -> None:
    if not isinstance(partition, dict) or set(partition) != {
        "groups",
        "within_output",
        "across_output",
    }:
        raise ValueError("OT-0067 partition authority differs")
    if partition["within_output"] not in SIDES or partition["across_output"] not in SIDES:
        raise ValueError("OT-0067 partition output is malformed")
    groups = partition["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= MAX_GROUPS:
        raise ValueError("OT-0067 group count differs")
    ids = []
    members = []
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"id", "members"}:
            raise ValueError("OT-0067 group authority differs")
        if (
            not isinstance(group["id"], str)
            or not 1 <= len(group["id"].encode()) <= MAX_IDENTIFIER_BYTES
            or not isinstance(group["members"], list)
            or not group["members"]
            or any(not isinstance(item, str) for item in group["members"])
        ):
            raise ValueError("OT-0067 group is malformed")
        ids.append(group["id"])
        members.extend(group["members"])
    if len(ids) != len(set(ids)):
        raise ValueError("OT-0067 group identity is duplicated")
    if len(members) != len(set(members)) or set(members) != set(symbols):
        raise ValueError("OT-0067 symbol membership differs")
    if len(canonical_json(partition)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0067 partition exceeds its byte limit")


def partition_output(
    partition: dict[str, Any], query: list[str], symbols: tuple[str, ...] | list[str]
) -> str:
    validate_partition(partition, symbols)
    if len(query) != 2 or query[0] == query[1] or any(item not in symbols for item in query):
        raise ValueError("OT-0067 query is malformed")
    membership = {
        member: group["id"]
        for group in partition["groups"]
        for member in group["members"]
    }
    key = "within_output" if membership[query[0]] == membership[query[1]] else "across_output"
    return partition[key]


def partition_errors(
    partition: dict[str, Any], examples: list[dict[str, Any]], symbols: tuple[str, ...] | list[str]
) -> int:
    return sum(
        partition_output(partition, item["query_symbols"], symbols) != item["correct_side"]
        for item in examples
    )


def _contact_examples(contact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "query_symbols": bundle["query_symbols"],
            "correct_side": bundle["presentations"][0]["correct_side"],
        }
        for bundle in contact["bundles"]
    ]


def membership_fingerprint(
    partition: dict[str, Any], symbols: tuple[str, ...] | list[str]
) -> str:
    validate_partition(partition, symbols)
    membership = {
        member: group["id"]
        for group in partition["groups"]
        for member in group["members"]
    }
    body = [
        membership[left] == membership[right]
        for left, right in itertools.combinations(symbols, 2)
    ]
    return sha256_bytes(canonical_json(body))


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    receipt_sha256: str,
    state: dict[str, Any],
) -> PartitionSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": receipt_sha256,
        "state": state,
    }
    return PartitionSnapshot(
        revision,
        parent_sha256,
        receipt_sha256,
        state,
        sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> PartitionSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0067-seed"}))
    return _snapshot(0, None, receipt, {"weights": [0.0, 0.0, 0.0, 0.0]})


def project_snapshot(snapshot: PartitionSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0067 snapshot exceeds inheritance budget")
    return value


def restore_snapshot(value: dict[str, Any]) -> PartitionSnapshot:
    if set(value) != {"revision", "parent_sha256", "outcome_receipt_sha256", "state", "sha256"}:
        raise ValueError("OT-0067 snapshot projection authority differs")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0067 snapshot identity differs")
    return restored


def snapshot_errors(snapshot: PartitionSnapshot, regime: dict[str, Any]) -> int:
    partition = snapshot.state.get("partition")
    if partition is None:
        return sum(item["correct_side"] != "left" for item in regime["heldout"])
    return partition_errors(partition, regime["heldout"], regime["symbols"])


def attempt_update(
    current: PartitionSnapshot,
    partition: dict[str, Any],
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[PartitionSnapshot, str]:
    if receipt is None:
        return current, "no-credit"
    try:
        expected = complete_contact(
            contact, [item["selected_side"] for item in receipt["outcomes"]]
        )
        if canonical_json(expected) != canonical_json(receipt):
            raise ValueError("receipt differs")
        validate_partition(partition, contact["symbols"])
    except (KeyError, TypeError, ValueError):
        return current, "invalid"
    if partition_errors(partition, _contact_examples(contact), contact["symbols"]):
        return current, "contact-imperfect"
    successor = _snapshot(
        current.revision + 1,
        current.sha256,
        receipt["sha256"],
        {"partition": copy.deepcopy(partition)},
    )
    try:
        project_snapshot(successor)
    except ValueError:
        return current, "invalid"
    return successor, "committed"


def stateless_certificate(regime: dict[str, Any]) -> dict[str, Any]:
    sides = [item["correct_side"] for item in regime["heldout"]]
    body = {
        "event_observation_invariant": True,
        "left_errors": sides.count("right"),
        "right_errors": sides.count("left"),
        "feature_deltas_zero": True,
    }
    return {**body, "pass": body["left_errors"] == body["right_errors"] == 4}


def exact_replay_errors(
    retained_rows: list[dict[str, Any]], heldout: list[dict[str, Any]]
) -> int:
    remembered = {
        tuple(row["contact"]["query_symbols"]): row["outcome"]["resolved_side"]
        for row in retained_rows
    }
    return sum(
        remembered.get(tuple(item["query_symbols"]), "left") != item["correct_side"]
        for item in heldout
    )


def compression_certificate(regime: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {"contact": public, "outcome": outcome}
        for public, outcome in zip(
            public_contact(regime["contact"])["bundles"],
            receipt["outcomes"],
            strict=True,
        )
    ]
    row_bytes = [len(canonical_json(item)) for item in rows]
    allowed = [()] + [
        (index,) for index, size in enumerate(row_bytes) if size <= INHERITANCE_LIMIT
    ]
    minimum_survivors = len(PARTITION_HYPOTHESES)
    divergent = True
    replay_errors = []
    for indices in allowed:
        observations = [regime["diagnostic_pairs"][index] for index in indices]
        surviving = consistent_partitions(regime["target_labels"], observations)
        behaviors = {
            tuple(same_group(labels, pair) for pair in regime["heldout_pairs"])
            for labels in surviving
        }
        minimum_survivors = min(minimum_survivors, len(surviving))
        divergent = divergent and len(behaviors) >= 2
        replay_errors.append(exact_replay_errors([rows[index] for index in indices], regime["heldout"]))
    full = consistent_partitions(regime["target_labels"], regime["diagnostic_pairs"])
    overlap = set(regime["diagnostic_pairs"]) & set(regime["heldout_pairs"])
    body = {
        "raw_bytes": len(canonical_json(rows)),
        "minimum_row_bytes": min(row_bytes),
        "maximum_row_bytes": max(row_bytes),
        "allowed_projection_count": len(allowed),
        "maximum_allowed_rows": max(len(indices) for indices in allowed),
        "minimum_surviving_partitions": minimum_survivors,
        "all_allowed_endpoint_divergent": divergent,
        "full_contact_unique": full == [regime["target_labels"]],
        "heldout_overlap_count": len(overlap),
        "allowed_replay_errors": replay_errors,
        "all_allowed_replay_errors_four": all(value == 4 for value in replay_errors),
    }
    return {
        **body,
        "pass": body["raw_bytes"] > INHERITANCE_LIMIT
        and body["minimum_row_bytes"] >= 513
        and body["maximum_allowed_rows"] == 1
        and body["minimum_surviving_partitions"] >= 2
        and body["all_allowed_endpoint_divergent"]
        and body["full_contact_unique"]
        and body["heldout_overlap_count"] == 0
        and body["all_allowed_replay_errors_four"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def _output_only_certificate(previous: dict[str, Any], regime: dict[str, Any]) -> dict[str, Any]:
    errors = []
    for within in SIDES:
        for across in SIDES:
            candidate = copy.deepcopy(previous)
            candidate["within_output"] = within
            candidate["across_output"] = across
            errors.append(
                partition_errors(candidate, _contact_examples(regime["contact"]), regime["symbols"])
            )
    body = {"minimum_contact_errors": min(errors), "error_vector": errors}
    return {**body, "pass": body["minimum_contact_errors"] >= 1}


def _fixed_control_vectors(
    task: dict[str, Any], references: list[dict[str, Any]]
) -> dict[str, Any]:
    left = [sum(item["correct_side"] != "left" for item in regime["heldout"]) for regime in task["regimes"]]
    right = [sum(item["correct_side"] != "right" for item in regime["heldout"]) for regime in task["regimes"]]
    alternating = [
        sum(item["correct_side"] != SIDES[index % 2] for index, item in enumerate(regime["heldout"]))
        for regime in task["regimes"]
    ]
    fixed_references = [
        [partition_errors(reference, regime["heldout"], regime["symbols"]) for regime in task["regimes"]]
        for reference in references
    ]
    vectors = {
        "empty": left,
        "digest": left,
        "no_persistence": left,
        "always_left": left,
        "always_right": right,
        "alternating": alternating,
        "fixed_references": fixed_references,
    }
    complete = [left, right, alternating, *fixed_references]
    return {
        **vectors,
        "pass": all(vector != [0, 0, 0] for vector in complete),
        "receipt_sha256": sha256_bytes(canonical_json(vectors)),
    }


def _one_group(partition: dict[str, Any], symbols: tuple[str, ...]) -> dict[str, Any]:
    return {
        "groups": [{"id": "one", "members": list(symbols)}],
        "within_output": partition["within_output"],
        "across_output": partition["across_output"],
    }


def _overbudget_partition(symbols: tuple[str, ...]) -> dict[str, Any]:
    return {
        "groups": [
            {
                "id": f"group-{index}-" + chr(97 + index) * 30,
                "members": [symbol],
            }
            for index, symbol in enumerate(symbols)
        ],
        "within_output": "left",
        "across_output": "right",
    }


def evaluate_case(case_index: int) -> dict[str, Any]:
    task = build_case(case_index)
    current = initial_snapshot()
    references: list[dict[str, Any]] = []
    results = []
    for regime in task["regimes"]:
        reference = reference_partition(regime)
        choices = ["left"] * len(regime["contact"]["bundles"])
        receipt = complete_contact(regime["contact"], choices)
        before = current
        updated, reason = attempt_update(before, reference, receipt, regime["contact"])
        withheld, withheld_reason = attempt_update(before, reference, None, regime["contact"])
        duplicate = copy.deepcopy(reference)
        duplicate["groups"][0]["members"].append(duplicate["groups"][1]["members"][0])
        duplicate_result, duplicate_reason = attempt_update(before, duplicate, receipt, regime["contact"])
        missing = copy.deepcopy(reference)
        missing["groups"][0]["members"].pop()
        missing_result, missing_reason = attempt_update(before, missing, receipt, regime["contact"])
        empty = copy.deepcopy(reference)
        empty["groups"].append({"id": "empty", "members": []})
        empty_result, empty_reason = attempt_update(before, empty, receipt, regime["contact"])
        unknown = copy.deepcopy(reference)
        unknown["groups"][0]["members"][0] = "unknown"
        unknown_result, unknown_reason = attempt_update(before, unknown, receipt, regime["contact"])
        overbudget_result, overbudget_reason = attempt_update(
            before, _overbudget_partition(regime["symbols"]), receipt, regime["contact"]
        )
        collapsed = _one_group(reference, regime["symbols"])
        collapsed_errors = partition_errors(collapsed, regime["heldout"], regime["symbols"])
        fixed_output_errors = []
        for side in SIDES:
            fixed = copy.deepcopy(reference)
            fixed["within_output"] = fixed["across_output"] = side
            fixed_output_errors.append(partition_errors(fixed, regime["heldout"], regime["symbols"]))
        imperfect_result, imperfect_reason = attempt_update(
            before, collapsed, receipt, regime["contact"]
        )
        fingerprint = membership_fingerprint(reference, regime["symbols"])
        result = {
            "index": regime["index"],
            "pre_update_errors": snapshot_errors(before, regime),
            "reference_errors": snapshot_errors(updated, regime),
            "update_reason": reason,
            "parent_exact": updated.parent_sha256 == before.sha256,
            "successor_exact": updated.sha256 != before.sha256,
            "restore_exact": restore_snapshot(project_snapshot(updated)).sha256 == updated.sha256,
            "rollback_errors": snapshot_errors(before, regime),
            "no_credit_preserved": withheld.sha256 == before.sha256 and withheld_reason == "no-credit",
            "duplicate_preserved": duplicate_result.sha256 == before.sha256 and duplicate_reason == "invalid",
            "missing_preserved": missing_result.sha256 == before.sha256 and missing_reason == "invalid",
            "empty_preserved": empty_result.sha256 == before.sha256 and empty_reason == "invalid",
            "unknown_preserved": unknown_result.sha256 == before.sha256 and unknown_reason == "invalid",
            "overbudget_preserved": overbudget_result.sha256 == before.sha256 and overbudget_reason == "invalid",
            "imperfect_preserved": imperfect_result.sha256 == before.sha256 and imperfect_reason == "contact-imperfect",
            "membership_sha256": fingerprint,
            "membership_changed": not references or fingerprint != membership_fingerprint(references[-1], regime["symbols"]),
            "output_only_correction": {"pass": True, "minimum_contact_errors": None}
            if not references
            else _output_only_certificate(references[-1], regime),
            "complete_deletion_errors": snapshot_errors(initial_snapshot(), regime),
            "one_group_ablation_errors": collapsed_errors,
            "membership_deletion_errors": snapshot_errors(missing_result, regime),
            "fixed_output_ablation_errors": fixed_output_errors,
            "stateless_certificate": stateless_certificate(regime),
            "compression_certificate": compression_certificate(regime, receipt),
            "snapshot_bytes": len(canonical_json(project_snapshot(updated))),
        }
        result["pass"] = (
            result["reference_errors"] == 0
            and result["update_reason"] == "committed"
            and result["parent_exact"]
            and result["successor_exact"]
            and result["restore_exact"]
            and result["no_credit_preserved"]
            and result["duplicate_preserved"]
            and result["missing_preserved"]
            and result["empty_preserved"]
            and result["unknown_preserved"]
            and result["overbudget_preserved"]
            and result["imperfect_preserved"]
            and result["membership_changed"]
            and result["output_only_correction"]["pass"]
            and result["complete_deletion_errors"] > 0
            and result["one_group_ablation_errors"] > 0
            and result["membership_deletion_errors"] > 0
            and all(value > 0 for value in result["fixed_output_ablation_errors"])
            and result["stateless_certificate"]["pass"]
            and result["compression_certificate"]["pass"]
            and result["snapshot_bytes"] <= INHERITANCE_LIMIT
        )
        results.append(result)
        references.append(reference)
        current = updated
    frozen_first = [
        partition_errors(references[0], regime["heldout"], regime["symbols"])
        for regime in task["regimes"]
    ]
    frozen_second = [
        partition_errors(references[1], regime["heldout"], regime["symbols"])
        for regime in task["regimes"]
    ]
    fixed = _fixed_control_vectors(task, references)
    body = {
        "case_index": case_index,
        "pre_update_errors": [item["pre_update_errors"] for item in results],
        "reference_errors": [item["reference_errors"] for item in results],
        "frozen_first_errors": frozen_first,
        "frozen_second_errors": frozen_second,
        "fixed_controls": fixed,
        "regimes": results,
    }
    body["pass"] = (
        all(item["pass"] for item in results)
        and body["reference_errors"] == [0, 0, 0]
        and frozen_first[1] == 8
        and frozen_second[2] == 8
        and fixed["pass"]
    )
    body["receipt_sha256"] = sha256_bytes(canonical_json(body))
    return body


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    surface = orientation + canonical_json(schema).decode()
    forbidden = [
        term
        for term in ("interleaved", "contiguous", "cross-cutting", "group-0")
        if term in surface.lower()
    ]
    body = {
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "forbidden_terms": forbidden,
        "concrete_symbol_hits": re.findall(r"symbol-[0-9a-f]{8,}", surface),
        "schema_unsupported_keywords": sorted(unsupported_keywords(schema)),
    }
    return {
        **body,
        "pass": not forbidden
        and not body["concrete_symbol_hits"]
        and not body["schema_unsupported_keywords"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def regime_three_impossibility_certificate() -> dict[str, Any]:
    previous = TARGET_LABELS[1]
    target = TARGET_LABELS[2]
    singleton = tuple(range(SYMBOL_COUNT))
    changed = [
        pair
        for pair in ALL_PAIRS
        if same_group(previous, pair) != same_group(target, pair)
    ]
    target_same = [pair for pair in changed if same_group(target, pair)]
    target_different = [pair for pair in changed if not same_group(target, pair)]
    singleton_mismatches = [
        pair
        for pair in ALL_PAIRS
        if same_group(singleton, pair) != same_group(target, pair)
    ]
    available_after_required_hiding = [
        pair for pair in ALL_PAIRS if pair not in set(target_same)
    ]
    body = {
        "regime_index": 3,
        "target_same_changed_pair_count": len(target_same),
        "target_different_changed_pair_count": len(target_different),
        "balanced_all_wrong_heldout_count": len(
            list(itertools.combinations(target_different, 4))
        ),
        "required_hidden_same_pairs_sha256": sha256_bytes(canonical_json(target_same)),
        "singleton_mismatch_pairs_sha256": sha256_bytes(
            canonical_json(singleton_mismatches)
        ),
        "required_hidden_equals_singleton_mismatches": target_same
        == singleton_mismatches,
        "singleton_matches_every_available_pair": all(
            same_group(singleton, pair) == same_group(target, pair)
            for pair in available_after_required_hiding
        ),
        "singleton_is_in_hypothesis_family": singleton in PARTITION_HYPOTHESES,
    }
    return {
        **body,
        "pass": body["target_same_changed_pair_count"] == 4
        and body["target_different_changed_pair_count"] >= 4
        and body["balanced_all_wrong_heldout_count"] == 495
        and body["required_hidden_equals_singleton_mismatches"]
        and body["singleton_matches_every_available_pair"]
        and body["singleton_is_in_hypothesis_family"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    surface = actor_surface_authority(repo)
    impossibility = regime_three_impossibility_certificate()
    body = {
        "case_count": 0,
        "passing_case_count": 0,
        "required_case_count": acceptance["scenario_count"],
        "regime_three_impossibility": impossibility,
        "partition_hypothesis_count": len(PARTITION_HYPOTHESES),
        "actor_surface": surface,
        "candidate_outputs": False,
        "hosted_model_calls": 0,
        "future_candidate_authorization": 0,
    }
    gates = {
        "complete": False,
        "regime_three_identifiable": not impossibility["pass"],
        "impossibility_reproduced": impossibility["pass"],
        "hypothesis_complete": body["partition_hypothesis_count"] == 4140,
        "actor_surface": surface["pass"],
        "candidate_free": not body["candidate_outputs"] and body["hosted_model_calls"] == 0,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        **body,
        "gates": gates,
        "disposition": "rejected",
        "pilot_pass": False,
    }


def validate_run_lock(repo: Path, execution: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0067 run lock omits implementation identity")
    if subprocess.run(["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo).returncode:
        raise RuntimeError("OT-0067 implementation is not an execution ancestor")
    observed = {name: sha256_file(repo / path) for name, path in fixed_input_paths().items()}
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0067 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(repo, "diff", "--name-only", f"{implementation}..{execution}", "--", *protected)
    if changed:
        raise RuntimeError(f"OT-0067 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0067 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution)
    if output.exists():
        raise RuntimeError("OT-0067 raw output already exists")
    first = run_calibration(repo)
    second = run_calibration(repo)
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    audit = subprocess.run(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    summary = dict(first)
    summary["gates"] = {
        **summary["gates"],
        "deterministic_replay": canonical_json(first) == canonical_json(second),
        "tests": tests.returncode == 0,
        "audit": audit.returncode == 0,
    }
    summary["pilot_pass"] = all(summary["gates"].values())
    summary["disposition"] = "promoted" if summary["pilot_pass"] else "rejected"
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution,
        "summary": summary,
        "impossibility_certificate": first["regime_three_impossibility"],
        "verification": {
            "tests_returncode": tests.returncode,
            "tests_stdout_sha256": sha256_bytes(tests.stdout.encode()),
            "tests_stderr_sha256": sha256_bytes(tests.stderr.encode()),
            "audit_returncode": audit.returncode,
            "audit_stdout_sha256": sha256_bytes(audit.stdout.encode()),
            "audit_stderr_sha256": sha256_bytes(audit.stderr.encode()),
        },
    }
    write_sealed_json(output, raw)
    output.chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="equivalence-partition-calibration-impossibility",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0067_harness.py --output $EVIDENCE/runs/OT-0067/ot-0067-equivalence-partition-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate output and hosted model calls are forbidden.",
                "Controller-private reference partitions prove opportunity only and are not endogenous evidence.",
                "The frozen regime-three identifiability and all-wrong heldout gates are jointly impossible.",
                "No learner is authorized and this is not representation-escape evidence.",
            ],
            input_manifests=[
                str(OT66_MANIFEST_PATH),
                str(OT65_MANIFEST_PATH),
                str(OT48_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0067-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, summary = run(args.repo.resolve(), args.run_id, args.output.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(args.repo.resolve())), "summary": summary},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
