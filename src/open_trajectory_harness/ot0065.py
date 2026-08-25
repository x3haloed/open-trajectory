from __future__ import annotations

import argparse
import copy
import itertools
import json
import re
import subprocess
import sys
from collections import deque
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


EXPERIMENT_ID = "OT-0065"
ACCEPTANCE_PATH = Path("spec/ot-0065-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0065-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0063/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0063/actor-output.schema.json")
OT63_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0063/ot-0063-temporal-state-topology-calibration-001.json"
)
OT62_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0062/ot-0062-categorical-predicate-representation-escape-candidate-001.json"
)
OT61_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0061/ot-0061-hosted-schema-preflight-repair-calibration-001.json"
)
OT59_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0059/ot-0059-categorical-predicate-carrier-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0065-temporal-state-topology-calibration-001"
SIDES = ("left", "right")
INHERITANCE_LIMIT = 1024
MAX_MACHINE_STATES = 6
MAX_IDENTIFIER_BYTES = 40


@dataclass(frozen=True)
class MachineSnapshot:
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
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0065.py"),
        "entrypoint_sha256": Path("experiments/ot_0065_harness.py"),
        "test_sha256": Path("tests/test_ot0065.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0062_manifest_sha256": OT62_MANIFEST_PATH,
        "ot0063_manifest_sha256": OT63_MANIFEST_PATH,
        "ot0061_manifest_sha256": OT61_MANIFEST_PATH,
        "ot0059_manifest_sha256": OT59_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def _rule(name: str, bits: tuple[int, ...]) -> str:
    count_a = bits.count(0)
    count_b = bits.count(1)
    conditions = {
        "odd-a": count_a % 2 == 1,
        "odd-b": count_b % 2 == 1,
        "even-a": count_a % 2 == 0,
        "even-b": count_b % 2 == 0,
        "suffix-aa": len(bits) >= 2 and bits[-2:] == (0, 0),
        "suffix-ab": len(bits) >= 2 and bits[-2:] == (0, 1),
        "suffix-ba": len(bits) >= 2 and bits[-2:] == (1, 0),
        "suffix-bb": len(bits) >= 2 and bits[-2:] == (1, 1),
        "last-a": bits[-1] == 0,
        "last-b": bits[-1] == 1,
        "mod3-a-1": count_a % 3 == 1,
        "mod3-b-1": count_b % 3 == 1,
        "length-odd": len(bits) % 2 == 1,
        "length-even": len(bits) % 2 == 0,
    }
    return "left" if conditions[name] else "right"


HYPOTHESES = (
    "odd-a",
    "odd-b",
    "even-a",
    "even-b",
    "suffix-aa",
    "suffix-ab",
    "suffix-ba",
    "suffix-bb",
    "last-a",
    "last-b",
    "mod3-a-1",
    "mod3-b-1",
    "length-odd",
    "length-even",
)
TARGET_RULES = ("odd-a", "suffix-ab", "mod3-b-1")


def _all_sequences(min_length: int, max_length: int) -> list[tuple[int, ...]]:
    return [
        sequence
        for length in range(min_length, max_length + 1)
        for sequence in itertools.product((0, 1), repeat=length)
    ]


def _balanced_pick(
    sequences: list[tuple[int, ...]], rule_name: str, count: int = 8
) -> list[tuple[int, ...]]:
    left = [item for item in sequences if _rule(rule_name, item) == "left"]
    right = [item for item in sequences if _rule(rule_name, item) == "right"]
    if len(left) < count // 2 or len(right) < count // 2:
        raise ValueError("OT-0065 heldout pool is not balanced")
    return left[: count // 2] + right[: count // 2]


def heldout_sequences(regime_index: int) -> list[tuple[int, ...]]:
    pool = _all_sequences(4, 8)
    if regime_index == 1:
        eligible = pool
    elif regime_index == 2:
        eligible = [
            item
            for item in pool
            if _rule(TARGET_RULES[1], item) != _rule(TARGET_RULES[0], item)
        ]
    else:
        eligible = [
            item
            for item in pool
            if _rule(TARGET_RULES[2], item) != _rule(TARGET_RULES[1], item)
        ]
    return _balanced_pick(eligible, TARGET_RULES[regime_index - 1])


def _consistent_hypotheses(
    target: str, observations: list[tuple[int, ...]]
) -> list[str]:
    return [
        name
        for name in HYPOTHESES
        if all(_rule(name, item) == _rule(target, item) for item in observations)
    ]


def diagnostic_sequences(
    target: str, heldout: list[tuple[int, ...]]
) -> list[tuple[int, ...]]:
    heldout_set = set(heldout)
    pool = [item for item in _all_sequences(1, 5) if item not in heldout_set]

    def row_allowed(item: tuple[int, ...]) -> bool:
        consistent = _consistent_hypotheses(target, [item])
        behaviors = {
            tuple(_rule(name, query) for query in heldout) for name in consistent
        }
        return len(consistent) >= 2 and len(behaviors) >= 2

    allowed = [item for item in pool if row_allowed(item)]
    selected: list[tuple[int, ...]] = []
    remaining = list(HYPOTHESES)
    while len(remaining) > 1:
        choices = []
        for item in allowed:
            if item in selected:
                continue
            narrowed = [
                name
                for name in remaining
                if _rule(name, item) == _rule(target, item)
            ]
            if 0 < len(narrowed) < len(remaining):
                choices.append((len(narrowed), len(item), item, narrowed))
        if not choices:
            raise ValueError("OT-0065 diagnostic family cannot identify target")
        _, _, chosen, remaining = min(choices, key=lambda value: value[:3])
        selected.append(chosen)
    for item in allowed:
        if item not in selected:
            selected.append(item)
        if len(selected) == 15:
            break
    if len(selected) != 15 or _consistent_hypotheses(target, selected) != [target]:
        raise ValueError("OT-0065 diagnostic set is incomplete")
    return selected


def cue_tokens(case_index: int) -> tuple[str, str]:
    values = [
        "cue-" + sha256_bytes(f"ot-0065:{case_index}:{index}".encode())[:12]
        for index in range(2)
    ]
    if case_index % 2:
        values.reverse()
    return values[0], values[1]


def _encode_sequence(bits: tuple[int, ...], cues: tuple[str, str]) -> list[str]:
    return [cues[value] for value in bits]


def _events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": side,
            "selector_features": [0, 0, 0, 0],
            "on_flags": [f"side-{side}"],
        }
        for side in SIDES
    ]


def _bundle(
    case_index: int,
    regime_index: int,
    bundle_index: int,
    bits: tuple[int, ...],
    cues: tuple[str, str],
    rule_name: str,
) -> dict[str, Any]:
    correct = _rule(rule_name, bits)
    return {
        "bundle_id": f"bundle-{regime_index}-{bundle_index:02d}",
        "cue_sequence": _encode_sequence(bits, cues),
        "presentations": [
            {
                "presentation_id": sha256_bytes(
                    f"ot-0065:{case_index}:{regime_index}:{bundle_index}:{trial}".encode()
                )[:20],
                "events": _events(),
                "correct_side": correct,
            }
            for trial in range(4)
        ],
    }


def public_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "cues": list(contact["cues"]),
        "bundles": [
            {
                "bundle_id": bundle["bundle_id"],
                "cue_sequence": bundle["cue_sequence"],
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


def complete_contact(
    contact: dict[str, Any], choices: list[str]
) -> dict[str, Any]:
    if len(choices) != len(contact["bundles"]) or any(
        choice not in SIDES for choice in choices
    ):
        raise ValueError("OT-0065 contact choices are malformed")
    outcomes = []
    for bundle, choice in zip(contact["bundles"], choices, strict=True):
        correct = bundle["presentations"][0]["correct_side"]
        outcomes.append(
            {
                "bundle_id": bundle["bundle_id"],
                "selected_side": choice,
                "success": choice == correct,
            }
        )
    body = {"kind": "ot-0065-completed-contact", "outcomes": outcomes}
    return {**body, "sha256": sha256_bytes(canonical_json(body))}


def build_regime(case_index: int, regime_index: int) -> dict[str, Any]:
    cues = cue_tokens(case_index)
    target = TARGET_RULES[regime_index - 1]
    heldout_bits = heldout_sequences(regime_index)
    diagnostics = diagnostic_sequences(target, heldout_bits)
    rotation = (case_index * 3 + regime_index) % len(diagnostics)
    diagnostics = diagnostics[rotation:] + diagnostics[:rotation]
    bundles = [
        _bundle(case_index, regime_index, index, bits, cues, target)
        for index, bits in enumerate(diagnostics)
    ]
    return {
        "index": regime_index,
        "target_rule": target,
        "cues": cues,
        "contact": {"cues": cues, "bundles": bundles},
        "diagnostic_bits": diagnostics,
        "heldout": [
            {"cue_sequence": _encode_sequence(bits, cues), "correct_side": _rule(target, bits)}
            for bits in heldout_bits
        ],
        "heldout_bits": heldout_bits,
    }


def build_case(case_index: int) -> dict[str, Any]:
    if not 0 <= case_index < 16:
        raise ValueError("OT-0065 case index is unavailable")
    return {
        "case_index": case_index,
        "regimes": [build_regime(case_index, index) for index in (1, 2, 3)],
    }


def reference_machine(rule_name: str, cues: tuple[str, str]) -> dict[str, Any]:
    a, b = cues
    if rule_name == "odd-a":
        return {
            "start": "even",
            "states": [
                {"id": "even", "output": "right", "edges": [{"cue": a, "next": "odd"}, {"cue": b, "next": "even"}]},
                {"id": "odd", "output": "left", "edges": [{"cue": a, "next": "even"}, {"cue": b, "next": "odd"}]},
            ],
        }
    if rule_name == "suffix-ab":
        return {
            "start": "none",
            "states": [
                {"id": "none", "output": "right", "edges": [{"cue": a, "next": "seen-a"}, {"cue": b, "next": "none"}]},
                {"id": "seen-a", "output": "right", "edges": [{"cue": a, "next": "seen-a"}, {"cue": b, "next": "accept"}]},
                {"id": "accept", "output": "left", "edges": [{"cue": a, "next": "seen-a"}, {"cue": b, "next": "none"}]},
            ],
        }
    if rule_name == "mod3-b-1":
        return {
            "start": "zero",
            "states": [
                {"id": "zero", "output": "right", "edges": [{"cue": a, "next": "zero"}, {"cue": b, "next": "one"}]},
                {"id": "one", "output": "left", "edges": [{"cue": a, "next": "one"}, {"cue": b, "next": "two"}]},
                {"id": "two", "output": "right", "edges": [{"cue": a, "next": "two"}, {"cue": b, "next": "zero"}]},
            ],
        }
    raise ValueError("OT-0065 reference rule is unavailable")


def validate_machine(machine: dict[str, Any], cues: tuple[str, str]) -> None:
    if not isinstance(machine, dict) or set(machine) != {"start", "states"}:
        raise ValueError("OT-0065 machine authority differs")
    states = machine["states"]
    if not isinstance(machine["start"], str) or not isinstance(states, list):
        raise ValueError("OT-0065 machine shape is malformed")
    if not 1 <= len(states) <= MAX_MACHINE_STATES:
        raise ValueError("OT-0065 machine state bound differs")
    if len(canonical_json(machine)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0065 machine exceeds its byte limit")
    ids = []
    transitions: dict[str, dict[str, str]] = {}
    for state in states:
        if not isinstance(state, dict) or set(state) != {"id", "output", "edges"}:
            raise ValueError("OT-0065 state authority differs")
        state_id = state["id"]
        if (
            not isinstance(state_id, str)
            or not state_id
            or len(state_id.encode()) > MAX_IDENTIFIER_BYTES
            or state["output"] not in SIDES
            or not isinstance(state["edges"], list)
        ):
            raise ValueError("OT-0065 state is malformed")
        ids.append(state_id)
        edges: dict[str, str] = {}
        for edge in state["edges"]:
            if not isinstance(edge, dict) or set(edge) != {"cue", "next"}:
                raise ValueError("OT-0065 edge authority differs")
            if edge["cue"] in edges:
                raise ValueError("OT-0065 machine is nondeterministic")
            edges[edge["cue"]] = edge["next"]
        if set(edges) != set(cues):
            raise ValueError("OT-0065 machine cue authority differs")
        transitions[state_id] = edges
    if len(ids) != len(set(ids)) or machine["start"] not in set(ids):
        raise ValueError("OT-0065 state identity differs")
    if any(target not in set(ids) for edges in transitions.values() for target in edges.values()):
        raise ValueError("OT-0065 transition target is unavailable")
    reachable = {machine["start"]}
    queue = deque([machine["start"]])
    while queue:
        for target in transitions[queue.popleft()].values():
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    if reachable != set(ids):
        raise ValueError("OT-0065 machine contains unreachable state")


def machine_output(
    machine: dict[str, Any], cue_sequence: list[str], cues: tuple[str, str]
) -> str:
    validate_machine(machine, cues)
    states = {state["id"]: state for state in machine["states"]}
    current = machine["start"]
    for cue in cue_sequence:
        if cue not in cues:
            raise ValueError("OT-0065 sequence cue is unavailable")
        edges = {item["cue"]: item["next"] for item in states[current]["edges"]}
        current = edges[cue]
    return states[current]["output"]


def machine_errors(machine: dict[str, Any], examples: list[dict[str, Any]], cues: tuple[str, str]) -> int:
    return sum(
        machine_output(machine, item["cue_sequence"], cues) != item["correct_side"]
        for item in examples
    )


def _contact_examples(contact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "cue_sequence": bundle["cue_sequence"],
            "correct_side": bundle["presentations"][0]["correct_side"],
        }
        for bundle in contact["bundles"]
    ]


def topology_fingerprint(machine: dict[str, Any], cues: tuple[str, str]) -> str:
    validate_machine(machine, cues)
    states = {state["id"]: state for state in machine["states"]}
    order = [machine["start"]]
    mapping = {machine["start"]: 0}
    for state_id in order:
        edges = {item["cue"]: item["next"] for item in states[state_id]["edges"]}
        for cue in cues:
            target = edges[cue]
            if target not in mapping:
                mapping[target] = len(order)
                order.append(target)
    body = {
        "state_count": len(order),
        "transitions": [
            [
                mapping[{item["cue"]: item["next"] for item in states[state_id]["edges"]}[cue]]
                for cue in cues
            ]
            for state_id in order
        ],
    }
    return sha256_bytes(canonical_json(body))


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    receipt_sha256: str,
    state: dict[str, Any],
) -> MachineSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": receipt_sha256,
        "state": state,
    }
    return MachineSnapshot(
        revision,
        parent_sha256,
        receipt_sha256,
        state,
        sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> MachineSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0065-seed"}))
    return _snapshot(0, None, receipt, {"weights": [0.0, 0.0, 0.0, 0.0]})


def project_snapshot(snapshot: MachineSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0065 snapshot exceeds inheritance budget")
    return value


def restore_snapshot(value: dict[str, Any]) -> MachineSnapshot:
    if set(value) != {"revision", "parent_sha256", "outcome_receipt_sha256", "state", "sha256"}:
        raise ValueError("OT-0065 snapshot projection authority differs")
    if (
        type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["parent_sha256"], (str, type(None)))
        or not isinstance(value["outcome_receipt_sha256"], str)
        or not isinstance(value["state"], dict)
        or not isinstance(value["sha256"], str)
    ):
        raise ValueError("OT-0065 snapshot projection is malformed")
    restored = _snapshot(
        value["revision"], value["parent_sha256"], value["outcome_receipt_sha256"], value["state"]
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0065 snapshot identity differs")
    return restored


def snapshot_errors(snapshot: MachineSnapshot, regime: dict[str, Any]) -> int:
    machine = snapshot.state.get("machine")
    if machine is None:
        return sum(item["correct_side"] != "left" for item in regime["heldout"])
    return machine_errors(machine, regime["heldout"], regime["cues"])


def attempt_update(
    current: MachineSnapshot,
    machine: dict[str, Any],
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[MachineSnapshot, str]:
    if receipt is None:
        return current, "no-credit"
    try:
        expected = complete_contact(contact, [item["selected_side"] for item in receipt["outcomes"]])
        if canonical_json(expected) != canonical_json(receipt):
            raise ValueError("receipt differs")
        validate_machine(machine, contact["cues"])
    except (KeyError, TypeError, ValueError):
        return current, "invalid"
    if machine_errors(machine, _contact_examples(contact), contact["cues"]):
        return current, "contact-imperfect"
    successor = _snapshot(
        current.revision + 1,
        current.sha256,
        receipt["sha256"],
        {"machine": copy.deepcopy(machine)},
    )
    project_snapshot(successor)
    return successor, "committed"


def stateless_certificate(regime: dict[str, Any]) -> dict[str, Any]:
    sides = [item["correct_side"] for item in regime["heldout"]]
    body = {
        "event_observation_invariant": all(_events() == _events() for _ in regime["heldout"]),
        "left_errors": sides.count("right"),
        "right_errors": sides.count("left"),
        "feature_deltas_zero": True,
    }
    return {**body, "pass": body["left_errors"] == body["right_errors"] == 4}


def compression_certificate(regime: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {"contact": public, "outcome": outcome}
        for public, outcome in zip(
            public_contact(regime["contact"])["bundles"], receipt["outcomes"], strict=True
        )
    ]
    row_bytes = [len(canonical_json(item)) for item in rows]
    allowed = [()] + [(index,) for index, size in enumerate(row_bytes) if size <= INHERITANCE_LIMIT]
    min_survivors = len(HYPOTHESES)
    divergent = True
    replay_errors = []
    for indices in allowed:
        observations = [regime["diagnostic_bits"][index] for index in indices]
        consistent = _consistent_hypotheses(regime["target_rule"], observations)
        behaviors = {
            tuple(_rule(name, bits) for bits in regime["heldout_bits"])
            for name in consistent
        }
        min_survivors = min(min_survivors, len(consistent))
        divergent = divergent and len(behaviors) >= 2
        retained = [rows[index] for index in indices]
        replay_errors.append(exact_replay_errors(retained, regime["heldout"]))
    full_consistent = _consistent_hypotheses(regime["target_rule"], regime["diagnostic_bits"])
    overlap = set(regime["diagnostic_bits"]) & set(regime["heldout_bits"])
    body = {
        "raw_bytes": len(canonical_json(rows)),
        "minimum_row_bytes": min(row_bytes),
        "maximum_row_bytes": max(row_bytes),
        "maximum_allowed_rows": max(map(len, allowed)),
        "allowed_projection_count": len(allowed),
        "minimum_surviving_hypotheses": min_survivors,
        "all_allowed_endpoint_divergent": divergent,
        "full_contact_unique": full_consistent == [regime["target_rule"]],
        "heldout_overlap_count": len(overlap),
        "allowed_replay_errors": replay_errors,
        "all_allowed_replay_errors_four": all(value == 4 for value in replay_errors),
    }
    return {
        **body,
        "pass": body["raw_bytes"] > INHERITANCE_LIMIT
        and body["minimum_row_bytes"] >= 513
        and body["maximum_allowed_rows"] == 1
        and body["minimum_surviving_hypotheses"] >= 2
        and body["all_allowed_endpoint_divergent"]
        and body["full_contact_unique"]
        and body["heldout_overlap_count"] == 0
        and body["all_allowed_replay_errors_four"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def exact_replay_errors(
    retained_rows: list[dict[str, Any]], heldout: list[dict[str, Any]]
) -> int:
    remembered: dict[tuple[str, ...], str] = {}
    for row in retained_rows:
        selected = row["outcome"]["selected_side"]
        correct = selected if row["outcome"]["success"] else (
            "right" if selected == "left" else "left"
        )
        remembered[tuple(row["contact"]["cue_sequence"])] = correct
    return sum(
        remembered.get(tuple(item["cue_sequence"]), "left") != item["correct_side"]
        for item in heldout
    )


def _reset_each_cue_errors(machine: dict[str, Any], regime: dict[str, Any]) -> int:
    validate_machine(machine, regime["cues"])
    states = {state["id"]: state for state in machine["states"]}
    start = states[machine["start"]]
    edges = {item["cue"]: item["next"] for item in start["edges"]}
    errors = 0
    for example in regime["heldout"]:
        final = machine["start"]
        for cue in example["cue_sequence"]:
            final = edges[cue]
        errors += states[final]["output"] != example["correct_side"]
    return errors


def _one_state_errors(machine: dict[str, Any], regime: dict[str, Any]) -> int:
    states = {state["id"]: state for state in machine["states"]}
    output = states[machine["start"]]["output"]
    return sum(item["correct_side"] != output for item in regime["heldout"])


def _output_only_certificate(prior: dict[str, Any], regime: dict[str, Any]) -> dict[str, Any]:
    states = prior["states"]
    minimum = len(regime["contact"]["bundles"])
    for outputs in itertools.product(SIDES, repeat=len(states)):
        candidate = copy.deepcopy(prior)
        for state, output in zip(candidate["states"], outputs, strict=True):
            state["output"] = output
        minimum = min(
            minimum,
            machine_errors(candidate, _contact_examples(regime["contact"]), regime["cues"]),
        )
    return {"minimum_contact_errors": minimum, "pass": minimum >= 1}


def _overbudget_machine(cues: tuple[str, str]) -> dict[str, Any]:
    identifiers = [f"state-{index}-" + chr(97 + index) * 32 for index in range(6)]
    return {
        "start": identifiers[0],
        "states": [
            {
                "id": state_id,
                "output": SIDES[index % 2],
                "edges": [
                    {"cue": cues[0], "next": identifiers[(index + 1) % 6]},
                    {"cue": cues[1], "next": identifiers[(index + 2) % 6]},
                ],
            }
            for index, state_id in enumerate(identifiers)
        ],
    }


def _fixed_control_vectors(
    task: dict[str, Any], references: list[dict[str, Any]]
) -> dict[str, Any]:
    left = [sum(item["correct_side"] != "left" for item in regime["heldout"]) for regime in task["regimes"]]
    right = [sum(item["correct_side"] != "right" for item in regime["heldout"]) for regime in task["regimes"]]
    alternating = [
        sum(
            item["correct_side"] != SIDES[index % 2]
            for index, item in enumerate(regime["heldout"])
        )
        for regime in task["regimes"]
    ]
    reference_vectors = [
        [
            machine_errors(reference, regime["heldout"], regime["cues"])
            for regime in task["regimes"]
        ]
        for reference in references
    ]
    vectors = {
        "empty": left,
        "digest": left,
        "verbatim": left,
        "no_persistence": left,
        "always_left": left,
        "always_right": right,
        "alternating": alternating,
        "stateless_left": left,
        "stateless_right": right,
        "fixed_references": reference_vectors,
    }
    complete_vectors = [left, right, alternating, *reference_vectors]
    return {
        **vectors,
        "pass": all(vector != [0, 0, 0] for vector in complete_vectors),
        "receipt_sha256": sha256_bytes(canonical_json(vectors)),
    }


def evaluate_case(case_index: int) -> dict[str, Any]:
    task = build_case(case_index)
    current = initial_snapshot()
    references: list[dict[str, Any]] = []
    results = []
    for regime in task["regimes"]:
        reference = reference_machine(regime["target_rule"], regime["cues"])
        choices = ["left"] * len(regime["contact"]["bundles"])
        receipt = complete_contact(regime["contact"], choices)
        before = current
        updated, reason = attempt_update(before, reference, receipt, regime["contact"])
        withheld, no_credit_reason = attempt_update(before, reference, None, regime["contact"])
        invalid = copy.deepcopy(reference)
        invalid["states"][0]["edges"] = invalid["states"][0]["edges"][:-1]
        invalid_result, invalid_reason = attempt_update(before, invalid, receipt, regime["contact"])
        cue_deleted = copy.deepcopy(reference)
        cue_deleted["states"][0]["edges"][0]["cue"] = ""
        cue_deleted_result, cue_deleted_reason = attempt_update(
            before, cue_deleted, receipt, regime["contact"]
        )
        unreachable = copy.deepcopy(reference)
        unreachable["states"].append(
            {
                "id": "unreachable",
                "output": "left",
                "edges": [
                    {"cue": cue, "next": "unreachable"} for cue in regime["cues"]
                ],
            }
        )
        unreachable_result, unreachable_reason = attempt_update(
            before, unreachable, receipt, regime["contact"]
        )
        overbudget_result, overbudget_reason = attempt_update(
            before, _overbudget_machine(regime["cues"]), receipt, regime["contact"]
        )
        imperfect = {
            "start": "only",
            "states": [
                {
                    "id": "only",
                    "output": "left",
                    "edges": [
                        {"cue": cue, "next": "only"} for cue in regime["cues"]
                    ],
                }
            ],
        }
        imperfect_result, imperfect_reason = attempt_update(
            before, imperfect, receipt, regime["contact"]
        )
        topology = topology_fingerprint(reference, regime["cues"])
        result = {
            "index": regime["index"],
            "pre_update_errors": snapshot_errors(before, regime),
            "reference_errors": snapshot_errors(updated, regime),
            "update_reason": reason,
            "parent_exact": updated.parent_sha256 == before.sha256,
            "successor_exact": updated.sha256 != before.sha256,
            "restore_exact": restore_snapshot(project_snapshot(updated)).sha256 == updated.sha256,
            "rollback_errors": snapshot_errors(before, regime),
            "no_credit_preserved": withheld.sha256 == before.sha256 and no_credit_reason == "no-credit",
            "invalid_preserved": invalid_result.sha256 == before.sha256 and invalid_reason == "invalid",
            "unreachable_preserved": unreachable_result.sha256 == before.sha256
            and unreachable_reason == "invalid",
            "overbudget_preserved": overbudget_result.sha256 == before.sha256
            and overbudget_reason == "invalid",
            "imperfect_preserved": imperfect_result.sha256 == before.sha256 and imperfect_reason == "contact-imperfect",
            "topology_sha256": topology,
            "topology_changed": not references
            or topology != topology_fingerprint(references[-1], regime["cues"]),
            "output_only_correction": (
                {"minimum_contact_errors": None, "pass": True}
                if not references
                else _output_only_certificate(references[-1], regime)
            ),
            "one_state_ablation_errors": _one_state_errors(reference, regime),
            "reset_each_cue_ablation_errors": _reset_each_cue_errors(reference, regime),
            "transition_deletion_ablation_errors": snapshot_errors(invalid_result, regime),
            "transition_deletion_preserved_parent": invalid_result.sha256 == before.sha256,
            "cue_edge_deletion_ablation_errors": snapshot_errors(cue_deleted_result, regime),
            "cue_edge_deletion_preserved_parent": cue_deleted_result.sha256 == before.sha256
            and cue_deleted_reason == "invalid",
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
            and result["invalid_preserved"]
            and result["unreachable_preserved"]
            and result["overbudget_preserved"]
            and result["imperfect_preserved"]
            and result["topology_changed"]
            and result["output_only_correction"]["pass"]
            and result["one_state_ablation_errors"] > 0
            and result["reset_each_cue_ablation_errors"] > 0
            and result["transition_deletion_ablation_errors"] > 0
            and result["transition_deletion_preserved_parent"]
            and result["cue_edge_deletion_ablation_errors"] > 0
            and result["cue_edge_deletion_preserved_parent"]
            and result["stateless_certificate"]["pass"]
            and result["compression_certificate"]["pass"]
            and result["snapshot_bytes"] <= INHERITANCE_LIMIT
        )
        results.append(result)
        references.append(reference)
        current = updated
    frozen_first = [
        machine_errors(references[0], regime["heldout"], regime["cues"])
        for regime in task["regimes"]
    ]
    frozen_second = [
        machine_errors(references[1], regime["heldout"], regime["cues"])
        for regime in task["regimes"]
    ]
    fixed_controls = _fixed_control_vectors(task, references)
    body = {
        "case_index": case_index,
        "pre_update_errors": [item["pre_update_errors"] for item in results],
        "reference_errors": [item["reference_errors"] for item in results],
        "frozen_first_errors": frozen_first,
        "frozen_second_errors": frozen_second,
        "fixed_controls": fixed_controls,
        "regimes": results,
    }
    body["pass"] = (
        all(item["pass"] for item in results)
        and body["reference_errors"] == [0, 0, 0]
        and frozen_first[1] == 8
        and frozen_second[2] >= 4
        and fixed_controls["pass"]
    )
    body["receipt_sha256"] = sha256_bytes(canonical_json(body))
    return body


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    surface = orientation + canonical_json(schema).decode()
    forbidden = [term for term in ("parity", "suffix", "modulo", "mod3") if term in surface.lower()]
    body = {
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "forbidden_terms": forbidden,
        "concrete_cue_hits": re.findall(r"cue-[0-9a-f]{8,}", surface),
        "schema_unsupported_keywords": sorted(unsupported_keywords(schema)),
    }
    return {
        **body,
        "pass": not forbidden
        and not body["concrete_cue_hits"]
        and not body["schema_unsupported_keywords"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    cases = [evaluate_case(index) for index in range(acceptance["scenario_count"])]
    reverse = [evaluate_case(index) for index in reversed(range(acceptance["scenario_count"]))]
    surface = actor_surface_authority(repo)
    body = {
        "case_count": len(cases),
        "passing_case_count": sum(item["pass"] for item in cases),
        "reference_error_vectors": sorted({tuple(item["reference_errors"]) for item in cases}),
        "pre_update_error_vectors": sorted({tuple(item["pre_update_errors"]) for item in cases}),
        "frozen_first_error_vectors": sorted({tuple(item["frozen_first_errors"]) for item in cases}),
        "frozen_second_error_vectors": sorted({tuple(item["frozen_second_errors"]) for item in cases}),
        "minimum_row_bytes": min(item["compression_certificate"]["minimum_row_bytes"] for case in cases for item in case["regimes"]),
        "minimum_surviving_hypotheses": min(item["compression_certificate"]["minimum_surviving_hypotheses"] for case in cases for item in case["regimes"]),
        "maximum_allowed_rows": max(item["compression_certificate"]["maximum_allowed_rows"] for case in cases for item in case["regimes"]),
        "maximum_heldout_overlap": max(item["compression_certificate"]["heldout_overlap_count"] for case in cases for item in case["regimes"]),
        "exact_replay_error_vectors": sorted({tuple(item["compression_certificate"]["allowed_replay_errors"]) for case in cases for item in case["regimes"]}),
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
        "hidden_opportunity": body["reference_error_vectors"] == [(0, 0, 0)],
        "contradiction": all(vector[1] == 8 for vector in body["frozen_first_error_vectors"]),
        "distinct_correction": all(vector[2] >= 4 for vector in body["frozen_second_error_vectors"]),
        "compression": body["minimum_row_bytes"] >= acceptance["minimum_complete_row_bytes"]
        and body["minimum_surviving_hypotheses"] >= 2
        and body["maximum_allowed_rows"] == acceptance["maximum_allowed_rows"],
        "heldout_disjoint": body["maximum_heldout_overlap"] == 0,
        "exact_replay": all(
            all(value == 4 for value in vector)
            for vector in body["exact_replay_error_vectors"]
        ),
        "actor_surface": surface["pass"],
        "reverse_order_placebo": body["reverse_order_placebo"],
        "candidate_free": not body["candidate_outputs"] and body["hosted_model_calls"] == 0,
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
        raise RuntimeError("OT-0065 run lock omits implementation identity")
    if subprocess.run(["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo).returncode:
        raise RuntimeError("OT-0065 implementation is not an execution ancestor")
    observed = {name: sha256_file(repo / path) for name, path in fixed_input_paths().items()}
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0065 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(repo, "diff", "--name-only", f"{implementation}..{execution}", "--", *protected)
    if changed:
        raise RuntimeError(f"OT-0065 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0065 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution)
    if output.exists():
        raise RuntimeError("OT-0065 raw output already exists")
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
        "cases": [evaluate_case(index) for index in range(load_json(repo / ACCEPTANCE_PATH)["scenario_count"])],
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
            kind="temporal-state-topology-candidate-free-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0065_harness.py --output $EVIDENCE/runs/OT-0065/ot-0065-temporal-state-topology-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate output and hosted model calls are forbidden.",
                "Controller-private reference machines prove opportunity only and are not endogenous evidence.",
                "A pass authorizes at most one fresh OT-0066 learner and is not representation-escape evidence.",
            ],
            input_manifests=[
                str(OT63_MANIFEST_PATH),
                str(OT62_MANIFEST_PATH),
                str(OT61_MANIFEST_PATH),
                str(OT59_MANIFEST_PATH),
                str(OT48_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0065-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, summary = run(args.repo.resolve(), args.run_id, args.output.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(args.repo.resolve())), "summary": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
