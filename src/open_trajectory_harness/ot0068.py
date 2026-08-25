from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from . import ot0067 as relational
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


EXPERIMENT_ID = "OT-0068"
ACCEPTANCE_PATH = Path("spec/ot-0068-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0068-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0068/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0068/actor-output.schema.json")
OT67_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0067/ot-0067-equivalence-partition-calibration-001.json"
)
OT66_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0066/ot-0066-disjoint-temporal-topology-candidate-001.json"
)
OT65_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0065/ot-0065-temporal-state-topology-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0068-identifiable-equivalence-calibration-001"
SIDES = relational.SIDES
SYMBOL_COUNT = 8
INHERITANCE_LIMIT = 620
MAX_GROUPS = 8
MAX_IDENTIFIER_BYTES = 40
PARTITION_HYPOTHESES = relational.PARTITION_HYPOTHESES
ALL_PAIRS = relational.ALL_PAIRS
TARGET_LABELS = (
    (0, 1, 0, 1, 0, 1, 0, 1),
    (0, 0, 0, 0, 1, 1, 1, 1),
    (0, 0, 1, 1, 0, 0, 1, 1),
)
HELDOUT_PAIRS = {
    1: ((0, 2), (4, 6), (1, 3), (5, 7), (0, 1), (0, 3), (2, 5), (4, 7)),
    2: ((0, 1), (0, 3), (4, 5), (4, 7), (0, 4), (0, 6), (1, 5), (1, 7)),
    3: ((0, 4), (0, 5), (1, 4), (2, 6), (0, 2), (0, 3), (1, 2), (1, 3)),
}


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0068.py"),
        "relational_core_sha256": Path("src/open_trajectory_harness/ot0067.py"),
        "entrypoint_sha256": Path("experiments/ot_0068_harness.py"),
        "test_sha256": Path("tests/test_ot0068.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0067_manifest_sha256": OT67_MANIFEST_PATH,
        "ot0066_manifest_sha256": OT66_MANIFEST_PATH,
        "ot0065_manifest_sha256": OT65_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def symbol_tokens(case_index: int) -> tuple[str, ...]:
    tokens = [
        "symbol-" + sha256_bytes(f"ot-0068:{case_index}:{index}".encode())[:12]
        for index in range(SYMBOL_COUNT)
    ]
    return tuple(
        sorted(
            tokens,
            key=lambda token: sha256_bytes(
                f"ot-0068-order:{case_index}:{token}".encode()
            ),
        )
    )


def heldout_pairs(regime_index: int) -> list[tuple[int, int]]:
    try:
        return list(HELDOUT_PAIRS[regime_index])
    except KeyError as error:
        raise ValueError("OT-0068 regime is unavailable") from error


def diagnostic_pairs(
    target: tuple[int, ...], heldout: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    heldout_set = set(heldout)
    pool = [pair for pair in ALL_PAIRS if pair not in heldout_set]
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
                if relational.same_group(labels, pair)
                == relational.same_group(target, pair)
            ]
            if 0 < len(narrowed) < len(remaining):
                choices.append((len(narrowed), pair, narrowed))
        if not choices:
            raise ValueError("OT-0068 diagnostics cannot identify the target")
        _, chosen, remaining = min(choices, key=lambda value: value[:2])
        selected.append(chosen)
    for pair in pool:
        if pair not in selected:
            selected.append(pair)
        if len(selected) == 15:
            break
    if (
        len(selected) != 15
        or relational.consistent_partitions(target, selected) != [target]
    ):
        raise ValueError("OT-0068 diagnostic set is incomplete")
    return selected


def _events(case_index: int, bundle_index: int) -> list[dict[str, Any]]:
    order = SIDES if (case_index + bundle_index) % 2 == 0 else tuple(reversed(SIDES))
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
    return {
        "bundle_id": f"bundle-{regime_index}-{bundle_index:02d}",
        "query_symbols": _encode_pair(pair, symbols),
        "presentations": [
            {
                "presentation_id": sha256_bytes(
                    f"ot-0068:{case_index}:{regime_index}:{bundle_index}".encode()
                )[:20],
                "events": _events(case_index, bundle_index),
                "correct_side": relational.resolved_side(target, pair),
            }
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
    if len(choices) != len(contact["bundles"]) or any(
        choice not in SIDES for choice in choices
    ):
        raise ValueError("OT-0068 contact choices are malformed")
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
    body = {"kind": "ot-0068-completed-contact", "outcomes": outcomes}
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
                "correct_side": relational.resolved_side(target, pair),
            }
            for pair in heldout
        ],
        "heldout_pairs": heldout,
    }


def build_case(case_index: int) -> dict[str, Any]:
    if not 0 <= case_index < 16:
        raise ValueError("OT-0068 case index is unavailable")
    return {
        "case_index": case_index,
        "regimes": [build_regime(case_index, index) for index in (1, 2, 3)],
    }


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    receipt_sha256: str,
    state: dict[str, Any],
) -> relational.PartitionSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": receipt_sha256,
        "state": state,
    }
    return relational.PartitionSnapshot(
        revision,
        parent_sha256,
        receipt_sha256,
        state,
        sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> relational.PartitionSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0068-seed"}))
    return _snapshot(0, None, receipt, {"weights": [0.0, 0.0, 0.0, 0.0]})


def project_snapshot(snapshot: relational.PartitionSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0068 snapshot exceeds inheritance budget")
    return value


def restore_snapshot(value: dict[str, Any]) -> relational.PartitionSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "outcome_receipt_sha256",
        "state",
        "sha256",
    }:
        raise ValueError("OT-0068 snapshot projection authority differs")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0068 snapshot identity differs")
    return restored


def snapshot_errors(
    snapshot: relational.PartitionSnapshot, regime: dict[str, Any]
) -> int:
    partition = snapshot.state.get("partition")
    if partition is None:
        return sum(item["correct_side"] != "left" for item in regime["heldout"])
    return relational.partition_errors(
        partition, regime["heldout"], regime["symbols"]
    )


def attempt_update(
    current: relational.PartitionSnapshot,
    partition: dict[str, Any],
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[relational.PartitionSnapshot, str]:
    if receipt is None:
        return current, "no-credit"
    try:
        expected = complete_contact(
            contact, [item["selected_side"] for item in receipt["outcomes"]]
        )
        if canonical_json(expected) != canonical_json(receipt):
            raise ValueError("receipt differs")
        relational.validate_partition(partition, contact["symbols"])
    except (KeyError, TypeError, ValueError):
        return current, "invalid"
    if relational.partition_errors(
        partition, relational._contact_examples(contact), contact["symbols"]
    ):
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


def compression_certificate(
    regime: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    rows = [
        {"contact": public, "outcome": outcome}
        for public, outcome in zip(
            public_contact(regime["contact"])["bundles"],
            receipt["outcomes"],
            strict=True,
        )
    ]
    row_payloads = [canonical_json(item) for item in rows]
    row_bytes = [len(item) for item in row_payloads]
    subset_sizes = [2] * (1 << len(rows))
    allowed = []
    for mask in range(1 << len(rows)):
        if mask:
            bit = mask & -mask
            index = bit.bit_length() - 1
            parent = mask ^ bit
            subset_sizes[mask] = (
                subset_sizes[parent]
                + row_bytes[index]
                + (0 if parent == 0 else 1)
            )
        if subset_sizes[mask] <= INHERITANCE_LIMIT:
            allowed.append(
                tuple(index for index in range(len(rows)) if mask & (1 << index))
            )
    evaluated_count = len(subset_sizes)
    minimum_survivors = len(PARTITION_HYPOTHESES)
    divergent = True
    replay_errors = []
    for indices in allowed:
        observations = [regime["diagnostic_pairs"][index] for index in indices]
        surviving = relational.consistent_partitions(
            regime["target_labels"], observations
        )
        behaviors = {
            tuple(
                relational.same_group(labels, pair)
                for pair in regime["heldout_pairs"]
            )
            for labels in surviving
        }
        minimum_survivors = min(minimum_survivors, len(surviving))
        divergent = divergent and len(behaviors) >= 2
        replay_errors.append(
            relational.exact_replay_errors(
                [rows[index] for index in indices], regime["heldout"]
            )
        )
    full = relational.consistent_partitions(
        regime["target_labels"], regime["diagnostic_pairs"]
    )
    overlap = set(regime["diagnostic_pairs"]) & set(regime["heldout_pairs"])
    body = {
        "raw_bytes": len(canonical_json(rows)),
        "minimum_row_bytes": min(row_bytes),
        "maximum_row_bytes": max(row_bytes),
        "evaluated_subset_count": evaluated_count,
        "allowed_projection_count": len(allowed),
        "maximum_measured_projection_bytes": max(subset_sizes),
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
        "pass": body["raw_bytes"] > 6000
        and 311 <= body["minimum_row_bytes"] <= INHERITANCE_LIMIT
        and body["maximum_row_bytes"] <= INHERITANCE_LIMIT
        and body["evaluated_subset_count"] == 32768
        and body["allowed_projection_count"] == 16
        and body["maximum_allowed_rows"] == 1
        and body["minimum_surviving_partitions"] >= 800
        and body["all_allowed_endpoint_divergent"]
        and body["full_contact_unique"]
        and body["heldout_overlap_count"] == 0
        and body["all_allowed_replay_errors_four"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def _overbudget_reference(reference: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(reference)
    for index, group in enumerate(candidate["groups"]):
        group["id"] = chr(97 + index) * MAX_IDENTIFIER_BYTES
    return candidate


def evaluate_case(case_index: int) -> dict[str, Any]:
    task = build_case(case_index)
    current = initial_snapshot()
    references: list[dict[str, Any]] = []
    results = []
    for regime in task["regimes"]:
        reference = relational.reference_partition(regime)
        choices = ["left"] * len(regime["contact"]["bundles"])
        receipt = complete_contact(regime["contact"], choices)
        before = current
        updated, reason = attempt_update(before, reference, receipt, regime["contact"])
        withheld, withheld_reason = attempt_update(
            before, reference, None, regime["contact"]
        )
        duplicate = copy.deepcopy(reference)
        duplicate["groups"][0]["members"].append(
            duplicate["groups"][1]["members"][0]
        )
        duplicate_result, duplicate_reason = attempt_update(
            before, duplicate, receipt, regime["contact"]
        )
        missing = copy.deepcopy(reference)
        missing["groups"][0]["members"].pop()
        missing_result, missing_reason = attempt_update(
            before, missing, receipt, regime["contact"]
        )
        empty = copy.deepcopy(reference)
        empty["groups"].append({"id": "empty", "members": []})
        empty_result, empty_reason = attempt_update(
            before, empty, receipt, regime["contact"]
        )
        unknown = copy.deepcopy(reference)
        unknown["groups"][0]["members"][0] = "unknown"
        unknown_result, unknown_reason = attempt_update(
            before, unknown, receipt, regime["contact"]
        )
        overbudget_result, overbudget_reason = attempt_update(
            before,
            _overbudget_reference(reference),
            receipt,
            regime["contact"],
        )
        collapsed = relational._one_group(reference, regime["symbols"])
        collapsed_errors = relational.partition_errors(
            collapsed, regime["heldout"], regime["symbols"]
        )
        fixed_output_errors = []
        for side in SIDES:
            fixed = copy.deepcopy(reference)
            fixed["within_output"] = fixed["across_output"] = side
            fixed_output_errors.append(
                relational.partition_errors(
                    fixed, regime["heldout"], regime["symbols"]
                )
            )
        imperfect_result, imperfect_reason = attempt_update(
            before, collapsed, receipt, regime["contact"]
        )
        fingerprint = relational.membership_fingerprint(
            reference, regime["symbols"]
        )
        result = {
            "index": regime["index"],
            "pre_update_errors": snapshot_errors(before, regime),
            "reference_errors": snapshot_errors(updated, regime),
            "update_reason": reason,
            "parent_exact": updated.parent_sha256 == before.sha256,
            "successor_exact": updated.sha256 != before.sha256,
            "restore_exact": restore_snapshot(project_snapshot(updated)).sha256
            == updated.sha256,
            "rollback_errors": snapshot_errors(before, regime),
            "no_credit_preserved": withheld.sha256 == before.sha256
            and withheld_reason == "no-credit",
            "duplicate_preserved": duplicate_result.sha256 == before.sha256
            and duplicate_reason == "invalid",
            "missing_preserved": missing_result.sha256 == before.sha256
            and missing_reason == "invalid",
            "empty_preserved": empty_result.sha256 == before.sha256
            and empty_reason == "invalid",
            "unknown_preserved": unknown_result.sha256 == before.sha256
            and unknown_reason == "invalid",
            "overbudget_preserved": overbudget_result.sha256 == before.sha256
            and overbudget_reason == "invalid",
            "imperfect_preserved": imperfect_result.sha256 == before.sha256
            and imperfect_reason == "contact-imperfect",
            "membership_sha256": fingerprint,
            "membership_changed": not references
            or fingerprint
            != relational.membership_fingerprint(
                references[-1], regime["symbols"]
            ),
            "output_only_correction": (
                {"pass": True, "minimum_contact_errors": None}
                if not references
                else relational._output_only_certificate(references[-1], regime)
            ),
            "complete_deletion_errors": snapshot_errors(initial_snapshot(), regime),
            "one_group_ablation_errors": collapsed_errors,
            "membership_deletion_errors": snapshot_errors(missing_result, regime),
            "fixed_output_ablation_errors": fixed_output_errors,
            "stateless_certificate": relational.stateless_certificate(regime),
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
        relational.partition_errors(
            references[0], regime["heldout"], regime["symbols"]
        )
        for regime in task["regimes"]
    ]
    frozen_second = [
        relational.partition_errors(
            references[1], regime["heldout"], regime["symbols"]
        )
        for regime in task["regimes"]
    ]
    fixed = relational._fixed_control_vectors(task, references)
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
        and body["pre_update_errors"] == [4, 8, 8]
        and body["reference_errors"] == [0, 0, 0]
        and frozen_first == [0, 8, 4]
        and frozen_second == [3, 0, 8]
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
        for term in ("interleaved", "contiguous", "crossed", "group-0")
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


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    order = range(acceptance["scenario_count"])
    cases = [evaluate_case(index) for index in order]
    reverse = [evaluate_case(index) for index in reversed(order)]
    surface = actor_surface_authority(repo)
    certificates = [
        item["compression_certificate"]
        for case in cases
        for item in case["regimes"]
    ]
    body = {
        "case_count": len(cases),
        "passing_case_count": sum(item["pass"] for item in cases),
        "partition_hypothesis_count": len(PARTITION_HYPOTHESES),
        "reference_error_vectors": sorted(
            {tuple(item["reference_errors"]) for item in cases}
        ),
        "pre_update_error_vectors": sorted(
            {tuple(item["pre_update_errors"]) for item in cases}
        ),
        "frozen_first_error_vectors": sorted(
            {tuple(item["frozen_first_errors"]) for item in cases}
        ),
        "frozen_second_error_vectors": sorted(
            {tuple(item["frozen_second_errors"]) for item in cases}
        ),
        "minimum_row_bytes": min(item["minimum_row_bytes"] for item in certificates),
        "maximum_row_bytes": max(item["maximum_row_bytes"] for item in certificates),
        "minimum_raw_bytes": min(item["raw_bytes"] for item in certificates),
        "minimum_surviving_partitions": min(
            item["minimum_surviving_partitions"] for item in certificates
        ),
        "maximum_allowed_rows": max(
            item["maximum_allowed_rows"] for item in certificates
        ),
        "evaluated_subset_counts": sorted(
            {item["evaluated_subset_count"] for item in certificates}
        ),
        "allowed_projection_counts": sorted(
            {item["allowed_projection_count"] for item in certificates}
        ),
        "maximum_heldout_overlap": max(
            item["heldout_overlap_count"] for item in certificates
        ),
        "exact_replay_error_vectors": sorted(
            {tuple(item["allowed_replay_errors"]) for item in certificates}
        ),
        "actor_surface": surface,
        "reverse_order_placebo": [item["receipt_sha256"] for item in cases]
        == list(reversed([item["receipt_sha256"] for item in reverse])),
        "candidate_outputs": False,
        "hosted_model_calls": 0,
        "future_candidate_authorization": 1,
        "case_receipt_sha256": sha256_bytes(canonical_json(cases)),
    }
    gates = {
        "complete": body["case_count"] == acceptance["scenario_count"]
        and body["passing_case_count"] == acceptance["scenario_count"],
        "partition_family_complete": body["partition_hypothesis_count"]
        == acceptance["partition_hypothesis_count"],
        "hidden_opportunity": body["reference_error_vectors"] == [(0, 0, 0)],
        "prior_harm": body["pre_update_error_vectors"] == [(4, 8, 8)],
        "contradiction": body["frozen_first_error_vectors"] == [(0, 8, 4)],
        "distinct_correction": body["frozen_second_error_vectors"] == [(3, 0, 8)],
        "compression": body["minimum_raw_bytes"]
        >= acceptance["minimum_raw_contact_bytes"]
        and body["minimum_row_bytes"] >= acceptance["minimum_complete_row_bytes"]
        and body["maximum_row_bytes"]
        <= acceptance["maximum_complete_row_bytes"]
        and body["minimum_surviving_partitions"]
        >= acceptance["minimum_surviving_partitions"]
        and body["maximum_allowed_rows"] == acceptance["maximum_allowed_rows"],
        "subset_exhaustion": body["evaluated_subset_counts"] == [32768]
        and body["allowed_projection_counts"] == [16],
        "heldout_disjoint": body["maximum_heldout_overlap"] == 0,
        "exact_replay": all(
            all(value == 4 for value in vector)
            for vector in body["exact_replay_error_vectors"]
        ),
        "actor_surface": surface["pass"],
        "reverse_order_placebo": body["reverse_order_placebo"],
        "candidate_free": not body["candidate_outputs"]
        and body["hosted_model_calls"] == 0,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        **body,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0068 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0068 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0068 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"OT-0068 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0068 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution)
    if output.exists():
        raise RuntimeError("OT-0068 raw output already exists")
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
        "cases": [
            evaluate_case(index)
            for index in range(load_json(repo / ACCEPTANCE_PATH)["scenario_count"])
        ],
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
            kind="identifiable-equivalence-partition-candidate-free-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0068_harness.py --output $EVIDENCE/runs/OT-0068/ot-0068-identifiable-equivalence-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate output and hosted model calls are forbidden.",
                "Controller-private reference partitions prove opportunity only and are not endogenous evidence.",
                "A pass authorizes at most one fresh OT-0069 learner and is not representation-escape evidence.",
            ],
            input_manifests=[
                str(OT67_MANIFEST_PATH),
                str(OT66_MANIFEST_PATH),
                str(OT65_MANIFEST_PATH),
                str(OT48_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0068-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, summary = run(
            args.repo.resolve(), args.run_id, args.output.resolve()
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "manifest": str(manifest.relative_to(args.repo.resolve())),
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
