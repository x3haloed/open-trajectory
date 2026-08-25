from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from itertools import combinations, permutations, product
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


EXPERIMENT_ID = "OT-0048"
ACCEPTANCE_PATH = Path("spec/ot-0048-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0048-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0048/actor-orientation.txt")
OT1_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0037/ot-0037-e6-deterministic-ot1-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0048-representation-escape-calibration-001"
DIMENSION_COUNT = 4
CANONICAL_POINTS = tuple(
    (1, *suffix) for suffix in product((-1, 1), repeat=DIMENSION_COUNT - 1)
)
RELATIONS = tuple(combinations(range(DIMENSION_COUNT), 3))
WITNESS_TERMS = {
    "answer",
    "interaction",
    "lookup",
    "mask",
    "multiply",
    "oracle",
    "parity",
    "product",
    "triple",
    "truth table",
    "xor",
}


@dataclass(frozen=True)
class ReferenceSnapshot:
    revision: int
    parent_sha256: str | None
    outcome_receipt_sha256: str
    relation: tuple[int, ...] | None
    polarity: int | None
    sha256: str


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    outcome_receipt_sha256: str,
    relation: tuple[int, ...] | None,
    polarity: int | None,
) -> ReferenceSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": outcome_receipt_sha256,
        "relation": relation,
        "polarity": polarity,
    }
    return ReferenceSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        outcome_receipt_sha256=outcome_receipt_sha256,
        relation=relation,
        polarity=polarity,
        sha256=sha256_bytes(canonical_json(body)),
    )


def initial_reference_snapshot() -> ReferenceSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "empty-reference"}))
    return _snapshot(0, None, receipt, None, None)


def project_reference(snapshot: ReferenceSnapshot) -> dict[str, Any]:
    return {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "relation": list(snapshot.relation) if snapshot.relation is not None else None,
        "polarity": snapshot.polarity,
        "sha256": snapshot.sha256,
    }


def restore_reference(value: dict[str, Any]) -> ReferenceSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "outcome_receipt_sha256",
        "relation",
        "polarity",
        "sha256",
    }:
        raise ValueError("OT-0048 reference projection has invalid authority")
    relation = (
        tuple(value["relation"]) if isinstance(value["relation"], list) else None
    )
    if (
        type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["parent_sha256"], (str, type(None)))
        or not isinstance(value["outcome_receipt_sha256"], str)
        or relation not in (*RELATIONS, None)
        or value["polarity"] not in (-1, 1, None)
        or (relation is None) is not (value["polarity"] is None)
    ):
        raise ValueError("OT-0048 reference projection is malformed")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        relation,
        value["polarity"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0048 reference projection identity differs")
    return restored


def _target_sign(
    point: tuple[int, ...], relation: tuple[int, ...], polarity: int
) -> int:
    sign = polarity
    for index in relation:
        sign *= point[index]
    return sign


def _event_id(prefix: str, pattern_id: int, side: int) -> str:
    digest = sha256_bytes(
        canonical_json({"prefix": prefix, "pattern_id": pattern_id, "side": side})
    )
    return f"event-{pattern_id:02d}-{side}-{digest[:16]}"


def build_split(
    prefix: str, relation: tuple[int, ...], polarity: int, scale: int
) -> dict[str, Any]:
    if type(scale) is not int or scale <= 0:
        raise ValueError("OT-0048 split scale must be a positive integer")
    pairs = []
    for pattern_id, point in enumerate(CANONICAL_POINTS):
        events = [
            {
                "event_id": _event_id(prefix, pattern_id, side),
                "selector_features": list(
                    tuple(scale * value for value in point)
                    if side == 0
                    else tuple(-scale * value for value in point)
                ),
            }
            for side in range(2)
        ]
        preferred_side = 0 if _target_sign(point, relation, polarity) == 1 else 1
        pairs.append(
            {
                "pattern_id": pattern_id,
                "events": events,
                "preferred_event_id": events[preferred_side]["event_id"],
            }
        )
    return {"pairs": pairs}


def public_contact(split: dict[str, Any]) -> dict[str, Any]:
    return {
        "pairs": [
            {
                "pattern_id": pair["pattern_id"],
                "events": pair["events"],
            }
            for pair in split["pairs"]
        ]
    }


def actor_view(
    encounter: dict[str, Any],
    current_snapshot: dict[str, Any],
    prior_choices: list[str],
    released_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    if set(encounter) != {"pairs"}:
        raise ValueError("OT-0048 actor encounter has unexpected authority")
    for pair in encounter["pairs"]:
        if set(pair) != {"pattern_id", "events"} or len(pair["events"]) != 2:
            raise ValueError("OT-0048 actor encounter is malformed")
        for event in pair["events"]:
            if set(event) != {"event_id", "selector_features"}:
                raise ValueError("OT-0048 actor event has unexpected authority")
    if set(current_snapshot) != {"revision", "parent_sha256", "state", "sha256"}:
        raise ValueError("OT-0048 actor snapshot envelope has unexpected authority")
    if not isinstance(prior_choices, list) or any(
        not isinstance(item, str) for item in prior_choices
    ):
        raise ValueError("OT-0048 prior choices are malformed")
    if released_receipt is not None:
        if set(released_receipt) != {
            "outcome_credit",
            "items",
            "receipt_sha256",
        } or released_receipt["outcome_credit"] is not True:
            raise ValueError("OT-0048 released receipt has unexpected authority")
        for item in released_receipt["items"]:
            if set(item) != {
                "pattern_id",
                "selected_event_id",
                "success",
            } or item["success"] not in (True, False):
                raise ValueError("OT-0048 released receipt item is malformed")
    return {
        "encounter": encounter,
        "current_snapshot": current_snapshot,
        "prior_choices": prior_choices,
        "released_receipt": released_receipt,
    }


def _canonical_event(pair: dict[str, Any]) -> dict[str, Any]:
    return next(
        event
        for event in pair["events"]
        if event["selector_features"][0] > 0
    )


def _sign_point(event: dict[str, Any]) -> tuple[int, ...]:
    features = event["selector_features"]
    if (
        len(features) != DIMENSION_COUNT
        or any(type(value) is not int or value == 0 for value in features)
    ):
        raise ValueError("OT-0048 event features cannot be normalized")
    return tuple(1 if value > 0 else -1 for value in features)


def reference_selections(
    snapshot: ReferenceSnapshot, split: dict[str, Any]
) -> list[str]:
    selected = []
    for pair in split["pairs"]:
        canonical = _canonical_event(pair)
        sign = 1
        if snapshot.relation is not None and snapshot.polarity is not None:
            sign = _target_sign(
                _sign_point(canonical), snapshot.relation, snapshot.polarity
            )
        selected.append(
            canonical["event_id"]
            if sign == 1
            else next(
                event["event_id"]
                for event in pair["events"]
                if event["event_id"] != canonical["event_id"]
            )
        )
    return selected


def weighted_selections(
    weights: tuple[int, ...], split: dict[str, Any]
) -> list[str]:
    selected = []
    for pair in split["pairs"]:
        selected.append(
            min(
                pair["events"],
                key=lambda event: (
                    -sum(
                        weight * feature
                        for weight, feature in zip(
                            weights, event["selector_features"], strict=True
                        )
                    ),
                    event["event_id"],
                ),
            )["event_id"]
        )
    return selected


def constant_selections(split: dict[str, Any], sign: int) -> list[str]:
    return [
        (
            _canonical_event(pair)["event_id"]
            if sign == 1
            else next(
                event["event_id"]
                for event in pair["events"]
                if event["event_id"] != _canonical_event(pair)["event_id"]
            )
        )
        for pair in split["pairs"]
    ]


def verbatim_raw_selections(
    raw_entries: dict[tuple[int, ...], int], split: dict[str, Any]
) -> list[str]:
    selected = []
    for pair in split["pairs"]:
        canonical = _canonical_event(pair)
        raw_point = tuple(canonical["selector_features"])
        sign = raw_entries.get(raw_point, 1)
        selected.append(
            canonical["event_id"]
            if sign == 1
            else next(
                event["event_id"]
                for event in pair["events"]
                if event["event_id"] != canonical["event_id"]
            )
        )
    return selected


def verbatim_raw_update(
    contact: dict[str, Any], receipt: dict[str, Any]
) -> dict[tuple[int, ...], int]:
    entries = {}
    for pair, item in zip(contact["pairs"], receipt["items"], strict=True):
        canonical = _canonical_event(pair)
        preferred = item["selected_event_id"]
        if not item["success"]:
            preferred = next(
                event["event_id"]
                for event in pair["events"]
                if event["event_id"] != preferred
            )
        entries[tuple(canonical["selector_features"])] = (
            1 if preferred == canonical["event_id"] else -1
        )
    return entries


def complete_contact(
    split: dict[str, Any], selected_event_ids: list[str]
) -> dict[str, Any]:
    if len(selected_event_ids) != len(split["pairs"]):
        raise ValueError("OT-0048 selection budget differs")
    items = []
    for pair, selected in zip(split["pairs"], selected_event_ids, strict=True):
        if selected not in {event["event_id"] for event in pair["events"]}:
            raise ValueError("OT-0048 selected event is outside its pair")
        items.append(
            {
                "pattern_id": pair["pattern_id"],
                "selected_event_id": selected,
                "success": selected == pair["preferred_event_id"],
            }
        )
    body = {"outcome_credit": True, "items": items}
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def neutralize_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    body = {
        "outcome_credit": False,
        "items": [
            {
                "pattern_id": item["pattern_id"],
                "selected_event_id": item["selected_event_id"],
            }
            for item in receipt["items"]
        ],
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def update_reference(
    current: ReferenceSnapshot,
    contact: dict[str, Any],
    receipt: dict[str, Any],
) -> ReferenceSnapshot:
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if sha256_bytes(canonical_json(body)) != receipt.get("receipt_sha256"):
        raise ValueError("OT-0048 completed receipt identity differs")
    if receipt.get("outcome_credit") is False:
        return current
    if receipt.get("outcome_credit") is not True:
        raise ValueError("OT-0048 outcome-credit authority is malformed")
    if len(receipt.get("items", [])) != len(contact["pairs"]):
        raise ValueError("OT-0048 completed receipt has the wrong budget")
    examples = []
    for pair, item in zip(contact["pairs"], receipt["items"], strict=True):
        if pair["pattern_id"] != item.get("pattern_id"):
            raise ValueError("OT-0048 receipt order differs")
        selected = next(
            (
                event
                for event in pair["events"]
                if event["event_id"] == item.get("selected_event_id")
            ),
            None,
        )
        if selected is None or item.get("success") not in (True, False):
            raise ValueError("OT-0048 completed item is malformed")
        preferred = selected
        if not item["success"]:
            preferred = next(
                event
                for event in pair["events"]
                if event["event_id"] != selected["event_id"]
            )
        canonical = _canonical_event(pair)
        examples.append(
            (
                _sign_point(canonical),
                1 if preferred["event_id"] == canonical["event_id"] else -1,
            )
        )
    matches = [
        (relation, polarity)
        for relation in RELATIONS
        for polarity in (-1, 1)
        if all(
            _target_sign(point, relation, polarity) == target
            for point, target in examples
        )
    ]
    if len(matches) != 1:
        raise RuntimeError("OT-0048 completed contact does not identify one structure")
    relation, polarity = matches[0]
    return _snapshot(
        current.revision + 1,
        current.sha256,
        receipt["receipt_sha256"],
        relation,
        polarity,
    )


def score(split: dict[str, Any], selected_event_ids: list[str]) -> int:
    if len(selected_event_ids) != len(split["pairs"]):
        raise ValueError("OT-0048 score budget differs")
    return sum(
        selected != pair["preferred_event_id"]
        for pair, selected in zip(split["pairs"], selected_event_ids, strict=True)
    )


def structural_certificate(
    relation: tuple[int, ...], polarity: int, scale: int
) -> dict[str, Any]:
    targets = tuple(_target_sign(point, relation, polarity) for point in CANONICAL_POINTS)
    scaled_points = tuple(
        tuple(scale * value for value in point) for point in CANONICAL_POINTS
    )
    constant_sum = sum(targets)
    first_moments = tuple(
        sum(
            target * point[index]
            for target, point in zip(targets, scaled_points, strict=True)
        )
        for index in range(DIMENSION_COUNT)
    )
    body = {
        "sample_count": len(CANONICAL_POINTS),
        "positive_count": sum(target == 1 for target in targets),
        "negative_count": sum(target == -1 for target in targets),
        "constant_sum": constant_sum,
        "first_moments": first_moments,
        "strict_margin_sum": 0,
        "spanning_determinant_absolute": 8 * scale**DIMENSION_COUNT,
        "tie_policy_cannot_solve_all_zero_margins": len(set(targets)) == 2,
    }
    return {
        **body,
        "pass": constant_sum == 0
        and first_moments == (0,) * DIMENSION_COUNT
        and body["spanning_determinant_absolute"] > 0
        and body["positive_count"] == body["negative_count"]
        and body["tie_policy_cannot_solve_all_zero_margins"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def promoted_weight_family() -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(
            magnitude * sign
            for magnitude, sign in zip(magnitudes, signs, strict=True)
        )
        for magnitudes in permutations((1, 5, 25, 125))
        for signs in product((-1, 1), repeat=DIMENSION_COUNT)
    )


def task_family() -> tuple[tuple[tuple[int, ...], int, tuple[int, ...], int], ...]:
    return tuple(
        (first, first_polarity, later, later_polarity)
        for first in RELATIONS
        for first_polarity in (-1, 1)
        for later in RELATIONS
        if later != first
        for later_polarity in (-1, 1)
    )


def build_task(
    case: tuple[tuple[int, ...], int, tuple[int, ...], int]
) -> dict[str, Any]:
    first, first_polarity, later, later_polarity = case
    regimes = (
        (first, first_polarity),
        (first, -first_polarity),
        (later, later_polarity),
    )
    contact_scales = (1, 3, 5)
    canary_scales = (2, 4, 6)
    body = {
        "regimes": [
            {
                "index": index,
                "contact": build_split(
                    f"case-contact-{index}",
                    relation,
                    polarity,
                    contact_scales[index - 1],
                ),
                "canary": build_split(
                    f"case-canary-{index}",
                    relation,
                    polarity,
                    canary_scales[index - 1],
                ),
                "relation": relation,
                "polarity": polarity,
                "contact_scale": contact_scales[index - 1],
                "canary_scale": canary_scales[index - 1],
            }
            for index, (relation, polarity) in enumerate(regimes, start=1)
        ]
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def expected_future_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("future candidate implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": "OT-0049",
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-representation-escape-task",
            }
        )
    )


def future_task_case(task_seed: str) -> tuple[tuple[int, ...], int, tuple[int, ...], int]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("future candidate task seed is malformed")
    family = task_family()
    return family[int(task_seed, 16) % len(family)]


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    source = (repo / Path("src/open_trajectory_harness/ot0048.py")).read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    definitions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    reachable = set()
    frontier = ["actor_view"]
    observed_names = set()
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        node = definitions[name]
        observed_names.update(
            item.id for item in ast.walk(node) if isinstance(item, ast.Name)
        )
        for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
            if isinstance(call.func, ast.Name) and call.func.id in definitions:
                frontier.append(call.func.id)
    forbidden_names = {
        "_target_sign",
        "build_split",
        "build_task",
        "future_task_case",
        "promoted_weight_family",
        "reference_selections",
        "score",
        "structural_certificate",
        "task_family",
        "update_reference",
    }
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    fixture_hits = sorted(term for term in WITNESS_TERMS if term in orientation.lower())
    probe = public_contact(build_split("surface-probe", RELATIONS[0], 1, 1))
    view = actor_view(
        probe,
        {"revision": 0, "parent_sha256": None, "state": {}, "sha256": "seed"},
        [],
        None,
    )
    serialized = canonical_json(view).decode().lower()
    serialized_hits = sorted(term for term in WITNESS_TERMS if term in serialized)
    reachable_source = "\n".join(
        ast.get_source_segment(source, definitions[name]) or "" for name in reachable
    ).lower()
    reachable_source_hits = sorted(
        term for term in WITNESS_TERMS if term in reachable_source
    )
    forbidden_keys = {
        "preferred_event_id",
        "relation",
        "polarity",
        "target",
        "reference",
        "solution",
    }
    def collect_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(
                *(collect_keys(item) for item in value.values()), set()
            )
        if isinstance(value, list):
            return set().union(*(collect_keys(item) for item in value), set())
        return set()

    observed_keys = collect_keys(view)
    body = {
        "roots": ["actor_view"],
        "reachable": sorted(reachable),
        "forbidden_reachable_names": sorted(forbidden_names & (reachable | observed_names)),
        "fixture_witness_hits": fixture_hits,
        "serialized_witness_hits": serialized_hits,
        "reachable_source_witness_hits": reachable_source_hits,
        "serialized_forbidden_keys": sorted(forbidden_keys & observed_keys),
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "probe_sha256": sha256_bytes(canonical_json(view)),
    }
    return {
        **body,
        "pass": not body["forbidden_reachable_names"]
        and not fixture_hits
        and not serialized_hits
        and not reachable_source_hits
        and not body["serialized_forbidden_keys"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def evaluate_case(
    case_index: int,
    case: tuple[tuple[int, ...], int, tuple[int, ...], int],
) -> dict[str, Any]:
    task = build_task(case)
    reference = initial_reference_snapshot()
    first_learned: ReferenceSnapshot | None = None
    reference_errors = []
    unchanged_errors = []
    frozen_first_errors = []
    projection_bytes = []
    structural = []
    no_credit_identity = []
    restoration = []
    parent_rollback = []
    fixed_scores: dict[str, list[int]] = {
        "fixed-canonical": [],
        "fixed-anticanonical": [],
        "fixed-zero": [],
        **{
            f"fixed-axis-{dimension}-{name}": []
            for dimension in range(DIMENSION_COUNT)
            for name in ("negative", "positive")
        },
        **{
            f"promoted-weight-{index:03d}": []
            for index in range(len(promoted_weight_family()))
        },
        "verbatim-raw-replay": [],
    }
    for regime in task["regimes"]:
        source = restore_reference(project_reference(reference))
        selected = reference_selections(source, regime["contact"])
        receipt = complete_contact(regime["contact"], selected)
        raw_entries = verbatim_raw_update(regime["contact"], receipt)
        neutralized = update_reference(
            source, regime["contact"], neutralize_receipt(receipt)
        )
        learned = update_reference(source, regime["contact"], receipt)
        if first_learned is None:
            first_learned = learned
        reference_errors.append(
            score(regime["canary"], reference_selections(learned, regime["canary"]))
        )
        unchanged_errors.append(
            score(regime["canary"], reference_selections(source, regime["canary"]))
        )
        frozen_first_errors.append(
            score(
                regime["canary"],
                reference_selections(first_learned, regime["canary"]),
            )
        )
        projection_bytes.append(len(canonical_json(project_reference(learned))))
        structural.append(
            structural_certificate(
                regime["relation"], regime["polarity"], regime["canary_scale"]
            )
        )
        no_credit_identity.append(neutralized.sha256 == source.sha256)
        restored = restore_reference(project_reference(learned))
        restoration.append(restored.sha256 == learned.sha256)
        parent_rollback.append(
            restore_reference(project_reference(source)).sha256 == source.sha256
        )
        fixed_scores["fixed-canonical"].append(
            score(regime["canary"], constant_selections(regime["canary"], 1))
        )
        fixed_scores["fixed-anticanonical"].append(
            score(regime["canary"], constant_selections(regime["canary"], -1))
        )
        fixed_scores["fixed-zero"].append(
            score(regime["canary"], weighted_selections((0, 0, 0, 0), regime["canary"]))
        )
        fixed_scores["verbatim-raw-replay"].append(
            score(
                regime["canary"],
                verbatim_raw_selections(raw_entries, regime["canary"]),
            )
        )
        for dimension in range(DIMENSION_COUNT):
            for name, sign in (("negative", -1), ("positive", 1)):
                weights = tuple(
                    sign if index == dimension else 0
                    for index in range(DIMENSION_COUNT)
                )
                fixed_scores[f"fixed-axis-{dimension}-{name}"].append(
                    score(regime["canary"], weighted_selections(weights, regime["canary"]))
                )
        for index, weights in enumerate(promoted_weight_family()):
            fixed_scores[f"promoted-weight-{index:03d}"].append(
                score(regime["canary"], weighted_selections(weights, regime["canary"]))
            )
        reference = learned
    assert first_learned is not None
    fixed_aggregates = {name: sum(values) for name, values in fixed_scores.items()}
    best_fixed_aggregate = min(fixed_aggregates.values())
    body = {
        "case_index": case_index,
        "task_sha256": task["task_sha256"],
        "reference_errors": reference_errors,
        "unchanged_errors": unchanged_errors,
        "frozen_first_errors": frozen_first_errors,
        "verbatim_raw_errors": fixed_scores["verbatim-raw-replay"],
        "best_fixed_aggregate_errors": best_fixed_aggregate,
        "fixed_score_receipt_sha256": sha256_bytes(canonical_json(fixed_scores)),
        "projection_bytes_max": max(projection_bytes),
        "structural_receipts": [item["receipt_sha256"] for item in structural],
        "checks": {
            "reference_solution": reference_errors == [0, 0, 0],
            "selector_change_ablation": unchanged_errors == [4, 8, 4],
            "harmful_later_regime": frozen_first_errors[1] == 8,
            "further_correction": frozen_first_errors[2] == 4
            and reference_errors[2] == 0,
            "current_class_impossible": all(item["pass"] for item in structural),
            "fixed_controls_fail": best_fixed_aggregate > 0
            and all(sum(values) > 0 for values in fixed_scores.values()),
            "verbatim_replay_fails": fixed_scores["verbatim-raw-replay"]
            == [4, 4, 4],
            "frozen_first_fails": sum(frozen_first_errors) > 0,
            "equal_active_budget": all(
                len(regime["contact"]["pairs"]) == len(CANONICAL_POINTS)
                and len(regime["canary"]["pairs"]) == len(CANONICAL_POINTS)
                for regime in task["regimes"]
            ),
            "outcome_credit_ablation": all(no_credit_identity),
            "bounded_projection": max(projection_bytes) <= 512,
            "fresh_restoration": all(restoration),
            "rollback_identity": all(parent_rollback),
        },
    }
    return {
        **body,
        "pass": all(body["checks"].values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0048.py"),
        "entrypoint_sha256": Path("experiments/ot_0048_harness.py"),
        "actor_orientation_sha256": ORIENTATION_PATH,
        "target_sha256": Path("TARGET.md"),
        "red_lines_sha256": Path("RED_LINES.md"),
        "program_sha256": Path("PROGRAM.md"),
        "evidence_contract_sha256": Path("docs/EVIDENCE.md"),
        "workflow_sha256": Path("docs/WORKFLOW.md"),
        "research_landscape_sha256": Path("docs/RESEARCH_LANDSCAPE.md"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "promoted_ot1_manifest_sha256": OT1_MANIFEST_PATH,
    }


def run_calibration(repo: Path, *, reverse: bool = False) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    family = task_family()
    indexed = list(enumerate(family))
    if reverse:
        indexed.reverse()
    results = [evaluate_case(index, case) for index, case in indexed]
    authority = actor_surface_authority(repo)
    ordered_receipts = [
        result["receipt_sha256"] for result in sorted(results, key=lambda item: item["case_index"])
    ]
    fixed_control_contract = [
        "fixed-canonical",
        "fixed-anticanonical",
        "fixed-zero",
        "all-eight-signed-unit-axes",
        "all-384-promoted-signed-permutation-weights",
        "verbatim-raw-replay",
        "frozen-first-reference",
    ]
    gates = {
        "scenario_count": len(results) == acceptance["scenario_count"],
        "all_scenarios": all(result["pass"] for result in results),
        "task_family_shape": len(RELATIONS) == acceptance["relation_count"]
        and all(len(build_task(case)["regimes"]) == acceptance["regime_count"] for case in family),
        "active_inheritance_budget": len(CANONICAL_POINTS)
        == acceptance["active_inheritance_budget"],
        "actor_surface_authority": authority["pass"],
        "candidate_actor_outputs": acceptance["candidate_actor_outputs"] is False,
        "hosted_model_calls": acceptance["hosted_model_calls"] == 0,
        "single_future_authorization": acceptance["authorized_candidate_count"] == 1,
        "fixed_control_contract": acceptance["fixed_selector_conditions"]
        == fixed_control_contract,
        "future_resource_contract": acceptance["future_candidate_experiment_id"]
        == "OT-0049"
        and acceptance["future_candidate_max_actor_turns"] == 6
        and acceptance["future_candidate_max_total_output_tokens"] == 48_000
        and acceptance["future_candidate_max_output_tokens_per_turn"] == 8_000
        and acceptance["future_candidate_tool_calls"] == 0
        and acceptance["future_candidate_independent_workers"] == 2
        and acceptance["future_candidate_context_resets_per_worker"] == 3,
    }
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "candidate_actor_outputs": False,
        "hosted_model_calls": 0,
        "scenario_count": len(results),
        "case_receipts_sha256": sha256_bytes(canonical_json(ordered_receipts)),
        "best_fixed_aggregate_errors_min": min(
            result["best_fixed_aggregate_errors"] for result in results
        ),
        "reference_errors": results[0]["reference_errors"],
        "unchanged_errors": results[0]["unchanged_errors"],
        "frozen_first_errors": results[0]["frozen_first_errors"],
        "verbatim_raw_errors": results[0]["verbatim_raw_errors"],
        "actor_surface_authority": authority,
        "gates": gates,
    }
    return {
        **body,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "authorized_candidate_count": acceptance["authorized_candidate_count"]
        if all(gates.values())
        else 0,
        "pilot_pass": all(gates.values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0048 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0048 implementation is not an execution ancestor")
    observed = {name: sha256_file(repo / path) for name, path in fixed_input_paths().items()}
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0048 fixed input identity differs")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0048 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    if output.exists():
        raise RuntimeError("OT-0048 output already exists")
    summary = run_calibration(repo)
    replay = run_calibration(repo)
    reverse = run_calibration(repo, reverse=True)
    summary["gates"].update(
        {
            "deterministic_replay": summary["receipt_sha256"] == replay["receipt_sha256"],
            "reverse_order_placebo": summary["receipt_sha256"] == reverse["receipt_sha256"],
        }
    )
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
    summary["gates"].update(
        {"tests": tests.returncode == 0, "audit": audit.returncode == 0}
    )
    summary["pilot_pass"] = all(summary["gates"].values())
    summary["disposition"] = "promoted" if summary["pilot_pass"] else "rejected"
    summary["authorized_candidate_count"] = (
        load_json(repo / ACCEPTANCE_PATH)["authorized_candidate_count"]
        if summary["pilot_pass"]
        else 0
    )
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "summary": summary,
    }
    write_sealed_json(output, raw)
    output.chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="representation-escape-evaluator-calibration",
            evidence_class="public-reconstructible",
            recipe=(
                "PYTHONPATH=src python3 experiments/ot_0048_harness.py "
                "--output $EVIDENCE/ot-0048-representation-escape-calibration-001.json"
            ),
            public_url=None,
            limitations=[
                "This is candidate-free evaluator calibration, not new OT-1 evidence.",
                "The controller-private reference is an existence proof, "
                "not a candidate mechanism.",
                "A pass authorizes at most one fresh future candidate and "
                "no hosted output was generated.",
                "This result does not widen OT-2 or establish OT-3.",
            ],
            input_manifests=[str(OT1_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0048-harness")
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
