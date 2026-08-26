"""OT-0070 trajectory authority and inactive-branch calibration.

This module adds only procedural fixture semantics above the generic trajectory
store.  It authorizes no learner and contains no actor or hosted-model path.
"""

from __future__ import annotations

import argparse
import inspect
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
from typing import Any, Callable, Iterable

from open_trajectory_evidence.evidence import (
    EvidenceError,
    default_store,
    record_artifact,
)

from .ot0002 import (
    canonical_json,
    child_environment,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
)
from .ot0003 import write_sealed_json
from .ot0070_reset_worker import ProjectionError, validate_projection_bytes
from .trajectory import (
    ACTOR_SOURCE,
    CONTROLLER_SOURCE,
    WORLD_SOURCE,
    TrajectoryStore,
    bootstrap_trajectory_store,
)


EXPERIMENT_ID = "OT-0070"
PROTOCOL_ORIGIN_COMMIT = "1ed893c"
ACCEPTANCE_PATH = Path("spec/ot-0070-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0070-run-lock.json")
DEFAULT_RUN_ID = "ot-0070-trajectory-authority-calibration-001"
RECONSTRUCTION_RECIPE = (
    "At the exact Git commit named by environment.git.commit and with a fresh "
    "$EVIDENCE, run OT_EVIDENCE_ROOT=$EVIDENCE PYTHONPATH=src python3 "
    "experiments/ot_0070_harness.py "
    "--reconstruct-only "
    "--output $EVIDENCE/runs/OT-0070/"
    "ot-0070-trajectory-authority-calibration-001.json"
)
CASE_INDICES = tuple(range(16))
PROJECTION_BYTE_LIMIT = 2048
MINIMUM_FULL_TRAJECTORY_BYTES = 8193
DISTRACTOR_COUNT = 16
DISTRACTOR_PADDING_BYTES = 480
TRACE_ROW_COUNT = 3
MAXIMUM_RECORD_BYTES = 4096
RESET_PROCESS_SECONDS = 5
MAXIMUM_RAW_ARTIFACT_BYTES = 1_048_576
WALL_SECONDS = 120
PROTOCOL_FROZEN_PATHS = (
    ACCEPTANCE_PATH,
    Path("experiments/OT-0070-trajectory-authority-calibration.md"),
    Path("docs/TRAJECTORY_PROJECTION_EPOCH.md"),
    Path("PROGRAM.md"),
    Path("TARGET.md"),
    Path("RED_LINES.md"),
    Path("docs/EVIDENCE.md"),
    Path("docs/WORKFLOW.md"),
)

_CALIBRATION_FAILURE_CODES = frozenset(
    {"calibration_timeout", "reset_timeout", "calibration_failed"}
)
_OPERATIONAL_FAILURE_CODES = frozenset(
    {
        *_CALIBRATION_FAILURE_CODES,
        "tests_timeout",
        "tests_failed",
        "audit_timeout",
        "audit_failed",
        "artifact_size",
    }
)

_RECORD_ID = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[0-9a-f]{16}")
_NO_EXPECTED_PARENT = object()


class ProtocolError(ValueError):
    """Raised when a procedural record or transition fails closed."""


@dataclass(frozen=True)
class PointerState:
    """One replay-derived pointer state; never an authoritative mutable field."""

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
class FixtureHistory:
    store: TrajectoryStore
    controller: "PointerController"
    ids: dict[str, Any]
    stage_outputs: dict[str, str]
    _actor: "ActorFixtureChannel"
    _world: "WorldResolver"
    _actor_interventions: "_AppendInterventionHarness"
    _world_interventions: "_AppendInterventionHarness"
    _controller_interventions: "_ControllerInterventionHarness"
    reset_result: dict[str, Any] | None = None


def fixed_input_paths(repo: Path | None = None) -> dict[str, Path]:
    """Named scientific and verification authorities hashed in the run lock.

    The implementation commit binds the complete tracked tree.  The execution
    validator separately permits only the prospective run-lock addition after
    that commit, so these named hashes are not treated as a partial runtime
    closure.
    """

    repo = (repo or Path.cwd()).resolve()
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "experiment_record_sha256": Path(
            "experiments/OT-0070-trajectory-authority-calibration.md"
        ),
        "evaluation_epoch_sha256": Path("docs/TRAJECTORY_PROJECTION_EPOCH.md"),
        "program_sha256": Path("PROGRAM.md"),
        "target_sha256": Path("TARGET.md"),
        "red_lines_sha256": Path("RED_LINES.md"),
        "evidence_contract_sha256": Path("docs/EVIDENCE.md"),
        "workflow_contract_sha256": Path("docs/WORKFLOW.md"),
        "trajectory_core_sha256": Path("src/open_trajectory_harness/trajectory.py"),
        "procedural_harness_sha256": Path("src/open_trajectory_harness/ot0070.py"),
        "reset_worker_sha256": Path(
            "src/open_trajectory_harness/ot0070_reset_worker.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0070_harness.py"),
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


def opaque_token(case_index: int, role: str, index: int, *, alpha: bool = False) -> str:
    """Derive a frozen opaque fixture token, with an optional consistent rename."""

    if case_index not in CASE_INDICES:
        raise ValueError("OT-0070 case index is unavailable")
    if type(role) is not str or not role or type(index) is not int or index < 0:
        raise ValueError("OT-0070 token coordinates are malformed")
    token = sha256_bytes(f"ot-0070:{case_index}:{role}:{index}".encode())[:16]
    if alpha:
        token = sha256_bytes(f"ot-0070:alpha:{token}".encode())[:16]
    return token


def distractor_padding(case_index: int, index: int) -> str:
    if case_index not in CASE_INDICES or not 0 <= index < DISTRACTOR_COUNT:
        raise ValueError("OT-0070 distractor coordinate is unavailable")
    digest = sha256_bytes(
        f"ot-0070:{case_index}:distractor:{index}:padding".encode()
    )
    return (digest * 8)[:DISTRACTOR_PADDING_BYTES]


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ProtocolError(f"{label} keys differ from the frozen schema")
    return value


def _checked_record_id(value: object, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if type(value) is not str or _RECORD_ID.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a lowercase record identity")
    return value


def _checked_token(value: object, label: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a bounded opaque token")
    return value


def _record(store: TrajectoryStore, record_id: str) -> dict[str, Any]:
    _checked_record_id(record_id, "record identity")
    try:
        record = store.get(record_id)
    except (KeyError, ValueError) as error:
        raise ProtocolError("named trajectory record is unavailable") from error
    if sha256_bytes(canonical_json(record)) != record_id:
        raise ProtocolError("stored record identity is not canonical")
    return _exact_keys(record, {"source", "parents", "payload"}, "record")


def validate_proposal(
    store: TrajectoryStore,
    proposal_id: str,
    *,
    expected_parent: str | None | object = _NO_EXPECTED_PARENT,
) -> dict[str, Any]:
    record = _record(store, proposal_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("proposal lacks actor-channel provenance")
    payload = _exact_keys(
        record["payload"],
        {"case_token", "occurrence", "record", "schema_version", "state"},
        "proposal payload",
    )
    if payload["record"] != "proposal" or payload["schema_version"] != 1:
        raise ProtocolError("proposal marker is invalid")
    _checked_token(payload["case_token"], "proposal case token")
    if type(payload["occurrence"]) is not int or payload["occurrence"] < 0:
        raise ProtocolError("proposal occurrence is invalid")
    state = _exact_keys(payload["state"], {"output"}, "proposal state")
    _checked_token(state["output"], "proposal state output")
    if expected_parent is not _NO_EXPECTED_PARENT:
        expected = [] if expected_parent is None else [expected_parent]
        if record["parents"] != expected:
            raise ProtocolError("proposal parent differs from replay-derived active state")
    return record


def validate_trial(
    store: TrajectoryStore,
    trial_id: str,
    *,
    expected_proposal_id: str | None = None,
) -> dict[str, Any]:
    """Validate provenance and exact binding without judging trial quality."""

    record = _record(store, trial_id)
    if record["source"] != WORLD_SOURCE:
        raise ProtocolError("trial lacks world-channel provenance")
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
        raise ProtocolError("trial marker is invalid")
    _checked_token(payload["case_token"], "trial case token")
    _checked_token(payload["executor_receipt"], "trial executor receipt")
    proposal_id = _checked_record_id(payload["proposal_id"], "trial proposal identity")
    if record["parents"] != [proposal_id]:
        raise ProtocolError("trial parent edge and payload binding disagree")
    if expected_proposal_id is not None and proposal_id != expected_proposal_id:
        raise ProtocolError("trial is bound to a different proposal")
    proposal = validate_proposal(store, proposal_id)
    if proposal["payload"]["case_token"] != payload["case_token"]:
        raise ProtocolError("proposal and trial case tokens differ")
    trace = payload["trace"]
    if type(trace) is not list or len(trace) != TRACE_ROW_COUNT:
        raise ProtocolError("trial trace length differs from the frozen schema")
    for index, raw_row in enumerate(trace):
        row = _exact_keys(
            raw_row,
            {"input", "proposal_output", "resolved_output", "trial_id"},
            f"trial row {index}",
        )
        for key in ("input", "proposal_output", "resolved_output", "trial_id"):
            _checked_token(row[key], f"trial row {index} {key}")
    return record


def _is_descendant(store: TrajectoryStore, descendant_id: str, ancestor_id: str) -> bool:
    frontier = [descendant_id]
    visited: set[str] = set()
    while frontier:
        current = frontier.pop()
        if current == ancestor_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        frontier.extend(_record(store, current)["parents"])
    return False


def validate_decision(store: TrajectoryStore, decision_id: str) -> dict[str, Any]:
    record = _record(store, decision_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("decision lacks actor-channel provenance")
    payload = _exact_keys(
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
    _checked_token(payload["case_token"], "decision case token")
    _checked_token(payload["decision_token"], "decision token")
    expected_active = _checked_record_id(
        payload["expected_active_id"], "decision expected active identity"
    )
    expected_pointer = _checked_record_id(
        payload["expected_pointer_event_id"], "decision expected pointer identity"
    )
    if payload["action"] in {"adopt", "set_down"}:
        selected = _checked_record_id(
            payload["selected_proposal_id"], "selected proposal identity"
        )
        trial = _checked_record_id(payload["trial_id"], "selected trial identity")
        if payload["rollback_target_id"] is not None:
            raise ProtocolError("adopt/set-down decision carries a rollback target")
        expected_parents = sorted({selected, trial, expected_pointer})
    else:
        if payload["selected_proposal_id"] is not None or payload["trial_id"] is not None:
            raise ProtocolError("rollback decision carries a selected branch")
        target = _checked_record_id(
            payload["rollback_target_id"], "rollback target identity"
        )
        expected_parents = sorted({expected_active, target, expected_pointer})
    if record["parents"] != expected_parents:
        raise ProtocolError("decision ancestry differs from its exact binding")
    return record


def _decision_result(
    store: TrajectoryStore,
    decision_id: str,
    state: PointerState,
    used_decisions: set[str],
) -> tuple[str, str]:
    decision = validate_decision(store, decision_id)
    payload = decision["payload"]
    if decision_id in used_decisions:
        raise ProtocolError("pointer decision was replayed")
    if (
        payload["expected_pointer_event_id"] != state.pointer_event_id
        or payload["expected_active_id"] != state.active_id
    ):
        raise ProtocolError("decision compare-and-swap state is stale")
    action = payload["action"]
    if action in {"adopt", "set_down"}:
        selected = payload["selected_proposal_id"]
        trial = payload["trial_id"]
        proposal = validate_proposal(store, selected, expected_parent=state.active_id)
        validate_trial(store, trial, expected_proposal_id=selected)
        if proposal["payload"]["case_token"] != payload["case_token"]:
            raise ProtocolError("decision and proposal case tokens differ")
        return action, selected if action == "adopt" else state.active_id
    target = payload["rollback_target_id"]
    current = validate_proposal(store, state.active_id)
    target_record = validate_proposal(store, target)
    if current["payload"]["case_token"] != payload["case_token"]:
        raise ProtocolError("rollback and active proposal case tokens differ")
    if target_record["payload"]["case_token"] != payload["case_token"]:
        raise ProtocolError("rollback and target proposal case tokens differ")
    if target == state.active_id or not _is_descendant(store, state.active_id, target):
        raise ProtocolError("rollback target is not a strict active ancestor")
    return action, target


def _pointer_records(store: TrajectoryStore) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record_id in store.record_ids:
        record = _record(store, record_id)
        if (
            record["source"] == CONTROLLER_SOURCE
            and type(record["payload"]) is dict
            and record["payload"].get("record") == "pointer"
        ):
            records[record_id] = record
    return records


def _validate_pointer_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = _exact_keys(
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
    _checked_record_id(payload["resulting_active_id"], "resulting active identity")
    _checked_record_id(payload["prior_active_id"], "prior active identity", nullable=True)
    _checked_record_id(payload["decision_id"], "pointer decision identity", nullable=True)
    _checked_record_id(
        payload["previous_pointer_event_id"],
        "previous pointer identity",
        nullable=True,
    )
    return payload


def replay_pointer(store: TrajectoryStore) -> PointerReplay:
    """Derive one authoritative active pointer from all controller events."""

    pointer_records = _pointer_records(store)
    if not pointer_records:
        raise ProtocolError("pointer trajectory has no genesis")
    payloads = {
        record_id: _validate_pointer_payload(record)
        for record_id, record in pointer_records.items()
    }
    genesis_ids = [
        record_id
        for record_id, payload in payloads.items()
        if payload["previous_pointer_event_id"] is None
    ]
    if len(genesis_ids) != 1:
        raise ProtocolError("pointer trajectory does not have exactly one genesis")
    genesis_id = genesis_ids[0]
    genesis_record = pointer_records[genesis_id]
    genesis = payloads[genesis_id]
    if (
        genesis["action"] != "initialize"
        or genesis["sequence"] != 0
        or genesis["prior_active_id"] is not None
        or genesis["decision_id"] is not None
        or genesis_record["parents"] != [genesis["resulting_active_id"]]
    ):
        raise ProtocolError("pointer genesis differs from the frozen initialization")
    validate_proposal(store, genesis["resulting_active_id"], expected_parent=None)
    states = [
        PointerState(0, genesis_id, genesis["resulting_active_id"], None)
    ]
    used_decisions: set[str] = set()
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
        record_id = children[0]
        if record_id in consumed:
            raise ProtocolError("pointer trajectory contains a cycle")
        record = pointer_records[record_id]
        payload = payloads[record_id]
        if payload["sequence"] != current.sequence + 1:
            raise ProtocolError("pointer sequence skips or repeats")
        if payload["prior_active_id"] != current.active_id:
            raise ProtocolError("pointer prior active identity is mismatched")
        decision_id = payload["decision_id"]
        if decision_id is None:
            raise ProtocolError("pointer transition omits its decision")
        action, resulting = _decision_result(
            store, decision_id, current, used_decisions
        )
        if payload["action"] != action or payload["resulting_active_id"] != resulting:
            raise ProtocolError("pointer transition differs from its decision")
        expected_parents = sorted(
            {decision_id, current.pointer_event_id, resulting}
        )
        if record["parents"] != expected_parents:
            raise ProtocolError("pointer transition ancestry is invalid")
        used_decisions.add(decision_id)
        consumed.add(record_id)
        states.append(
            PointerState(payload["sequence"], record_id, resulting, decision_id)
        )
    if consumed != set(pointer_records):
        raise ProtocolError("pointer trajectory contains a disconnected event")
    return PointerReplay(tuple(states), tuple(sorted(used_decisions)))


def consumer_output(store: TrajectoryStore, state: PointerState) -> str:
    """Emit only the opaque output named by a replay-derived active proposal."""

    record = store.get(state.active_id)
    if record["source"] != ACTOR_SOURCE:
        raise ProtocolError("active state is not an actor-channel proposal")
    payload = _exact_keys(
        record["payload"],
        {"case_token", "occurrence", "record", "schema_version", "state"},
        "active proposal payload",
    )
    if payload["record"] != "proposal" or payload["schema_version"] != 1:
        raise ProtocolError("active proposal marker is invalid")
    proposal_state = _exact_keys(payload["state"], {"output"}, "active proposal state")
    return _checked_token(proposal_state["output"], "active proposal output")


class _AppendInterventionHarness:
    """Harness-only raw writer bound to exactly one bootstrap capability."""

    __slots__ = ("_capability", "_store")

    def __init__(self, store: TrajectoryStore, capability: object) -> None:
        self._store = store
        self._capability = capability

    def append(
        self, payload: dict[str, Any], parents: Iterable[str] = ()
    ) -> str:
        return self._store.append(self._capability, payload, parents)


class _ControllerInterventionHarness:
    """Private bootstrap authority for controller-source negative controls."""

    __slots__ = ("_capability", "_store")

    def __init__(self, store: TrajectoryStore, capability: object) -> None:
        self._store = store
        self._capability = capability

    def append_pointer(
        self, payload: dict[str, Any], parents: Iterable[str]
    ) -> str:
        return self._store.append(self._capability, payload, parents)

    def append_record(
        self, payload: dict[str, Any], parents: Iterable[str]
    ) -> str:
        return self._store.append(self._capability, payload, parents)


class PointerController:
    """Controller capability facade with replay-derived CAS transitions only."""

    __slots__ = ("_capability", "_store")

    def __init__(self, store: TrajectoryStore, capability: object) -> None:
        self._store = store
        self._capability = capability

    def initialize(self, active_proposal_id: str) -> str:
        if _pointer_records(self._store):
            raise ProtocolError("pointer trajectory is already initialized")
        validate_proposal(self._store, active_proposal_id, expected_parent=None)
        payload = {
            "action": "initialize",
            "decision_id": None,
            "previous_pointer_event_id": None,
            "prior_active_id": None,
            "record": "pointer",
            "resulting_active_id": active_proposal_id,
            "schema_version": 1,
            "sequence": 0,
        }
        pointer_id = self._store.append(
            self._capability, payload, [active_proposal_id]
        )
        if replay_pointer(self._store).current.pointer_event_id != pointer_id:
            raise ProtocolError("pointer initialization did not replay exactly")
        return pointer_id

    def apply(self, decision_id: str, *, reverse_parent_input: bool = False) -> str:
        replay = replay_pointer(self._store)
        current = replay.current
        action, resulting = _decision_result(
            self._store, decision_id, current, set(replay.decision_ids)
        )
        parents = [decision_id, current.pointer_event_id, resulting]
        if reverse_parent_input:
            parents.reverse()
        payload = {
            "action": action,
            "decision_id": decision_id,
            "previous_pointer_event_id": current.pointer_event_id,
            "prior_active_id": current.active_id,
            "record": "pointer",
            "resulting_active_id": resulting,
            "schema_version": 1,
            "sequence": current.sequence + 1,
        }
        pointer_id = self._store.append(self._capability, payload, parents)
        observed = replay_pointer(self._store).current
        if observed.pointer_event_id != pointer_id or observed.active_id != resulting:
            raise ProtocolError("appended pointer transition did not replay exactly")
        return pointer_id

    def replay(self) -> PointerReplay:
        return replay_pointer(self._store)


class ActorFixtureChannel:
    """Synthetic actor-channel fixture writer; this is not an actor runtime."""

    __slots__ = ("_alpha", "_case_index", "_capability", "_store")

    def __init__(
        self,
        store: TrajectoryStore,
        capability: object,
        case_index: int,
        *,
        alpha: bool,
    ) -> None:
        self._store = store
        self._capability = capability
        self._case_index = case_index
        self._alpha = alpha

    @property
    def case_token(self) -> str:
        return opaque_token(self._case_index, "case", 0, alpha=self._alpha)

    def token(self, role: str, index: int) -> str:
        return opaque_token(self._case_index, role, index, alpha=self._alpha)

    def proposal(
        self,
        *,
        occurrence: int,
        output_role: str,
        parent_id: str | None,
    ) -> str:
        payload = {
            "case_token": self.case_token,
            "occurrence": occurrence,
            "record": "proposal",
            "schema_version": 1,
            "state": {
                "output": opaque_token(
                    self._case_index, output_role, 0, alpha=self._alpha
                )
            },
        }
        parents = [] if parent_id is None else [parent_id]
        proposal_id = self._store.append(self._capability, payload, parents)
        validate_proposal(self._store, proposal_id, expected_parent=parent_id)
        return proposal_id

    def decision(
        self,
        *,
        action: str,
        decision_index: int,
        state: PointerState,
        selected_proposal_id: str | None = None,
        trial_id: str | None = None,
        rollback_target_id: str | None = None,
        reverse_parent_input: bool = False,
    ) -> str:
        payload = {
            "action": action,
            "case_token": self.case_token,
            "decision_token": opaque_token(
                self._case_index, "decision", decision_index, alpha=self._alpha
            ),
            "expected_active_id": state.active_id,
            "expected_pointer_event_id": state.pointer_event_id,
            "record": "decision",
            "rollback_target_id": rollback_target_id,
            "schema_version": 1,
            "selected_proposal_id": selected_proposal_id,
            "trial_id": trial_id,
        }
        if action in {"adopt", "set_down"}:
            parents = [selected_proposal_id, trial_id, state.pointer_event_id]
        elif action == "rollback":
            parents = [state.active_id, rollback_target_id, state.pointer_event_id]
        else:
            raise ValueError("OT-0070 fixture decision action is unavailable")
        if any(item is None for item in parents):
            raise ValueError("OT-0070 fixture decision omits an exact parent")
        if reverse_parent_input:
            parents.reverse()
        decision_id = self._store.append(self._capability, payload, parents)
        validate_decision(self._store, decision_id)
        return decision_id

class WorldResolver:
    """The sole fixture path that can append independently resolved trials."""

    __slots__ = ("_alpha", "_case_index", "_capability", "_store")

    def __init__(
        self,
        store: TrajectoryStore,
        capability: object,
        case_index: int,
        *,
        alpha: bool,
    ) -> None:
        self._store = store
        self._capability = capability
        self._case_index = case_index
        self._alpha = alpha

    def resolved_output(self, index: int) -> str:
        value = sha256_bytes(
            f"ot-0070:{self._case_index}:resolved:{index}".encode()
        )[:16]
        if self._alpha:
            value = sha256_bytes(f"ot-0070:alpha:{value}".encode())[:16]
        return value

    def trial(
        self,
        proposal_id: str,
        *,
        matching_quality: bool,
        reverse_parent_input: bool = False,
    ) -> str:
        proposal = validate_proposal(self._store, proposal_id)
        trace = []
        for index in range(TRACE_ROW_COUNT):
            resolved = self.resolved_output(index)
            proposal_output = (
                resolved
                if matching_quality
                else opaque_token(
                    self._case_index,
                    "nonmatching-output",
                    index,
                    alpha=self._alpha,
                )
            )
            if not matching_quality and proposal_output == resolved:
                raise RuntimeError("OT-0070 nonmatching placebo collided")
            trace.append(
                {
                    "input": opaque_token(
                        self._case_index, "trial-input", index, alpha=self._alpha
                    ),
                    "proposal_output": proposal_output,
                    "resolved_output": resolved,
                    "trial_id": opaque_token(
                        self._case_index, "trial-row", index, alpha=self._alpha
                    ),
                }
            )
        payload = {
            "case_token": proposal["payload"]["case_token"],
            "executor_receipt": opaque_token(
                self._case_index, "executor-receipt", 0, alpha=self._alpha
            ),
            "proposal_id": proposal_id,
            "record": "trial",
            "schema_version": 1,
            "trace": trace,
        }
        parents = [proposal_id]
        if reverse_parent_input:
            parents.reverse()
        trial_id = self._store.append(self._capability, payload, parents)
        validate_trial(self._store, trial_id, expected_proposal_id=proposal_id)
        return trial_id

def _append_distractors(
    store: TrajectoryStore,
    actor: ActorFixtureChannel,
    actor_interventions: _AppendInterventionHarness,
    case_index: int,
    order: str,
) -> tuple[str, ...]:
    if order not in {"ascending", "descending"}:
        raise ValueError("OT-0070 distractor order is unavailable")
    indices = list(range(DISTRACTOR_COUNT))
    if order == "descending":
        indices.reverse()
    by_index: dict[int, str] = {}
    for index in indices:
        payload = {
            "case_token": actor.case_token,
            "index": index,
            "padding": distractor_padding(case_index, index),
            "record": "distractor",
            "schema_version": 1,
            "token": actor.token("distractor", index),
        }
        by_index[index] = actor_interventions.append(payload)
    return tuple(by_index[index] for index in range(DISTRACTOR_COUNT))


def build_fixture_history(
    case_index: int,
    *,
    distractor_order: str = "ascending",
    reverse_parent_input: bool = False,
    alpha: bool = False,
    matching_quality: bool = False,
    include_distractors: bool = True,
) -> FixtureHistory:
    """Build the exact initialize→set-down→adopt→rollback fixture lineage."""

    if case_index not in CASE_INDICES:
        raise ValueError("OT-0070 case index is unavailable")
    (
        store,
        actor_capability,
        world_capability,
        controller_capability,
    ) = bootstrap_trajectory_store(max_record_bytes=MAXIMUM_RECORD_BYTES)
    actor = ActorFixtureChannel(
        store, actor_capability, case_index, alpha=alpha
    )
    world = WorldResolver(store, world_capability, case_index, alpha=alpha)
    controller = PointerController(store, controller_capability)
    actor_interventions = _AppendInterventionHarness(store, actor_capability)
    world_interventions = _AppendInterventionHarness(store, world_capability)
    controller_interventions = _ControllerInterventionHarness(
        store, controller_capability
    )
    distractors = (
        _append_distractors(
            store,
            actor,
            actor_interventions,
            case_index,
            distractor_order,
        )
        if include_distractors
        else ()
    )

    active_parent = actor.proposal(
        occurrence=0, output_role="active-output", parent_id=None
    )
    initialize_pointer = controller.initialize(active_parent)
    initial_state = controller.replay().current
    initial_output = consumer_output(store, initial_state)

    proposal = actor.proposal(
        occurrence=1, output_role="proposal-output", parent_id=active_parent
    )
    proposal_before = canonical_json(store.get(proposal))
    trial = world.trial(
        proposal,
        matching_quality=matching_quality,
        reverse_parent_input=reverse_parent_input,
    )
    sibling_proposal = actor.proposal(
        occurrence=2, output_role="sibling-output", parent_id=active_parent
    )
    sibling_trial = world.trial(
        sibling_proposal,
        matching_quality=not matching_quality,
        reverse_parent_input=reverse_parent_input,
    )

    set_down_decision = actor.decision(
        action="set_down",
        decision_index=0,
        state=initial_state,
        selected_proposal_id=proposal,
        trial_id=trial,
        reverse_parent_input=reverse_parent_input,
    )
    set_down_pointer = controller.apply(
        set_down_decision, reverse_parent_input=reverse_parent_input
    )
    set_down_state = controller.replay().current
    set_down_output = consumer_output(store, set_down_state)

    adopt_decision = actor.decision(
        action="adopt",
        decision_index=1,
        state=set_down_state,
        selected_proposal_id=proposal,
        trial_id=trial,
        reverse_parent_input=reverse_parent_input,
    )
    adopt_pointer = controller.apply(
        adopt_decision, reverse_parent_input=reverse_parent_input
    )
    adopt_state = controller.replay().current
    adopt_output = consumer_output(store, adopt_state)

    rollback_decision = actor.decision(
        action="rollback",
        decision_index=2,
        state=adopt_state,
        rollback_target_id=active_parent,
        reverse_parent_input=reverse_parent_input,
    )
    rollback_pointer = controller.apply(
        rollback_decision, reverse_parent_input=reverse_parent_input
    )
    rollback_state = controller.replay().current
    rollback_output = consumer_output(store, rollback_state)

    record_ids_before_inactive = store.record_ids
    inactive_proposal = actor.proposal(
        occurrence=3, output_role="inactive-output", parent_id=active_parent
    )
    inactive_trial = world.trial(
        inactive_proposal,
        matching_quality=matching_quality,
        reverse_parent_input=reverse_parent_input,
    )
    inactive_output = consumer_output(store, controller.replay().current)

    ids: dict[str, Any] = {
        "active_parent": active_parent,
        "initialize_pointer": initialize_pointer,
        "proposal": proposal,
        "trial": trial,
        "sibling_proposal": sibling_proposal,
        "sibling_trial": sibling_trial,
        "set_down_decision": set_down_decision,
        "set_down_pointer": set_down_pointer,
        "adopt_decision": adopt_decision,
        "adopt_pointer": adopt_pointer,
        "rollback_decision": rollback_decision,
        "rollback_pointer": rollback_pointer,
        "inactive_proposal": inactive_proposal,
        "inactive_trial": inactive_trial,
        "distractors": distractors,
        "proposal_before": proposal_before,
        "record_ids_before_inactive": record_ids_before_inactive,
    }
    return FixtureHistory(
        store=store,
        controller=controller,
        ids=ids,
        stage_outputs={
            "initial": initial_output,
            "set_down": set_down_output,
            "adopt": adopt_output,
            "rollback": rollback_output,
            "after_inactive": inactive_output,
        },
        _actor=actor,
        _world=world,
        _actor_interventions=actor_interventions,
        _world_interventions=world_interventions,
        _controller_interventions=controller_interventions,
    )


def _raw_decision_payload(
    *,
    case_token: str,
    decision_token: str,
    action: str,
    expected_active_id: str,
    expected_pointer_event_id: str,
    selected_proposal_id: str | None,
    trial_id: str | None,
    rollback_target_id: str | None = None,
) -> dict[str, Any]:
    return {
        "action": action,
        "case_token": case_token,
        "decision_token": decision_token,
        "expected_active_id": expected_active_id,
        "expected_pointer_event_id": expected_pointer_event_id,
        "record": "decision",
        "rollback_target_id": rollback_target_id,
        "schema_version": 1,
        "selected_proposal_id": selected_proposal_id,
        "trial_id": trial_id,
    }


def _pointer_unchanged_after_rejection(
    history: FixtureHistory, decision_id: str
) -> bool:
    before = history.controller.replay().current
    before_ids = history.store.record_ids
    try:
        history.controller.apply(decision_id)
    except ProtocolError:
        after = history.controller.replay().current
        return before == after and before_ids == history.store.record_ids
    return False


def decision_intervention_controls(
    history: FixtureHistory, case_index: int
) -> dict[str, bool]:
    """Exercise malformed bindings without allowing any pointer transition."""

    store = history.store
    ids = history.ids
    state = history.controller.replay().current
    case_token = store.get(ids["active_parent"])["payload"]["case_token"]
    actor = history._actor
    world = history._world
    missing_id = sha256_bytes(f"ot-0070:{case_index}:missing".encode())

    def token(index: int) -> str:
        return opaque_token(case_index, "invalid-decision", index)

    missing_payload = _raw_decision_payload(
        case_token=case_token,
        decision_token=token(0),
        action="adopt",
        expected_active_id=state.active_id,
        expected_pointer_event_id=state.pointer_event_id,
        selected_proposal_id=missing_id,
        trial_id=ids["trial"],
    )
    missing_decision = history._actor_interventions.append(
        missing_payload,
        [ids["proposal"], ids["trial"], state.pointer_event_id],
    )

    untrialed = actor.proposal(
        occurrence=10, output_role="untrialed-output", parent_id=state.active_id
    )
    untrialed_decision = history._actor_interventions.append(
        _raw_decision_payload(
            case_token=case_token,
            decision_token=token(1),
            action="adopt",
            expected_active_id=state.active_id,
            expected_pointer_event_id=state.pointer_event_id,
            selected_proposal_id=untrialed,
            trial_id=ids["trial"],
        ),
        [untrialed, ids["trial"], state.pointer_event_id],
    )

    nonancestor = actor.proposal(
        occurrence=11, output_role="nonancestor-output", parent_id=None
    )
    nonancestor_trial = world.trial(nonancestor, matching_quality=True)
    nonancestor_decision = history._actor_interventions.append(
        _raw_decision_payload(
            case_token=case_token,
            decision_token=token(2),
            action="adopt",
            expected_active_id=state.active_id,
            expected_pointer_event_id=state.pointer_event_id,
            selected_proposal_id=nonancestor,
            trial_id=nonancestor_trial,
        ),
        [nonancestor, nonancestor_trial, state.pointer_event_id],
    )

    sibling_decision = history._actor_interventions.append(
        _raw_decision_payload(
            case_token=case_token,
            decision_token=token(3),
            action="adopt",
            expected_active_id=state.active_id,
            expected_pointer_event_id=state.pointer_event_id,
            selected_proposal_id=ids["proposal"],
            trial_id=ids["sibling_trial"],
        ),
        [ids["proposal"], ids["sibling_trial"], state.pointer_event_id],
    )

    trial_payload = json.loads(
        canonical_json(store.get(ids["trial"])["payload"])
    )
    misbound_trial = history._world_interventions.append(
        trial_payload, [ids["sibling_proposal"]]
    )
    misbound_decision = history._actor_interventions.append(
        _raw_decision_payload(
            case_token=case_token,
            decision_token=token(4),
            action="adopt",
            expected_active_id=state.active_id,
            expected_pointer_event_id=state.pointer_event_id,
            selected_proposal_id=ids["proposal"],
            trial_id=misbound_trial,
        ),
        [ids["proposal"], misbound_trial, state.pointer_event_id],
    )

    stale_payload = _raw_decision_payload(
        case_token=case_token,
        decision_token=token(5),
        action="adopt",
        expected_active_id=ids["active_parent"],
        expected_pointer_event_id=ids["initialize_pointer"],
        selected_proposal_id=ids["proposal"],
        trial_id=ids["trial"],
    )
    stale_decision = history._actor_interventions.append(
        stale_payload,
        [ids["proposal"], ids["trial"], ids["initialize_pointer"]],
    )

    results = {
        "missing": _pointer_unchanged_after_rejection(history, missing_decision),
        "untrialed": _pointer_unchanged_after_rejection(
            history, untrialed_decision
        ),
        "nonancestor": _pointer_unchanged_after_rejection(
            history, nonancestor_decision
        ),
        "sibling_trial": _pointer_unchanged_after_rejection(
            history, sibling_decision
        ),
        "misbound_trial": _pointer_unchanged_after_rejection(
            history, misbound_decision
        ),
        "stale": _pointer_unchanged_after_rejection(history, stale_decision),
        "replayed": _pointer_unchanged_after_rejection(
            history, ids["set_down_decision"]
        ),
    }
    return results


def provenance_controls(history: FixtureHistory, case_index: int) -> dict[str, bool]:
    store = history.store
    ids = history.ids
    trial_payload = json.loads(canonical_json(store.get(ids["trial"])["payload"]))
    proposal_payload = json.loads(
        canonical_json(store.get(ids["proposal"])["payload"])
    )
    forged_actor_trial_payload = {
        **trial_payload,
        "source": WORLD_SOURCE,
    }
    forged_actor_trial = history._actor_interventions.append(
        forged_actor_trial_payload, [ids["proposal"]]
    )
    controller_proposal = history._controller_interventions.append_record(
        proposal_payload, [ids["active_parent"]]
    )
    altered_trial_payload = json.loads(canonical_json(trial_payload))
    altered_trial_payload["trace"][0]["resolved_output"] = opaque_token(
        case_index, "controller-altered", 0
    )
    controller_trial = history._controller_interventions.append_record(
        altered_trial_payload, [ids["proposal"]]
    )

    def rejected(function: Callable[[], object]) -> bool:
        try:
            function()
        except (PermissionError, ProtocolError):
            return True
        return False

    return {
        "source_string_rejected": rejected(
            lambda: store.append(WORLD_SOURCE, trial_payload, [ids["proposal"]])
        ),
        "actor_asserted_world_rejected": rejected(
            lambda: validate_trial(store, forged_actor_trial)
        ),
        "controller_actor_rejected": rejected(
            lambda: validate_proposal(store, controller_proposal)
        ),
        "controller_altered_world_rejected": rejected(
            lambda: validate_trial(store, controller_trial)
        ),
    }


def _append_raw_pointer(
    history: FixtureHistory,
    *,
    action: str,
    decision_id: str,
    previous_pointer_event_id: str,
    prior_active_id: str,
    resulting_active_id: str,
    sequence: int,
) -> str:
    payload = {
        "action": action,
        "decision_id": decision_id,
        "previous_pointer_event_id": previous_pointer_event_id,
        "prior_active_id": prior_active_id,
        "record": "pointer",
        "resulting_active_id": resulting_active_id,
        "schema_version": 1,
        "sequence": sequence,
    }
    return history._controller_interventions.append_pointer(
        payload,
        [decision_id, previous_pointer_event_id, resulting_active_id],
    )


def _replay_rejects(function: Callable[[], object]) -> bool:
    try:
        function()
    except ProtocolError:
        return True
    return False


def pointer_failure_controls(case_index: int) -> dict[str, bool]:
    forked = build_fixture_history(case_index, include_distractors=False)
    fork_actor = forked._actor
    fork_state = PointerState(
        2,
        forked.ids["adopt_pointer"],
        forked.ids["proposal"],
        forked.ids["adopt_decision"],
    )
    fork_decision = fork_actor.decision(
        action="rollback",
        decision_index=20,
        state=fork_state,
        rollback_target_id=forked.ids["active_parent"],
    )
    _append_raw_pointer(
        forked,
        action="rollback",
        decision_id=fork_decision,
        previous_pointer_event_id=forked.ids["adopt_pointer"],
        prior_active_id=forked.ids["proposal"],
        resulting_active_id=forked.ids["active_parent"],
        sequence=3,
    )

    skipped = build_fixture_history(case_index, include_distractors=False)
    skipped_actor = skipped._actor
    skipped_state = skipped.controller.replay().current
    skipped_decision = skipped_actor.decision(
        action="adopt",
        decision_index=21,
        state=skipped_state,
        selected_proposal_id=skipped.ids["proposal"],
        trial_id=skipped.ids["trial"],
    )
    _append_raw_pointer(
        skipped,
        action="adopt",
        decision_id=skipped_decision,
        previous_pointer_event_id=skipped_state.pointer_event_id,
        prior_active_id=skipped_state.active_id,
        resulting_active_id=skipped.ids["proposal"],
        sequence=skipped_state.sequence + 2,
    )

    mismatched = build_fixture_history(case_index, include_distractors=False)
    mismatched_actor = mismatched._actor
    mismatched_state = mismatched.controller.replay().current
    mismatched_decision = mismatched_actor.decision(
        action="adopt",
        decision_index=22,
        state=mismatched_state,
        selected_proposal_id=mismatched.ids["proposal"],
        trial_id=mismatched.ids["trial"],
    )
    _append_raw_pointer(
        mismatched,
        action="adopt",
        decision_id=mismatched_decision,
        previous_pointer_event_id=mismatched_state.pointer_event_id,
        prior_active_id=mismatched.ids["proposal"],
        resulting_active_id=mismatched.ids["proposal"],
        sequence=mismatched_state.sequence + 1,
    )

    noncas = build_fixture_history(case_index, include_distractors=False)
    case_token = noncas.store.get(noncas.ids["active_parent"])["payload"][
        "case_token"
    ]
    stale_decision = noncas._actor_interventions.append(
        _raw_decision_payload(
            case_token=case_token,
            decision_token=opaque_token(case_index, "invalid-pointer", 0),
            action="adopt",
            expected_active_id=noncas.ids["active_parent"],
            expected_pointer_event_id=noncas.ids["initialize_pointer"],
            selected_proposal_id=noncas.ids["proposal"],
            trial_id=noncas.ids["trial"],
        ),
        [
            noncas.ids["proposal"],
            noncas.ids["trial"],
            noncas.ids["initialize_pointer"],
        ],
    )
    noncas_state = noncas.controller.replay().current
    _append_raw_pointer(
        noncas,
        action="adopt",
        decision_id=stale_decision,
        previous_pointer_event_id=noncas_state.pointer_event_id,
        prior_active_id=noncas_state.active_id,
        resulting_active_id=noncas.ids["proposal"],
        sequence=noncas_state.sequence + 1,
    )

    controller_api = {
        name
        for name, member in inspect.getmembers(PointerController)
        if not name.startswith("_") and callable(member)
    }
    capability_getters = {
        name
        for name in (
            "actor_channel",
            "world_channel",
            "controller_channel",
            "capabilities",
        )
        if hasattr(TrajectoryStore, name)
    }
    return {
        "fork": _replay_rejects(lambda: replay_pointer(forked.store)),
        "skipped": _replay_rejects(lambda: replay_pointer(skipped.store)),
        "mismatched_prior": _replay_rejects(
            lambda: replay_pointer(mismatched.store)
        ),
        "non_cas": _replay_rejects(lambda: replay_pointer(noncas.store)),
        "no_direct_write_api": controller_api
        == {"initialize", "apply", "replay"}
        and not capability_getters,
    }


def _projection_controls(history: FixtureHistory) -> dict[str, Any]:
    store = history.store
    actor_selection = validate_decision(
        store, history.ids["adopt_decision"]
    )["payload"]
    proposal = actor_selection["selected_proposal_id"]
    trial = actor_selection["trial_id"]
    projection_bytes = store.serialize_projection(
        [proposal, trial], byte_limit=PROJECTION_BYTE_LIMIT
    )
    local_validation = validate_projection_bytes(projection_bytes)

    def incomplete_rejected(selected: list[str]) -> bool:
        try:
            validate_projection_bytes(
                store.serialize_projection(
                    selected, byte_limit=PROJECTION_BYTE_LIMIT
                )
            )
        except (ProjectionError, ValueError):
            return True
        return False

    try:
        store.serialize_projection(
            history.ids["distractors"], byte_limit=PROJECTION_BYTE_LIMIT
        )
    except ValueError:
        overbudget_rejected = True
    else:
        overbudget_rejected = False
    return {
        "projection_bytes": len(projection_bytes),
        "projection": json.loads(projection_bytes),
        "projection_raw": projection_bytes,
        "local_validation": local_validation,
        "proposal_exclusion_rejected": incomplete_rejected([trial]),
        "trial_exclusion_rejected": incomplete_rejected([proposal]),
        "overbudget_rejected": overbudget_rejected,
    }


def _reset_failure(status: str, *, within_bound: bool) -> dict[str, Any]:
    return {
        "status": status,
        "pass": False,
        "within_bound": within_bound,
        "projected_record_count": 0,
        "external_parent_count": 0,
        "external_parent_lookup": False,
        "unrelated_lookup": False,
        "controller_store_serialized": False,
        "workspace_empty_before": False,
        "workspace_empty_after": False,
    }


def run_reset_worker(repo: Path, projection_bytes: bytes) -> dict[str, Any]:
    """Pass only canonical projection bytes to a fresh process in an empty cwd."""

    environment = {
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(repo / "src"),
    }
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="ot-0070-reset-") as workspace:
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "open_trajectory_harness.ot0070_reset_worker",
                ],
                cwd=workspace,
                env=environment,
                input=projection_bytes,
                capture_output=True,
                timeout=RESET_PROCESS_SECONDS,
            )
    except subprocess.TimeoutExpired:
        return _reset_failure("timeout", within_bound=False)
    except OSError:
        return _reset_failure("launch-error", within_bound=False)
    elapsed = time.monotonic() - started
    if process.returncode != 0:
        return _reset_failure(
            "rejected", within_bound=elapsed <= RESET_PROCESS_SECONDS
        )
    if process.stderr:
        return _reset_failure(
            "unexpected-diagnostics",
            within_bound=elapsed <= RESET_PROCESS_SECONDS,
        )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError:
        return _reset_failure(
            "malformed-output", within_bound=elapsed <= RESET_PROCESS_SECONDS
        )
    if process.stdout != canonical_json(result):
        return _reset_failure(
            "noncanonical-output",
            within_bound=elapsed <= RESET_PROCESS_SECONDS,
        )
    if type(result) is not dict or not result.get("pass"):
        return _reset_failure(
            "invalid-output", within_bound=elapsed <= RESET_PROCESS_SECONDS
        )
    required = {
        "projected_record_count",
        "external_parent_count",
        "external_parent_lookup",
        "unrelated_lookup",
        "controller_store_serialized",
        "workspace_empty_before",
        "workspace_empty_after",
    }
    if not required <= set(result):
        return _reset_failure(
            "incomplete-output", within_bound=elapsed <= RESET_PROCESS_SECONDS
        )
    return {
        **{key: result[key] for key in sorted(required)},
        "status": "passed",
        "pass": True,
        "within_bound": elapsed <= RESET_PROCESS_SECONDS,
    }


def _source_counts(store: TrajectoryStore) -> dict[str, int]:
    counts = {ACTOR_SOURCE: 0, CONTROLLER_SOURCE: 0, WORLD_SOURCE: 0}
    for record_id in store.record_ids:
        counts[store.get(record_id)["source"]] += 1
    return counts


def normalized_history(history: FixtureHistory) -> dict[str, Any]:
    """Erase incidental identities while retaining every structural verdict."""

    replay = history.controller.replay()
    roles = {
        history.ids["active_parent"]: "active_parent",
        history.ids["proposal"]: "proposal",
    }
    pointer_actions = [
        history.store.get(state.pointer_event_id)["payload"]["action"]
        for state in replay.states
    ]
    actor_selection = validate_decision(
        history.store, history.ids["adopt_decision"]
    )["payload"]
    projection = history.store.serialize_projection(
        [actor_selection["selected_proposal_id"], actor_selection["trial_id"]]
    )
    return {
        "record_count": len(history.store),
        "source_counts": _source_counts(history.store),
        "distractor_count": len(history.ids["distractors"]),
        "full_trajectory_bytes": len(history.store.serialize_full()),
        "projection_bytes": len(projection),
        "pointer_sequences": [state.sequence for state in replay.states],
        "pointer_actions": pointer_actions,
        "active_roles": [roles.get(state.active_id, "other") for state in replay.states],
        "output_relations": {
            "set_down_preserves": history.stage_outputs["set_down"]
            == history.stage_outputs["initial"],
            "adoption_changes": history.stage_outputs["adopt"]
            != history.stage_outputs["initial"],
            "rollback_restores": history.stage_outputs["rollback"]
            == history.stage_outputs["initial"],
            "inactive_ignored": history.stage_outputs["after_inactive"]
            == history.stage_outputs["rollback"],
        },
    }


def _quality_verdict(history: FixtureHistory) -> dict[str, Any]:
    replay = history.controller.replay()
    adopted_state = replay.states[2]
    return {
        "protocol_valid": replay.current.sequence == 3,
        "adoption_transition": adopted_state.active_id == history.ids["proposal"],
        "selected_exact": canonical_json(history.store.get(adopted_state.active_id))
        == history.ids["proposal_before"],
        "action_trace": [
            history.store.get(state.pointer_event_id)["payload"]["action"]
            for state in replay.states
        ],
    }


def _matching_trial_rows(history: FixtureHistory) -> int:
    trace = validate_trial(history.store, history.ids["trial"])["payload"][
        "trace"
    ]
    return sum(
        row["proposal_output"] == row["resolved_output"] for row in trace
    )


def _quality_placebo(case_index: int) -> dict[str, Any]:
    matching = build_fixture_history(
        case_index, matching_quality=True, include_distractors=False
    )
    nonmatching = build_fixture_history(
        case_index, matching_quality=False, include_distractors=False
    )
    matching_verdict = _quality_verdict(matching)
    nonmatching_verdict = _quality_verdict(nonmatching)
    matching_rows = _matching_trial_rows(matching)
    nonmatching_rows = _matching_trial_rows(nonmatching)
    distinct_trials = matching.ids["trial"] != nonmatching.ids["trial"]
    same_protocol = matching_verdict == nonmatching_verdict
    return {
        "matching_protocol": matching_verdict,
        "nonmatching_protocol": nonmatching_verdict,
        "matching_row_count": matching_rows,
        "nonmatching_row_count": nonmatching_rows,
        "distinct_trial_identities": distinct_trials,
        "same_protocol_verdict": same_protocol,
        "effective_intervention": matching_rows == TRACE_ROW_COUNT
        and nonmatching_rows == 0
        and distinct_trials,
        "pass": same_protocol
        and matching_rows == TRACE_ROW_COUNT
        and nonmatching_rows == 0
        and distinct_trials,
    }


def evaluate_case(
    case_index: int,
    *,
    repo: Path | None = None,
    execute_reset: bool = True,
) -> dict[str, Any]:
    """Evaluate one frozen case without executing any actor or hosted call."""

    if case_index not in CASE_INDICES:
        raise ValueError("OT-0070 case index is unavailable")
    repo = (repo or Path(__file__).resolve().parents[2]).resolve()
    main = build_fixture_history(case_index)
    reverse_order = build_fixture_history(
        case_index,
        distractor_order="descending",
        reverse_parent_input=True,
    )
    alpha = build_fixture_history(case_index, alpha=True)

    main_normalized = normalized_history(main)
    order_normalized = normalized_history(reverse_order)
    alpha_normalized = normalized_history(alpha)
    projection = _projection_controls(main)
    full_serialized = main.store.serialize_full()
    full_bytes = len(full_serialized)
    core_ids = {
        key: value
        for key, value in main.ids.items()
        if key
        not in {"proposal_before", "record_ids_before_inactive"}
    }
    reverse_core_ids = {
        key: value
        for key, value in reverse_order.ids.items()
        if key
        not in {"proposal_before", "record_ids_before_inactive"}
    }
    order_placebo = (
        core_ids == reverse_core_ids
        and main.store.serialize_full() == reverse_order.store.serialize_full()
        and main_normalized == order_normalized
    )
    alpha_placebo = main_normalized == alpha_normalized

    inactive_state = main.controller.replay().current
    inactive_output_before_projection = consumer_output(main.store, inactive_state)
    main.store.serialize_projection(
        [main.ids["inactive_proposal"], main.ids["inactive_trial"]]
    )
    inactive_projection_ignored = (
        consumer_output(main.store, inactive_state)
        == inactive_output_before_projection
    )

    if execute_reset:
        reset_result = run_reset_worker(repo, projection["projection_raw"])
    else:
        reset_result = {
            **projection["local_validation"],
            "status": "passed",
            "within_bound": True,
            "workspace_empty_before": True,
            "workspace_empty_after": True,
        }
    main.reset_result = reset_result

    replay = main.controller.replay()
    pointer_roles = {
        main.ids["active_parent"]: "active_parent",
        main.ids["proposal"]: "proposal",
    }
    replay_summary = {
        "sequences": [state.sequence for state in replay.states],
        "active_roles": [
            pointer_roles.get(state.active_id, "other") for state in replay.states
        ],
        "actions": [
            main.store.get(state.pointer_event_id)["payload"]["action"]
            for state in replay.states
        ],
    }
    records_after = set(main.store.record_ids)
    required_retained = {
        main.ids["active_parent"],
        main.ids["proposal"],
        main.ids["trial"],
        main.ids["sibling_proposal"],
        main.ids["sibling_trial"],
        main.ids["inactive_proposal"],
        main.ids["inactive_trial"],
    }
    result = {
        "case_index": case_index,
        "record_count": len(main.store),
        "distractor_count": len(main.ids["distractors"]),
        "full_trajectory_bytes": full_bytes,
        "projection_bytes": projection["projection_bytes"],
        "pointer_replay": replay_summary,
        "set_down_preserved_active": main.stage_outputs["set_down"]
        == main.stage_outputs["initial"],
        "adoption_changed_output": main.stage_outputs["adopt"]
        != main.stage_outputs["initial"],
        "rollback_restored_output": main.stage_outputs["rollback"]
        == main.stage_outputs["initial"],
        "inactive_branch_ignored": main.stage_outputs["after_inactive"]
        == main.stage_outputs["rollback"],
        "inactive_projection_ignored": inactive_projection_ignored,
        "adopted_bytes_exact": canonical_json(
            main.store.get(main.ids["proposal"])
        )
        == main.ids["proposal_before"],
        "branches_retained": required_retained <= records_after,
        "append_only_growth": set(main.ids["record_ids_before_inactive"])
        < records_after,
        "projection": {
            "proposal_exclusion_rejected": projection[
                "proposal_exclusion_rejected"
            ],
            "trial_exclusion_rejected": projection["trial_exclusion_rejected"],
            "overbudget_rejected": projection["overbudget_rejected"],
            "external_parent_count": reset_result["external_parent_count"],
        },
        "reset": {
            "status": reset_result["status"],
            "pass": reset_result["pass"],
            "within_bound": reset_result["within_bound"],
            "projected_record_count": reset_result["projected_record_count"],
            "external_parent_lookup": reset_result["external_parent_lookup"],
            "unrelated_lookup": reset_result["unrelated_lookup"],
            "controller_store_serialized": reset_result[
                "controller_store_serialized"
            ],
            "workspace_empty_before": reset_result["workspace_empty_before"],
            "workspace_empty_after": reset_result["workspace_empty_after"],
        },
        "decision_controls": decision_intervention_controls(main, case_index),
        "provenance_controls": provenance_controls(main, case_index),
        "pointer_controls": pointer_failure_controls(case_index),
        "quality_placebo": _quality_placebo(case_index),
        "order_placebo": order_placebo,
        "alpha_placebo": alpha_placebo,
        "consumer_trial_unreachable": "trial"
        not in inspect.getsource(consumer_output).lower()
        and "replay_pointer" not in consumer_output.__code__.co_names,
        "normalized": main_normalized,
        "record_identity_sha256": sha256_bytes(canonical_json(core_ids)),
        "full_trajectory_sha256": sha256_bytes(full_serialized),
        "projection_sha256": sha256_bytes(projection["projection_raw"]),
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
    }
    result["pass"] = (
        result["distractor_count"] == DISTRACTOR_COUNT
        and result["full_trajectory_bytes"] >= MINIMUM_FULL_TRAJECTORY_BYTES
        and result["projection_bytes"] <= PROJECTION_BYTE_LIMIT
        and result["pointer_replay"]
        == {
            "sequences": [0, 1, 2, 3],
            "active_roles": [
                "active_parent",
                "active_parent",
                "proposal",
                "active_parent",
            ],
            "actions": ["initialize", "set_down", "adopt", "rollback"],
        }
        and result["set_down_preserved_active"]
        and result["adoption_changed_output"]
        and result["rollback_restored_output"]
        and result["inactive_branch_ignored"]
        and result["inactive_projection_ignored"]
        and result["adopted_bytes_exact"]
        and result["branches_retained"]
        and result["append_only_growth"]
        and all(result["projection"].values())
        and result["projection"]["external_parent_count"] == 1
        and result["reset"]["pass"]
        and result["reset"]["projected_record_count"] == 2
        and not result["reset"]["external_parent_lookup"]
        and not result["reset"]["unrelated_lookup"]
        and not result["reset"]["controller_store_serialized"]
        and result["reset"]["workspace_empty_before"]
        and result["reset"]["workspace_empty_after"]
        and result["reset"]["within_bound"]
        and all(result["decision_controls"].values())
        and all(result["provenance_controls"].values())
        and all(result["pointer_controls"].values())
        and result["quality_placebo"]["pass"]
        and result["order_placebo"]
        and result["alpha_placebo"]
        and result["consumer_trial_unreachable"]
        and not result["candidate_outputs"]
        and result["actor_turns"] == 0
        and result["actor_tool_calls"] == 0
        and result["hosted_model_calls"] == 0
    )
    result["receipt_sha256"] = sha256_bytes(canonical_json(result))
    return result


def _normalized_case_roles(result: dict[str, Any]) -> list[dict[str, Any]]:
    reset = dict(result["reset"])
    roles = {
        "authority": {
            "pointer_replay": result["pointer_replay"],
            "set_down_preserved_active": result["set_down_preserved_active"],
            "adoption_changed_output": result["adoption_changed_output"],
            "rollback_restored_output": result["rollback_restored_output"],
            "inactive_branch_ignored": result["inactive_branch_ignored"],
            "inactive_projection_ignored": result[
                "inactive_projection_ignored"
            ],
            "adopted_bytes_exact": result["adopted_bytes_exact"],
            "branches_retained": result["branches_retained"],
            "append_only_growth": result["append_only_growth"],
            "consumer_trial_unreachable": result["consumer_trial_unreachable"],
        },
        "decision-controls": result["decision_controls"],
        "exact-fixture": {
            "record_identity_sha256": result["record_identity_sha256"],
            "full_trajectory_sha256": result["full_trajectory_sha256"],
            "projection_sha256": result["projection_sha256"],
        },
        "provenance-controls": result["provenance_controls"],
        "pointer-controls": result["pointer_controls"],
        "projection-reset": {"projection": result["projection"], "reset": reset},
        "quality-placebo": result["quality_placebo"],
        "renaming-order-placebos": {
            "alpha": result["alpha_placebo"],
            "order": result["order_placebo"],
        },
        "resources": {
            "candidate_outputs": result["candidate_outputs"],
            "actor_turns": result["actor_turns"],
            "actor_tool_calls": result["actor_tool_calls"],
            "hosted_model_calls": result["hosted_model_calls"],
            "distractor_count": result["distractor_count"],
            "full_trajectory_bytes": result["full_trajectory_bytes"],
            "projection_bytes": result["projection_bytes"],
        },
    }
    return [
        {"case_index": result["case_index"], "role": role, "result": value}
        for role, value in sorted(roles.items())
    ]


def _reset_operational_failure(reset: dict[str, Any]) -> str | None:
    """Map all reset outcomes onto the frozen public failure vocabulary."""

    status = reset.get("status")
    within_bound = reset.get("within_bound")
    if status == "passed" and within_bound is True:
        return None
    if status == "timeout" or within_bound is False:
        return "reset_timeout"
    return "calibration_failed"


def _validate_acceptance(acceptance: dict[str, Any]) -> None:
    expected = {
        "scenario_indices": list(CASE_INDICES),
        "run_order": ["forward-1", "reverse-1", "forward-2", "reverse-2"],
        "forward_case_order": list(CASE_INDICES),
        "reverse_case_order": list(reversed(CASE_INDICES)),
        "projection_byte_limit": PROJECTION_BYTE_LIMIT,
        "minimum_full_trajectory_bytes": MINIMUM_FULL_TRAJECTORY_BYTES,
        "distractor_count": DISTRACTOR_COUNT,
        "distractor_padding_bytes": DISTRACTOR_PADDING_BYTES,
        "trace_row_count": TRACE_ROW_COUNT,
        "maximum_record_bytes": MAXIMUM_RECORD_BYTES,
        "candidate_outputs": False,
        "hosted_model_calls": 0,
        "authorized_candidate_count": 0,
    }
    for key, value in expected.items():
        if acceptance.get(key) != value:
            raise RuntimeError(f"OT-0070 acceptance field {key} differs")
    resource = acceptance.get("resource_budget")
    if resource != {
        "wall_seconds": WALL_SECONDS,
        "fresh_reset_process_seconds": RESET_PROCESS_SECONDS,
        "maximum_raw_artifact_bytes": MAXIMUM_RAW_ARTIFACT_BYTES,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_calls": 0,
    }:
        raise RuntimeError("OT-0070 resource budget differs")


def _calibration_disposition(gates: dict[str, bool]) -> str:
    if all(gates.values()):
        return "promoted"
    operational = {
        "wall_time",
        "reset_time",
        "bounded_execution",
        "artifact_size",
        "candidate_free",
        "actor_free",
        "hosted_free",
        "authorizes_no_learner",
        "tests",
        "audit",
    }
    if any(not value for name, value in gates.items() if name in operational):
        return "invalidated"
    return "rejected"


def _failed_case_receipt(case_index: int, code: str) -> dict[str, Any]:
    body = {
        "case_index": case_index,
        "role": "operational-failure",
        "result": {"code": code},
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def assemble_calibration_result(
    acceptance: dict[str, Any],
    runs: list[dict[str, Any]],
    *,
    wall_within_bound: bool,
) -> dict[str, Any]:
    """Pure deterministic aggregation for public reconstruction and tests."""

    _validate_acceptance(acceptance)
    normalized_hashes = [item["normalized_sha256"] for item in runs]
    compact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "run_order": [item["run"] for item in runs],
        "runs": runs,
        "case_evaluation_count": sum(len(item["case_order"]) for item in runs),
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "authorized_candidate_count": 0,
        "operational_failure": None,
    }
    gates = {
        "exact_run_order": compact["run_order"] == acceptance["run_order"],
        "all_cases_pass": all(
            item["passing_case_count"] == len(CASE_INDICES) for item in runs
        ),
        "normalized_replay": len(normalized_hashes) == 4
        and len(set(normalized_hashes)) == 1,
        "bounded_execution": all(
            not item["operational_failures"] for item in runs
        ),
        "wall_time": wall_within_bound,
        "reset_time": all(item["reset_within_bound"] for item in runs),
        "artifact_size": True,
        "candidate_free": True,
        "actor_free": True,
        "hosted_free": True,
        "authorizes_no_learner": True,
    }
    result = {
        **compact,
        "artifact_bytes": 0,
        "gates": gates,
        "calibration_pass": False,
        "disposition": "rejected",
    }
    for _ in range(4):
        result["artifact_bytes"] = len(canonical_json(result))
        result["gates"]["artifact_size"] = (
            result["artifact_bytes"] <= MAXIMUM_RAW_ARTIFACT_BYTES
        )
        result["calibration_pass"] = all(result["gates"].values())
        result["disposition"] = _calibration_disposition(result["gates"])
    if len(canonical_json(result)) != result["artifact_bytes"]:
        raise RuntimeError("OT-0070 artifact-size receipt did not stabilize")
    return result


def run_calibration(repo: Path, *, deadline: float | None = None) -> dict[str, Any]:
    """Execute the exact frozen four-run sequence.

    This function is intentionally not called at import time or by unit tests.
    """

    repo = repo.resolve()
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    _validate_acceptance(acceptance)
    if deadline is None:
        deadline = time.monotonic() + WALL_SECONDS
    runs: list[dict[str, Any]] = []
    for run_label in acceptance["run_order"]:
        case_order = (
            acceptance["forward_case_order"]
            if run_label.startswith("forward")
            else acceptance["reverse_case_order"]
        )
        normalized: list[dict[str, Any]] = []
        case_receipts: list[tuple[int, str]] = []
        passing_case_count = 0
        reset_within_bound = True
        operational_failures: list[dict[str, Any]] = []
        for case_index in case_order:
            if time.monotonic() >= deadline:
                return _calibration_failure_summary(
                    acceptance,
                    "calibration_timeout",
                    wall_within_bound=False,
                )
            try:
                case_result = evaluate_case(
                    case_index, repo=repo, execute_reset=True
                )
            except Exception:  # Preserve no exception-dependent public bytes.
                return _calibration_failure_summary(
                    acceptance,
                    "calibration_failed",
                    wall_within_bound=time.monotonic() <= deadline,
                )
            if time.monotonic() > deadline:
                return _calibration_failure_summary(
                    acceptance,
                    "calibration_timeout",
                    wall_within_bound=False,
                )
            reset = case_result["reset"]
            code = _reset_operational_failure(reset)
            if code is not None:
                return _calibration_failure_summary(
                    acceptance,
                    code,
                    wall_within_bound=time.monotonic() <= deadline,
                )
            normalized.extend(_normalized_case_roles(case_result))
            case_receipts.append(
                (case_index, case_result["receipt_sha256"])
            )
            passing_case_count += int(case_result["pass"])
            reset_within_bound = (
                reset_within_bound and case_result["reset"]["within_bound"]
            )
        normalized.sort(key=lambda item: (item["case_index"], item["role"]))
        runs.append(
            {
                "run": run_label,
                "case_order": list(case_order),
                "passing_case_count": passing_case_count,
                "case_receipts": sorted(case_receipts),
                "normalized": normalized,
                "normalized_sha256": sha256_bytes(canonical_json(normalized)),
                "reset_within_bound": reset_within_bound,
                "operational_failures": operational_failures,
            }
        )
    if time.monotonic() > deadline:
        return _calibration_failure_summary(
            acceptance, "calibration_timeout", wall_within_bound=False
        )
    return assemble_calibration_result(
        acceptance,
        runs,
        wall_within_bound=True,
    )


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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_output_contract(
    repo: Path,
    run_id: str,
    output: Path,
    *,
    allow_existing_manifest: bool = False,
) -> dict[str, Path]:
    """Fail before execution unless raw and manifest identities are exact/fresh."""

    repo = repo.resolve()
    if run_id != DEFAULT_RUN_ID:
        raise RuntimeError("OT-0070 run identity differs from the frozen default")
    store = default_store(repo).resolve()
    allowed_in_repo_store = (repo / ".evidence").resolve()
    if _is_relative_to(store, repo) and not _is_relative_to(
        store, allowed_in_repo_store
    ):
        raise RuntimeError("OT-0070 in-repository evidence root is not .evidence")
    expected_output = expected_output_path(repo)
    if output.resolve() != expected_output:
        raise RuntimeError("OT-0070 output path differs from the frozen location")
    if _is_relative_to(expected_output, repo) and (repo / ".git").exists():
        relative_output = expected_output.relative_to(repo)
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(relative_output)],
            cwd=repo,
        )
        if ignored.returncode != 0:
            raise RuntimeError("OT-0070 in-repository evidence output is not ignored")
    manifest = expected_manifest_path(repo)
    failure_root = store / "failures" / EXPERIMENT_ID
    failed_manifest = failure_root / f"{DEFAULT_RUN_ID}-manifest.json"
    failure_receipt = failure_root / f"{DEFAULT_RUN_ID}-post-audit.json"
    if expected_output.exists():
        raise RuntimeError("OT-0070 raw output already exists")
    if manifest.exists() and not allow_existing_manifest:
        raise RuntimeError("OT-0070 evidence manifest already exists")
    if failed_manifest.exists() or failure_receipt.exists():
        raise RuntimeError("OT-0070 prior publication-failure evidence exists")
    return {
        "store": store,
        "output": expected_output,
        "manifest": manifest,
        "failed_manifest": failed_manifest,
        "failure_receipt": failure_receipt,
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    if lock.get("schema_version") != 1 or lock.get("experiment_id") != EXPERIMENT_ID:
        raise RuntimeError("OT-0070 run lock identity differs")
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0070 run lock omits implementation identity")
    protocol_origin = git_output(
        repo, "rev-parse", f"{PROTOCOL_ORIGIN_COMMIT}^{{commit}}"
    )
    if lock.get("protocol_origin_git_commit") != protocol_origin:
        raise RuntimeError("OT-0070 protocol origin identity differs")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", protocol_origin, implementation],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0070 implementation predates the frozen protocol")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0070 implementation is not an execution ancestor")
    execution_parent = git_output(repo, "rev-parse", f"{execution_commit}^")
    if execution_parent != implementation:
        raise RuntimeError("OT-0070 execution is not the direct run-lock child")
    implementation_tree = git_output(
        repo, "rev-parse", f"{implementation}^{{tree}}"
    )
    if lock.get("implementation_git_tree") != implementation_tree:
        raise RuntimeError("OT-0070 implementation tree identity differs")
    protocol_changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{protocol_origin}..{execution_commit}",
        "--",
        *(str(path) for path in PROTOCOL_FROZEN_PATHS),
    )
    if protocol_changed:
        raise RuntimeError(
            f"OT-0070 frozen protocol changed after origin: {protocol_changed}"
        )
    fixed_paths = fixed_input_paths(repo)
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_paths.items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0070 fixed runtime identity differs")
    tree_delta = git_output(
        repo,
        "diff",
        "--name-status",
        f"{implementation}..{execution_commit}",
    )
    expected_delta = f"A\t{RUN_LOCK_PATH.as_posix()}"
    if tree_delta != expected_delta:
        raise RuntimeError(
            "OT-0070 execution tree differs from implementation plus run lock"
        )
    return lock


def _bounded_command(
    command: list[str], repo: Path, deadline: float, *, stage: str
) -> dict[str, Any]:
    if stage not in {"tests", "audit"}:
        raise ValueError("OT-0070 bounded stage is unavailable")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {
            "status": f"{stage}_timeout",
            "returncode": None,
            "within_bound": False,
        }
    try:
        process = subprocess.run(
            command,
            cwd=repo,
            env=child_environment(repo),
            capture_output=True,
            text=True,
            timeout=remaining,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": f"{stage}_timeout",
            "returncode": None,
            "within_bound": False,
        }
    except OSError:
        within_bound = time.monotonic() <= deadline
        return {
            "status": (
                f"{stage}_failed" if within_bound else f"{stage}_timeout"
            ),
            "returncode": None,
            "within_bound": within_bound,
        }
    within_bound = time.monotonic() <= deadline
    return {
        "status": (
            "passed"
            if process.returncode == 0 and within_bound
            else f"{stage}_timeout"
            if not within_bound
            else f"{stage}_failed"
        ),
        "returncode": process.returncode,
        "within_bound": within_bound,
    }


def _calibration_failure_summary(
    acceptance: dict[str, Any], code: str, *, wall_within_bound: bool
) -> dict[str, Any]:
    """Return one compact invalidation, never a timing-dependent run prefix."""

    _validate_acceptance(acceptance)
    if code not in _CALIBRATION_FAILURE_CODES:
        raise ValueError("OT-0070 calibration failure code is unavailable")
    if type(wall_within_bound) is not bool:
        raise TypeError("OT-0070 wall-bound verdict must be boolean")
    gates = {
        "exact_run_order": False,
        "all_cases_pass": False,
        "normalized_replay": False,
        "bounded_execution": False,
        "wall_time": wall_within_bound,
        "reset_time": False,
        "artifact_size": True,
        "candidate_free": True,
        "actor_free": True,
        "hosted_free": True,
        "authorizes_no_learner": True,
    }
    summary = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "run_order": acceptance["run_order"],
        "runs": [],
        "case_evaluation_count": 0,
        "partial_results_retained": False,
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "authorized_candidate_count": 0,
        "operational_failure": code,
        "artifact_bytes": 0,
        "gates": gates,
        "calibration_pass": False,
        "disposition": "invalidated",
    }
    for _ in range(8):
        summary["artifact_bytes"] = len(canonical_json(summary))
    if len(canonical_json(summary)) != summary["artifact_bytes"]:
        raise RuntimeError("OT-0070 invalidation-size receipt did not stabilize")
    return summary


def _validated_stage_receipt(
    receipt: dict[str, Any], stage: str
) -> dict[str, Any]:
    if stage not in {"tests", "audit"}:
        raise ValueError("OT-0070 verification stage is unavailable")
    value = _exact_keys(
        receipt, {"returncode", "status", "within_bound"}, f"{stage} receipt"
    )
    status = value["status"]
    allowed = {"passed", f"{stage}_timeout", f"{stage}_failed"}
    if status not in allowed:
        raise ProtocolError(f"{stage} receipt status is unavailable")
    if type(value["within_bound"]) is not bool:
        raise ProtocolError(f"{stage} receipt bound verdict is not boolean")
    returncode = value["returncode"]
    if returncode is not None and type(returncode) is not int:
        raise ProtocolError(f"{stage} receipt return code is invalid")
    if status == "passed" and (
        returncode != 0 or not value["within_bound"]
    ):
        raise ProtocolError(f"{stage} passed receipt is inconsistent")
    if status == f"{stage}_timeout" and value["within_bound"]:
        raise ProtocolError(f"{stage} timeout receipt is inconsistent")
    if status == f"{stage}_failed" and (
        returncode == 0 or not value["within_bound"]
    ):
        raise ProtocolError(f"{stage} failure receipt is inconsistent")
    return json.loads(canonical_json(value))


def _compact_invalidation_summary(
    summary: dict[str, Any], code: str, gates: dict[str, bool]
) -> dict[str, Any]:
    if code not in _OPERATIONAL_FAILURE_CODES:
        raise ValueError("OT-0070 operational failure code is unavailable")
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": summary["claim_limit"],
        "run_order": summary.get("run_order", []),
        "runs": [],
        "case_evaluation_count": 0,
        "partial_results_retained": False,
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "authorized_candidate_count": 0,
        "operational_failure": code,
        "gates": gates,
        "calibration_pass": False,
        "disposition": "invalidated",
    }


def _stabilize_raw_artifact(raw: dict[str, Any]) -> dict[str, Any]:
    for _ in range(16):
        observed = len(canonical_json(raw))
        if raw["raw_artifact_bytes"] == observed:
            return raw
        raw["raw_artifact_bytes"] = observed
    raise RuntimeError("OT-0070 raw artifact-size receipt did not stabilize")


def build_raw_artifact(
    *,
    run_id: str,
    implementation_commit: str,
    execution_commit: str,
    summary: dict[str, Any],
    tests: dict[str, Any],
    audit: dict[str, Any],
    complete_run_within_bound: bool,
) -> dict[str, Any]:
    """Build deterministic public bytes from statuses, never observed durations."""

    if run_id != DEFAULT_RUN_ID:
        raise ValueError("OT-0070 raw artifact run identity differs")
    for label, commit in (
        ("implementation", implementation_commit),
        ("execution", execution_commit),
    ):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError(f"OT-0070 {label} commit identity is malformed")
    if type(complete_run_within_bound) is not bool:
        raise TypeError("OT-0070 complete-run bound verdict must be boolean")
    tests_receipt = _validated_stage_receipt(tests, "tests")
    audit_receipt = _validated_stage_receipt(audit, "audit")
    stable_summary = json.loads(canonical_json(summary))
    if stable_summary.get("experiment_id") != EXPERIMENT_ID:
        raise ProtocolError("OT-0070 summary experiment identity differs")
    if type(stable_summary.get("gates")) is not dict or not all(
        type(value) is bool for value in stable_summary["gates"].values()
    ):
        raise ProtocolError("OT-0070 summary gates are malformed")
    gates = {
        **stable_summary["gates"],
        "tests": tests_receipt["status"] == "passed",
        "audit": audit_receipt["status"] == "passed",
        "wall_time": complete_run_within_bound,
        "artifact_size": True,
    }
    failure = stable_summary.get("operational_failure")
    if failure is not None and failure not in _CALIBRATION_FAILURE_CODES:
        raise ProtocolError("OT-0070 summary failure code is unavailable")
    if failure is None and tests_receipt["status"] != "passed":
        failure = tests_receipt["status"]
    if failure is None and audit_receipt["status"] != "passed":
        failure = audit_receipt["status"]
    if failure is None and not complete_run_within_bound:
        failure = "calibration_timeout"

    if failure is None:
        stable_summary["gates"] = gates
        stable_summary["calibration_pass"] = all(gates.values())
        stable_summary["disposition"] = _calibration_disposition(gates)
        if stable_summary["disposition"] == "invalidated":
            if not gates.get("artifact_size", True):
                failure = "artifact_size"
            elif not gates.get("reset_time", True):
                failure = "reset_timeout"
            else:
                failure = "calibration_failed"
    if failure is not None:
        stable_summary = _compact_invalidation_summary(
            stable_summary, failure, gates
        )

    evidence_class = (
        "public-reconstructible"
        if stable_summary["disposition"] in {"promoted", "rejected"}
        else "exploratory-only"
    )

    def envelope(value: dict[str, Any], classification: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "run_id": run_id,
            "implementation_git_commit": implementation_commit,
            "execution_git_commit": execution_commit,
            "evidence_class": classification,
            "raw_artifact_bytes": 0,
            "summary": value,
            "verification": {
                "tests": tests_receipt,
                "audit": audit_receipt,
            },
        }

    raw = _stabilize_raw_artifact(envelope(stable_summary, evidence_class))
    if raw["raw_artifact_bytes"] <= MAXIMUM_RAW_ARTIFACT_BYTES:
        return raw

    oversized_gates = {**gates, "artifact_size": False}
    compact_summary = _compact_invalidation_summary(
        stable_summary, "artifact_size", oversized_gates
    )
    compact_raw = _stabilize_raw_artifact(
        envelope(compact_summary, "exploratory-only")
    )
    if compact_raw["raw_artifact_bytes"] > MAXIMUM_RAW_ARTIFACT_BYTES:
        raise RuntimeError("OT-0070 invalidation artifact exceeds its bound")
    return compact_raw


def _locked_execution_context(
    repo: Path,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0070 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", execution_commit):
        raise RuntimeError("OT-0070 execution identity is malformed")
    lock = validate_run_lock(repo, execution_commit)
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    _validate_acceptance(acceptance)
    return execution_commit, lock, acceptance


def _bounded_calibration(
    repo: Path, acceptance: dict[str, Any], deadline: float
) -> dict[str, Any]:
    """Run the complete calibration behind an outer remaining-time watchdog."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return _calibration_failure_summary(
            acceptance, "calibration_timeout", wall_within_bound=False
        )
    try:
        process = subprocess.run(
            [
                sys.executable,
                "experiments/ot_0070_harness.py",
                "--repo",
                ".",
                "--calibration-worker",
            ],
            cwd=repo,
            env=child_environment(repo),
            capture_output=True,
            timeout=remaining,
        )
    except subprocess.TimeoutExpired:
        return _calibration_failure_summary(
            acceptance, "calibration_timeout", wall_within_bound=False
        )
    except OSError:
        return _calibration_failure_summary(
            acceptance,
            "calibration_failed",
            wall_within_bound=time.monotonic() <= deadline,
        )
    if time.monotonic() > deadline:
        return _calibration_failure_summary(
            acceptance, "calibration_timeout", wall_within_bound=False
        )
    if process.returncode != 0 or process.stderr:
        return _calibration_failure_summary(
            acceptance, "calibration_failed", wall_within_bound=True
        )
    try:
        summary = json.loads(process.stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _calibration_failure_summary(
            acceptance, "calibration_failed", wall_within_bound=True
        )
    if type(summary) is not dict or process.stdout != canonical_json(summary):
        return _calibration_failure_summary(
            acceptance, "calibration_failed", wall_within_bound=True
        )
    if (
        summary.get("experiment_id") != EXPERIMENT_ID
        or summary.get("run_order") != acceptance["run_order"]
        or type(summary.get("gates")) is not dict
        or not all(type(value) is bool for value in summary["gates"].values())
    ):
        return _calibration_failure_summary(
            acceptance, "calibration_failed", wall_within_bound=True
        )
    failure = summary.get("operational_failure")
    if failure is not None and failure not in _CALIBRATION_FAILURE_CODES:
        return _calibration_failure_summary(
            acceptance, "calibration_failed", wall_within_bound=True
        )
    return summary


def _execute_locked_raw(
    repo: Path,
    run_id: str,
    execution_commit: str,
    lock: dict[str, Any],
    acceptance: dict[str, Any],
) -> tuple[dict[str, Any], float]:
    """Run deterministic stages under one deadline and build unsealed bytes."""

    deadline = time.monotonic() + WALL_SECONDS
    summary = _bounded_calibration(repo, acceptance, deadline)
    tests = _bounded_command(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        repo,
        deadline,
        stage="tests",
    )
    audit = _bounded_command(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        repo,
        deadline,
        stage="audit",
    )
    raw = build_raw_artifact(
        run_id=run_id,
        implementation_commit=lock["implementation_git_commit"],
        execution_commit=execution_commit,
        summary=summary,
        tests=tests,
        audit=audit,
        complete_run_within_bound=time.monotonic() <= deadline,
    )
    return raw, deadline


def reconstruct(
    repo: Path, run_id: str, output: Path
) -> tuple[Path, dict[str, Any]]:
    """Rebuild raw bytes without manifest publication side effects."""

    repo = repo.resolve()
    output_contract = validate_output_contract(
        repo,
        run_id,
        output,
        allow_existing_manifest=True,
    )
    execution_commit, lock, acceptance = _locked_execution_context(repo)
    raw, _deadline = _execute_locked_raw(
        repo, run_id, execution_commit, lock, acceptance
    )
    write_sealed_json(output_contract["output"], raw)
    return output_contract["output"], raw["summary"]


def _quarantine_failed_publication(
    *,
    manifest: Path,
    failed_manifest: Path,
    failure_receipt: Path,
    run_id: str,
    post_manifest_audit: dict[str, Any],
) -> None:
    """Remove failed publication authority while preserving bounded forensics."""

    audit_receipt = _validated_stage_receipt(post_manifest_audit, "audit")
    if audit_receipt["status"] == "passed":
        raise ValueError("OT-0070 cannot quarantine a passing publication audit")
    if failed_manifest.exists() or failure_receipt.exists():
        raise RuntimeError("OT-0070 publication-failure destination exists")
    copied = False
    try:
        failed_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(manifest, failed_manifest)
        if sha256_file(manifest) != sha256_file(failed_manifest):
            failed_manifest.unlink(missing_ok=True)
            raise RuntimeError("OT-0070 failed-manifest copy differs")
        failed_manifest.chmod(0)
        copied = True
    finally:
        # The final tracked path is publication authority.  A failed final
        # audit must never leave that authority in place, even if quarantine
        # storage itself fails.
        manifest.unlink(missing_ok=True)
    receipt = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "operational_failure": audit_receipt["status"],
        "public_manifest_retained": False,
        "raw_artifact_retained": True,
        "failed_manifest_retained": copied,
    }
    write_sealed_json(failure_receipt, receipt)


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    """Execute only from a clean, prospectively locked commit and record evidence."""

    repo = repo.resolve()
    output_contract = validate_output_contract(repo, run_id, output)
    execution_commit, lock, acceptance = _locked_execution_context(repo)
    raw, deadline = _execute_locked_raw(
        repo, run_id, execution_commit, lock, acceptance
    )
    write_sealed_json(output_contract["output"], raw)
    output_contract["output"].chmod(0o600)
    try:
        if output_contract["manifest"].exists():
            raise EvidenceError("OT-0070 evidence manifest collision")
        manifest = record_artifact(
            repo=repo,
            input_path=output_contract["output"],
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="trajectory-authority-candidate-free-calibration",
            evidence_class=raw["evidence_class"],
            recipe=(
                RECONSTRUCTION_RECIPE
                if raw["evidence_class"] == "public-reconstructible"
                else None
            ),
            public_url=None,
            limitations=[
                "Candidate output, actor turns, and hosted calls are forbidden.",
                "Synthetic fixture decisions are not evidence of useful judgment.",
                "A pass authorizes no learner and establishes only procedural mechanics.",
            ],
            input_manifests=[],
            store=output_contract["store"],
        )
    finally:
        output_contract["output"].chmod(0)
    post_manifest_audit = _bounded_command(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        repo,
        deadline,
        stage="audit",
    )
    if post_manifest_audit["status"] != "passed" or not post_manifest_audit[
        "within_bound"
    ]:
        _quarantine_failed_publication(
            manifest=manifest,
            failed_manifest=output_contract["failed_manifest"],
            failure_receipt=output_contract["failure_receipt"],
            run_id=run_id,
            post_manifest_audit=post_manifest_audit,
        )
        raise RuntimeError(
            "OT-0070 post-manifest audit failed; public authority was quarantined"
        )
    return manifest, raw["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0070-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reconstruct-only", action="store_true")
    parser.add_argument(
        "--calibration-worker", action="store_true", help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    if args.calibration_worker:
        if args.output is not None or args.reconstruct_only:
            parser.error("calibration worker accepts no output mode")
        try:
            summary = run_calibration(args.repo.resolve())
        except (OSError, RuntimeError, ValueError):
            return 2
        sys.stdout.buffer.write(canonical_json(summary))
        return 0
    if args.output is None:
        parser.error("--output is required")
    try:
        operation = reconstruct if args.reconstruct_only else run
        result_path, summary = operation(
            args.repo.resolve(), args.run_id, args.output.resolve()
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                (
                    "output"
                    if args.reconstruct_only
                    else "manifest"
                ): (
                    f"$EVIDENCE/runs/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
                    if args.reconstruct_only
                    else str(result_path.relative_to(args.repo.resolve()))
                ),
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
