"""OT-0071 receipted projection-practice opportunity calibration.

This module implements a candidate-free vertical slice above the frozen
OT-0070 trajectory store.  Synthetic actor-channel fixture payloads are
authored in fresh processes, independently appended under channel capability,
and accepted only through exact ancestry and compare-and-swap validation.
"""

from __future__ import annotations

import argparse
import functools
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from open_trajectory_evidence.evidence import default_store, record_artifact

from .ot0002 import (
    canonical_json,
    child_environment,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
)
from .ot0003 import read_sealed_json, write_sealed_json
from .trajectory import (
    ACTOR_SOURCE,
    CONTROLLER_SOURCE,
    WORLD_SOURCE,
    TrajectoryStore,
    bootstrap_trajectory_store,
)


EXPERIMENT_ID = "OT-0071"
PROTOCOL_ORIGIN_COMMIT = "91e468f2b2b2783256ab718cad1833f8529e40ab"
ACCEPTANCE_PATH = Path("spec/ot-0071-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0071-run-lock.json")
EXPERIMENT_PATH = Path(
    "experiments/OT-0071-receipted-projection-practice-opportunity-calibration.md"
)
DEFAULT_RUN_ID = "ot-0071-receipted-projection-practice-opportunity-calibration-001"
DERIVATION_ID = "ot-0071-derivation-001"
TASK_RELATIVE_PATH = Path("tasks/OT-0071/ot-0071-derivation-001.json")
DERIVATION_RELATIVE_PATH = Path(
    "derivations/OT-0071/ot-0071-derivation-001.json"
)
CASE_INDICES = tuple(range(16))
REGIME_INDICES = tuple(range(3))
PROJECTION_BYTES = 2048
MAX_RECORD_BYTES = 4096
RESET_SECONDS = 5
WALL_SECONDS = 240
MAX_RAW_BYTES = 4_194_304
FULL_TRAJECTORY_MINIMUM = 32_769
ACCEPTANCE_SHA256 = "d88ee1e120d406e9e23fbfaae6785e617e21cfd0dcfd03b2bac00caef9b922c0"
RECONSTRUCTION_RECIPE = (
    "At environment.git.commit with a fresh $EVIDENCE, run "
    "OT_EVIDENCE_ROOT=$EVIDENCE PYTHONPATH=src python3 -m "
    "open_trajectory_harness.ot0071 --reconstruct-only"
)

PROTOCOL_FROZEN_PATHS = (
    Path("TARGET.md"),
    Path("RED_LINES.md"),
    Path("PROGRAM.md"),
    Path("docs/EVIDENCE.md"),
    Path("docs/TRAJECTORY_PROJECTION_EPOCH.md"),
    Path("docs/WORKFLOW.md"),
    Path(
        "evidence/manifests/OT-0070/"
        "ot-0070-trajectory-authority-calibration-001.json"
    ),
    EXPERIMENT_PATH,
    Path("spec/ot-0070-acceptance.json"),
    Path("spec/ot-0070-run-lock.json"),
    ACCEPTANCE_PATH,
    Path("src/open_trajectory_harness/ot0002.py"),
    Path("src/open_trajectory_harness/ot0070.py"),
    Path("src/open_trajectory_harness/trajectory.py"),
)

_RECORD_ID = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[0-9a-f]{32}")


class ProtocolError(ValueError):
    """Raised when OT-0071 schema, ancestry, or authority fails closed."""


@dataclass(frozen=True)
class PointerState:
    sequence: int
    pointer_event_id: str
    active_id: str
    decision_id: str | None


@dataclass(frozen=True)
class PointerReplay:
    states: tuple[PointerState, ...]
    decision_ids: tuple[str, ...]

    @property
    def current(self) -> PointerState:
        return self.states[-1]


@dataclass
class CaseRuntime:
    store: TrajectoryStore
    actor_capability: object
    world_capability: object
    controller_capability: object
    controller: "PointerController"
    implementation_commit: str
    acceptance: dict[str, Any]
    case_index: int
    case: dict[str, Any]
    genesis_id: str
    directory_id: str
    sources: tuple[dict[str, str], ...]
    schedule: tuple[int, int, int]


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ProtocolError(f"{label} keys differ from the frozen schema")
    return value


def _rid(value: object, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a lowercase record identity")
    return value


def _token(value: object, label: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a bounded opaque token")
    return value


def _commit(value: object, label: str = "implementation commit") -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ProtocolError(f"{label} is not a full Git commit identity")
    return value


def expansion(
    implementation_commit: str,
    domain: str,
    indices: list[int | str],
    length: int,
) -> str:
    """Expand exact domain/index material under the frozen canonical rule."""

    _commit(implementation_commit)
    if type(domain) is not str or not domain or type(indices) is not list:
        raise ValueError("opaque expansion domain or indices are invalid")
    if type(length) is not int or length < 1:
        raise ValueError("opaque expansion length is invalid")
    output = ""
    counter = 0
    while len(output) < length:
        output += sha256_bytes(
            canonical_json(
                {
                    "counter": counter,
                    "domain": domain,
                    "implementation_commit": implementation_commit,
                    "indices": indices,
                }
            )
        )
        counter += 1
    return output[:length]


def opaque_token(
    implementation_commit: str, domain: str, indices: list[int | str]
) -> str:
    return expansion(implementation_commit, domain, indices, 32)


def build_task(implementation_commit: str) -> dict[str, Any]:
    """Mechanically derive the public-reconstructible private task from I."""

    implementation_commit = _commit(implementation_commit)
    cases = []
    for case_index in CASE_INDICES:
        cases.append(
            {
                "address_handles_by_semantic_branch": [
                    opaque_token(
                        implementation_commit,
                        "address-handle",
                        [case_index, branch],
                    )
                    for branch in range(3)
                ],
                "branch_keys_by_semantic_branch": [
                    opaque_token(
                        implementation_commit, "branch-key", [case_index, branch]
                    )
                    for branch in range(3)
                ],
                "case_index": case_index,
                "case_token": opaque_token(
                    implementation_commit, "case", [case_index]
                ),
                "contact_tokens": [
                    opaque_token(
                        implementation_commit, "contact", [case_index, regime]
                    )
                    for regime in REGIME_INDICES
                ],
                "query_keys_by_semantic_query": [
                    opaque_token(
                        implementation_commit, "query", [case_index, query]
                    )
                    for query in range(3)
                ],
            }
        )
    task = {
        "acceptance_sha256": ACCEPTANCE_SHA256,
        "cases": cases,
        "experiment_id": EXPERIMENT_ID,
        "implementation_commit": implementation_commit,
        "schema_version": 1,
    }
    validate_task(task)
    return task


def validate_task(task: dict[str, Any]) -> None:
    task = _exact(
        task,
        {
            "acceptance_sha256",
            "cases",
            "experiment_id",
            "implementation_commit",
            "schema_version",
        },
        "task",
    )
    if (
        task["schema_version"] != 1
        or task["experiment_id"] != EXPERIMENT_ID
        or task["acceptance_sha256"] != ACCEPTANCE_SHA256
    ):
        raise ProtocolError("task identity differs from the frozen derivation")
    implementation = _commit(task["implementation_commit"])
    cases = task["cases"]
    if type(cases) is not list or len(cases) != len(CASE_INDICES):
        raise ProtocolError("task case count differs")
    all_tokens: list[str] = []
    for expected_index, raw in enumerate(cases):
        case = _exact(
            raw,
            {
                "address_handles_by_semantic_branch",
                "branch_keys_by_semantic_branch",
                "case_index",
                "case_token",
                "contact_tokens",
                "query_keys_by_semantic_query",
            },
            "task case",
        )
        if case["case_index"] != expected_index:
            raise ProtocolError("task case ordering differs")
        expected_groups = {
            "address_handles_by_semantic_branch": [
                opaque_token(implementation, "address-handle", [expected_index, i])
                for i in range(3)
            ],
            "branch_keys_by_semantic_branch": [
                opaque_token(implementation, "branch-key", [expected_index, i])
                for i in range(3)
            ],
            "contact_tokens": [
                opaque_token(implementation, "contact", [expected_index, i])
                for i in range(3)
            ],
            "query_keys_by_semantic_query": [
                opaque_token(implementation, "query", [expected_index, i])
                for i in range(3)
            ],
        }
        if case["case_token"] != opaque_token(
            implementation, "case", [expected_index]
        ):
            raise ProtocolError("task case token differs")
        for key, expected_values in expected_groups.items():
            if case[key] != expected_values:
                raise ProtocolError(f"task {key} differs")
            all_tokens.extend(expected_values)
        all_tokens.append(case["case_token"])
    if len(all_tokens) != len(set(all_tokens)):
        raise ProtocolError("task opaque token domains collided")


@functools.lru_cache(maxsize=None)
def _record(store: TrajectoryStore, record_id: str) -> dict[str, Any]:
    checked = _rid(record_id, "record identity")
    assert checked is not None
    try:
        record = store.get(checked)
    except (KeyError, ValueError) as error:
        raise ProtocolError("named trajectory record is unavailable") from error
    if sha256_bytes(canonical_json(record)) != checked:
        raise ProtocolError("stored record identity is not canonical")
    return _exact(record, {"parents", "payload", "source"}, "record")


def _coefficient_vector(value: object, label: str) -> list[int]:
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(item) is not int or item not in {0, 1} for item in value)
    ):
        raise ProtocolError(f"{label} is not a two-bit coefficient vector")
    return list(value)


def mechanism_output(coefficients: list[int], feature: list[int]) -> int:
    coefficients = _coefficient_vector(coefficients, "mechanism coefficients")
    feature = _coefficient_vector(feature, "mechanism feature")
    return sum(left * right for left, right in zip(coefficients, feature, strict=True)) % 2


@functools.lru_cache(maxsize=None)
def validate_source_context(store: TrajectoryStore, context_id: str) -> dict[str, Any]:
    record = _record(store, context_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("source context lacks world-channel provenance")
    payload = _exact(
        record["payload"],
        {"branch_key", "case_token", "record", "schema_version"},
        "source-context payload",
    )
    if payload["record"] != "source_context" or payload["schema_version"] != 1:
        raise ProtocolError("source-context marker is invalid")
    _token(payload["branch_key"], "source-context branch key")
    _token(payload["case_token"], "source-context case token")
    if len(record["parents"]) != 1:
        raise ProtocolError("source context does not descend exactly from genesis")
    return record


@functools.lru_cache(maxsize=None)
def validate_proposal(store: TrajectoryStore, proposal_id: str) -> dict[str, Any]:
    record = _record(store, proposal_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("proposal lacks actor-channel provenance")
    payload = _exact(
        record["payload"],
        {
            "case_token",
            "coefficients",
            "note",
            "occurrence",
            "record",
            "schema_version",
            "source_context_id",
        },
        "mechanism-proposal payload",
    )
    if payload["record"] != "proposal" or payload["schema_version"] != 2:
        raise ProtocolError("mechanism-proposal marker is invalid")
    _token(payload["case_token"], "proposal case token")
    _coefficient_vector(payload["coefficients"], "proposal coefficients")
    if type(payload["note"]) is not str or len(payload["note"].encode()) > 128:
        raise ProtocolError("proposal note exceeds its bound")
    occurrence = payload["occurrence"]
    if occurrence not in {"genesis", "source", "successor"}:
        raise ProtocolError("proposal occurrence is unavailable")
    context_id = _rid(
        payload["source_context_id"], "proposal source context", nullable=True
    )
    if occurrence == "genesis":
        if record["parents"] or context_id is not None or payload["coefficients"] != [0, 0]:
            raise ProtocolError("genesis proposal differs from the neutral fixture")
    elif occurrence == "source":
        if context_id is None or len(record["parents"]) != 2 or context_id not in record["parents"]:
            raise ProtocolError("source proposal ancestry is invalid")
        context = validate_source_context(store, context_id)
        other = next(parent for parent in record["parents"] if parent != context_id)
        genesis = validate_proposal(store, other)
        if genesis["payload"]["occurrence"] != "genesis":
            raise ProtocolError("source proposal does not descend from genesis")
        if context["payload"]["case_token"] != payload["case_token"] or genesis["payload"]["case_token"] != payload["case_token"]:
            raise ProtocolError("source proposal case binding differs")
    else:
        if context_id is not None or len(record["parents"]) != 2:
            raise ProtocolError("successor proposal ancestry is invalid")
        markers = [
            _record(store, parent)["payload"].get("record")
            for parent in record["parents"]
        ]
        if sorted(markers) != ["projection_request", "proposal"]:
            raise ProtocolError("successor parents are not active plus request")
    return record


@functools.lru_cache(maxsize=None)
def validate_trial(
    store: TrajectoryStore,
    trial_id: str,
    *,
    expected_proposal_id: str | None = None,
) -> dict[str, Any]:
    record = _record(store, trial_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("trial lacks world-channel provenance")
    payload = _exact(
        record["payload"],
        {
            "case_token",
            "executor_receipt",
            "proposal_id",
            "record",
            "schema_version",
            "scope",
            "trace",
        },
        "mechanism-trial payload",
    )
    if payload["record"] != "trial" or payload["schema_version"] != 2:
        raise ProtocolError("mechanism-trial marker is invalid")
    _token(payload["case_token"], "trial case token")
    _token(payload["executor_receipt"], "trial executor receipt")
    proposal_id = _rid(payload["proposal_id"], "trial proposal")
    assert proposal_id is not None
    if record["parents"] != [proposal_id] or (
        expected_proposal_id is not None and proposal_id != expected_proposal_id
    ):
        raise ProtocolError("trial binding differs from its proposal")
    proposal = validate_proposal(store, proposal_id)
    expected_scope = "source" if proposal["payload"]["occurrence"] == "source" else "successor"
    if payload["scope"] != expected_scope:
        raise ProtocolError("trial scope differs from proposal occurrence")
    if proposal["payload"]["case_token"] != payload["case_token"]:
        raise ProtocolError("trial and proposal case tokens differ")
    expected_length = 2 if expected_scope == "source" else 3
    trace = payload["trace"]
    if type(trace) is not list or len(trace) != expected_length:
        raise ProtocolError("trial trace length differs")
    for index, raw in enumerate(trace):
        row = _exact(
            raw,
            {"feature", "input", "proposal_output", "resolved_output", "trial_id"},
            f"trial row {index}",
        )
        _coefficient_vector(row["feature"], f"trial row {index} feature")
        _token(row["input"], f"trial row {index} input")
        _token(row["trial_id"], f"trial row {index} identity")
        if type(row["proposal_output"]) is not int or row["proposal_output"] not in {0, 1}:
            raise ProtocolError("trial proposal output is not binary")
        if type(row["resolved_output"]) is not int or row["resolved_output"] not in {0, 1}:
            raise ProtocolError("trial resolved output is not binary")
    return record


@functools.lru_cache(maxsize=None)
def validate_decision(store: TrajectoryStore, decision_id: str) -> dict[str, Any]:
    record = _record(store, decision_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("decision lacks actor-channel provenance")
    payload = _exact(
        record["payload"],
        {
            "action",
            "case_token",
            "decision_token",
            "expected_active_id",
            "expected_pointer_event_id",
            "record",
            "rollback_target_id",
            "schema_version",
            "selected_proposal_id",
            "trial_id",
        },
        "decision payload",
    )
    if payload["record"] != "decision" or payload["schema_version"] != 1:
        raise ProtocolError("decision marker is invalid")
    if payload["action"] not in {"adopt", "rollback", "set_down"}:
        raise ProtocolError("decision action is unavailable")
    _token(payload["case_token"], "decision case token")
    _token(payload["decision_token"], "decision token")
    active = _rid(payload["expected_active_id"], "decision expected active")
    pointer = _rid(payload["expected_pointer_event_id"], "decision expected pointer")
    assert active is not None and pointer is not None
    if payload["action"] in {"adopt", "set_down"}:
        selected = _rid(payload["selected_proposal_id"], "decision selected proposal")
        trial = _rid(payload["trial_id"], "decision trial")
        if payload["rollback_target_id"] is not None:
            raise ProtocolError("adopt/set-down carries rollback target")
        expected_parents = sorted({selected, trial, pointer})
    else:
        if payload["selected_proposal_id"] is not None or payload["trial_id"] is not None:
            raise ProtocolError("rollback carries selected branch")
        target = _rid(payload["rollback_target_id"], "decision rollback target")
        expected_parents = sorted({active, target, pointer})
    if record["parents"] != expected_parents:
        raise ProtocolError("decision ancestry differs from payload binding")
    return record


def _pointer_records(store: TrajectoryStore) -> dict[str, dict[str, Any]]:
    return {
        record_id: record
        for record_id in store.record_ids
        if (record := _record(store, record_id))["source"] == CONTROLLER_SOURCE
        and record["payload"].get("record") == "pointer"
    }


def _pointer_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = _exact(
        record["payload"],
        {
            "action",
            "decision_id",
            "previous_pointer_event_id",
            "prior_active_id",
            "record",
            "resulting_active_id",
            "schema_version",
            "sequence",
        },
        "pointer payload",
    )
    if payload["record"] != "pointer" or payload["schema_version"] != 1:
        raise ProtocolError("pointer marker is invalid")
    if payload["action"] not in {"adopt", "initialize", "rollback", "set_down"}:
        raise ProtocolError("pointer action is unavailable")
    if type(payload["sequence"]) is not int or payload["sequence"] < 0:
        raise ProtocolError("pointer sequence is invalid")
    for key in ("decision_id", "previous_pointer_event_id", "prior_active_id"):
        _rid(payload[key], f"pointer {key}", nullable=True)
    _rid(payload["resulting_active_id"], "pointer resulting active")
    return payload


def _prior_active_parent(store: TrajectoryStore, proposal_id: str) -> str:
    proposal = validate_proposal(store, proposal_id)
    if proposal["payload"]["occurrence"] != "successor":
        raise ProtocolError("active predecessor exists only for successor proposals")
    matches = [
        parent
        for parent in proposal["parents"]
        if _record(store, parent)["payload"].get("record") == "proposal"
    ]
    if len(matches) != 1:
        raise ProtocolError("successor does not have one prior-active parent")
    return matches[0]


def _rollback_chain_contains(
    store: TrajectoryStore, current_id: str, target_id: str
) -> bool:
    current = current_id
    while current != target_id:
        proposal = validate_proposal(store, current)
        if proposal["payload"]["occurrence"] != "successor":
            return False
        current = _prior_active_parent(store, current)
    target = validate_proposal(store, target_id)
    return target["payload"]["occurrence"] in {"genesis", "successor"}


def _decision_result(
    store: TrajectoryStore,
    decision_id: str,
    state: PointerState,
    used: set[str],
) -> tuple[str, str]:
    decision = validate_decision(store, decision_id)
    payload = decision["payload"]
    if decision_id in used:
        raise ProtocolError("pointer decision was replayed")
    if payload["expected_active_id"] != state.active_id or payload["expected_pointer_event_id"] != state.pointer_event_id:
        raise ProtocolError("decision compare-and-swap state is stale")
    action = payload["action"]
    if action in {"adopt", "set_down"}:
        selected = payload["selected_proposal_id"]
        trial = payload["trial_id"]
        proposal = validate_proposal(store, selected)
        validate_trial(store, trial, expected_proposal_id=selected)
        if proposal["payload"]["occurrence"] != "successor" or _prior_active_parent(store, selected) != state.active_id:
            raise ProtocolError("selected successor does not descend from active state")
        if proposal["payload"]["case_token"] != payload["case_token"]:
            raise ProtocolError("decision and selected proposal cases differ")
        return action, selected if action == "adopt" else state.active_id
    target = payload["rollback_target_id"]
    current = validate_proposal(store, state.active_id)
    target_record = validate_proposal(store, target)
    if current["payload"]["case_token"] != payload["case_token"] or target_record["payload"]["case_token"] != payload["case_token"]:
        raise ProtocolError("rollback case binding differs")
    if target == state.active_id or not _rollback_chain_contains(store, state.active_id, target):
        raise ProtocolError("rollback target is not on the active-predecessor chain")
    return action, target


def replay_pointer(store: TrajectoryStore) -> PointerReplay:
    records = _pointer_records(store)
    if not records:
        raise ProtocolError("pointer trajectory has no genesis")
    payloads = {record_id: _pointer_payload(record) for record_id, record in records.items()}
    genesis_ids = [
        record_id
        for record_id, payload in payloads.items()
        if payload["previous_pointer_event_id"] is None
    ]
    if len(genesis_ids) != 1:
        raise ProtocolError("pointer trajectory lacks unique genesis")
    genesis_id = genesis_ids[0]
    genesis = payloads[genesis_id]
    if (
        genesis["action"] != "initialize"
        or genesis["sequence"] != 0
        or genesis["prior_active_id"] is not None
        or genesis["decision_id"] is not None
        or records[genesis_id]["parents"] != [genesis["resulting_active_id"]]
    ):
        raise ProtocolError("pointer genesis differs")
    genesis_proposal = validate_proposal(store, genesis["resulting_active_id"])
    if genesis_proposal["payload"]["occurrence"] != "genesis":
        raise ProtocolError("pointer initializes a non-genesis proposal")
    states = [PointerState(0, genesis_id, genesis["resulting_active_id"], None)]
    used: set[str] = set()
    consumed = {genesis_id}
    while True:
        current = states[-1]
        children = [
            record_id
            for record_id, payload in payloads.items()
            if payload["previous_pointer_event_id"] == current.pointer_event_id
        ]
        if not children:
            break
        if len(children) != 1:
            raise ProtocolError("pointer trajectory forks")
        pointer_id = children[0]
        if pointer_id in consumed:
            raise ProtocolError("pointer trajectory cycles")
        payload = payloads[pointer_id]
        if payload["sequence"] != current.sequence + 1 or payload["prior_active_id"] != current.active_id:
            raise ProtocolError("pointer sequence or prior active differs")
        decision_id = payload["decision_id"]
        if decision_id is None:
            raise ProtocolError("pointer transition omits decision")
        action, result = _decision_result(store, decision_id, current, used)
        if payload["action"] != action or payload["resulting_active_id"] != result:
            raise ProtocolError("pointer transition differs from decision")
        if records[pointer_id]["parents"] != sorted(
            {decision_id, current.pointer_event_id, result}
        ):
            raise ProtocolError("pointer transition parents differ")
        used.add(decision_id)
        consumed.add(pointer_id)
        states.append(PointerState(payload["sequence"], pointer_id, result, decision_id))
    if consumed != set(records):
        raise ProtocolError("pointer trajectory contains disconnected events")
    return PointerReplay(tuple(states), tuple(sorted(used)))


class PointerController:
    """Controller-only pointer append facade using OT-0071 replay semantics."""

    __slots__ = ("_capability", "_store")

    def __init__(self, store: TrajectoryStore, capability: object) -> None:
        self._store = store
        self._capability = capability

    def initialize(self, proposal_id: str) -> str:
        if _pointer_records(self._store):
            raise ProtocolError("pointer is already initialized")
        proposal = validate_proposal(self._store, proposal_id)
        if proposal["payload"]["occurrence"] != "genesis":
            raise ProtocolError("pointer initialization requires genesis")
        payload = {
            "action": "initialize",
            "decision_id": None,
            "previous_pointer_event_id": None,
            "prior_active_id": None,
            "record": "pointer",
            "resulting_active_id": proposal_id,
            "schema_version": 1,
            "sequence": 0,
        }
        pointer_id = self._store.append(self._capability, payload, [proposal_id])
        if replay_pointer(self._store).current.pointer_event_id != pointer_id:
            raise ProtocolError("pointer initialization did not replay")
        return pointer_id

    def apply(self, decision_id: str) -> str:
        replay = replay_pointer(self._store)
        current = replay.current
        action, result = _decision_result(
            self._store, decision_id, current, set(replay.decision_ids)
        )
        payload = {
            "action": action,
            "decision_id": decision_id,
            "previous_pointer_event_id": current.pointer_event_id,
            "prior_active_id": current.active_id,
            "record": "pointer",
            "resulting_active_id": result,
            "schema_version": 1,
            "sequence": current.sequence + 1,
        }
        pointer_id = self._store.append(
            self._capability,
            payload,
            [decision_id, current.pointer_event_id, result],
        )
        observed = replay_pointer(self._store).current
        if observed.pointer_event_id != pointer_id or observed.active_id != result:
            raise ProtocolError("pointer transition did not replay")
        return pointer_id

    def replay(self) -> PointerReplay:
        return replay_pointer(self._store)


def run_reset_worker(
    repo: Path,
    kind: str,
    inputs: dict[str, Any],
    *,
    envelope_limit: int = 8192,
) -> dict[str, Any]:
    envelope = {"inputs": inputs, "kind": kind, "schema_version": 1}
    raw = canonical_json(envelope)
    if len(raw) > envelope_limit:
        raise ProtocolError("reset envelope exceeds the frozen aggregate bound")
    environment = {
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(repo.resolve() / "src"),
    }
    try:
        with tempfile.TemporaryDirectory(prefix="ot-0071-reset-") as workspace:
            process = subprocess.run(
                [sys.executable, "-m", "open_trajectory_harness.ot0071_reset_worker"],
                cwd=workspace,
                env=environment,
                input=raw,
                capture_output=True,
                timeout=RESET_SECONDS,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProtocolError("fresh reset process failed operationally") from error
    if process.returncode != 0 or process.stderr:
        raise ProtocolError("fresh reset process rejected its exact envelope")
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise ProtocolError("fresh reset output is not JSON") from error
    if process.stdout != canonical_json(result):
        raise ProtocolError("fresh reset output is not canonical")
    result = _exact(
        result,
        {
            "kind",
            "payloads",
            "schema_version",
            "workspace_empty_after",
            "workspace_empty_before",
        },
        "fresh reset result",
    )
    if (
        result["schema_version"] != 1
        or result["kind"] != kind
        or not result["workspace_empty_before"]
        or not result["workspace_empty_after"]
        or type(result["payloads"]) is not dict
    ):
        raise ProtocolError("fresh reset result violates isolation")
    return result["payloads"]


def _case(task: dict[str, Any], case_index: int) -> dict[str, Any]:
    validate_task(task)
    if case_index not in CASE_INDICES:
        raise ProtocolError("case index is unavailable")
    case = task["cases"][case_index]
    if case["case_index"] != case_index:
        raise ProtocolError("task case index differs")
    return case


def _proposal_parent_by_marker(
    store: TrajectoryStore, proposal_id: str, marker: str
) -> str:
    proposal = validate_proposal(store, proposal_id)
    matches = [
        parent
        for parent in proposal["parents"]
        if _record(store, parent)["payload"].get("record") == marker
    ]
    if len(matches) != 1:
        raise ProtocolError(f"proposal does not have one {marker} parent")
    return matches[0]


@functools.lru_cache(maxsize=None)
def active_practice_id(store: TrajectoryStore, active_id: str) -> str | None:
    proposal = validate_proposal(store, active_id)
    occurrence = proposal["payload"]["occurrence"]
    if occurrence == "genesis":
        return None
    if occurrence != "successor":
        raise ProtocolError("active proposal occurrence cannot carry practice")
    request_id = _proposal_parent_by_marker(store, active_id, "projection_request")
    request = validate_projection_request(store, request_id)
    return request["payload"]["practice_id"]


@functools.lru_cache(maxsize=None)
def validate_locator(store: TrajectoryStore, locator_id: str) -> dict[str, Any]:
    record = _record(store, locator_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("locator lacks actor-channel provenance")
    payload = _exact(
        record["payload"],
        {
            "body",
            "case_token",
            "proposal_id",
            "record",
            "schema_version",
            "source_context_id",
            "surface_sha256",
            "trial_id",
        },
        "locator payload",
    )
    if payload["record"] != "locator" or payload["schema_version"] != 1:
        raise ProtocolError("locator marker is invalid")
    _token(payload["case_token"], "locator case token")
    context_id = _rid(payload["source_context_id"], "locator source context")
    proposal_id = _rid(payload["proposal_id"], "locator proposal")
    trial_id = _rid(payload["trial_id"], "locator trial")
    assert context_id is not None and proposal_id is not None and trial_id is not None
    if record["parents"] != sorted({context_id, proposal_id, trial_id}):
        raise ProtocolError("locator ancestry differs from named branch")
    context = validate_source_context(store, context_id)
    proposal = validate_proposal(store, proposal_id)
    trial = validate_trial(store, trial_id, expected_proposal_id=proposal_id)
    if (
        proposal["payload"]["occurrence"] != "source"
        or proposal["payload"]["source_context_id"] != context_id
        or context["payload"]["case_token"] != payload["case_token"]
        or proposal["payload"]["case_token"] != payload["case_token"]
        or trial["payload"]["case_token"] != payload["case_token"]
    ):
        raise ProtocolError("locator branch bindings differ")
    body = _exact(payload["body"], {"record", "record_id"}, "locator body")
    if body != {"record": context, "record_id": context_id}:
        raise ProtocolError("locator body is not the complete source context")
    if len(canonical_json(body)) > 1024:
        raise ProtocolError("locator body exceeds its bound")
    surface = {
        "proposal": {"record": proposal, "record_id": proposal_id},
        "source_context": {"record": context, "record_id": context_id},
        "trial": {"record": trial, "record_id": trial_id},
    }
    if payload["surface_sha256"] != sha256_bytes(canonical_json(surface)):
        raise ProtocolError("locator surface digest differs")
    return record


@functools.lru_cache(maxsize=None)
def validate_directory(store: TrajectoryStore, directory_id: str) -> dict[str, Any]:
    record = _record(store, directory_id)
    if record["source"] != CONTROLLER_SOURCE:
        raise ProtocolError("directory lacks controller-channel provenance")
    payload = _exact(
        record["payload"],
        {"case_token", "entries", "record", "schema_version"},
        "directory payload",
    )
    if payload["record"] != "directory" or payload["schema_version"] != 1:
        raise ProtocolError("directory marker is invalid")
    _token(payload["case_token"], "directory case token")
    entries = payload["entries"]
    if type(entries) is not list or len(entries) != 3:
        raise ProtocolError("directory entry count differs")
    locator_ids: list[str] = []
    handles: list[str] = []
    for index, raw in enumerate(entries):
        entry = _exact(
            raw,
            {"address_handle", "locator_id", "proposal_id", "trial_id"},
            f"directory entry {index}",
        )
        handles.append(_token(entry["address_handle"], "directory address"))
        locator_id = _rid(entry["locator_id"], "directory locator")
        proposal_id = _rid(entry["proposal_id"], "directory proposal")
        trial_id = _rid(entry["trial_id"], "directory trial")
        assert locator_id is not None and proposal_id is not None and trial_id is not None
        locator = validate_locator(store, locator_id)
        if (
            locator["payload"]["proposal_id"] != proposal_id
            or locator["payload"]["trial_id"] != trial_id
            or locator["payload"]["case_token"] != payload["case_token"]
        ):
            raise ProtocolError("directory tuple differs from locator binding")
        locator_ids.append(locator_id)
    if len(set(handles)) != 3 or len(set(locator_ids)) != 3:
        raise ProtocolError("directory identities are not unique")
    if record["parents"] != sorted(locator_ids):
        raise ProtocolError("directory parents differ from locators")
    return record


def directory_entry(
    store: TrajectoryStore, directory_id: str, address_handle: str
) -> dict[str, Any]:
    directory = validate_directory(store, directory_id)
    matches = [
        entry
        for entry in directory["payload"]["entries"]
        if entry["address_handle"] == address_handle
    ]
    if len(matches) != 1:
        raise ProtocolError("directory address does not resolve exactly once")
    return matches[0]


@functools.lru_cache(maxsize=None)
def _validate_contact_historical(
    store: TrajectoryStore, contact_id: str
) -> dict[str, Any]:
    record = _record(store, contact_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("contact lacks world-channel provenance")
    payload = _exact(
        record["payload"],
        {
            "active_practice_id",
            "active_proposal_id",
            "case_token",
            "directory_id",
            "pointer_event_id",
            "query_keys",
            "record",
            "regime",
            "schema_version",
        },
        "contact payload",
    )
    if payload["record"] != "contact" or payload["schema_version"] != 1:
        raise ProtocolError("contact marker is invalid")
    _token(payload["case_token"], "contact case token")
    _token(payload["regime"], "contact regime token")
    active_id = _rid(payload["active_proposal_id"], "contact active proposal")
    pointer_id = _rid(payload["pointer_event_id"], "contact pointer")
    directory_id = _rid(payload["directory_id"], "contact directory")
    practice_id = _rid(
        payload["active_practice_id"], "contact active practice", nullable=True
    )
    assert active_id is not None and pointer_id is not None and directory_id is not None
    replay = replay_pointer(store)
    historical = [
        state
        for state in replay.states
        if state.pointer_event_id == pointer_id and state.active_id == active_id
    ]
    if len(historical) != 1:
        raise ProtocolError("contact does not bind one replay-derived pointer state")
    proposal = validate_proposal(store, active_id)
    directory = validate_directory(store, directory_id)
    if proposal["payload"]["case_token"] != payload["case_token"] or directory["payload"]["case_token"] != payload["case_token"]:
        raise ProtocolError("contact case binding differs")
    if active_practice_id(store, active_id) != practice_id:
        raise ProtocolError("contact active practice is not replay-derived")
    queries = payload["query_keys"]
    if type(queries) is not list or len(queries) != 3:
        raise ProtocolError("contact query count differs")
    checked_queries = [_token(query, "contact query") for query in queries]
    if checked_queries != sorted(set(checked_queries)):
        raise ProtocolError("contact queries are not sorted and unique")
    expected_parents = sorted(
        {active_id, pointer_id, directory_id}
        | ({practice_id} if practice_id is not None else set())
    )
    if record["parents"] != expected_parents:
        raise ProtocolError("contact ancestry differs")
    return record


def validate_contact(
    store: TrajectoryStore, contact_id: str, *, require_current: bool = False
) -> dict[str, Any]:
    record = _validate_contact_historical(store, contact_id)
    if require_current:
        payload = record["payload"]
        current = replay_pointer(store).current
        if (
            current.active_id != payload["active_proposal_id"]
            or current.pointer_event_id != payload["pointer_event_id"]
        ):
            raise ProtocolError("contact is stale for the current pointer")
    return record


def _validate_binary_trace(
    trace: object,
    *,
    length: int,
    active_key: str,
    label: str,
) -> list[dict[str, Any]]:
    if type(trace) is not list or len(trace) != length:
        raise ProtocolError(f"{label} trace length differs")
    expected_keys = {active_key, "feature", "input", "resolved_output", "trial_id"}
    checked = []
    for index, raw in enumerate(trace):
        row = _exact(raw, expected_keys, f"{label} row {index}")
        _coefficient_vector(row["feature"], f"{label} row feature")
        _token(row["input"], f"{label} row input")
        _token(row["trial_id"], f"{label} row identity")
        if type(row[active_key]) is not int or row[active_key] not in {0, 1}:
            raise ProtocolError(f"{label} active output is not binary")
        if type(row["resolved_output"]) is not int or row["resolved_output"] not in {0, 1}:
            raise ProtocolError(f"{label} resolved output is not binary")
        checked.append(row)
    return checked


@functools.lru_cache(maxsize=None)
def validate_correction(
    store: TrajectoryStore, correction_id: str
) -> dict[str, Any]:
    record = _record(store, correction_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("correction consequence lacks world provenance")
    payload = _exact(
        record["payload"],
        {
            "active_proposal_id",
            "case_token",
            "contact_id",
            "directory_id",
            "pointer_event_id",
            "record",
            "regime",
            "schema_version",
            "trace",
        },
        "correction-consequence payload",
    )
    if payload["record"] != "correction_consequence" or payload["schema_version"] != 1:
        raise ProtocolError("correction-consequence marker is invalid")
    contact_id = _rid(payload["contact_id"], "correction contact")
    assert contact_id is not None
    contact = validate_contact(store, contact_id)
    for key in ("active_proposal_id", "directory_id", "pointer_event_id", "case_token", "regime"):
        if payload[key] != contact["payload"][key]:
            raise ProtocolError(f"correction {key} differs from contact")
    expected_parents = sorted(
        {
            contact_id,
            payload["active_proposal_id"],
            payload["directory_id"],
            payload["pointer_event_id"],
        }
    )
    if record["parents"] != expected_parents:
        raise ProtocolError("correction ancestry differs")
    _validate_binary_trace(
        payload["trace"], length=3, active_key="active_output", label="correction"
    )
    return record


@functools.lru_cache(maxsize=None)
def _validate_diagnostic_request_historical(
    store: TrajectoryStore, request_id: str
) -> dict[str, Any]:
    record = _record(store, request_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("diagnostic request lacks actor provenance")
    payload = _exact(
        record["payload"],
        {
            "address_handle",
            "case_token",
            "contact_id",
            "correction_consequence_id",
            "directory_id",
            "expected_active_id",
            "expected_pointer_event_id",
            "locator_id",
            "proposal_id",
            "query_key",
            "record",
            "regime",
            "schema_version",
            "trial_id",
        },
        "diagnostic-request payload",
    )
    if payload["record"] != "diagnostic_request" or payload["schema_version"] != 1:
        raise ProtocolError("diagnostic-request marker is invalid")
    for key in ("address_handle", "case_token", "query_key", "regime"):
        _token(payload[key], f"diagnostic {key}")
    contact_id = _rid(payload["contact_id"], "diagnostic contact")
    correction_id = _rid(
        payload["correction_consequence_id"], "diagnostic correction"
    )
    directory_id = _rid(payload["directory_id"], "diagnostic directory")
    assert contact_id is not None and correction_id is not None and directory_id is not None
    contact = validate_contact(store, contact_id)
    correction = validate_correction(store, correction_id)
    if correction["payload"]["contact_id"] != contact_id:
        raise ProtocolError("diagnostic correction is not contact-bound")
    entry = directory_entry(store, directory_id, payload["address_handle"])
    for key in ("locator_id", "proposal_id", "trial_id"):
        if payload[key] != entry[key]:
            raise ProtocolError("diagnostic tuple differs from directory")
    if payload["query_key"] not in contact["payload"]["query_keys"]:
        raise ProtocolError("diagnostic query is absent from contact")
    for request_key, contact_key in (
        ("case_token", "case_token"),
        ("regime", "regime"),
        ("expected_active_id", "active_proposal_id"),
        ("expected_pointer_event_id", "pointer_event_id"),
        ("directory_id", "directory_id"),
    ):
        if payload[request_key] != contact["payload"][contact_key]:
            raise ProtocolError("diagnostic current-state binding differs")
    expected_parents = sorted(
        {
            contact_id,
            correction_id,
            directory_id,
            payload["locator_id"],
            payload["proposal_id"],
            payload["trial_id"],
        }
    )
    if record["parents"] != expected_parents:
        raise ProtocolError("diagnostic ancestry differs")
    return record


def validate_diagnostic_request(
    store: TrajectoryStore, request_id: str, *, require_current: bool = False
) -> dict[str, Any]:
    record = _validate_diagnostic_request_historical(store, request_id)
    if require_current:
        validate_contact(store, record["payload"]["contact_id"], require_current=True)
    return record


@functools.lru_cache(maxsize=None)
def validate_outcome(store: TrajectoryStore, outcome_id: str) -> dict[str, Any]:
    record = _record(store, outcome_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("attempt outcome lacks world provenance")
    payload = _exact(
        record["payload"],
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
        "attempt-outcome payload",
    )
    if payload["record"] != "attempt_outcome" or payload["schema_version"] != 1:
        raise ProtocolError("attempt-outcome marker is invalid")
    for key in (
        "address_handle",
        "case_token",
        "proposal_output",
        "query_key",
        "resolved_output",
    ):
        _token(payload[key], f"outcome {key}")
    if type(payload["world_receipt"]) is not str or len(payload["world_receipt"]) != 512:
        raise ProtocolError("outcome world receipt length differs")
    request_id = _rid(payload["request_id"], "outcome request")
    assert request_id is not None
    request = validate_diagnostic_request(store, request_id)
    if payload["address_handle"] != request["payload"]["address_handle"] or payload["query_key"] != request["payload"]["query_key"] or payload["case_token"] != request["payload"]["case_token"]:
        raise ProtocolError("outcome does not copy request identity")
    proposal_id = request["payload"]["proposal_id"]
    proposal = validate_proposal(store, proposal_id)
    context_id = proposal["payload"]["source_context_id"]
    assert context_id is not None
    if payload["proposal_output"] != validate_source_context(store, context_id)["payload"]["branch_key"]:
        raise ProtocolError("outcome proposal output differs from source context")
    expected_parents = sorted(
        {request_id, context_id, proposal_id, request["payload"]["trial_id"]}
    )
    if record["parents"] != expected_parents:
        raise ProtocolError("outcome ancestry differs")
    return record


def _practice_rows(
    rows: object, query_keys: list[str], directory_handles: set[str], label: str
) -> list[dict[str, str]]:
    if type(rows) is not list or len(rows) != 3:
        raise ProtocolError(f"{label} row count differs")
    checked = []
    for index, raw in enumerate(rows):
        row = _exact(raw, {"address_handle", "query_key"}, f"{label} row {index}")
        handle = _token(row["address_handle"], f"{label} address")
        query = _token(row["query_key"], f"{label} query")
        if handle not in directory_handles:
            raise ProtocolError(f"{label} address is absent from directory")
        checked.append({"address_handle": handle, "query_key": query})
    if [row["query_key"] for row in checked] != sorted(query_keys):
        raise ProtocolError(f"{label} rows do not cover sorted contact queries")
    return checked


@functools.lru_cache(maxsize=None)
def validate_practice_receipt(
    store: TrajectoryStore, receipt_id: str
) -> dict[str, Any]:
    record = _record(store, receipt_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("practice receipt lacks actor provenance")
    payload = _exact(
        record["payload"],
        {
            "case_token",
            "contact_id",
            "correction_consequence_id",
            "directory_id",
            "expected_active_id",
            "expected_pointer_event_id",
            "previous_practice_id",
            "record",
            "regime",
            "rows",
            "schema_version",
            "support_outcome_ids",
        },
        "practice-receipt payload",
    )
    if payload["record"] != "practice_receipt" or payload["schema_version"] != 1:
        raise ProtocolError("practice-receipt marker is invalid")
    contact_id = _rid(payload["contact_id"], "receipt contact")
    correction_id = _rid(payload["correction_consequence_id"], "receipt correction")
    directory_id = _rid(payload["directory_id"], "receipt directory")
    previous = _rid(payload["previous_practice_id"], "receipt previous practice", nullable=True)
    assert contact_id is not None and correction_id is not None and directory_id is not None
    contact = validate_contact(store, contact_id)
    validate_correction(store, correction_id)
    directory = validate_directory(store, directory_id)
    for key, contact_key in (
        ("case_token", "case_token"),
        ("regime", "regime"),
        ("expected_active_id", "active_proposal_id"),
        ("expected_pointer_event_id", "pointer_event_id"),
        ("directory_id", "directory_id"),
    ):
        if payload[key] != contact["payload"][contact_key]:
            raise ProtocolError("practice receipt current-state binding differs")
    if previous != contact["payload"]["active_practice_id"]:
        raise ProtocolError("practice receipt previous practice differs")
    support = payload["support_outcome_ids"]
    if type(support) is not list or len(support) != 6:
        raise ProtocolError("practice receipt support count differs")
    checked_support = [_rid(item, "practice support outcome") for item in support]
    if checked_support != sorted(set(checked_support)):
        raise ProtocolError("practice support outcomes are not sorted and unique")
    grouped: dict[str, set[str]] = {}
    for outcome_id in checked_support:
        assert outcome_id is not None
        outcome = validate_outcome(store, outcome_id)
        request = validate_diagnostic_request(store, outcome["payload"]["request_id"])
        if request["payload"]["contact_id"] != contact_id or request["payload"]["correction_consequence_id"] != correction_id or request["payload"]["directory_id"] != directory_id:
            raise ProtocolError("practice support is stale or misbound")
        grouped.setdefault(outcome["payload"]["query_key"], set()).add(
            outcome["payload"]["address_handle"]
        )
    handles = {entry["address_handle"] for entry in directory["payload"]["entries"]}
    if len(grouped) != 2 or any(value != handles for value in grouped.values()):
        raise ProtocolError("practice support is not two complete exhaustive queries")
    _practice_rows(payload["rows"], contact["payload"]["query_keys"], handles, "receipt")
    expected_parents = sorted(
        {contact_id, correction_id, directory_id, *checked_support}
        | ({previous} if previous is not None else set())
    )
    if record["parents"] != expected_parents:
        raise ProtocolError("practice receipt ancestry differs")
    return record


@functools.lru_cache(maxsize=None)
def validate_practice(store: TrajectoryStore, practice_id: str) -> dict[str, Any]:
    record = _record(store, practice_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("compact practice lacks actor provenance")
    payload = _exact(
        record["payload"],
        {"case_token", "practice_receipt_id", "record", "rows", "schema_version"},
        "practice payload",
    )
    if payload["record"] != "practice" or payload["schema_version"] != 1:
        raise ProtocolError("practice marker is invalid")
    receipt_id = _rid(payload["practice_receipt_id"], "practice receipt")
    assert receipt_id is not None
    if record["parents"] != [receipt_id]:
        raise ProtocolError("compact practice is not exact receipt child")
    receipt = validate_practice_receipt(store, receipt_id)
    if payload["case_token"] != receipt["payload"]["case_token"] or payload["rows"] != receipt["payload"]["rows"]:
        raise ProtocolError("compact practice differs from full receipt")
    if len(store.serialize_projection([practice_id])) > PROJECTION_BYTES:
        raise ProtocolError("compact practice exceeds active projection budget")
    return record


@functools.lru_cache(maxsize=None)
def heldout_query_from_practice(
    store: TrajectoryStore, practice_id: str, contact_id: str
) -> str:
    practice = validate_practice(store, practice_id)
    receipt = validate_practice_receipt(
        store, practice["payload"]["practice_receipt_id"]
    )
    contact = validate_contact(store, contact_id)
    support_queries = {
        validate_outcome(store, outcome_id)["payload"]["query_key"]
        for outcome_id in receipt["payload"]["support_outcome_ids"]
    }
    missing = [
        query for query in contact["payload"]["query_keys"] if query not in support_queries
    ]
    if len(missing) != 1:
        raise ProtocolError("practice support does not structurally derive heldout query")
    return missing[0]


@functools.lru_cache(maxsize=None)
def _validate_projection_request_historical(
    store: TrajectoryStore, request_id: str
) -> dict[str, Any]:
    record = _record(store, request_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("projection request lacks actor provenance")
    payload = _exact(
        record["payload"],
        {
            "address_handle",
            "case_token",
            "contact_id",
            "directory_id",
            "expected_active_id",
            "expected_pointer_event_id",
            "locator_id",
            "practice_id",
            "proposal_id",
            "query_key",
            "record",
            "regime",
            "schema_version",
            "trial_id",
        },
        "projection-request payload",
    )
    if payload["record"] != "projection_request" or payload["schema_version"] != 1:
        raise ProtocolError("projection-request marker is invalid")
    contact_id = _rid(payload["contact_id"], "projection contact")
    directory_id = _rid(payload["directory_id"], "projection directory")
    practice_id = _rid(payload["practice_id"], "projection practice")
    assert contact_id is not None and directory_id is not None and practice_id is not None
    contact = validate_contact(store, contact_id)
    practice = validate_practice(store, practice_id)
    heldout = heldout_query_from_practice(store, practice_id, contact_id)
    if payload["query_key"] != heldout:
        raise ProtocolError("projection request query is not structurally held out")
    rows = [row for row in practice["payload"]["rows"] if row["query_key"] == heldout]
    if len(rows) != 1 or payload["address_handle"] != rows[0]["address_handle"]:
        raise ProtocolError("projection request differs from pure practice lookup")
    entry = directory_entry(store, directory_id, payload["address_handle"])
    for key in ("locator_id", "proposal_id", "trial_id"):
        if payload[key] != entry[key]:
            raise ProtocolError("projection request tuple differs from directory")
    for request_key, contact_key in (
        ("case_token", "case_token"),
        ("regime", "regime"),
        ("expected_active_id", "active_proposal_id"),
        ("expected_pointer_event_id", "pointer_event_id"),
        ("directory_id", "directory_id"),
    ):
        if payload[request_key] != contact["payload"][contact_key]:
            raise ProtocolError("projection request current-state binding differs")
    expected_parents = sorted(
        {
            practice_id,
            contact_id,
            directory_id,
            payload["locator_id"],
            payload["proposal_id"],
            payload["trial_id"],
        }
    )
    if record["parents"] != expected_parents:
        raise ProtocolError("projection request ancestry differs")
    return record


def validate_projection_request(
    store: TrajectoryStore, request_id: str, *, require_current: bool = False
) -> dict[str, Any]:
    record = _validate_projection_request_historical(store, request_id)
    if require_current:
        validate_contact(store, record["payload"]["contact_id"], require_current=True)
    return record


@functools.lru_cache(maxsize=None)
def validate_endpoint(store: TrajectoryStore, endpoint_id: str) -> dict[str, Any]:
    record = _record(store, endpoint_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("endpoint lacks world provenance")
    payload = _exact(
        record["payload"],
        {
            "active_proposal_id",
            "case_token",
            "directory_id",
            "pointer_event_id",
            "record",
            "regime",
            "schema_version",
            "trace",
        },
        "endpoint payload",
    )
    if payload["record"] != "endpoint" or payload["schema_version"] != 1:
        raise ProtocolError("endpoint marker is invalid")
    states = [
        state
        for state in replay_pointer(store).states
        if state.active_id == payload["active_proposal_id"]
        and state.pointer_event_id == payload["pointer_event_id"]
    ]
    if len(states) != 1:
        raise ProtocolError("endpoint does not bind one replay-derived pointer state")
    validate_directory(store, payload["directory_id"])
    validate_proposal(store, payload["active_proposal_id"])
    if record["parents"] != sorted(
        {payload["active_proposal_id"], payload["pointer_event_id"], payload["directory_id"]}
    ):
        raise ProtocolError("endpoint ancestry differs")
    _validate_binary_trace(
        payload["trace"], length=6, active_key="active_output", label="endpoint"
    )
    return record


def _append_source_bundle(
    runtime: CaseRuntime,
    branch_order: tuple[int, int, int] = (0, 1, 2),
) -> tuple[tuple[dict[str, str], ...], str]:
    store = runtime.store
    case = runtime.case
    coefficients = runtime.acceptance["mechanism_world"][
        "coefficient_vectors_by_semantic_branch"
    ]
    source_features = runtime.acceptance["mechanism_world"]["source_trial_features"]
    if sorted(branch_order) != [0, 1, 2]:
        raise ValueError("source append order is not a permutation")
    sources: list[dict[str, str] | None] = [None, None, None]
    for branch in branch_order:
        context_payload = {
            "branch_key": case["branch_keys_by_semantic_branch"][branch],
            "case_token": case["case_token"],
            "record": "source_context",
            "schema_version": 1,
        }
        context_id = store.append(
            runtime.world_capability, context_payload, [runtime.genesis_id]
        )
        validate_source_context(store, context_id)
        proposal_payload = {
            "case_token": case["case_token"],
            "coefficients": list(coefficients[branch]),
            "note": "",
            "occurrence": "source",
            "record": "proposal",
            "schema_version": 2,
            "source_context_id": context_id,
        }
        proposal_id = store.append(
            runtime.actor_capability,
            proposal_payload,
            [runtime.genesis_id, context_id],
        )
        validate_proposal(store, proposal_id)
        trace = []
        for feature_index, feature in enumerate(source_features):
            output = mechanism_output(coefficients[branch], feature)
            trace.append(
                {
                    "feature": list(feature),
                    "input": opaque_token(
                        runtime.implementation_commit,
                        "source-input",
                        [runtime.case_index, branch, feature_index],
                    ),
                    "proposal_output": output,
                    "resolved_output": output,
                    "trial_id": opaque_token(
                        runtime.implementation_commit,
                        "source-trial-row",
                        [runtime.case_index, branch, feature_index],
                    ),
                }
            )
        trial_payload = {
            "case_token": case["case_token"],
            "executor_receipt": opaque_token(
                runtime.implementation_commit,
                "executor-receipt",
                [runtime.case_index, "source", branch, -1],
            ),
            "proposal_id": proposal_id,
            "record": "trial",
            "schema_version": 2,
            "scope": "source",
            "trace": trace,
        }
        trial_id = store.append(runtime.world_capability, trial_payload, [proposal_id])
        validate_trial(store, trial_id, expected_proposal_id=proposal_id)
        context = _record(store, context_id)
        proposal = _record(store, proposal_id)
        trial = _record(store, trial_id)
        surface = {
            "proposal": {"record": proposal, "record_id": proposal_id},
            "source_context": {"record": context, "record_id": context_id},
            "trial": {"record": trial, "record_id": trial_id},
        }
        locator_payload = {
            "body": {"record": context, "record_id": context_id},
            "case_token": case["case_token"],
            "proposal_id": proposal_id,
            "record": "locator",
            "schema_version": 1,
            "source_context_id": context_id,
            "surface_sha256": sha256_bytes(canonical_json(surface)),
            "trial_id": trial_id,
        }
        locator_id = store.append(
            runtime.actor_capability,
            locator_payload,
            [context_id, proposal_id, trial_id],
        )
        validate_locator(store, locator_id)
        sources[branch] = {
            "context_id": context_id,
            "locator_id": locator_id,
            "proposal_id": proposal_id,
            "trial_id": trial_id,
        }
    if any(source is None for source in sources):
        raise ProtocolError("source bundle omitted a semantic branch")
    checked_sources = tuple(source for source in sources if source is not None)
    digest = sha256_bytes(
        canonical_json(
            [
                {
                    key: source[key]
                    for key in ("context_id", "locator_id", "proposal_id", "trial_id")
                }
                for source in checked_sources
            ]
        )
    )
    return checked_sources, digest


def build_case_runtime(
    task: dict[str, Any],
    acceptance: dict[str, Any],
    case_index: int,
    *,
    source_order: tuple[int, int, int] = (0, 1, 2),
) -> tuple[CaseRuntime, str]:
    """Build source history first, then derive the sealed regime schedule."""

    case = _case(task, case_index)
    store, actor, world, controller_capability = bootstrap_trajectory_store(
        max_record_bytes=MAX_RECORD_BYTES
    )
    genesis_payload = {
        "case_token": case["case_token"],
        "coefficients": [0, 0],
        "note": "",
        "occurrence": "genesis",
        "record": "proposal",
        "schema_version": 2,
        "source_context_id": None,
    }
    genesis_id = store.append(actor, genesis_payload, [])
    validate_proposal(store, genesis_id)
    pointer = PointerController(store, controller_capability)
    pointer.initialize(genesis_id)
    provisional = CaseRuntime(
        store=store,
        actor_capability=actor,
        world_capability=world,
        controller_capability=controller_capability,
        controller=pointer,
        implementation_commit=task["implementation_commit"],
        acceptance=acceptance,
        case_index=case_index,
        case=case,
        genesis_id=genesis_id,
        directory_id="",
        sources=(),
        schedule=(0, 0, 0),
    )
    sources, source_digest = _append_source_bundle(provisional, source_order)
    rank_assignment = acceptance["address_world"][
        "address_rank_assignment_by_case_modulo_eight"
    ][case_index % 8]
    entries: list[dict[str, str] | None] = [None, None, None]
    for semantic_branch, rank in enumerate(rank_assignment):
        source = sources[semantic_branch]
        entries[rank] = {
            "address_handle": case["address_handles_by_semantic_branch"][
                semantic_branch
            ],
            "locator_id": source["locator_id"],
            "proposal_id": source["proposal_id"],
            "trial_id": source["trial_id"],
        }
    if any(entry is None for entry in entries):
        raise ProtocolError("address-rank assignment is not a permutation")
    directory_payload = {
        "case_token": case["case_token"],
        "entries": entries,
        "record": "directory",
        "schema_version": 1,
    }
    directory_id = store.append(
        controller_capability,
        directory_payload,
        [source["locator_id"] for source in sources],
    )
    validate_directory(store, directory_id)
    # This is deliberately after every source context/proposal/trial/locator ID.
    schedule = tuple(
        acceptance["address_world"]["case_regime_permutation_indices"][case_index]
    )
    runtime = CaseRuntime(
        **{
            **provisional.__dict__,
            "directory_id": directory_id,
            "sources": sources,
            "schedule": schedule,
        }
    )
    return runtime, source_digest


def _target_semantic_branch(runtime: CaseRuntime, regime_index: int) -> int:
    permutation_index = runtime.schedule[regime_index]
    permutation = runtime.acceptance["address_world"]["semantic_permutations"][
        permutation_index
    ]
    heldout = runtime.acceptance["address_world"]["heldout_query_semantic_index"]
    return permutation[heldout]


def _target_coefficients(runtime: CaseRuntime, regime_index: int) -> list[int]:
    branch = _target_semantic_branch(runtime, regime_index)
    return list(
        runtime.acceptance["mechanism_world"][
            "coefficient_vectors_by_semantic_branch"
        ][branch]
    )


def append_contact(runtime: CaseRuntime, regime_index: int) -> str:
    state = runtime.controller.replay().current
    practice_id = active_practice_id(runtime.store, state.active_id)
    payload = {
        "active_practice_id": practice_id,
        "active_proposal_id": state.active_id,
        "case_token": runtime.case["case_token"],
        "directory_id": runtime.directory_id,
        "pointer_event_id": state.pointer_event_id,
        "query_keys": sorted(runtime.case["query_keys_by_semantic_query"]),
        "record": "contact",
        "regime": runtime.case["contact_tokens"][regime_index],
        "schema_version": 1,
    }
    parents = [state.active_id, state.pointer_event_id, runtime.directory_id]
    if practice_id is not None:
        parents.append(practice_id)
    contact_id = runtime.store.append(runtime.world_capability, payload, parents)
    validate_contact(runtime.store, contact_id, require_current=True)
    return contact_id


def append_correction(
    runtime: CaseRuntime, contact_id: str, regime_index: int
) -> str:
    contact = validate_contact(runtime.store, contact_id, require_current=True)
    active = validate_proposal(
        runtime.store, contact["payload"]["active_proposal_id"]
    )
    active_coefficients = active["payload"]["coefficients"]
    target = _target_coefficients(runtime, regime_index)
    features = runtime.acceptance["mechanism_world"][
        "successor_correction_features"
    ]
    trace = []
    for feature_index, feature in enumerate(features):
        trace.append(
            {
                "active_output": mechanism_output(active_coefficients, feature),
                "feature": list(feature),
                "input": opaque_token(
                    runtime.implementation_commit,
                    "correction-input",
                    [runtime.case_index, regime_index, feature_index + 3],
                ),
                "resolved_output": mechanism_output(target, feature),
                "trial_id": opaque_token(
                    runtime.implementation_commit,
                    "correction-trial-row",
                    [runtime.case_index, regime_index, feature_index + 3],
                ),
            }
        )
    payload = {
        "active_proposal_id": contact["payload"]["active_proposal_id"],
        "case_token": runtime.case["case_token"],
        "contact_id": contact_id,
        "directory_id": runtime.directory_id,
        "pointer_event_id": contact["payload"]["pointer_event_id"],
        "record": "correction_consequence",
        "regime": runtime.case["contact_tokens"][regime_index],
        "schema_version": 1,
        "trace": trace,
    }
    correction_id = runtime.store.append(
        runtime.world_capability,
        payload,
        [
            contact_id,
            payload["active_proposal_id"],
            payload["pointer_event_id"],
            runtime.directory_id,
        ],
    )
    validate_correction(runtime.store, correction_id)
    return correction_id


def trace_errors(trace: list[dict[str, Any]], active_key: str) -> int:
    return sum(row[active_key] != row["resolved_output"] for row in trace)


def _source_for_entry(runtime: CaseRuntime, entry: dict[str, Any]) -> dict[str, str]:
    matches = [source for source in runtime.sources if source["proposal_id"] == entry["proposal_id"]]
    if len(matches) != 1:
        raise ProtocolError("directory tuple does not map to one source branch")
    return matches[0]


def append_diagnostics(
    repo: Path,
    runtime: CaseRuntime,
    contact_id: str,
    correction_id: str,
    regime_index: int,
    *,
    reverse_order: bool = False,
) -> tuple[str, ...]:
    contact_projection = runtime.store.project([contact_id])
    directory_projection = runtime.store.project([runtime.directory_id])
    outcomes: list[str] = []
    permutation = runtime.acceptance["address_world"]["semantic_permutations"][
        runtime.schedule[regime_index]
    ]
    diagnostic_queries = runtime.acceptance["address_world"][
        "diagnostic_query_semantic_indices"
    ]
    attempts = [
        (diagnostic_index, semantic_query, address_rank)
        for diagnostic_index, semantic_query in enumerate(diagnostic_queries)
        for address_rank in range(3)
    ]
    if reverse_order:
        attempts.reverse()
    for diagnostic_index, semantic_query, address_rank in attempts:
        query_key = runtime.case["query_keys_by_semantic_query"][semantic_query]
        resolved_key = runtime.case["branch_keys_by_semantic_branch"][
            permutation[semantic_query]
        ]
        directory = validate_directory(runtime.store, runtime.directory_id)
        entry = directory["payload"]["entries"][address_rank]
        request_payload = run_reset_worker(
            repo,
            "diagnostic",
            {
                "address_handle": entry["address_handle"],
                "attempt_ordinal": address_rank,
                "contact": contact_projection,
                "correction_consequence_id": correction_id,
                "directory": directory_projection,
                "query_key": query_key,
            },
        )
        request_parents = [
            contact_id,
            correction_id,
            runtime.directory_id,
            request_payload["locator_id"],
            request_payload["proposal_id"],
            request_payload["trial_id"],
        ]
        request_id = runtime.store.append(
            runtime.actor_capability, request_payload, request_parents
        )
        validate_diagnostic_request(
            runtime.store, request_id, require_current=True
        )
        if len(runtime.store.serialize_projection([request_id])) > PROJECTION_BYTES:
            raise ProtocolError("diagnostic request projection exceeds budget")
        selected = _source_for_entry(runtime, entry)
        proposal_output = validate_source_context(
            runtime.store, selected["context_id"]
        )["payload"]["branch_key"]
        outcome_payload = {
            "address_handle": entry["address_handle"],
            "case_token": runtime.case["case_token"],
            "proposal_output": proposal_output,
            "query_key": query_key,
            "record": "attempt_outcome",
            "request_id": request_id,
            "resolved_output": resolved_key,
            "schema_version": 1,
            "world_receipt": expansion(
                runtime.implementation_commit,
                "world-receipt",
                [
                    runtime.case_index,
                    regime_index,
                    diagnostic_index,
                    address_rank,
                ],
                512,
            ),
        }
        outcome_id = runtime.store.append(
            runtime.world_capability,
            outcome_payload,
            [
                request_id,
                selected["context_id"],
                selected["proposal_id"],
                selected["trial_id"],
            ],
        )
        validate_outcome(runtime.store, outcome_id)
        outcome_bytes = len(runtime.store.serialize_projection([outcome_id]))
        if not 1025 <= outcome_bytes <= PROJECTION_BYTES:
            raise ProtocolError("outcome projection differs from frozen geometry")
        outcomes.append(outcome_id)
    return tuple(outcomes)


def append_practice(
    repo: Path,
    runtime: CaseRuntime,
    contact_id: str,
    correction_id: str,
    outcome_ids: tuple[str, ...],
) -> tuple[str, str]:
    contact = validate_contact(runtime.store, contact_id)
    previous_id = contact["payload"]["active_practice_id"]
    payloads = run_reset_worker(
        repo,
        "practice_fit",
        {
            "contact": runtime.store.project([contact_id]),
            "correction_consequence": runtime.store.project([correction_id]),
            "directory": runtime.store.project([runtime.directory_id]),
            "outcomes": [runtime.store.project([outcome]) for outcome in outcome_ids],
            "previous_practice": (
                runtime.store.project([previous_id]) if previous_id is not None else None
            ),
        },
        envelope_limit=24_576,
    )
    payloads = _exact(
        payloads,
        {"practice_payload", "practice_receipt_payload"},
        "practice-fit payloads",
    )
    receipt_payload = payloads["practice_receipt_payload"]
    receipt_parents = [
        contact_id,
        correction_id,
        runtime.directory_id,
        *outcome_ids,
    ]
    if previous_id is not None:
        receipt_parents.append(previous_id)
    receipt_id = runtime.store.append(
        runtime.actor_capability, receipt_payload, receipt_parents
    )
    validate_practice_receipt(runtime.store, receipt_id)
    if len(canonical_json(runtime.store.get(receipt_id))) > MAX_RECORD_BYTES:
        raise ProtocolError("full practice receipt exceeds record budget")
    practice_payload = payloads["practice_payload"]
    if practice_payload.get("practice_receipt_id") != receipt_id:
        raise ProtocolError("fresh fitter predicted a different receipt identity")
    practice_id = runtime.store.append(
        runtime.actor_capability, practice_payload, [receipt_id]
    )
    validate_practice(runtime.store, practice_id)
    return receipt_id, practice_id


def append_projection_request(
    repo: Path,
    runtime: CaseRuntime,
    contact_id: str,
    practice_id: str,
) -> str:
    heldout = heldout_query_from_practice(runtime.store, practice_id, contact_id)
    request_payload = run_reset_worker(
        repo,
        "practice_execute",
        {
            "contact": runtime.store.project([contact_id]),
            "directory": runtime.store.project([runtime.directory_id]),
            "heldout_query_key": heldout,
            "practice": runtime.store.project([practice_id]),
        },
    )
    parents = [
        practice_id,
        contact_id,
        runtime.directory_id,
        request_payload["locator_id"],
        request_payload["proposal_id"],
        request_payload["trial_id"],
    ]
    request_id = runtime.store.append(
        runtime.actor_capability, request_payload, parents
    )
    validate_projection_request(runtime.store, request_id, require_current=True)
    if len(runtime.store.serialize_projection([request_id])) > PROJECTION_BYTES:
        raise ProtocolError("projection request exceeds budget")
    return request_id


def append_successor(
    repo: Path,
    runtime: CaseRuntime,
    contact_id: str,
    request_id: str,
    regime_index: int,
) -> tuple[str, str]:
    request = validate_projection_request(
        runtime.store, request_id, require_current=True
    )
    payload = request["payload"]
    successor_payload = run_reset_worker(
        repo,
        "successor",
        {
            "contact": runtime.store.project([contact_id]),
            "locator": runtime.store.project([payload["locator_id"]]),
            "projection_request": runtime.store.project([request_id]),
            "selected_branch": runtime.store.project(
                [payload["proposal_id"], payload["trial_id"]]
            ),
        },
    )
    prior_active = validate_contact(runtime.store, contact_id)["payload"][
        "active_proposal_id"
    ]
    successor_id = runtime.store.append(
        runtime.actor_capability,
        successor_payload,
        [prior_active, request_id],
    )
    validate_proposal(runtime.store, successor_id)
    coefficients = successor_payload["coefficients"]
    target = _target_coefficients(runtime, regime_index)
    features = runtime.acceptance["mechanism_world"][
        "successor_correction_features"
    ]
    trace = []
    for feature_index, feature in enumerate(features):
        trace.append(
            {
                "feature": list(feature),
                "input": opaque_token(
                    runtime.implementation_commit,
                    "correction-input",
                    [runtime.case_index, regime_index, feature_index],
                ),
                "proposal_output": mechanism_output(coefficients, feature),
                "resolved_output": mechanism_output(target, feature),
                "trial_id": opaque_token(
                    runtime.implementation_commit,
                    "correction-trial-row",
                    [runtime.case_index, regime_index, feature_index],
                ),
            }
        )
    trial_payload = {
        "case_token": runtime.case["case_token"],
        "executor_receipt": opaque_token(
            runtime.implementation_commit,
            "executor-receipt",
            [runtime.case_index, "successor", -1, regime_index],
        ),
        "proposal_id": successor_id,
        "record": "trial",
        "schema_version": 2,
        "scope": "successor",
        "trace": trace,
    }
    trial_id = runtime.store.append(
        runtime.world_capability, trial_payload, [successor_id]
    )
    validate_trial(runtime.store, trial_id, expected_proposal_id=successor_id)
    return successor_id, trial_id


def append_decision(
    repo: Path,
    runtime: CaseRuntime,
    *,
    action: str,
    decision_occurrence: int,
    selected_id: str | None = None,
    trial_id: str | None = None,
    rollback_target_id: str | None = None,
) -> str:
    state = runtime.controller.replay().current
    selected_projection = None
    if action in {"adopt", "set_down"}:
        if selected_id is None or trial_id is None:
            raise ProtocolError("selected decision omits branch")
        selected_projection = runtime.store.project([selected_id, trial_id])
    payload = run_reset_worker(
        repo,
        "decision",
        {
            "case_token": runtime.case["case_token"],
            "decision_token": opaque_token(
                runtime.implementation_commit,
                "decision",
                [runtime.case_index, state.sequence, decision_occurrence],
            ),
            "expected_active_id": state.active_id,
            "expected_pointer_event_id": state.pointer_event_id,
            "requested_action": action,
            "rollback_target_id": rollback_target_id,
            "selected_branch": selected_projection,
        },
    )
    if action in {"adopt", "set_down"}:
        parents = [selected_id, trial_id, state.pointer_event_id]
    else:
        parents = [state.active_id, rollback_target_id, state.pointer_event_id]
    decision_id = runtime.store.append(runtime.actor_capability, payload, parents)
    validate_decision(runtime.store, decision_id)
    return decision_id


def append_endpoint(runtime: CaseRuntime, regime_index: int) -> str:
    state = runtime.controller.replay().current
    active = validate_proposal(runtime.store, state.active_id)
    coefficients = active["payload"]["coefficients"]
    target = _target_coefficients(runtime, regime_index)
    replicas = runtime.acceptance["mechanism_world"]["endpoint_feature_replicas"]
    trace = []
    for replica_index, features in enumerate(replicas):
        for feature_index, feature in enumerate(features):
            trace.append(
                {
                    "active_output": mechanism_output(coefficients, feature),
                    "feature": list(feature),
                    "input": opaque_token(
                        runtime.implementation_commit,
                        "endpoint-input",
                        [
                            runtime.case_index,
                            regime_index,
                            replica_index,
                            feature_index,
                        ],
                    ),
                    "resolved_output": mechanism_output(target, feature),
                    "trial_id": opaque_token(
                        runtime.implementation_commit,
                        "endpoint-trial-row",
                        [
                            runtime.case_index,
                            regime_index,
                            replica_index,
                            feature_index,
                        ],
                    ),
                }
            )
    payload = {
        "active_proposal_id": state.active_id,
        "case_token": runtime.case["case_token"],
        "directory_id": runtime.directory_id,
        "pointer_event_id": state.pointer_event_id,
        "record": "endpoint",
        "regime": runtime.case["contact_tokens"][regime_index],
        "schema_version": 1,
        "trace": trace,
    }
    endpoint_id = runtime.store.append(
        runtime.world_capability,
        payload,
        [state.active_id, state.pointer_event_id, runtime.directory_id],
    )
    validate_endpoint(runtime.store, endpoint_id)
    return endpoint_id


def execute_reference_regime(
    repo: Path,
    runtime: CaseRuntime,
    regime_index: int,
    *,
    requested_action: str = "adopt",
    reverse_diagnostics: bool = False,
) -> dict[str, Any]:
    if requested_action not in {"adopt", "set_down"}:
        raise ValueError("reference regime action is unavailable")
    contact_id = append_contact(runtime, regime_index)
    correction_id = append_correction(runtime, contact_id, regime_index)
    correction = validate_correction(runtime.store, correction_id)
    pre_errors = trace_errors(correction["payload"]["trace"], "active_output")
    outcomes = append_diagnostics(
        repo,
        runtime,
        contact_id,
        correction_id,
        regime_index,
        reverse_order=reverse_diagnostics,
    )
    multi_outcome_rejected = True
    for count in range(2, 7):
        for subset in itertools.combinations(outcomes, count):
            try:
                runtime.store.serialize_projection(subset)
            except ValueError:
                continue
            multi_outcome_rejected = False
    receipt_id, practice_id = append_practice(
        repo, runtime, contact_id, correction_id, outcomes
    )
    request_id = append_projection_request(repo, runtime, contact_id, practice_id)
    successor_id, trial_id = append_successor(
        repo, runtime, contact_id, request_id, regime_index
    )
    successor_trial = validate_trial(runtime.store, trial_id)
    trial_errors = trace_errors(successor_trial["payload"]["trace"], "proposal_output")

    decision = append_decision(
        repo,
        runtime,
        action=requested_action,
        decision_occurrence=regime_index,
        selected_id=successor_id,
        trial_id=trial_id,
    )
    runtime.controller.apply(decision)
    endpoint_id = append_endpoint(runtime, regime_index)
    endpoint_errors = trace_errors(
        validate_endpoint(runtime.store, endpoint_id)["payload"]["trace"],
        "active_output",
    )

    projection_sizes = {
        "compact_practice": len(runtime.store.serialize_projection([practice_id])),
        "contact": len(runtime.store.serialize_projection([contact_id])),
        "correction": len(runtime.store.serialize_projection([correction_id])),
        "directory": len(runtime.store.serialize_projection([runtime.directory_id])),
        "locator": len(
            runtime.store.serialize_projection(
                [validate_projection_request(runtime.store, request_id)["payload"]["locator_id"]]
            )
        ),
        "projection_request": len(runtime.store.serialize_projection([request_id])),
        "selected_branch": len(
            runtime.store.serialize_projection(
                [
                    validate_projection_request(runtime.store, request_id)["payload"]["proposal_id"],
                    validate_projection_request(runtime.store, request_id)["payload"]["trial_id"],
                ]
            )
        ),
    }
    return {
        "contact_id": contact_id,
        "correction_errors": pre_errors,
        "endpoint_errors": endpoint_errors,
        "outcome_ids": list(outcomes),
        "multi_outcome_rejected": multi_outcome_rejected,
        "practice_id": practice_id,
        "practice_rows": validate_practice(runtime.store, practice_id)["payload"]["rows"],
        "projection_sizes": projection_sizes,
        "receipt_id": receipt_id,
        "requested_action": requested_action,
        "request_id": request_id,
        "successor_id": successor_id,
        "successor_trial_errors": trial_errors,
    }


def evaluate_set_down_control(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    case_index: int,
    target_regime: int,
) -> int:
    runtime, _ = build_case_runtime(task, acceptance, case_index)
    for regime_index in range(target_regime):
        execute_reference_regime(repo, runtime, regime_index)
    result = execute_reference_regime(
        repo, runtime, target_regime, requested_action="set_down"
    )
    return result["endpoint_errors"]


def evaluate_prior_replay_control(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    case_index: int,
    target_regime: int,
) -> dict[str, int]:
    if target_regime not in {1, 2}:
        raise ValueError("prior replay exists only after a reversal")
    runtime, _ = build_case_runtime(task, acceptance, case_index)
    prior_practice = None
    for regime_index in range(target_regime):
        result = execute_reference_regime(repo, runtime, regime_index)
        prior_practice = result["practice_id"]
    assert prior_practice is not None
    contact_id = append_contact(runtime, target_regime)
    request_id = append_projection_request(
        repo, runtime, contact_id, prior_practice
    )
    successor_id, trial_id = append_successor(
        repo, runtime, contact_id, request_id, target_regime
    )
    trial_errors = trace_errors(
        validate_trial(runtime.store, trial_id)["payload"]["trace"],
        "proposal_output",
    )
    decision_id = append_decision(
        repo,
        runtime,
        action="adopt",
        decision_occurrence=target_regime,
        selected_id=successor_id,
        trial_id=trial_id,
    )
    runtime.controller.apply(decision_id)
    endpoint_id = append_endpoint(runtime, target_regime)
    endpoint_errors = trace_errors(
        validate_endpoint(runtime.store, endpoint_id)["payload"]["trace"],
        "active_output",
    )
    return {"endpoint_errors": endpoint_errors, "trial_errors": trial_errors}


def evaluate_case(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    case_index: int,
    *,
    include_independent_controls: bool = False,
    reverse_diagnostics: bool = False,
    source_order: tuple[int, int, int] = (0, 1, 2),
) -> dict[str, Any]:
    runtime, source_digest = build_case_runtime(
        task, acceptance, case_index, source_order=source_order
    )
    regimes = []
    for regime_index in REGIME_INDICES:
        result = execute_reference_regime(
            repo,
            runtime,
            regime_index,
            reverse_diagnostics=reverse_diagnostics,
        )
        regimes.append(result)
    row_changes = [
        sum(left != right for left, right in zip(regimes[index - 1]["practice_rows"], regimes[index]["practice_rows"], strict=True))
        for index in (1, 2)
    ]
    full_bytes = len(runtime.store.serialize_full())
    set_down_errors = None
    prior_replay = None
    if include_independent_controls:
        set_down_errors = [
            evaluate_set_down_control(
                repo, task, acceptance, case_index, regime_index
            )
            for regime_index in REGIME_INDICES
        ]
        prior_replay = [
            evaluate_prior_replay_control(
                repo, task, acceptance, case_index, regime_index
            )
            for regime_index in (1, 2)
        ]
    summary = {
        "case_index": case_index,
        "correction_errors": [item["correction_errors"] for item in regimes],
        "endpoint_errors": [item["endpoint_errors"] for item in regimes],
        "full_trajectory_bytes": full_bytes,
        "practice_row_changes": row_changes,
        "projection_maximum_bytes": max(
            size for item in regimes for size in item["projection_sizes"].values()
        ),
        "source_bundle_sha256": source_digest,
        "successor_trial_errors": [item["successor_trial_errors"] for item in regimes],
    }
    if prior_replay is not None and set_down_errors is not None:
        summary.update(
            {
                "prior_replay_endpoint_errors": [
                    item["endpoint_errors"] for item in prior_replay
                ],
                "prior_replay_trial_errors": [
                    item["trial_errors"] for item in prior_replay
                ],
                "set_down_endpoint_errors": set_down_errors,
            }
        )
    summary["pass"] = (
        summary["correction_errors"] == [2, 2, 2]
        and summary["endpoint_errors"] == [0, 0, 0]
        and summary["successor_trial_errors"] == [0, 0, 0]
        and summary["practice_row_changes"] == [3, 3]
        and summary["projection_maximum_bytes"] <= PROJECTION_BYTES
        and all(item["multi_outcome_rejected"] for item in regimes)
        and full_bytes >= FULL_TRAJECTORY_MINIMUM
    )
    if include_independent_controls:
        summary["pass"] = (
            summary["pass"]
            and summary["set_down_endpoint_errors"] == [4, 4, 4]
            and summary["prior_replay_trial_errors"] == [2, 2]
            and summary["prior_replay_endpoint_errors"] == [4, 4]
        )
    body = {**summary, "record_ids_sha256": sha256_bytes(canonical_json(runtime.store.record_ids))}
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def _rank_assignment(acceptance: dict[str, Any], case_index: int) -> list[int]:
    return acceptance["address_world"][
        "address_rank_assignment_by_case_modulo_eight"
    ][case_index % 8]


def correct_semantic_branch(
    acceptance: dict[str, Any], case_index: int, regime_index: int
) -> int:
    schedule = acceptance["address_world"]["case_regime_permutation_indices"][
        case_index
    ]
    permutation = acceptance["address_world"]["semantic_permutations"][
        schedule[regime_index]
    ]
    return permutation[acceptance["address_world"]["heldout_query_semantic_index"]]


def correct_directory_rank(
    acceptance: dict[str, Any], case_index: int, regime_index: int
) -> int:
    return _rank_assignment(acceptance, case_index)[
        correct_semantic_branch(acceptance, case_index, regime_index)
    ]


def semantic_branch_at_rank(
    acceptance: dict[str, Any], case_index: int, selected_rank: int
) -> int:
    try:
        return _rank_assignment(acceptance, case_index).index(selected_rank)
    except ValueError as error:
        raise ProtocolError("selected directory rank is unavailable") from error


def _policy_identity(family: str, parameters: Any, policy_name: str) -> str:
    return sha256_bytes(
        canonical_json(
            {
                "family": family,
                "parameters": parameters,
                "policy_name": policy_name,
            }
        )
    )


def _score_rank_schedule(
    acceptance: dict[str, Any], choices: list[list[int]]
) -> tuple[int, int]:
    wrong = 0
    failed_cases = 0
    for case_index in CASE_INDICES:
        case_wrong = sum(
            choices[case_index][regime_index]
            != correct_directory_rank(acceptance, case_index, regime_index)
            for regime_index in REGIME_INDICES
        )
        wrong += case_wrong
        failed_cases += case_wrong > 0
    return failed_cases, wrong


def pure_control_calibration(
    task: dict[str, Any], acceptance: dict[str, Any]
) -> dict[str, Any]:
    """Exhaustively score frozen policies without redundant process spawning."""

    validate_task(task)
    stationary_rows = []
    stationary_case_minimum = 3
    stationary_permutation_ids = []
    for table in itertools.product(range(3), repeat=3):
        choices = []
        per_case_wrong = []
        for case_index in CASE_INDICES:
            query_key = task["cases"][case_index][
                "query_keys_by_semantic_query"
            ][acceptance["address_world"]["heldout_query_semantic_index"]]
            query_rank = sorted(
                task["cases"][case_index]["query_keys_by_semantic_query"]
            ).index(query_key)
            selected = table[query_rank]
            case_choices = [selected, selected, selected]
            choices.append(case_choices)
            per_case_wrong.append(
                sum(
                    selected
                    != correct_directory_rank(acceptance, case_index, regime)
                    for regime in REGIME_INDICES
                )
            )
        failed, wrong = _score_rank_schedule(acceptance, choices)
        stationary_case_minimum = min(stationary_case_minimum, min(per_case_wrong))
        policy_id = _policy_identity(
            "stationary-practice-table", list(table), f"stationary.{''.join(map(str, table))}"
        )
        stationary_rows.append([policy_id, failed, wrong])
        if len(set(table)) == 3:
            stationary_permutation_ids.append(policy_id)

    clock_rows = []
    for clock in itertools.product(range(3), repeat=3):
        choices = [list(clock) for _ in CASE_INDICES]
        failed, wrong = _score_rank_schedule(acceptance, choices)
        clock_rows.append(
            [
                _policy_identity(
                    "fixed-clock", list(clock), f"clock.{''.join(map(str, clock))}"
                ),
                failed,
                wrong,
            ]
        )

    one_step_rows = []
    histogram: dict[str, int] = {}
    for initial in range(3):
        for table in itertools.product(range(3), repeat=6):
            choices = []
            for case_index in CASE_INDICES:
                selected = initial
                active_branch = semantic_branch_at_rank(
                    acceptance, case_index, selected
                )
                case_choices = [selected]
                for regime_index in (1, 2):
                    all_match = (
                        active_branch
                        == correct_semantic_branch(
                            acceptance, case_index, regime_index
                        )
                    )
                    selected = table[selected * 2 + int(all_match)]
                    active_branch = semantic_branch_at_rank(
                        acceptance, case_index, selected
                    )
                    case_choices.append(selected)
                choices.append(case_choices)
            failed, wrong = _score_rank_schedule(acceptance, choices)
            parameters = {"initial": initial, "transition_table": list(table)}
            policy_id = _policy_identity(
                "one-step-consequence",
                parameters,
                f"one-step.{initial}.{''.join(map(str, table))}",
            )
            one_step_rows.append([policy_id, failed, wrong])
            key = f"{failed}:{wrong}"
            histogram[key] = histogram.get(key, 0) + 1

    all_rows = sorted(stationary_rows + clock_rows + one_step_rows)
    best_score = min((row[2], row[2] * 4, row[0]) for row in all_rows)
    tied = sorted(
        row[0]
        for row in all_rows
        if (row[2], row[2] * 4) == best_score[:2]
    )
    result = {
        "best_control": {
            "endpoint_errors": best_score[1],
            "failed_regimes": best_score[0],
            "policy_id": best_score[2],
            "tie_count": len(tied),
            "tied_policy_ids": tied[:16],
        },
        "complete_table_sha256": sha256_bytes(canonical_json(all_rows)),
        "fixed_clock_count": len(clock_rows),
        "fixed_clock_minimum_wrong": min(row[2] for row in clock_rows),
        "one_step_count": len(one_step_rows),
        "one_step_histogram": dict(sorted(histogram.items())),
        "one_step_minimum_failed_cases": min(row[1] for row in one_step_rows),
        "one_step_minimum_wrong": min(row[2] for row in one_step_rows),
        "stationary_case_minimum_wrong_regimes": stationary_case_minimum,
        "stationary_permutation_count": len(stationary_permutation_ids),
        "stationary_table_count": len(stationary_rows),
    }
    result["pass"] = (
        result["stationary_table_count"] == 27
        and result["stationary_permutation_count"] == 6
        and result["stationary_case_minimum_wrong_regimes"] >= 2
        and result["fixed_clock_count"] == 27
        and result["fixed_clock_minimum_wrong"] >= 30
        and result["one_step_count"] == 2187
        and result["one_step_minimum_failed_cases"] >= 13
        and result["one_step_minimum_wrong"] >= 20
    )
    body = {key: result[key] for key in sorted(result) if key != "receipt_sha256"}
    return {**result, "receipt_sha256": sha256_bytes(canonical_json(body))}


def append_control_practice(
    runtime: CaseRuntime,
    contact_id: str,
    reference_receipt_id: str,
    reference_practice_id: str,
    selected_rank: int,
) -> str:
    """Append one evaluator-named actor fixture for a frozen control policy."""

    if selected_rank not in range(3):
        raise ValueError("control directory rank is unavailable")
    heldout = heldout_query_from_practice(
        runtime.store, reference_practice_id, contact_id
    )
    directory = validate_directory(runtime.store, runtime.directory_id)
    selected_handle = directory["payload"]["entries"][selected_rank][
        "address_handle"
    ]
    reference_practice = validate_practice(
        runtime.store, reference_practice_id
    )
    reference_rows = reference_practice["payload"]["rows"]
    current = next(
        row["address_handle"]
        for row in reference_rows
        if row["query_key"] == heldout
    )
    if current == selected_handle:
        return reference_practice_id
    rows = [dict(row) for row in reference_rows]
    for row in rows:
        if row["query_key"] == heldout:
            row["address_handle"] = selected_handle
    receipt = validate_practice_receipt(runtime.store, reference_receipt_id)
    receipt_payload = json.loads(json.dumps(receipt["payload"]))
    receipt_payload["rows"] = rows
    control_receipt_id = runtime.store.append(
        runtime.actor_capability,
        receipt_payload,
        receipt["parents"],
    )
    validate_practice_receipt(runtime.store, control_receipt_id)
    control_payload = {
        "case_token": runtime.case["case_token"],
        "practice_receipt_id": control_receipt_id,
        "record": "practice",
        "rows": rows,
        "schema_version": 1,
    }
    control_practice_id = runtime.store.append(
        runtime.actor_capability, control_payload, [control_receipt_id]
    )
    validate_practice(runtime.store, control_practice_id)
    return control_practice_id


def clone_case_runtime(runtime: CaseRuntime) -> CaseRuntime:
    """Fork immutable trajectory bytes into fresh store-local authorities."""

    store, actor, world, controller_capability = bootstrap_trajectory_store(
        max_record_bytes=MAX_RECORD_BYTES
    )
    capabilities = {
        ACTOR_SOURCE: actor,
        WORLD_SOURCE: world,
        CONTROLLER_SOURCE: controller_capability,
    }
    pending = {
        record_id: runtime.store.get(record_id)
        for record_id in runtime.store.record_ids
    }
    appended: set[str] = set()
    while pending:
        progressed = False
        for record_id, record in list(pending.items()):
            if not set(record["parents"]) <= appended:
                continue
            observed = store.append(
                capabilities[record["source"]],
                record["payload"],
                record["parents"],
            )
            if observed != record_id:
                raise ProtocolError("trajectory fork changed content identity")
            appended.add(record_id)
            del pending[record_id]
            progressed = True
        if not progressed:
            raise ProtocolError("trajectory fork encountered cyclic ancestry")
    return CaseRuntime(
        store=store,
        actor_capability=actor,
        world_capability=world,
        controller_capability=controller_capability,
        controller=PointerController(store, controller_capability),
        implementation_commit=runtime.implementation_commit,
        acceptance=runtime.acceptance,
        case_index=runtime.case_index,
        case=runtime.case,
        genesis_id=runtime.genesis_id,
        directory_id=runtime.directory_id,
        sources=runtime.sources,
        schedule=runtime.schedule,
    )


def build_selected_rank_prefix(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    case_index: int,
    regime_index: int,
) -> tuple[CaseRuntime, str, str, str]:
    runtime, _ = build_case_runtime(task, acceptance, case_index)
    contact_id = append_contact(runtime, regime_index)
    correction_id = append_correction(runtime, contact_id, regime_index)
    outcomes = append_diagnostics(
        repo, runtime, contact_id, correction_id, regime_index
    )
    reference_receipt, reference_practice = append_practice(
        repo, runtime, contact_id, correction_id, outcomes
    )
    return runtime, contact_id, reference_receipt, reference_practice


def evaluate_selected_rank_from_prefix(
    repo: Path,
    runtime: CaseRuntime,
    contact_id: str,
    reference_receipt: str,
    reference_practice: str,
    regime_index: int,
    selected_rank: int,
    *,
    action: str,
    exercise_rollback: bool,
) -> dict[str, Any]:
    acceptance = runtime.acceptance
    case_index = runtime.case_index
    selected_practice = append_control_practice(
        runtime,
        contact_id,
        reference_receipt,
        reference_practice,
        selected_rank,
    )
    request_id = append_projection_request(
        repo, runtime, contact_id, selected_practice
    )
    successor_id, trial_id = append_successor(
        repo, runtime, contact_id, request_id, regime_index
    )
    trial_errors = trace_errors(
        validate_trial(runtime.store, trial_id)["payload"]["trace"],
        "proposal_output",
    )
    decision_id = append_decision(
        repo,
        runtime,
        action=action,
        decision_occurrence=0,
        selected_id=successor_id,
        trial_id=trial_id,
    )
    runtime.controller.apply(decision_id)
    endpoint_id = append_endpoint(runtime, regime_index)
    endpoint_errors = trace_errors(
        validate_endpoint(runtime.store, endpoint_id)["payload"]["trace"],
        "active_output",
    )
    rollback_restored = None
    if exercise_rollback and action == "adopt":
        rollback_id = append_decision(
            repo,
            runtime,
            action="rollback",
            decision_occurrence=1,
            rollback_target_id=runtime.genesis_id,
        )
        runtime.controller.apply(rollback_id)
        rollback_restored = (
            runtime.controller.replay().current.active_id == runtime.genesis_id
        )
    correct = selected_rank == correct_directory_rank(
        acceptance, case_index, regime_index
    )
    expected_trial = 0 if correct else 2
    expected_endpoint = 4 if action == "set_down" or not correct else 0
    return {
        "action": action,
        "case_index": case_index,
        "endpoint_errors": endpoint_errors,
        "expected_endpoint_errors": expected_endpoint,
        "expected_trial_errors": expected_trial,
        "pass": trial_errors == expected_trial
        and endpoint_errors == expected_endpoint
        and (rollback_restored is not False),
        "regime_index": regime_index,
        "rollback_restored": rollback_restored,
        "selected_rank": selected_rank,
        "trial_errors": trial_errors,
    }


def evaluate_selected_rank_path(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    case_index: int,
    regime_index: int,
    selected_rank: int,
    *,
    action: str = "adopt",
    exercise_rollback: bool = False,
) -> dict[str, Any]:
    """Carry one frozen rank through the actual successor/action/endpoint path."""

    if action not in {"adopt", "set_down"}:
        raise ValueError("selected-rank action is unavailable")
    runtime, contact_id, reference_receipt, reference_practice = (
        build_selected_rank_prefix(
            repo, task, acceptance, case_index, regime_index
        )
    )
    return evaluate_selected_rank_from_prefix(
        repo,
        runtime,
        contact_id,
        reference_receipt,
        reference_practice,
        regime_index,
        selected_rank,
        action=action,
        exercise_rollback=exercise_rollback,
    )


def causal_equivalence_grid(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Run every selected rank plus action-specific set-down and rollback."""

    rows = []
    set_down_rows = []
    for case_index in CASE_INDICES:
        for regime_index in REGIME_INDICES:
            prefix = build_selected_rank_prefix(
                repo, task, acceptance, case_index, regime_index
            )
            for selected_rank in range(3):
                if deadline is not None and time.monotonic() >= deadline:
                    raise ProtocolError("causal equivalence grid exceeded wall budget")
                runtime = clone_case_runtime(prefix[0])
                rows.append(
                    evaluate_selected_rank_from_prefix(
                        repo,
                        runtime,
                        prefix[1],
                        prefix[2],
                        prefix[3],
                        regime_index,
                        selected_rank,
                        action="adopt",
                        exercise_rollback=True,
                    )
                )
            correct_rank = correct_directory_rank(
                acceptance, case_index, regime_index
            )
            runtime = clone_case_runtime(prefix[0])
            set_down_rows.append(
                evaluate_selected_rank_from_prefix(
                    repo,
                    runtime,
                    prefix[1],
                    prefix[2],
                    prefix[3],
                    regime_index,
                    correct_rank,
                    action="set_down",
                    exercise_rollback=False,
                )
            )
    normalized = [
        {
            key: row[key]
            for key in (
                "action",
                "case_index",
                "endpoint_errors",
                "expected_endpoint_errors",
                "expected_trial_errors",
                "pass",
                "regime_index",
                "rollback_restored",
                "selected_rank",
                "trial_errors",
            )
        }
        for row in rows + set_down_rows
    ]
    result = {
        "adopt_path_count": len(rows),
        "all_pure_causal_scores_match": all(row["pass"] for row in rows),
        "all_rollbacks_restore_genesis": all(
            row["rollback_restored"] for row in rows
        ),
        "normalized_sha256": sha256_bytes(canonical_json(normalized)),
        "set_down_path_count": len(set_down_rows),
        "set_down_scores_match": all(row["pass"] for row in set_down_rows),
    }
    result["pass"] = (
        result["adopt_path_count"] == 16 * 3 * 3
        and result["set_down_path_count"] == 16 * 3
        and result["all_pure_causal_scores_match"]
        and result["all_rollbacks_restore_genesis"]
        and result["set_down_scores_match"]
    )
    return result


def decisive_intervention_calibration(
    repo: Path, task: dict[str, Any], acceptance: dict[str, Any]
) -> dict[str, Any]:
    """Exercise representative failure seams without quality-based rescue."""

    runtime, _ = build_case_runtime(task, acceptance, 0)
    result = execute_reference_regime(repo, runtime, 0)
    contact_id = result["contact_id"]
    correction_id = next(
        parent
        for parent in validate_practice_receipt(runtime.store, result["receipt_id"])["parents"]
        if runtime.store.get(parent)["payload"].get("record")
        == "correction_consequence"
    )
    outcome_ids = tuple(result["outcome_ids"])

    def rejects(operation: Any) -> bool:
        try:
            operation()
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return True
        return False

    contact_projection = runtime.store.project([contact_id])
    correction_projection = runtime.store.project([correction_id])
    directory_projection = runtime.store.project([runtime.directory_id])
    outcome_projections = [runtime.store.project([item]) for item in outcome_ids]
    first_query = validate_outcome(runtime.store, outcome_ids[0])["payload"]["query_key"]
    one_query_missing = [
        projection
        for projection, outcome_id in zip(outcome_projections, outcome_ids, strict=True)
        if validate_outcome(runtime.store, outcome_id)["payload"]["query_key"]
        != first_query
    ]

    verdicts: dict[str, bool] = {}
    verdicts["withhold_complete_diagnostic_batch"] = rejects(
        lambda: run_reset_worker(
            repo,
            "practice_fit",
            {
                "contact": contact_projection,
                "correction_consequence": correction_projection,
                "directory": directory_projection,
                "outcomes": outcome_projections[:-1],
                "previous_practice": None,
            },
            envelope_limit=24_576,
        )
    )
    verdicts["withhold_one_diagnostic_query"] = rejects(
        lambda: run_reset_worker(
            repo,
            "practice_fit",
            {
                "contact": contact_projection,
                "correction_consequence": correction_projection,
                "directory": directory_projection,
                "outcomes": one_query_missing,
                "previous_practice": None,
            },
            envelope_limit=24_576,
        )
    )
    verdicts["withhold_compact_practice"] = rejects(
        lambda: run_reset_worker(
            repo,
            "practice_execute",
            {
                "contact": contact_projection,
                "directory": directory_projection,
                "heldout_query_key": runtime.case["query_keys_by_semantic_query"][2],
            },
        )
    )
    verdicts["full_receipt_as_application"] = rejects(
        lambda: append_projection_request(
            repo, runtime, contact_id, result["receipt_id"]
        )
    )
    verdicts["stale_contact"] = rejects(
        lambda: validate_contact(runtime.store, contact_id, require_current=True)
    )
    verdicts["stale_projection_request"] = rejects(
        lambda: validate_projection_request(
            runtime.store, result["request_id"], require_current=True
        )
    )

    practice = validate_practice(runtime.store, result["practice_id"])
    for label, mutate in (
        ("delete_practice_row", lambda rows: rows.pop()),
        (
            "duplicate_practice_query",
            lambda rows: rows.__setitem__(1, dict(rows[0])),
        ),
        (
            "swap_practice_outputs",
            lambda rows: (
                rows[0].__setitem__("address_handle", rows[1]["address_handle"]),
                rows[1].__setitem__("address_handle", rows[0]["address_handle"]),
            ),
        ),
    ):
        def malformed_practice(mutate: Any = mutate) -> None:
            payload = json.loads(json.dumps(practice["payload"]))
            mutate(payload["rows"])
            record_id = runtime.store.append(
                runtime.actor_capability, payload, practice["parents"]
            )
            validate_practice(runtime.store, record_id)

        verdicts[label] = rejects(malformed_practice)

    locator_id = runtime.sources[0]["locator_id"]
    locator = validate_locator(runtime.store, locator_id)

    def opaque_locator_placebo() -> None:
        payload = json.loads(json.dumps(locator["payload"]))
        payload["body"] = {"record": payload["body"]["record"], "record_id": "0" * 64}
        record_id = runtime.store.append(
            runtime.actor_capability, payload, locator["parents"]
        )
        validate_locator(runtime.store, record_id)

    verdicts["opaque_locator_placebo"] = rejects(opaque_locator_placebo)
    verdicts["forged_source"] = rejects(
        lambda: runtime.store.append(
            object(), {"record": "forged", "schema_version": 1}, []
        )
    )
    verdicts["inactive_source_rollback"] = rejects(
        lambda: runtime.controller.apply(
            append_decision(
                repo,
                runtime,
                action="rollback",
                decision_occurrence=77,
                rollback_target_id=runtime.sources[0]["proposal_id"],
            )
        )
    )
    verdicts["wrong_expected_pointer"] = rejects(
        lambda: runtime.controller.apply(
            runtime.store.append(
                runtime.actor_capability,
                {
                    **validate_decision(
                        runtime.store,
                        append_decision(
                            repo,
                            runtime,
                            action="set_down",
                            decision_occurrence=78,
                            selected_id=result["successor_id"],
                            trial_id=next(
                                record_id
                                for record_id in runtime.store.record_ids
                                if runtime.store.get(record_id)["payload"].get("record") == "trial"
                                and runtime.store.get(record_id)["payload"].get("proposal_id") == result["successor_id"]
                            ),
                        ),
                    )["payload"],
                    "expected_pointer_event_id": runtime.sources[0]["proposal_id"],
                },
                [],
            )
        )
    )
    result_body = {
        "verdicts": dict(sorted(verdicts.items())),
        "rejection_count": sum(verdicts.values()),
    }
    result_body["pass"] = all(verdicts.values()) and len(verdicts) == 13
    result_body["sha256"] = sha256_bytes(canonical_json(result_body))
    return result_body


def fixed_input_paths(repo: Path | None = None) -> dict[str, Path]:
    """Return every named runtime authority additionally bound by L."""

    repo = (repo or Path.cwd()).resolve()
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "experiment_record_sha256": EXPERIMENT_PATH,
        "target_sha256": Path("TARGET.md"),
        "red_lines_sha256": Path("RED_LINES.md"),
        "program_sha256": Path("PROGRAM.md"),
        "evidence_contract_sha256": Path("docs/EVIDENCE.md"),
        "workflow_contract_sha256": Path("docs/WORKFLOW.md"),
        "evaluation_epoch_sha256": Path("docs/TRAJECTORY_PROJECTION_EPOCH.md"),
        "predecessor_manifest_sha256": Path(
            "evidence/manifests/OT-0070/"
            "ot-0070-trajectory-authority-calibration-001.json"
        ),
        "trajectory_core_sha256": Path("src/open_trajectory_harness/trajectory.py"),
        "harness_sha256": Path("src/open_trajectory_harness/ot0071.py"),
        "reset_worker_sha256": Path(
            "src/open_trajectory_harness/ot0071_reset_worker.py"
        ),
        "canonical_helper_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_helper_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
    }
    for test_path in sorted((repo / "tests").glob("test_*.py")):
        relative = test_path.relative_to(repo)
        key = "test_" + relative.as_posix().replace("/", "_").replace(".", "_")
        paths[f"{key}_sha256"] = relative
    return paths


def _validate_acceptance(repo: Path, acceptance: dict[str, Any]) -> None:
    if sha256_file(repo / ACCEPTANCE_PATH) != ACCEPTANCE_SHA256:
        raise ProtocolError("acceptance bytes differ from the frozen identity")
    if (
        acceptance.get("schema_version") != 1
        or acceptance.get("experiment_id") != EXPERIMENT_ID
        or acceptance.get("scenario_indices") != list(CASE_INDICES)
        or acceptance.get("run_order")
        != ["forward-1", "reverse-1", "forward-2", "reverse-2"]
        or acceptance.get("candidate_outputs") is not False
        or acceptance.get("hosted_model_calls") != 0
    ):
        raise ProtocolError("acceptance identity or candidate-free authority differs")


def _logical_evidence_path(path: Path) -> str:
    return "$EVIDENCE/" + path.as_posix()


def _write_tracked_json_once(path: Path, value: dict[str, Any]) -> None:
    """Write canonical tracked lock bytes exclusively, without sealing mode bits."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(canonical_json(value))
    except FileExistsError as error:
        raise RuntimeError(f"tracked output already exists: {path.name}") from error


def expected_task_path(repo: Path) -> Path:
    return (default_store(repo.resolve()) / TASK_RELATIVE_PATH).resolve()


def expected_derivation_path(repo: Path) -> Path:
    return (default_store(repo.resolve()) / DERIVATION_RELATIVE_PATH).resolve()


def expected_output_path(repo: Path) -> Path:
    return (
        default_store(repo.resolve())
        / "runs"
        / EXPERIMENT_ID
        / f"{DEFAULT_RUN_ID}.json"
    ).resolve()


def expected_manifest_path(repo: Path) -> Path:
    return (
        repo.resolve()
        / "evidence"
        / "manifests"
        / EXPERIMENT_ID
        / f"{DEFAULT_RUN_ID}.json"
    )


def build_derivation_receipt(
    implementation_commit: str, task_bytes: bytes
) -> dict[str, Any]:
    _commit(implementation_commit)
    task = json.loads(task_bytes)
    if canonical_json(task) != task_bytes:
        raise ProtocolError("derived task bytes are not canonical")
    validate_task(task)
    if task["implementation_commit"] != implementation_commit:
        raise ProtocolError("derived task is not bound to implementation")
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "derivation_id": DERIVATION_ID,
        "implementation_git_commit": implementation_commit,
        "task_path": _logical_evidence_path(TASK_RELATIVE_PATH),
        "task_sha256": sha256_bytes(task_bytes),
        "task_bytes": len(task_bytes),
        "attempt": 1,
        "authoritative": True,
    }


def validate_derivation(
    repo: Path, implementation_commit: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    task, task_bytes = read_sealed_json(expected_task_path(repo))
    receipt, receipt_bytes = read_sealed_json(expected_derivation_path(repo))
    expected = build_derivation_receipt(implementation_commit, task_bytes)
    if receipt != expected or receipt_bytes != canonical_json(expected):
        raise ProtocolError("derivation receipt differs from exact task bytes")
    return task, receipt


def build_run_lock(
    repo: Path,
    implementation_commit: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    fixed = {
        name: sha256_file(repo / path)
        for name, path in fixed_input_paths(repo).items()
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "protocol_origin_git_commit": PROTOCOL_ORIGIN_COMMIT,
        "implementation_git_commit": implementation_commit,
        "implementation_git_tree": git_output(
            repo, "rev-parse", f"{implementation_commit}^{{tree}}"
        ),
        "derivation_id": DERIVATION_ID,
        "derivation_receipt_path": _logical_evidence_path(DERIVATION_RELATIVE_PATH),
        "derivation_receipt_sha256": sha256_bytes(canonical_json(receipt)),
        "task_path": _logical_evidence_path(TASK_RELATIVE_PATH),
        "task_sha256": receipt["task_sha256"],
        "run_id": DEFAULT_RUN_ID,
        "raw_output_path": _logical_evidence_path(
            Path("runs") / EXPERIMENT_ID / f"{DEFAULT_RUN_ID}.json"
        ),
        "public_manifest_path": (
            f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
        ),
        "reconstruction_recipe": RECONSTRUCTION_RECIPE,
        "predecessor_manifest_sha256": fixed["predecessor_manifest_sha256"],
        "fixed_inputs": fixed,
    }


def _assert_protocol_unchanged(repo: Path, commit: str) -> None:
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{PROTOCOL_ORIGIN_COMMIT}..{commit}",
        "--",
        *(path.as_posix() for path in PROTOCOL_FROZEN_PATHS),
    )
    if changed:
        raise RuntimeError(f"OT-0071 frozen protocol changed after P: {changed}")


def prepare_authoritative(repo: Path) -> tuple[Path, Path, Path]:
    """Perform the single I-bound task derivation and write prospective L."""

    repo = repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0071 preparation requires clean HEAD exactly I")
    implementation = git_output(repo, "rev-parse", "HEAD")
    _commit(implementation)
    _assert_protocol_unchanged(repo, implementation)
    if (repo / RUN_LOCK_PATH).exists():
        raise RuntimeError("OT-0071 run lock already exists")
    task_path = expected_task_path(repo)
    receipt_path = expected_derivation_path(repo)
    output_path = expected_output_path(repo)
    manifest_path = expected_manifest_path(repo)
    failure_root = default_store(repo) / "failures" / EXPERIMENT_ID
    if any(
        path.exists()
        for path in (
            task_path,
            receipt_path,
            output_path,
            manifest_path,
            failure_root / f"{DEFAULT_RUN_ID}-manifest.json",
            failure_root / f"{DEFAULT_RUN_ID}-post-audit.json",
        )
    ):
        raise RuntimeError("OT-0071 preparation collided with prior authority")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    _validate_acceptance(repo, acceptance)
    task = build_task(implementation)
    task_bytes = canonical_json(task)
    receipt = build_derivation_receipt(implementation, task_bytes)
    lock = build_run_lock(repo, implementation, receipt)
    write_sealed_json(task_path, task)
    write_sealed_json(receipt_path, receipt)
    _write_tracked_json_once(repo / RUN_LOCK_PATH, lock)
    return task_path, receipt_path, repo / RUN_LOCK_PATH


def validate_run_lock(
    repo: Path, execution_commit: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    lock = load_json(repo / RUN_LOCK_PATH)
    required = {
        "schema_version",
        "experiment_id",
        "protocol_origin_git_commit",
        "implementation_git_commit",
        "implementation_git_tree",
        "derivation_id",
        "derivation_receipt_path",
        "derivation_receipt_sha256",
        "task_path",
        "task_sha256",
        "run_id",
        "raw_output_path",
        "public_manifest_path",
        "reconstruction_recipe",
        "predecessor_manifest_sha256",
        "fixed_inputs",
    }
    _exact(lock, required, "run lock")
    if (
        lock["schema_version"] != 1
        or lock["experiment_id"] != EXPERIMENT_ID
        or lock["protocol_origin_git_commit"] != PROTOCOL_ORIGIN_COMMIT
        or lock["derivation_id"] != DERIVATION_ID
        or lock["run_id"] != DEFAULT_RUN_ID
        or lock["reconstruction_recipe"] != RECONSTRUCTION_RECIPE
    ):
        raise ProtocolError("run lock fixed identity differs")
    implementation = _commit(lock["implementation_git_commit"])
    assert implementation is not None
    if git_output(repo, "rev-parse", f"{execution_commit}^") != implementation:
        raise ProtocolError("L is not the direct child of I")
    if git_output(repo, "rev-parse", f"{implementation}^{{tree}}") != lock[
        "implementation_git_tree"
    ]:
        raise ProtocolError("implementation tree differs from run lock")
    if git_output(repo, "diff", "--name-status", f"{implementation}..{execution_commit}") != (
        f"A\t{RUN_LOCK_PATH.as_posix()}"
    ):
        raise ProtocolError("L differs from I by more than the one run lock")
    _assert_protocol_unchanged(repo, execution_commit)
    observed = {
        name: sha256_file(repo / path)
        for name, path in fixed_input_paths(repo).items()
    }
    if observed != lock["fixed_inputs"]:
        raise ProtocolError("fixed runtime identities differ from run lock")
    task, receipt = validate_derivation(repo, implementation)
    if (
        lock["task_sha256"] != receipt["task_sha256"]
        or lock["derivation_receipt_sha256"]
        != sha256_bytes(canonical_json(receipt))
        or lock["predecessor_manifest_sha256"]
        != observed["predecessor_manifest_sha256"]
    ):
        raise ProtocolError("run lock derivation binding differs")
    return lock, task


def _case_verdict(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result[key]
        for key in (
            "case_index",
            "correction_errors",
            "endpoint_errors",
            "pass",
            "practice_row_changes",
            "successor_trial_errors",
        )
    }


def run_calibration(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Run the frozen four traversals and complete causal controls."""

    repo = repo.resolve()
    validate_task(task)
    _validate_acceptance(repo, acceptance)
    if deadline is None:
        deadline = time.monotonic() + WALL_SECONDS
    runs = []
    for label in acceptance["run_order"]:
        reverse = label.startswith("reverse")
        order = (
            acceptance["reverse_case_order"]
            if reverse
            else acceptance["forward_case_order"]
        )
        verdicts = []
        receipts = []
        for case_index in order:
            if time.monotonic() >= deadline:
                raise ProtocolError("reference traversal exceeded wall budget")
            result = evaluate_case(
                repo,
                task,
                acceptance,
                case_index,
                reverse_diagnostics=reverse,
                source_order=(2, 1, 0) if reverse else (0, 1, 2),
            )
            verdicts.append(_case_verdict(result))
            receipts.append([case_index, result["receipt_sha256"]])
        normalized = sorted(verdicts, key=lambda row: row["case_index"])
        runs.append(
            {
                "run": label,
                "case_order": list(order),
                "passing_case_count": sum(row["pass"] for row in verdicts),
                "normalized_sha256": sha256_bytes(canonical_json(normalized)),
                "case_receipts_sha256": sha256_bytes(
                    canonical_json(sorted(receipts))
                ),
            }
        )

    pure_controls = pure_control_calibration(task, acceptance)
    interventions = decisive_intervention_calibration(repo, task, acceptance)
    causal_controls = causal_equivalence_grid(
        repo, task, acceptance, deadline=deadline
    )
    set_down = []
    prior_replay = []
    for case_index in CASE_INDICES:
        for regime_index in REGIME_INDICES:
            if time.monotonic() >= deadline:
                raise ProtocolError("independent controls exceeded wall budget")
            set_down.append(
                evaluate_set_down_control(
                    repo, task, acceptance, case_index, regime_index
                )
            )
        for regime_index in (1, 2):
            prior_replay.append(
                evaluate_prior_replay_control(
                    repo, task, acceptance, case_index, regime_index
                )
            )

    alpha_commit = sha256_bytes(
        canonical_json(
            {
                "domain": "ot-0071-alpha-renaming",
                "implementation_commit": task["implementation_commit"],
            }
        )
    )[:40]
    alpha_task = build_task(alpha_commit)
    alpha_verdicts = []
    for case_index in CASE_INDICES:
        if time.monotonic() >= deadline:
            raise ProtocolError("alpha-renaming control exceeded wall budget")
        alpha_verdicts.append(
            _case_verdict(
                evaluate_case(
                    repo,
                    alpha_task,
                    acceptance,
                    case_index,
                    reverse_diagnostics=True,
                    source_order=(2, 1, 0),
                )
            )
        )
    alpha_digest = sha256_bytes(
        canonical_json(sorted(alpha_verdicts, key=lambda row: row["case_index"]))
    )
    normalized_digests = [run["normalized_sha256"] for run in runs]
    reference_digest = normalized_digests[0]
    gates = {
        "exact_run_order": [run["run"] for run in runs]
        == acceptance["run_order"],
        "all_cases_pass": all(run["passing_case_count"] == 16 for run in runs),
        "normalized_replay": len(set(normalized_digests)) == 1,
        "order_placebos": runs[0]["case_receipts_sha256"]
        == runs[1]["case_receipts_sha256"]
        == runs[2]["case_receipts_sha256"]
        == runs[3]["case_receipts_sha256"],
        "alpha_renaming": alpha_digest == reference_digest,
        "pure_controls": pure_controls["pass"],
        "decisive_interventions": interventions["pass"],
        "causal_equivalence": causal_controls["pass"],
        "set_down": set(set_down) == {4} and len(set_down) == 48,
        "prior_practice_replay": len(prior_replay) == 32
        and all(
            row == {"trial_errors": 2, "endpoint_errors": 4}
            for row in prior_replay
        ),
        "candidate_free": True,
        "actor_free": True,
        "hosted_free": True,
        "within_wall_budget": time.monotonic() <= deadline,
    }
    calibration_pass = all(gates.values())
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "run_order": acceptance["run_order"],
        "runs": runs,
        "pure_controls": pure_controls,
        "decisive_interventions": interventions,
        "causal_controls": causal_controls,
        "independent_controls": {
            "set_down_count": len(set_down),
            "set_down_sha256": sha256_bytes(canonical_json(set_down)),
            "prior_replay_count": len(prior_replay),
            "prior_replay_sha256": sha256_bytes(canonical_json(prior_replay)),
        },
        "alpha_verdict_sha256": alpha_digest,
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "gates": gates,
        "calibration_pass": calibration_pass,
        "disposition": "promoted" if calibration_pass else "rejected",
        "authorized_candidate_count": 1 if calibration_pass else 0,
    }


def _bounded_command(
    command: list[str], repo: Path, deadline: float, stage: str
) -> dict[str, Any]:
    remaining = deadline - time.monotonic()
    if stage not in {"tests", "audit"}:
        raise ValueError("verification stage is unavailable")
    if remaining <= 0:
        return {"status": f"{stage}_timeout", "returncode": None}
    try:
        process = subprocess.run(
            command,
            cwd=repo,
            env=child_environment(repo),
            capture_output=True,
            timeout=remaining,
        )
    except subprocess.TimeoutExpired:
        return {"status": f"{stage}_timeout", "returncode": None}
    return {
        "status": "passed" if process.returncode == 0 else f"{stage}_failed",
        "returncode": process.returncode,
    }


def build_raw_artifact(
    run_id: str,
    implementation_commit: str,
    execution_commit: str,
    summary: dict[str, Any],
    tests: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    if run_id != DEFAULT_RUN_ID:
        raise ProtocolError("run identity differs from frozen authority")
    for commit in (implementation_commit, execution_commit):
        _commit(commit)
    verification_pass = tests["status"] == audit["status"] == "passed"
    stable_summary = json.loads(canonical_json(summary))
    if not verification_pass:
        stable_summary["calibration_pass"] = False
        stable_summary["disposition"] = "invalidated"
        stable_summary["authorized_candidate_count"] = 0
    reconstructible = verification_pass and stable_summary.get("disposition") in {
        "promoted",
        "rejected",
    }
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": implementation_commit,
        "execution_git_commit": execution_commit,
        "evidence_class": "public-reconstructible" if reconstructible else "exploratory-only",
        "raw_artifact_bytes": 0,
        "summary": stable_summary,
        "verification": {"tests": tests, "audit": audit},
    }
    for _ in range(16):
        size = len(canonical_json(raw))
        if raw["raw_artifact_bytes"] == size:
            break
        raw["raw_artifact_bytes"] = size
    if raw["raw_artifact_bytes"] != len(canonical_json(raw)):
        raise RuntimeError("raw artifact size did not stabilize")
    if raw["raw_artifact_bytes"] > MAX_RAW_BYTES:
        raise RuntimeError("raw artifact exceeds frozen bound")
    return raw


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_output_contract(
    repo: Path, *, allow_existing_manifest: bool = False
) -> dict[str, Path]:
    repo = repo.resolve()
    store = default_store(repo).resolve()
    if _is_relative_to(store, repo) and not _is_relative_to(
        store, (repo / ".evidence").resolve()
    ):
        raise RuntimeError("in-repository evidence root must be ignored .evidence")
    output = expected_output_path(repo)
    manifest = expected_manifest_path(repo)
    failure_root = store / "failures" / EXPERIMENT_ID
    failed_manifest = failure_root / f"{DEFAULT_RUN_ID}-manifest.json"
    failure_receipt = failure_root / f"{DEFAULT_RUN_ID}-post-audit.json"
    if _is_relative_to(output, repo) and subprocess.run(
        ["git", "check-ignore", "-q", "--", str(output.relative_to(repo))],
        cwd=repo,
    ).returncode:
        raise RuntimeError("in-repository raw evidence path is not ignored")
    if output.exists():
        raise RuntimeError("raw output already exists")
    if manifest.exists() and not allow_existing_manifest:
        raise RuntimeError("public manifest already exists")
    if failed_manifest.exists() or failure_receipt.exists():
        raise RuntimeError("publication-failure authority already exists")
    return {
        "store": store,
        "output": output,
        "manifest": manifest,
        "failed_manifest": failed_manifest,
        "failure_receipt": failure_receipt,
    }


def _locked_context(
    repo: Path,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("execution requires clean HEAD exactly L")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock, task = validate_run_lock(repo, execution)
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    _validate_acceptance(repo, acceptance)
    return execution, lock, task, acceptance


def _execute_locked_raw(
    repo: Path,
    execution: str,
    lock: dict[str, Any],
    task: dict[str, Any],
    acceptance: dict[str, Any],
) -> tuple[dict[str, Any], float]:
    deadline = time.monotonic() + WALL_SECONDS
    try:
        summary = run_calibration(
            repo, task, acceptance, deadline=deadline
        )
    except (OSError, RuntimeError, ValueError):
        summary = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "claim_limit": acceptance["claim_limit"],
            "run_order": acceptance["run_order"],
            "runs": [],
            "candidate_outputs": False,
            "actor_turns": 0,
            "actor_tool_calls": 0,
            "hosted_model_calls": 0,
            "gates": {"calibration": False},
            "calibration_pass": False,
            "disposition": "invalidated",
            "authorized_candidate_count": 0,
            "operational_failure": "calibration_failed",
        }
    tests = _bounded_command(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        repo,
        deadline,
        "tests",
    )
    audit = _bounded_command(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        repo,
        deadline,
        "audit",
    )
    if time.monotonic() > deadline:
        summary["calibration_pass"] = False
        summary["disposition"] = "invalidated"
        summary["authorized_candidate_count"] = 0
        summary["operational_failure"] = "wall_timeout"
    raw = build_raw_artifact(
        DEFAULT_RUN_ID,
        lock["implementation_git_commit"],
        execution,
        summary,
        tests,
        audit,
    )
    return raw, deadline


def reconstruct(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    contract = validate_output_contract(repo, allow_existing_manifest=True)
    execution, lock, task, acceptance = _locked_context(repo)
    raw, _ = _execute_locked_raw(repo, execution, lock, task, acceptance)
    write_sealed_json(contract["output"], raw)
    return contract["output"], raw["summary"]


def _quarantine_failed_publication(
    contract: dict[str, Path], manifest: Path, audit: dict[str, Any]
) -> None:
    copied = False
    try:
        contract["failed_manifest"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(manifest, contract["failed_manifest"])
        if sha256_file(manifest) != sha256_file(contract["failed_manifest"]):
            raise RuntimeError("quarantined manifest copy differs")
        contract["failed_manifest"].chmod(0)
        copied = True
    finally:
        manifest.unlink(missing_ok=True)
    write_sealed_json(
        contract["failure_receipt"],
        {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "run_id": DEFAULT_RUN_ID,
            "operational_failure": audit["status"],
            "public_manifest_retained": False,
            "raw_artifact_retained": True,
            "failed_manifest_retained": copied,
        },
    )


def run(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    contract = validate_output_contract(repo)
    execution, lock, task, acceptance = _locked_context(repo)
    raw, deadline = _execute_locked_raw(repo, execution, lock, task, acceptance)
    write_sealed_json(contract["output"], raw)
    contract["output"].chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=contract["output"],
            experiment_id=EXPERIMENT_ID,
            artifact_id=DEFAULT_RUN_ID,
            kind="receipted-projection-practice-opportunity-calibration",
            evidence_class=raw["evidence_class"],
            recipe=(
                RECONSTRUCTION_RECIPE
                if raw["evidence_class"] == "public-reconstructible"
                else None
            ),
            public_url=None,
            limitations=[
                "All actor-channel records are synthetic fixtures; no candidate output occurred.",
                "The reference fitter is an evaluator-owned opportunity witness, not learned machinery.",
                "A pass establishes only the frozen bounded causal interface and authorizes one OT-0072.",
            ],
            input_manifests=[acceptance["predecessor_manifest"]],
            store=contract["store"],
        )
    finally:
        contract["output"].chmod(0)
    post_audit = _bounded_command(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        repo,
        deadline,
        "audit",
    )
    if post_audit["status"] != "passed":
        _quarantine_failed_publication(contract, manifest, post_audit)
        raise RuntimeError("post-manifest audit failed; authority quarantined")
    return manifest, raw["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0071-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-authoritative", action="store_true")
    modes.add_argument("--reconstruct-only", action="store_true")
    modes.add_argument("--calibration-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.prepare_authoritative:
            task, receipt, lock = prepare_authoritative(repo)
            payload = {
                "task": _logical_evidence_path(task.relative_to(default_store(repo))),
                "derivation_receipt": _logical_evidence_path(
                    receipt.relative_to(default_store(repo))
                ),
                "run_lock": str(lock.relative_to(repo)),
            }
        elif args.calibration_worker:
            _execution, _lock, task, acceptance = _locked_context(repo)
            sys.stdout.buffer.write(canonical_json(run_calibration(repo, task, acceptance)))
            return 0
        else:
            operation = reconstruct if args.reconstruct_only else run
            path, summary = operation(repo)
            payload = {
                "output" if args.reconstruct_only else "manifest": (
                    _logical_evidence_path(path.relative_to(default_store(repo)))
                    if args.reconstruct_only
                    else str(path.relative_to(repo))
                ),
                "summary": summary,
            }
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
