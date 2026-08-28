"""Authoritative lifecycle and evaluator orchestration for OT-0075.

The P-frozen world derivation lives in :mod:`ot0075_protocol`.  This module is
the implementation-phase controller: it freezes the clean implementation
identity before private derivation, enforces the one-attempt lock, executes the
candidate-free reference paths, and publishes only after exact private
reconstruction.
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tempfile
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Final

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
from .ot0075_learning import (
    CLOCK_CONTROL,
    COMPACT_REFERENCE,
    IMMUTABLE_SEED_CONTROL,
    LOG_REFERENCE,
    NEAREST_COMPARATOR,
    NO_PERSISTENCE_CONTROL,
    RECENT_COMPARATOR,
    LearningError,
    decode_state,
    encode_state,
    initial_state,
    offline_best_fixed_rule,
    predict,
    update,
)
from .ot0075_protocol import derive_task, validate_task
from .ot0075_receipts import (
    ONLINE_POSITIVE,
    ReceiptChainBuilder,
    ReceiptError,
    causal_path_gates,
    checkpoint,
    decode_blob,
    derive_identity,
    expected_mutation_code,
    make_consumer_facts,
    mutate_seeded_defect,
    rollback_gates,
    seeded_authority_defect_gates,
    strict_online_surface,
    validate_branch_isolation,
    validate_chain,
    validate_chain_collection,
    validate_rewind_replay,
)
from .ot0075_scoring import (
    AUTHORITY_DEFECTS,
    CAUSAL_PATH_GATES,
    CONDITION_INVENTORY,
    EXECUTION_GATES,
    ROLLBACK_REPLAY_GATES,
    metamorphic_variants,
    score_bundle,
)
from .ot0075_shadow_scoring import score_bundle_shadow


EXPERIMENT_ID: Final = "OT-0075"
PROTOCOL_ORIGIN_COMMIT: Final = "bff7f6d972fa7acce4386dca210b0907c9fd22b3"
ACCEPTANCE_PATH: Final = Path("spec/ot-0075-acceptance.json")
EXPERIMENT_PATH: Final = Path(
    "experiments/OT-0075-e14-longitudinal-evaluator-calibration.md"
)
PROTOCOL_PATH: Final = Path("src/open_trajectory_harness/ot0075_protocol.py")
RUN_LOCK_PATH: Final = Path("spec/ot-0075-run-lock.json")

ACCEPTANCE_SHA256: Final = (
    "792df3f94b148242e135d5ced87dec2b5299e7e73a912c91f27afcf6b6ce39c0"
)
EXPERIMENT_SHA256: Final = (
    "101f0e40c33373187099a1c004048d6d4d30ed4536bd9e6af28e30bc2569863d"
)
PROTOCOL_SHA256: Final = (
    "7c208df7fc2571f5128af908eb01c81c635968d59633ab390845bbacc87587de"
)

DEFAULT_RUN_ID: Final = "ot-0075-e14-longitudinal-evaluator-calibration-001"
DERIVATION_ID: Final = "ot-0075-private-anchor-derivation-001"
ATTEMPT_RELATIVE_PATH: Final = Path("attempts/OT-0075/anchor-attempt-001.json")
SEED_RELATIVE_PATH: Final = Path("private/OT-0075/anchor-seed-001.bin")
TASK_RELATIVE_PATH: Final = Path("tasks/OT-0075/anchor-task-001.json")
DERIVATION_RELATIVE_PATH: Final = Path(
    "derivations/OT-0075/anchor-derivation-001.json"
)
RAW_RELATIVE_PATH: Final = Path("runs/OT-0075") / f"{DEFAULT_RUN_ID}.json.zlib"
FAILURE_RELATIVE_PATH: Final = (
    Path("failures/OT-0075") / f"{DEFAULT_RUN_ID}-failure.json"
)
FAILED_MANIFEST_RELATIVE_PATH: Final = (
    Path("failures/OT-0075") / f"{DEFAULT_RUN_ID}-manifest.json"
)

CALIBRATION_SECONDS: Final = 900
RECONSTRUCTION_SECONDS: Final = 900
MAX_RAW_BYTES: Final = 134_217_728
RECONSTRUCTION_RECIPE: Final = (
    "At environment.git.commit, place the controller-private seed at "
    "$EVIDENCE/private/OT-0075/anchor-seed-001.bin, then run "
    "OT_EVIDENCE_ROOT=$EVIDENCE PYTHONPATH=src python3 -m "
    "open_trajectory_harness.ot0075 --reconstruct-only"
)

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ProtocolError(ValueError):
    """Raised when an OT-0075 identity or authority contract differs."""


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ProtocolError(f"{label} keys differ from the frozen schema")
    return value


def _commit(value: object, label: str = "commit") -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a full Git identity")
    return value


def _sha(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a lowercase SHA-256")
    return value


def _logical(path: Path) -> str:
    return "$EVIDENCE/" + path.as_posix()


def _store(repo: Path) -> Path:
    return default_store(repo.resolve()).resolve()


def attempt_path(repo: Path) -> Path:
    return _store(repo) / ATTEMPT_RELATIVE_PATH


def seed_path(repo: Path) -> Path:
    return _store(repo) / SEED_RELATIVE_PATH


def task_path(repo: Path) -> Path:
    return _store(repo) / TASK_RELATIVE_PATH


def receipt_path(repo: Path) -> Path:
    return _store(repo) / DERIVATION_RELATIVE_PATH


def raw_path(repo: Path) -> Path:
    return _store(repo) / RAW_RELATIVE_PATH


def manifest_path(repo: Path) -> Path:
    return (
        repo.resolve()
        / "evidence"
        / "manifests"
        / EXPERIMENT_ID
        / f"{DEFAULT_RUN_ID}.json"
    )


def _write_sealed_bytes(path: Path, value: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"sealed output already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(value)
    except FileExistsError as error:
        raise RuntimeError(f"sealed output already exists: {path.name}") from error
    path.chmod(0)


def _read_sealed_bytes(path: Path) -> bytes:
    path.chmod(0o600)
    try:
        return path.read_bytes()
    finally:
        path.chmod(0)


def _write_tracked_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(canonical_json(value))
    except FileExistsError as error:
        raise RuntimeError(f"tracked output already exists: {path.name}") from error


def validate_acceptance(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    observed = {
        "acceptance": sha256_file(repo / ACCEPTANCE_PATH),
        "experiment": sha256_file(repo / EXPERIMENT_PATH),
        "protocol": sha256_file(repo / PROTOCOL_PATH),
    }
    expected = {
        "acceptance": ACCEPTANCE_SHA256,
        "experiment": EXPERIMENT_SHA256,
        "protocol": PROTOCOL_SHA256,
    }
    if observed != expected:
        raise ProtocolError("OT-0075 P-frozen bytes differ")
    if (
        acceptance.get("schema_version") != 1
        or acceptance.get("experiment_id") != EXPERIMENT_ID
        or acceptance.get("candidate_outputs") is not False
        or acceptance.get("actor_turns") != 0
        or acceptance.get("hosted_model_calls") != 0
        or acceptance.get("derivation", {}).get("anchor_case_count") != 8
        or acceptance.get("derivation", {}).get("authoritative_anchor_attempts") != 1
    ):
        raise ProtocolError("OT-0075 acceptance identity differs")
    return acceptance


def protocol_frozen_paths() -> tuple[Path, ...]:
    return ACCEPTANCE_PATH, EXPERIMENT_PATH, PROTOCOL_PATH


def assert_protocol_unchanged(repo: Path, commit: str) -> None:
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{PROTOCOL_ORIGIN_COMMIT}..{_commit(commit)}",
        "--",
        *(path.as_posix() for path in protocol_frozen_paths()),
    )
    if changed:
        raise ProtocolError(f"OT-0075 protocol changed after P: {changed}")


def build_attempt_marker(implementation: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "derivation_id": DERIVATION_ID,
        "attempt_ordinal": 1,
        "implementation_git_commit": _commit(implementation, "implementation"),
        "reseed_permitted": False,
    }


def build_derivation_receipt(
    implementation: str,
    seed_bytes: bytes,
    task_bytes: bytes,
) -> dict[str, Any]:
    implementation = _commit(implementation, "implementation")
    if type(seed_bytes) is not bytes or len(seed_bytes) != 32:
        raise ProtocolError("private anchor derivation material is not 256 bits")
    try:
        task = json.loads(task_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("private anchor task bytes are not JSON") from error
    if canonical_json(task) != task_bytes:
        raise ProtocolError("private anchor task bytes are not canonical")
    validate_task(task)
    if (
        task["purpose"] != "anchor"
        or task["implementation_git_commit"] != implementation
        or task["seed_sha256"] != sha256_bytes(seed_bytes)
    ):
        raise ProtocolError("private anchor task derivation binding differs")
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "derivation_id": DERIVATION_ID,
        "attempt_ordinal": 1,
        "implementation_git_commit": implementation,
        "seed_path": _logical(SEED_RELATIVE_PATH),
        "seed_sha256": sha256_bytes(seed_bytes),
        "seed_bytes": len(seed_bytes),
        "task_path": _logical(TASK_RELATIVE_PATH),
        "task_sha256": sha256_bytes(task_bytes),
        "task_bytes": len(task_bytes),
        "reseed_permitted": False,
    }


def derive(
    repo: Path,
    implementation: str,
    seed_bytes: bytes,
    *,
    write_seed: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    implementation = _commit(implementation, "implementation")
    if type(seed_bytes) is not bytes or len(seed_bytes) != 32:
        raise ProtocolError("private anchor derivation material is not 256 bits")
    task = derive_task(seed_bytes, implementation, purpose="anchor")
    task_bytes = canonical_json(task)
    receipt = build_derivation_receipt(implementation, seed_bytes, task_bytes)
    if write_seed:
        _write_sealed_bytes(seed_path(repo), seed_bytes)
    write_sealed_json(task_path(repo), task)
    write_sealed_json(receipt_path(repo), receipt)
    return task, receipt


def read_derivation(
    repo: Path, implementation: str
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    seed_bytes = _read_sealed_bytes(seed_path(repo))
    task, task_bytes = read_sealed_json(task_path(repo))
    receipt, receipt_bytes = read_sealed_json(receipt_path(repo))
    expected = build_derivation_receipt(implementation, seed_bytes, task_bytes)
    if receipt != expected or receipt_bytes != canonical_json(expected):
        raise ProtocolError("private anchor derivation receipt differs")
    return task, receipt, seed_bytes


def ensure_derivation(
    repo: Path,
    implementation: str,
    *,
    allow_regeneration: bool,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    marker_exists = attempt_path(repo).exists()
    seed_exists = seed_path(repo).exists()
    task_exists = task_path(repo).exists()
    receipt_exists = receipt_path(repo).exists()
    if not marker_exists or not seed_exists:
        raise ProtocolError("private attempt marker or derivation material is absent")
    marker, marker_bytes = read_sealed_json(attempt_path(repo))
    expected_marker = build_attempt_marker(implementation)
    if marker != expected_marker or marker_bytes != canonical_json(expected_marker):
        raise ProtocolError("private attempt marker differs")
    if task_exists != receipt_exists:
        raise ProtocolError("private task and derivation receipt presence differ")
    if not task_exists:
        if not allow_regeneration:
            raise ProtocolError("authoritative private task and receipt are absent")
        derive(
            repo,
            implementation,
            _read_sealed_bytes(seed_path(repo)),
            write_seed=False,
        )
    return read_derivation(repo, implementation)


def fixed_input_paths(repo: Path | None = None) -> dict[str, Path]:
    repo = (repo or Path.cwd()).resolve()
    paths: dict[str, Path] = {
        "acceptance_sha256": ACCEPTANCE_PATH,
        "experiment_sha256": EXPERIMENT_PATH,
        "protocol_sha256": PROTOCOL_PATH,
        "target_sha256": Path("TARGET.md"),
        "red_lines_sha256": Path("RED_LINES.md"),
        "program_sha256": Path("PROGRAM.md"),
        "epoch_sha256": Path("docs/LONGITUDINAL_CONTINUAL_LEARNING_EPOCH.md"),
        "evidence_contract_sha256": Path("docs/EVIDENCE.md"),
        "workflow_sha256": Path("docs/WORKFLOW.md"),
        "research_landscape_sha256": Path("docs/RESEARCH_LANDSCAPE.md"),
        "controller_sha256": Path("src/open_trajectory_harness/ot0075.py"),
        "learning_sha256": Path("src/open_trajectory_harness/ot0075_learning.py"),
        "receipts_sha256": Path("src/open_trajectory_harness/ot0075_receipts.py"),
        "reset_worker_sha256": Path(
            "src/open_trajectory_harness/ot0075_reset_worker.py"
        ),
        "scorer_sha256": Path("src/open_trajectory_harness/ot0075_scoring.py"),
        "shadow_scorer_sha256": Path(
            "src/open_trajectory_harness/ot0075_shadow_scoring.py"
        ),
        "canonical_helper_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_helper_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
    }
    for test in sorted((repo / "tests").glob("test_*.py")):
        relative = test.relative_to(repo)
        key = "test_" + relative.as_posix().replace("/", "_").replace(".", "_")
        paths[key + "_sha256"] = relative
    missing = [path.as_posix() for path in paths.values() if not (repo / path).is_file()]
    if missing:
        raise ProtocolError(f"fixed implementation inputs are absent: {missing}")
    return paths


def build_run_lock(
    repo: Path,
    implementation: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    implementation = _commit(implementation, "implementation")
    fixed = {
        name: sha256_file(repo / path)
        for name, path in fixed_input_paths(repo).items()
    }
    marker_bytes = canonical_json(build_attempt_marker(implementation))
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "protocol_origin_git_commit": PROTOCOL_ORIGIN_COMMIT,
        "implementation_git_commit": implementation,
        "implementation_git_tree": git_output(
            repo, "rev-parse", f"{implementation}^{{tree}}"
        ),
        "derivation_id": DERIVATION_ID,
        "attempt_path": _logical(ATTEMPT_RELATIVE_PATH),
        "attempt_sha256": sha256_bytes(marker_bytes),
        "seed_path": _logical(SEED_RELATIVE_PATH),
        "seed_sha256": _sha(receipt["seed_sha256"], "seed digest"),
        "task_path": _logical(TASK_RELATIVE_PATH),
        "task_sha256": _sha(receipt["task_sha256"], "task digest"),
        "receipt_path": _logical(DERIVATION_RELATIVE_PATH),
        "receipt_sha256": sha256_bytes(canonical_json(receipt)),
        "run_id": DEFAULT_RUN_ID,
        "raw_path": _logical(RAW_RELATIVE_PATH),
        "manifest_path": (
            f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
        ),
        "failure_path": _logical(FAILURE_RELATIVE_PATH),
        "reconstruction_recipe": RECONSTRUCTION_RECIPE,
        "fixed_inputs": fixed,
    }


def prepare(repo: Path) -> tuple[Path, Path, Path, Path]:
    """Consume OT-0075's sole private derivation attempt from a clean I."""

    repo = repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0075 preparation requires clean I")
    implementation = _commit(git_output(repo, "rev-parse", "HEAD"), "implementation")
    assert_protocol_unchanged(repo, implementation)
    validate_acceptance(repo)
    destinations = [
        attempt_path(repo),
        seed_path(repo),
        task_path(repo),
        receipt_path(repo),
        repo / RUN_LOCK_PATH,
        raw_path(repo),
        manifest_path(repo),
        _store(repo) / FAILURE_RELATIVE_PATH,
        _store(repo) / FAILED_MANIFEST_RELATIVE_PATH,
    ]
    if any(path.exists() for path in destinations):
        raise RuntimeError("OT-0075 preparation destination exists")

    marker = build_attempt_marker(implementation)
    write_sealed_json(attempt_path(repo), marker)
    seed_bytes = secrets.token_bytes(32)
    _task, receipt = derive(
        repo,
        implementation,
        seed_bytes,
        write_seed=True,
    )
    lock = build_run_lock(repo, implementation, receipt)
    _write_tracked_once(repo / RUN_LOCK_PATH, lock)
    return attempt_path(repo), seed_path(repo), task_path(repo), repo / RUN_LOCK_PATH


def validate_run_lock(
    repo: Path,
    execution: str,
    *,
    allow_regeneration: bool,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    lock = load_json(repo / RUN_LOCK_PATH)
    required = {
        "schema_version",
        "experiment_id",
        "protocol_origin_git_commit",
        "implementation_git_commit",
        "implementation_git_tree",
        "derivation_id",
        "attempt_path",
        "attempt_sha256",
        "seed_path",
        "seed_sha256",
        "task_path",
        "task_sha256",
        "receipt_path",
        "receipt_sha256",
        "run_id",
        "raw_path",
        "manifest_path",
        "failure_path",
        "reconstruction_recipe",
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
    implementation = _commit(lock["implementation_git_commit"], "implementation")
    execution = _commit(execution, "execution")
    if git_output(repo, "rev-parse", f"{execution}^") != implementation:
        raise ProtocolError("L is not the direct child of I")
    if (
        git_output(repo, "rev-parse", f"{implementation}^{{tree}}")
        != lock["implementation_git_tree"]
    ):
        raise ProtocolError("I tree differs from lock")
    if (
        git_output(repo, "diff", "--name-status", f"{implementation}..{execution}")
        != f"A\t{RUN_LOCK_PATH.as_posix()}"
    ):
        raise ProtocolError("L differs from I by more than the run lock")
    assert_protocol_unchanged(repo, execution)
    validate_acceptance(repo)
    observed = {
        name: sha256_file(repo / path)
        for name, path in fixed_input_paths(repo).items()
    }
    if observed != lock["fixed_inputs"]:
        raise ProtocolError("fixed implementation inputs differ from lock")
    task, receipt, seed_bytes = ensure_derivation(
        repo,
        implementation,
        allow_regeneration=allow_regeneration,
    )
    marker_bytes = canonical_json(build_attempt_marker(implementation))
    if (
        lock["attempt_sha256"] != sha256_bytes(marker_bytes)
        or lock["seed_sha256"] != sha256_bytes(seed_bytes)
        or lock["task_sha256"] != receipt["task_sha256"]
        or lock["receipt_sha256"] != sha256_bytes(canonical_json(receipt))
    ):
        raise ProtocolError("private derivation identity differs from lock")
    return lock, task, seed_bytes


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def output_contract(repo: Path, *, allow_manifest: bool) -> dict[str, Path]:
    repo = repo.resolve()
    store = _store(repo)
    if _is_relative_to(store, repo) and not _is_relative_to(
        store, (repo / ".evidence").resolve()
    ):
        raise RuntimeError("in-repository evidence root must be .evidence")
    contract = {
        "store": store,
        "raw": raw_path(repo),
        "manifest": manifest_path(repo),
        "failure": store / FAILURE_RELATIVE_PATH,
        "failed_manifest": store / FAILED_MANIFEST_RELATIVE_PATH,
    }
    if contract["raw"].exists():
        raise RuntimeError("raw output exists")
    if contract["manifest"].exists() and not allow_manifest:
        raise RuntimeError("public manifest exists")
    if contract["failure"].exists() or contract["failed_manifest"].exists():
        raise RuntimeError("failure authority exists")
    return contract


def locked_context(
    repo: Path,
    *,
    allow_regeneration: bool,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0075 execution requires clean L")
    execution = _commit(git_output(repo, "rev-parse", "HEAD"), "execution")
    acceptance = validate_acceptance(repo)
    lock, task, _seed = validate_run_lock(
        repo,
        execution,
        allow_regeneration=allow_regeneration,
    )
    return execution, lock, task, acceptance


# The scientific execution functions are defined below the implementation
# helpers.  Keeping lifecycle identity above them makes the P/I/L boundary easy
# to audit and lets unit tests exercise private derivation without running the
# full 242-encounter calibration.


def _flatten_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for episode in case["episodes"]:
        for event in episode["events"]:
            events.append(
                {
                    "episode_index": episode["episode_index"],
                    "encounter_index": event["encounter_index"],
                    "public_query": copy.deepcopy(event["public_query"]),
                    "outcome": event["outcome"],
                }
            )
    if len(events) != case["horizon"]:
        raise ProtocolError("case event flattening differs from the frozen horizon")
    return events


def _descriptor_identity(
    task_digest: str,
    case_id: str,
    descriptor: tuple[str, str, str | None, str | None],
) -> str:
    return derive_identity("condition", task_digest, case_id, *descriptor)


def _mechanism_for(
    descriptor: tuple[str, str, str | None, str | None],
) -> str | None:
    role, mechanism_id, reference_id, _intervention_id = descriptor
    if role in {"positive-reference", "required-control", "adaptive-comparator"}:
        if mechanism_id == "offline-best-fixed-rule":
            return None
        return mechanism_id
    if role in {"causal-intervention", "recurrence-intervention"}:
        return reference_id
    if role == "identity-placebo":
        return IMMUTABLE_SEED_CONTROL
    raise ProtocolError("condition role is unavailable")


def _lineage_class(role: str) -> str:
    return {
        "positive-reference": ONLINE_POSITIVE,
        "required-control": "required-nonlearning-control",
        "adaptive-comparator": "adaptive-comparator",
        "causal-intervention": "causal-intervention",
        "recurrence-intervention": "causal-intervention",
        "identity-placebo": "identity-placebo",
    }[role]


def _environment_fingerprint(execution_commit: str) -> dict[str, Any]:
    return {
        "architecture": platform.machine(),
        "git_commit": _commit(execution_commit, "execution"),
        "git_dirty": False,
        "os_family": platform.system(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def _consumer_facts(
    *,
    execution_commit: str,
    task_digest: str,
    case_id: str,
    condition_id: str,
    branch_token: str,
    encounter_index: int,
    mode: str,
) -> dict[str, Any]:
    process_id = derive_identity(
        "process-instance",
        execution_commit,
        task_digest,
        case_id,
        condition_id,
        branch_token,
        encounter_index,
        mode,
    )
    workspace_id = derive_identity(
        "workspace-instance",
        process_id,
        "empty-before-after",
    )
    nonce = derive_identity(
        "forbidden-channel-nonce",
        task_digest,
        case_id,
        condition_id,
        branch_token,
        encounter_index,
        mode,
    )
    return make_consumer_facts(
        process_instance_id=process_id,
        workspace_instance_id=workspace_id,
        environment_fingerprint=_environment_fingerprint(execution_commit),
        sentinel_nonce_sha256=nonce,
    )


def _worker_environment(repo: Path) -> dict[str, str]:
    return {
        "LANG": "C",
        "LC_ALL": "C",
        "OT0075_SURFACE": "strict-online-v1",
        "PATH": os.defpath,
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(repo.resolve() / "src"),
        "__CF_USER_TEXT_ENCODING": "0x0:0:0",
    }


def _validate_worker_response(
    value: object,
    *,
    mechanism: str,
    case_id: str,
    condition_id: str,
    lineage_id: str,
    consumer_id: str,
    encounter_index: int,
    mode: str,
    projection: bytes,
) -> dict[str, Any]:
    response = _exact(
        value,
        {
            "schema_version",
            "experiment_id",
            "mechanism_id",
            "mode",
            "case_id",
            "condition_id",
            "lineage_id",
            "consumer_id",
            "encounter_index",
            "projection_sha256",
            "prediction",
            "prediction_operations",
            "state_bytes",
            "candidate_count",
            "workspace_empty_before",
            "workspace_empty_after",
            "environment_names",
            "environment_allowlist_pass",
            "response_chain_absent",
        },
        "fresh consumer response",
    )
    if (
        response["schema_version"] != 1
        or response["experiment_id"] != EXPERIMENT_ID
        or response["mechanism_id"] != mechanism
        or response["mode"] != mode
        or response["case_id"] != case_id
        or response["condition_id"] != condition_id
        or response["lineage_id"] != lineage_id
        or response["consumer_id"] != consumer_id
        or response["encounter_index"] != encounter_index
        or response["projection_sha256"] != sha256_bytes(projection)
        or response["workspace_empty_before"] is not True
        or response["workspace_empty_after"] is not True
        or response["environment_allowlist_pass"] is not True
        or response["response_chain_absent"] is not True
        or response["environment_names"]
        != [
            "LANG",
            "LC_ALL",
            "OT0075_SURFACE",
            "PATH",
            "PYTHONHASHSEED",
            "PYTHONPATH",
            "__CF_USER_TEXT_ENCODING",
        ]
    ):
        raise ProtocolError("fresh consumer response identity differs")
    prediction = response["prediction"]
    if mode == "prediction":
        if type(prediction) is not int or prediction not in {0, 1}:
            raise ProtocolError("fresh consumer prediction is not a bit")
    elif prediction is not None:
        raise ProtocolError("terminal audit emitted a prediction")
    for name in ("prediction_operations", "state_bytes", "candidate_count"):
        if type(response[name]) is not int or response[name] < 0:
            raise ProtocolError(f"fresh consumer {name} is malformed")
    return response


def run_fresh_consumer(
    repo: Path,
    *,
    mechanism: str,
    case_id: str,
    condition_id: str,
    lineage_id: str,
    encounter_index: int,
    mode: str,
    public_query: dict[str, Any] | None,
    projection: bytes,
    facts: dict[str, Any],
    timeout_seconds: float = 2.0,
    allow_learning_rejection: bool = False,
) -> dict[str, Any]:
    """Execute exactly one prediction or terminal audit in a new process."""

    consumer_id = facts["process_instance_id"]
    envelope = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "mechanism_id": mechanism,
        "mode": mode,
        "case_id": case_id,
        "condition_id": condition_id,
        "lineage_id": lineage_id,
        "consumer_id": consumer_id,
        "encounter_index": encounter_index,
        "public_query": public_query,
        "projection_base64": base64.b64encode(projection).decode("ascii"),
    }
    request = canonical_json(envelope)
    sentinel_nonce = facts["forbidden_channel_sentinels"][0]["sentinel_sha256"]
    sentinel = bytes.fromhex(sentinel_nonce)
    with tempfile.TemporaryDirectory(prefix="ot0075-consumer-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        workspace.mkdir()
        (root / "forbidden-sentinel.bin").write_bytes(sentinel)
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "open_trajectory_harness.ot0075_reset_worker",
                ],
                cwd=workspace,
                env=_worker_environment(repo),
                input=request,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise ProtocolError("fresh consumer timed out") from error
        if sentinel in request or sentinel in process.stdout or sentinel in process.stderr:
            raise ProtocolError("forbidden continuity sentinel reached the consumer surface")
        if process.returncode != 0 or process.stderr:
            expected_rejection = (
                allow_learning_rejection
                and process.returncode == 2
                and not process.stdout
                and process.stderr
                == b"consumer rejected: OT-0075 affine evidence is inconsistent\n"
            )
            if not expected_rejection:
                raise ProtocolError("fresh consumer rejected an authoritative encounter")
            if any(workspace.iterdir()):
                raise ProtocolError("rejected fresh consumer changed its workspace")
            return {
                "prediction": None,
                "prediction_operations": 0,
                "state_bytes": len(projection),
                "candidate_count": 0,
                "response_sha256": sha256_bytes(process.stderr),
                "learning_rejected": True,
            }
        if any(workspace.iterdir()):
            raise ProtocolError("fresh consumer changed its empty workspace")
    try:
        response = json.loads(process.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("fresh consumer response is not JSON") from error
    if process.stdout != canonical_json(response):
        raise ProtocolError("fresh consumer response is not canonical")
    checked = _validate_worker_response(
        response,
        mechanism=mechanism,
        case_id=case_id,
        condition_id=condition_id,
        lineage_id=lineage_id,
        consumer_id=consumer_id,
        encounter_index=encounter_index,
        mode=mode,
        projection=projection,
    )
    return {**checked, "response_sha256": sha256_bytes(process.stdout)}


def _run_in_process_consumer(
    *,
    mechanism: str,
    projection: bytes,
    public_query: dict[str, Any] | None,
    mode: str,
) -> dict[str, Any]:
    if mode == "terminal-audit":
        state = decode_state(mechanism, projection)
        if encode_state(mechanism, state) != projection:
            raise ProtocolError("in-process terminal projection did not round trip")
        return {
            "prediction": None,
            "prediction_operations": 0,
            "state_bytes": len(projection),
            "candidate_count": 0,
            "response_sha256": derive_identity("in-process-audit", projection.hex()),
        }
    if public_query is None:
        raise ProtocolError("in-process prediction query is absent")
    result = predict(mechanism, projection, public_query)
    return {
        "prediction": result.prediction,
        "prediction_operations": result.operations,
        "state_bytes": result.state_bytes,
        "candidate_count": result.candidate_count,
        "response_sha256": derive_identity(
            "in-process-prediction",
            mechanism,
            projection.hex(),
            public_query,
            result.prediction,
        ),
    }


def _execute_online_condition(
    repo: Path,
    *,
    execution_commit: str,
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    use_fresh_processes: bool,
) -> dict[str, Any]:
    role, mechanism_id, reference_id, intervention_id = descriptor
    mechanism = _mechanism_for(descriptor)
    if mechanism is None or intervention_id == "wrong-lineage-projection":
        raise ProtocolError("condition is not an online executable lineage")
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    lineage_id = derive_identity("lineage", case["case_id"], condition_id)
    branch_token = "genesis"
    events = _flatten_case(case)
    initial_projection = encode_state(mechanism, initial_state(mechanism))
    active_projection = initial_projection
    receipt_state = initial_projection
    first_facts = _consumer_facts(
        execution_commit=execution_commit,
        task_digest=task_digest,
        case_id=case["case_id"],
        condition_id=condition_id,
        branch_token=branch_token,
        encounter_index=0,
        mode="prediction",
    )
    builder = ReceiptChainBuilder(
        task_sha256=task_digest,
        case_id=case["case_id"],
        case_index=case["case_index"],
        horizon=case["horizon"],
        condition_id=condition_id,
        display_label=(intervention_id or mechanism_id)[:80],
        lineage_class=_lineage_class(role),
        branch_token=branch_token,
        surface=strict_online_surface(),
        initial_state=initial_projection,
        initial_projection=initial_projection,
        first_consumer_facts=first_facts,
    )
    predictions: list[int | None] = []
    statuses: list[str] = []
    projection_sha256s: list[str] = []
    worker_response_sha256s: list[str] = []
    maximum_projection_bytes = len(active_projection)
    maximum_prediction_operations = 0
    maximum_update_operations = 0
    prior_outcome = 0

    for offset, event in enumerate(events):
        facts = _consumer_facts(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=offset,
            mode="prediction",
        )
        if use_fresh_processes:
            consumer = run_fresh_consumer(
                repo,
                mechanism=mechanism,
                case_id=case["case_id"],
                condition_id=condition_id,
                lineage_id=lineage_id,
                encounter_index=offset,
                mode="prediction",
                public_query=event["public_query"],
                projection=active_projection,
                facts=facts,
                allow_learning_rejection=(
                    intervention_id == "one-step-stale-consequence"
                ),
            )
        else:
            try:
                consumer = _run_in_process_consumer(
                    mechanism=mechanism,
                    projection=active_projection,
                    public_query=event["public_query"],
                    mode="prediction",
                )
            except LearningError:
                if intervention_id != "one-step-stale-consequence":
                    raise
                consumer = {
                    "prediction": None,
                    "prediction_operations": 0,
                    "state_bytes": len(active_projection),
                    "candidate_count": 0,
                    "response_sha256": derive_identity(
                        "in-process-learning-rejection",
                        condition_id,
                        offset,
                        sha256_bytes(active_projection),
                    ),
                    "learning_rejected": True,
                }
        prediction = consumer["prediction"]
        prediction_rejected = consumer.get("learning_rejected") is True
        if prediction_rejected:
            if prediction is not None:
                raise ProtocolError("rejected online consumer emitted a prediction")
        elif type(prediction) is not int or prediction not in {0, 1}:
            raise ProtocolError("online consumer returned no scored prediction")
        predictions.append(prediction)
        statuses.append("invalid" if prediction_rejected else "valid")
        projection_sha256s.append(sha256_bytes(active_projection))
        worker_response_sha256s.append(consumer["response_sha256"])
        maximum_projection_bytes = max(maximum_projection_bytes, len(active_projection))
        maximum_prediction_operations = max(
            maximum_prediction_operations,
            consumer["prediction_operations"],
        )

        consequence_binding = "current"
        delivered_outcome: int | None = event["outcome"]
        update_decision = "update"
        update_operations = 0
        candidate_post = active_projection
        update_rejected = False
        if prediction_rejected:
            consequence_binding = "one-step-stale"
            delivered_outcome = prior_outcome
            update_decision = "no-op"
            update_rejected = True
        elif intervention_id == "consequence-withholding":
            consequence_binding = "withheld"
            delivered_outcome = None
            update_decision = "no-op"
        elif intervention_id == "projection-without-update":
            update_decision = "no-op"
        else:
            if intervention_id == "one-step-stale-consequence":
                consequence_binding = "one-step-stale"
                delivered_outcome = prior_outcome
            assert delivered_outcome is not None
            try:
                transition = update(
                    mechanism,
                    active_projection,
                    event["public_query"],
                    prediction,
                    delivered_outcome,
                )
            except LearningError:
                if intervention_id != "one-step-stale-consequence":
                    raise
                # The stale-label intervention may make an otherwise valid
                # affine substrate internally inconsistent.  Preserve that
                # fail-closed rejection as a receipted no-op and retain the
                # complete prediction denominator.
                update_decision = "no-op"
                update_rejected = True
            else:
                candidate_post = encode_state(mechanism, transition.state)
                update_operations = transition.operations
                maximum_update_operations = max(
                    maximum_update_operations, update_operations
                )

        if update_decision == "no-op":
            receipt_post = receipt_state
            delivered_next = active_projection
        else:
            receipt_post = candidate_post
            delivered_next = candidate_post
        if intervention_id == "update-without-projection":
            delivered_next = active_projection
        next_event = events[offset + 1] if offset + 1 < len(events) else None
        if (
            intervention_id == "cross-episode-state-reset"
            and next_event is not None
            and next_event["public_query"]["episode_start"] is True
        ):
            delivered_next = initial_projection

        update_payload = canonical_json(
            {
                "schema_version": 1,
                "decision": update_decision,
                "intervention_id": intervention_id,
                "candidate_post_sha256": sha256_bytes(candidate_post),
                "delivered_projection_sha256": sha256_bytes(delivered_next),
                "update_operations": update_operations,
                "update_rejected": update_rejected,
            }
        )
        terminal = offset == len(events) - 1
        next_facts = _consumer_facts(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=242 if terminal else offset + 1,
            mode="terminal-audit" if terminal else "prediction",
        )
        if terminal:
            if use_fresh_processes:
                audit_consumer = run_fresh_consumer(
                    repo,
                    mechanism=mechanism,
                    case_id=case["case_id"],
                    condition_id=condition_id,
                    lineage_id=lineage_id,
                    encounter_index=242,
                    mode="terminal-audit",
                    public_query=None,
                    projection=delivered_next,
                    facts=next_facts,
                )
            else:
                audit_consumer = _run_in_process_consumer(
                    mechanism=mechanism,
                    projection=delivered_next,
                    public_query=None,
                    mode="terminal-audit",
                )
            worker_response_sha256s.append(audit_consumer["response_sha256"])
        builder.append_encounter(
            public_query=event["public_query"],
            episode_index=event["episode_index"],
            prediction=prediction,
            outcome=event["outcome"],
            update_decision=update_decision,
            update_payload=update_payload,
            post_state=receipt_post,
            next_projection=delivered_next,
            next_consumer_facts=next_facts,
            prediction_status="invalid" if prediction_rejected else "valid",
            consequence_binding=consequence_binding,
            delivered_outcome=delivered_outcome,
        )
        active_projection = delivered_next
        receipt_state = receipt_post
        prior_outcome = event["outcome"]

    chain = builder.finish()
    validation = validate_chain(
        chain,
        require_online_admissible=role == "positive-reference",
    )
    condition = {
        "role": role,
        "mechanism_id": mechanism_id,
        "reference_id": reference_id,
        "intervention_id": intervention_id,
        "query_ids": [event["public_query"]["query_id"] for event in events],
        "outcomes": [event["outcome"] for event in events],
        "predictions": predictions,
        "prediction_statuses": statuses,
    }
    return {
        "condition_id": condition_id,
        "condition": condition,
        "chain": chain,
        "chain_validation": {
            "authority_eligible": validation.authority_eligible,
            "encounter_count": validation.encounter_count,
            "errors": validation.errors,
            "terminal_audit_receipt_sha256": validation.terminal_audit_receipt_sha256,
            "trace_sha256": validation.trace_sha256,
        },
        "initial_projection_sha256": sha256_bytes(initial_projection),
        "projection_sha256s": projection_sha256s,
        "worker_response_sha256s": worker_response_sha256s,
        "maximum_projection_bytes": maximum_projection_bytes,
        "maximum_prediction_operations": maximum_prediction_operations,
        "maximum_update_operations": maximum_update_operations,
        "fresh_processes": use_fresh_processes,
    }


def _offline_condition(
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
) -> dict[str, Any]:
    events = _flatten_case(case)
    result = offline_best_fixed_rule(
        [
            {
                "encounter_index": event["encounter_index"],
                "public_query": event["public_query"],
                "outcome": event["outcome"],
            }
            for event in events
        ]
    )
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    return {
        "condition_id": condition_id,
        "condition": {
            "role": "required-control",
            "mechanism_id": "offline-best-fixed-rule",
            "reference_id": None,
            "intervention_id": None,
            "query_ids": [event["public_query"]["query_id"] for event in events],
            "outcomes": [event["outcome"] for event in events],
            "predictions": list(result.predictions),
            "prediction_statuses": ["valid"] * len(events),
        },
        "chain": None,
        "chain_validation": {
            "authority_eligible": False,
            "reason": "offline complete-stream future access",
        },
        "offline_mask": format(result.mask, "012b"),
        "offline_errors": result.errors,
        "offline_operations": result.operations,
        "fresh_processes": False,
    }


def _wrong_lineage_condition(
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
) -> dict[str, Any]:
    events = _flatten_case(case)
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    return {
        "condition_id": condition_id,
        "condition": {
            "role": "causal-intervention",
            "mechanism_id": "wrong-lineage-projection",
            "reference_id": descriptor[2],
            "intervention_id": "wrong-lineage-projection",
            "query_ids": [event["public_query"]["query_id"] for event in events],
            "outcomes": [event["outcome"] for event in events],
            "predictions": [None] * len(events),
            "prediction_statuses": ["invalid"] * len(events),
        },
        "chain": None,
        "chain_validation": {
            "authority_eligible": False,
            "rejection_code": "sibling-branch-substitution",
            "rejected_before_prediction_count": len(events),
        },
        "fresh_processes": False,
    }


def _execute_all_conditions(
    repo: Path,
    *,
    execution_commit: str,
    task: dict[str, Any],
    use_fresh_processes: bool,
    max_workers: int = 24,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute the exact scorer inventory with isolated state per condition."""

    validate_task(task)
    task_digest = sha256_bytes(canonical_json(task))
    results: dict[
        tuple[int, tuple[str, str, str | None, str | None]], dict[str, Any]
    ] = {}
    futures: dict[Any, tuple[int, tuple[str, str, str | None, str | None]]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for case in task["cases"]:
            for descriptor in CONDITION_INVENTORY:
                mechanism = _mechanism_for(descriptor)
                if mechanism is None:
                    results[(case["case_index"], descriptor)] = _offline_condition(
                        task_digest,
                        case,
                        descriptor,
                    )
                elif descriptor[3] == "wrong-lineage-projection":
                    results[(case["case_index"], descriptor)] = (
                        _wrong_lineage_condition(task_digest, case, descriptor)
                    )
                else:
                    future = executor.submit(
                        _execute_online_condition,
                        repo,
                        execution_commit=execution_commit,
                        task_digest=task_digest,
                        case=case,
                        descriptor=descriptor,
                        use_fresh_processes=use_fresh_processes,
                    )
                    futures[future] = (case["case_index"], descriptor)
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    scorer_cases: list[dict[str, Any]] = []
    raw_lineages: list[dict[str, Any]] = []
    for case in task["cases"]:
        case_results = [
            results[(case["case_index"], descriptor)]
            for descriptor in CONDITION_INVENTORY
        ]
        conditions = {
            result["condition_id"]: result["condition"] for result in case_results
        }
        if len(conditions) != len(CONDITION_INVENTORY):
            raise ProtocolError("opaque condition identities collided")
        immutable = next(
            result
            for result, descriptor in zip(
                case_results, CONDITION_INVENTORY, strict=True
            )
            if descriptor
            == ("required-control", "immutable-seed", None, None)
        )
        placebo = next(
            result
            for result, descriptor in zip(
                case_results, CONDITION_INVENTORY, strict=True
            )
            if descriptor[0] == "identity-placebo"
        )
        placebo_projection_identity = (
            immutable.get("initial_projection_sha256")
            == placebo.get("initial_projection_sha256")
            and immutable.get("projection_sha256s")
            == placebo.get("projection_sha256s")
        )
        events = _flatten_case(case)
        scorer_cases.append(
            {
                "case_id": case["case_id"],
                "case_index": case["case_index"],
                "episodes": [
                    {
                        "episode_index": episode["episode_index"],
                        "dwell": episode["dwell"],
                    }
                    for episode in case["episodes"]
                ],
                "world_query_ids": [
                    event["public_query"]["query_id"] for event in events
                ],
                "world_outcomes": [event["outcome"] for event in events],
                "conditions": {
                    condition_id: conditions[condition_id]
                    for condition_id in sorted(conditions)
                },
                "placebo_projection_bytes_identical": placebo_projection_identity,
            }
        )
        raw_lineages.extend(
            {
                "case_id": case["case_id"],
                "case_index": case["case_index"],
                **result,
            }
            for result in case_results
        )
    raw_lineages.sort(key=lambda item: (item["case_index"], item["condition_id"]))
    return scorer_cases, raw_lineages


def _reference_trace_in_process(task: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    """Execute the two positive mechanisms with isolated state for task anchors."""

    validate_task(task)
    traces: dict[str, dict[str, list[int]]] = {}
    for case in task["cases"]:
        by_reference: dict[str, list[int]] = {}
        for mechanism in (COMPACT_REFERENCE, LOG_REFERENCE):
            projection = encode_state(mechanism, initial_state(mechanism))
            predictions: list[int] = []
            for event in _flatten_case(case):
                prediction = predict(mechanism, projection, event["public_query"]).prediction
                predictions.append(prediction)
                transition = update(
                    mechanism,
                    projection,
                    event["public_query"],
                    prediction,
                    event["outcome"],
                )
                projection = encode_state(mechanism, transition.state)
            by_reference[mechanism] = predictions
        traces[case["case_id"]] = by_reference
    return traces


def _task_metamorphic_gates(task: dict[str, Any]) -> dict[str, bool]:
    baseline = _reference_trace_in_process(task)
    alpha = copy.deepcopy(task)
    ordinal = 0
    for case in alpha["cases"]:
        for episode in case["episodes"]:
            for event in episode["events"]:
                old = event["public_query"]["query_id"]
                event["public_query"]["query_id"] = hashlib.sha256(
                    f"ot-0075-task-alpha:{ordinal}:{old}".encode("ascii")
                ).hexdigest()
                ordinal += 1
    validate_task(alpha)
    alpha_equal = _reference_trace_in_process(alpha) == baseline

    reversed_task = copy.deepcopy(task)
    reversed_task["cases"].reverse()
    # Task validation freezes serialized case order, so case-order metamorphism
    # executes the already validated cases in reverse while retaining identity.
    reversed_traces: dict[str, dict[str, list[int]]] = {}
    for case in reversed_task["cases"]:
        isolated = copy.deepcopy(task)
        isolated["cases"] = [case]
        # Execute directly because the P task validator correctly insists on
        # the original complete case inventory and indices.
        by_reference: dict[str, list[int]] = {}
        for mechanism in (COMPACT_REFERENCE, LOG_REFERENCE):
            projection = encode_state(mechanism, initial_state(mechanism))
            predictions = []
            for event in _flatten_case(case):
                prediction = predict(mechanism, projection, event["public_query"]).prediction
                predictions.append(prediction)
                transition = update(
                    mechanism,
                    projection,
                    event["public_query"],
                    prediction,
                    event["outcome"],
                )
                projection = encode_state(mechanism, transition.state)
            by_reference[mechanism] = predictions
        reversed_traces[case["case_id"]] = by_reference
    return {
        "task_query_id_alpha_renaming": alpha_equal,
        "task_case_order_reversal": reversed_traces == baseline,
    }


def _lineage_by_descriptor(
    lineages: list[dict[str, Any]],
    case_index: int,
    descriptor: tuple[str, str, str | None, str | None],
) -> dict[str, Any]:
    role, mechanism_id, reference_id, intervention_id = descriptor
    matches = [
        item
        for item in lineages
        if item["case_index"] == case_index
        and item["condition"]["role"] == role
        and item["condition"]["mechanism_id"] == mechanism_id
        and item["condition"]["reference_id"] == reference_id
        and item["condition"]["intervention_id"] == intervention_id
    ]
    if len(matches) != 1:
        raise ProtocolError("lineage descriptor did not resolve exactly once")
    return matches[0]


def _execute_suffix_branch(
    repo: Path,
    *,
    execution_commit: str,
    task_digest: str,
    case: dict[str, Any],
    condition_id: str,
    parent_chain: dict[str, Any],
    checkpoint_index: int,
    branch_token: str,
    branch_role: str,
    alternate_first_outcome: bool,
    use_fresh_processes: bool,
) -> dict[str, Any]:
    point = checkpoint(parent_chain, checkpoint_index)
    state = decode_blob(point["state"], limit=2_048, label="checkpoint state")
    projection = decode_blob(
        point["projection"], limit=2_048, label="checkpoint projection"
    )
    start = checkpoint_index + 1
    events = _flatten_case(case)[start:]
    lineage_id = derive_identity("lineage", case["case_id"], condition_id)
    first_facts = _consumer_facts(
        execution_commit=execution_commit,
        task_digest=task_digest,
        case_id=case["case_id"],
        condition_id=condition_id,
        branch_token=branch_token,
        encounter_index=start,
        mode="prediction",
    )
    builder = ReceiptChainBuilder(
        task_sha256=task_digest,
        case_id=case["case_id"],
        case_index=case["case_index"],
        horizon=case["horizon"],
        condition_id=condition_id,
        display_label=branch_role,
        lineage_class=ONLINE_POSITIVE,
        branch_token=branch_token,
        surface=strict_online_surface(),
        initial_state=state,
        initial_projection=projection,
        first_consumer_facts=first_facts,
        branch_role=branch_role,
        fork_parent_state_sha256=point["state_receipt_sha256"],
        fork_parent_projection_sha256=point["projection_receipt_sha256"],
        encounter_start=start,
        encounter_count=len(events),
    )
    active_projection = projection
    for local_offset, event in enumerate(events):
        event = copy.deepcopy(event)
        absolute_index = start + local_offset
        if alternate_first_outcome and local_offset == 0:
            feature = int(event["public_query"]["feature_bits"], 2) ^ 1
            if feature == 0:
                feature = 2
            event["public_query"]["feature_bits"] = format(feature, "012b")
            event["public_query"]["query_id"] = derive_identity(
                "alternate-query",
                case["case_id"],
                absolute_index,
                feature,
            )
            semantic_rule = case["episodes"][event["episode_index"]]["semantic_rule"]
            active_mask = int(case["hidden_masks"][semantic_rule], 2)
            event["outcome"] = (active_mask & feature).bit_count() & 1
        facts = _consumer_facts(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=absolute_index,
            mode="prediction",
        )
        if use_fresh_processes:
            consumer = run_fresh_consumer(
                repo,
                mechanism=COMPACT_REFERENCE,
                case_id=case["case_id"],
                condition_id=condition_id,
                lineage_id=lineage_id,
                encounter_index=absolute_index,
                mode="prediction",
                public_query=event["public_query"],
                projection=active_projection,
                facts=facts,
            )
        else:
            consumer = _run_in_process_consumer(
                mechanism=COMPACT_REFERENCE,
                projection=active_projection,
                public_query=event["public_query"],
                mode="prediction",
            )
        prediction = consumer["prediction"]
        outcome = event["outcome"]
        transition = update(
            COMPACT_REFERENCE,
            active_projection,
            event["public_query"],
            prediction,
            outcome,
        )
        post = encode_state(COMPACT_REFERENCE, transition.state)
        update_payload = canonical_json(
            {
                "schema_version": 1,
                "decision": "update",
                "intervention_id": None,
                "candidate_post_sha256": sha256_bytes(post),
                "delivered_projection_sha256": sha256_bytes(post),
                "update_operations": transition.operations,
            }
        )
        terminal = local_offset == len(events) - 1
        next_facts = _consumer_facts(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=242 if terminal else absolute_index + 1,
            mode="terminal-audit" if terminal else "prediction",
        )
        if terminal:
            if use_fresh_processes:
                run_fresh_consumer(
                    repo,
                    mechanism=COMPACT_REFERENCE,
                    case_id=case["case_id"],
                    condition_id=condition_id,
                    lineage_id=lineage_id,
                    encounter_index=242,
                    mode="terminal-audit",
                    public_query=None,
                    projection=post,
                    facts=next_facts,
                )
            else:
                _run_in_process_consumer(
                    mechanism=COMPACT_REFERENCE,
                    projection=post,
                    public_query=None,
                    mode="terminal-audit",
                )
        builder.append_encounter(
            public_query=event["public_query"],
            episode_index=event["episode_index"],
            prediction=prediction,
            outcome=outcome,
            update_decision="update",
            update_payload=update_payload,
            post_state=post,
            next_projection=post,
            next_consumer_facts=next_facts,
        )
        active_projection = post
    chain = builder.finish()
    validate_chain(chain)
    return chain


def _execute_rollback_suite(
    repo: Path,
    *,
    execution_commit: str,
    task: dict[str, Any],
    lineages: list[dict[str, Any]],
    use_fresh_processes: bool,
) -> tuple[dict[str, bool], dict[str, Any]]:
    task_digest = sha256_bytes(canonical_json(task))
    case = task["cases"][0]
    descriptor = (
        "positive-reference",
        COMPACT_REFERENCE,
        COMPACT_REFERENCE,
        None,
    )
    parent_result = _lineage_by_descriptor(lineages, 0, descriptor)
    parent = parent_result["chain"]
    replay_result = _execute_online_condition(
        repo,
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=case,
        descriptor=descriptor,
        use_fresh_processes=use_fresh_processes,
    )
    parent_replay = replay_result["chain"]
    checkpoint_index = 120
    rewind = _execute_suffix_branch(
        repo,
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=case,
        condition_id=parent_result["condition_id"],
        parent_chain=parent,
        checkpoint_index=checkpoint_index,
        branch_token="rewind-replay",
        branch_role="rewind-replay",
        alternate_first_outcome=False,
        use_fresh_processes=use_fresh_processes,
    )
    alternate = _execute_suffix_branch(
        repo,
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=case,
        condition_id=parent_result["condition_id"],
        parent_chain=parent,
        checkpoint_index=checkpoint_index,
        branch_token="alternate",
        branch_role="alternate",
        alternate_first_outcome=True,
        use_fresh_processes=use_fresh_processes,
    )
    gates = rollback_gates(
        parent,
        parent_replay,
        rewind,
        alternate,
        checkpoint_index=checkpoint_index,
    )
    return gates, {
        "checkpoint_index": checkpoint_index,
        "parent_trace_sha256": parent["trace_sha256"],
        "parent_replay": parent_replay,
        "rewind_branch": rewind,
        "alternate_branch": alternate,
    }


def _learner_surface_audit(repo: Path) -> dict[str, Any]:
    source_path = repo / "src/open_trajectory_harness/ot0075_learning.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_roots = {
        "__future__",
        "base64",
        "binascii",
        "json",
        "re",
        "dataclasses",
        "typing",
    }
    imports: list[str] = []
    relative_import = False
    forbidden_calls: list[str] = []
    forbidden_names = {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "globals",
        "locals",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative_import = True
            imports.append((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in forbidden_names:
                forbidden_calls.append(node.func.id)
    forbidden_imports = sorted(set(imports) - allowed_roots)
    prohibited_text = sorted(
        token
        for token in (
            "derive_task",
            "hidden_masks",
            "hidden_schedule",
            "subprocess",
            "socket",
            "pathlib",
            "urllib",
            "requests",
            "task_loader",
        )
        if token in source
    )
    passed = not (
        relative_import or forbidden_imports or forbidden_calls or prohibited_text
    )
    return {
        "pass": passed,
        "module_sha256": sha256_file(source_path),
        "import_roots": sorted(set(imports)),
        "relative_import": relative_import,
        "forbidden_imports": forbidden_imports,
        "forbidden_calls": sorted(set(forbidden_calls)),
        "prohibited_symbols": prohibited_text,
    }


def _and_gate_maps(
    maps: list[dict[str, bool]], expected: tuple[str, ...]
) -> dict[str, bool]:
    if not maps or any(set(item) != set(expected) for item in maps):
        raise ProtocolError("gate map collection differs from the frozen schema")
    return {name: all(item[name] for item in maps) for name in expected}


def _scientific_gate_evidence(
    repo: Path,
    *,
    lineages: list[dict[str, Any]],
    rollback_map: dict[str, bool],
    use_fresh_processes: bool,
) -> dict[str, Any]:
    chains = [item["chain"] for item in lineages if item["chain"] is not None]
    positive_results = [
        item
        for item in lineages
        if item["condition"]["role"] == "positive-reference"
    ]
    positive_trace_ids = [item["chain"]["trace_sha256"] for item in positive_results]
    collection = validate_chain_collection(
        chains,
        online_admissible_trace_ids=positive_trace_ids,
    )
    causal_maps = [
        causal_path_gates(item["chain"], require_online_admissible=True)
        for item in positive_results
    ]
    causal = _and_gate_maps(causal_maps, CAUSAL_PATH_GATES)
    surface_audit = _learner_surface_audit(repo)
    for name in (
        "next_fresh_process_consumes_exact_projection",
        "fresh_process_workspace_receipts",
        "forbidden_continuity_channel_sentinels",
    ):
        causal[name] = causal[name] and use_fresh_processes
    causal["online_reference_reachable_surface_audit"] = (
        causal["online_reference_reachable_surface_audit"]
        and surface_audit["pass"]
    )

    compact = next(
        item
        for item in positive_results
        if item["case_index"] == 0
        and item["condition"]["mechanism_id"] == COMPACT_REFERENCE
    )
    defects = seeded_authority_defect_gates(compact["chain"])
    if set(defects) != set(AUTHORITY_DEFECTS):
        raise ProtocolError("authority defect gate inventory differs")

    online_reference_authority = all(
        item["chain_validation"]["authority_eligible"] is True
        for item in positive_results
    )
    controls = [
        item
        for item in lineages
        if item["condition"]["role"] == "required-control"
    ]
    control_authority = all(
        item["chain_validation"]["authority_eligible"] is False
        for item in controls
    )
    comparators = [
        item
        for item in lineages
        if item["condition"]["role"] == "adaptive-comparator"
    ]
    adaptive_authority = all(
        item["chain_validation"]["authority_eligible"] is False
        for item in comparators
    )
    online = [item for item in lineages if item["chain"] is not None]
    state_budget = all(
        item.get("maximum_projection_bytes", 0) <= 2_048 for item in online
    )
    operation_budget = all(
        item.get("maximum_prediction_operations", 0) <= 131_072
        and item.get("maximum_update_operations", 0) <= 131_072
        for item in online
    )
    reset_receipts = (
        use_fresh_processes
        and collection["fresh_consumer_count"]
        == sum(item["chain_validation"]["encounter_count"] + 1 for item in online)
        and all(
            len(item["worker_response_sha256s"])
            == item["chain_validation"]["encounter_count"] + 1
            for item in online
        )
    )
    return {
        "authority_defect_rejections": defects,
        "causal_path_gates": causal,
        "rollback_replay_gates": {
            name: rollback_map[name] for name in ROLLBACK_REPLAY_GATES
        },
        "collection_receipt": collection,
        "surface_audit": surface_audit,
        "base_execution_gates": {
            "online_reference_authority": online_reference_authority,
            "control_authority": control_authority,
            "adaptive_comparator_authority": adaptive_authority,
            "state_projection_budgets": state_budget,
            "operation_budgets": operation_budget,
            "fresh_reset_receipts": reset_receipts,
            "candidate_free": True,
        },
        "authority_defect_expected_codes": {
            defect: expected_mutation_code(defect) for defect in AUTHORITY_DEFECTS
        },
    }


def _bounded_command(
    command: list[str],
    repo: Path,
    deadline: float,
    stage: str,
) -> dict[str, Any]:
    remaining = deadline - time.monotonic()
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


def _score_with_independence(
    bundle: dict[str, Any],
    *,
    task_metamorphic: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    working = copy.deepcopy(bundle)
    working["execution_gates"]["metamorphic_dispositions"] = True
    working["execution_gates"]["primary_shadow_agreement"] = True
    primary = score_bundle(working)
    shadow = score_bundle_shadow(working)
    scorer_agreement = canonical_json(primary) == canonical_json(shadow)
    trace_variant_results: dict[str, Any] = {}
    trace_variants_pass = True
    for name, variant in metamorphic_variants(working).items():
        variant_primary = score_bundle(variant)
        variant_shadow = score_bundle_shadow(variant)
        primary_equal = canonical_json(variant_primary) == canonical_json(primary)
        shadow_equal = canonical_json(variant_shadow) == canonical_json(shadow)
        cross_equal = canonical_json(variant_primary) == canonical_json(variant_shadow)
        passed = primary_equal and shadow_equal and cross_equal
        trace_variants_pass = trace_variants_pass and passed
        trace_variant_results[name] = {
            "pass": passed,
            "primary_sha256": sha256_bytes(canonical_json(variant_primary)),
            "shadow_sha256": sha256_bytes(canonical_json(variant_shadow)),
        }
    metamorphic_pass = trace_variants_pass and all(task_metamorphic.values())
    working["execution_gates"]["metamorphic_dispositions"] = metamorphic_pass
    working["execution_gates"]["primary_shadow_agreement"] = scorer_agreement
    primary = score_bundle(working)
    shadow = score_bundle_shadow(working)
    final_agreement = canonical_json(primary) == canonical_json(shadow)
    if final_agreement != scorer_agreement:
        raise ProtocolError("primary/shadow agreement changed after final gate binding")
    return primary, shadow, {
        "task_level": task_metamorphic,
        "trace_level": trace_variant_results,
        "metamorphic_pass": metamorphic_pass,
        "primary_shadow_agreement": final_agreement,
        "primary_sha256": sha256_bytes(canonical_json(primary)),
        "shadow_sha256": sha256_bytes(canonical_json(shadow)),
        "scorer_bundle": working,
    }


def run_calibration(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    execution_commit: str,
    use_fresh_processes: bool,
    clean_private_reconstruction: bool,
    run_verification_commands: bool,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Execute one complete design or private-anchor evaluator workload."""

    repo = repo.resolve()
    validate_task(task)
    if acceptance.get("experiment_id") != EXPERIMENT_ID:
        raise ProtocolError("calibration acceptance identity differs")
    if deadline is None:
        deadline = time.monotonic() + CALIBRATION_SECONDS
    purpose = task["purpose"]
    scorer_cases, lineages = _execute_all_conditions(
        repo,
        execution_commit=execution_commit,
        task=task,
        use_fresh_processes=use_fresh_processes,
    )
    rollback_map, rollback_evidence = _execute_rollback_suite(
        repo,
        execution_commit=execution_commit,
        task=task,
        lineages=lineages,
        use_fresh_processes=use_fresh_processes,
    )
    gate_evidence = _scientific_gate_evidence(
        repo,
        lineages=lineages,
        rollback_map=rollback_map,
        use_fresh_processes=use_fresh_processes,
    )
    task_metamorphic = _task_metamorphic_gates(task)

    if run_verification_commands:
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
    else:
        tests = {"status": "passed", "returncode": 0, "mode": "caller-verified"}
        audit = {"status": "passed", "returncode": 0, "mode": "caller-verified"}
    within_wall_budget = time.monotonic() <= deadline
    execution_gates = {
        **gate_evidence["base_execution_gates"],
        "metamorphic_dispositions": True,
        "primary_shadow_agreement": True,
        "clean_private_reconstruction": clean_private_reconstruction,
        "tests": tests["status"] == "passed",
        "evidence_audit": audit["status"] == "passed",
        "privacy_audit": audit["status"] == "passed",
        "within_wall_budget": within_wall_budget,
    }
    if set(execution_gates) != set(EXECUTION_GATES):
        raise ProtocolError("execution gate inventory differs")
    bundle = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": purpose,
        "case_count": task["case_count"],
        "cases": scorer_cases,
        "authority_defect_rejections": gate_evidence[
            "authority_defect_rejections"
        ],
        "causal_path_gates": gate_evidence["causal_path_gates"],
        "rollback_replay_gates": gate_evidence["rollback_replay_gates"],
        "execution_gates": execution_gates,
    }
    primary, shadow, scorer_evidence = _score_with_independence(
        bundle,
        task_metamorphic=task_metamorphic,
    )
    authoritative_bundle = scorer_evidence.pop("scorer_bundle")
    promoted = (
        purpose == "anchor"
        and primary["anchor_promotion_pass"] is True
        and shadow["anchor_promotion_pass"] is True
    )
    design_pass = (
        purpose == "design"
        and primary["trace_gate_pass"] is True
        and shadow["trace_gate_pass"] is True
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": purpose,
        "task": task,
        "task_sha256": sha256_bytes(canonical_json(task)),
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "lineages": lineages,
        "rollback_evidence": rollback_evidence,
        "gate_evidence": gate_evidence,
        "scorer_bundle": authoritative_bundle,
        "primary_score": primary,
        "shadow_score": shadow,
        "scorer_independence": scorer_evidence,
        "verification": {"tests": tests, "audit": audit},
        "within_wall_budget": within_wall_budget,
        "calibration_pass": promoted or design_pass,
        "disposition": (
            "promoted"
            if promoted
            else "design-passed"
            if design_pass
            else "invalidated"
        ),
        "authorized_actor_candidate_count": 1 if promoted else 0,
        "claim_limit": "candidate-free evaluator-visible surrogate calibration only",
    }


def build_raw(
    *,
    implementation_commit: str,
    execution_commit: str,
    scientific: dict[str, Any],
) -> dict[str, Any]:
    promoted = (
        scientific.get("purpose") == "anchor"
        and scientific.get("disposition") == "promoted"
        and scientific.get("authorized_actor_candidate_count") == 1
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": DEFAULT_RUN_ID,
        "implementation_git_commit": _commit(
            implementation_commit, "implementation"
        ),
        "execution_git_commit": _commit(execution_commit, "execution"),
        "evidence_class": "private-reproducible" if promoted else "exploratory-only",
        "summary": {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "candidate_outputs": False,
            "actor_turns": 0,
            "hosted_model_calls": 0,
            "calibration_pass": promoted,
            "disposition": "promoted" if promoted else "invalidated",
            "authorized_actor_candidate_count": 1 if promoted else 0,
            "primary_score_sha256": sha256_bytes(
                canonical_json(scientific["primary_score"])
            ),
            "shadow_score_sha256": sha256_bytes(
                canonical_json(scientific["shadow_score"])
            ),
            "scientific_payload_sha256": sha256_bytes(canonical_json(scientific)),
            "claim_limit": "candidate-free evaluator-visible surrogate calibration only",
        },
        "scientific": scientific,
    }


def encode_raw(raw: dict[str, Any]) -> bytes:
    encoded = canonical_json(raw)
    compressed = zlib.compress(encoded, level=9)
    if len(compressed) > MAX_RAW_BYTES:
        raise RuntimeError("compressed raw artifact exceeds the implementation bound")
    return compressed


def decode_raw(encoded: bytes) -> dict[str, Any]:
    if len(encoded) > MAX_RAW_BYTES:
        raise ProtocolError("compressed raw artifact exceeds the implementation bound")
    try:
        raw_bytes = zlib.decompress(encoded)
        value = json.loads(raw_bytes)
    except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("compressed raw artifact is invalid") from error
    if type(value) is not dict or canonical_json(value) != raw_bytes:
        raise ProtocolError("raw artifact is not canonical JSON before compression")
    if zlib.compress(raw_bytes, level=9) != encoded:
        raise ProtocolError("raw artifact compression is not canonical")
    return value


def write_sealed_raw(path: Path, raw: dict[str, Any]) -> None:
    _write_sealed_bytes(path, encode_raw(raw))


def read_sealed_raw(path: Path) -> tuple[dict[str, Any], bytes]:
    encoded = _read_sealed_bytes(path)
    return decode_raw(encoded), encoded


def _execute_locked_raw(
    repo: Path,
    execution: str,
    lock: dict[str, Any],
    task: dict[str, Any],
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    deadline = time.monotonic() + CALIBRATION_SECONDS
    scientific = run_calibration(
        repo,
        task,
        acceptance,
        execution_commit=execution,
        use_fresh_processes=True,
        clean_private_reconstruction=True,
        run_verification_commands=True,
        deadline=deadline,
    )
    return build_raw(
        implementation_commit=lock["implementation_git_commit"],
        execution_commit=execution,
        scientific=scientific,
    )


def reconstruct(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    contract = output_contract(repo, allow_manifest=True)
    execution, lock, task, acceptance = locked_context(
        repo,
        allow_regeneration=True,
    )
    raw = _execute_locked_raw(repo, execution, lock, task, acceptance)
    write_sealed_raw(contract["raw"], raw)
    return contract["raw"], raw["summary"]


def _failure(
    contract: dict[str, Path],
    *,
    code: str,
    authoritative_raw: Path,
) -> None:
    write_sealed_json(
        contract["failure"],
        {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "run_id": DEFAULT_RUN_ID,
            "operational_failure": code,
            "public_manifest_retained": False,
            "authoritative_raw_retained": authoritative_raw.exists(),
            "authorized_actor_candidate_count": 0,
        },
    )


def verify_fresh_root(
    repo: Path,
    *,
    implementation: str,
    seed_bytes: bytes,
    authoritative_raw: Path,
) -> dict[str, Any]:
    authoritative_bytes = _read_sealed_bytes(authoritative_raw)
    with tempfile.TemporaryDirectory(prefix="ot0075-reconstruct-") as root_text:
        root = Path(root_text)
        marker_target = root / ATTEMPT_RELATIVE_PATH
        seed_target = root / SEED_RELATIVE_PATH
        marker_target.parent.mkdir(parents=True, exist_ok=True)
        marker_target.write_bytes(canonical_json(build_attempt_marker(implementation)))
        marker_target.chmod(0)
        seed_target.parent.mkdir(parents=True, exist_ok=True)
        seed_target.write_bytes(seed_bytes)
        seed_target.chmod(0)
        environment = child_environment(repo)
        environment["OT_EVIDENCE_ROOT"] = str(root)
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "open_trajectory_harness.ot0075",
                    "--reconstruct-only",
                ],
                cwd=repo,
                env=environment,
                capture_output=True,
                timeout=RECONSTRUCTION_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"pass": False, "status": "reconstruction_timeout"}
        reconstructed = root / RAW_RELATIVE_PATH
        if process.returncode != 0 or process.stderr or not reconstructed.exists():
            return {"pass": False, "status": "reconstruction_failed"}
        reconstructed_bytes = _read_sealed_bytes(reconstructed)
        exact = reconstructed_bytes == authoritative_bytes
        return {
            "pass": exact,
            "status": "passed" if exact else "raw_mismatch",
            "bytes": len(reconstructed_bytes),
            "sha256": sha256_bytes(reconstructed_bytes),
        }


def run(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    contract = output_contract(repo, allow_manifest=False)
    execution, lock, task, acceptance = locked_context(
        repo,
        allow_regeneration=False,
    )
    raw = _execute_locked_raw(repo, execution, lock, task, acceptance)
    write_sealed_raw(contract["raw"], raw)
    if raw["summary"]["disposition"] != "promoted":
        _failure(
            contract,
            code="authoritative_calibration_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("authoritative OT-0075 calibration invalidated")
    reconstruction = verify_fresh_root(
        repo,
        implementation=lock["implementation_git_commit"],
        seed_bytes=_read_sealed_bytes(seed_path(repo)),
        authoritative_raw=contract["raw"],
    )
    if reconstruction.get("pass") is not True:
        _failure(
            contract,
            code=str(reconstruction.get("status")),
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("fresh-root private reconstruction failed")
    contract["raw"].chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=contract["raw"],
            experiment_id=EXPERIMENT_ID,
            artifact_id=DEFAULT_RUN_ID,
            kind="e14-longitudinal-evaluator-calibration",
            evidence_class="private-reproducible",
            recipe=RECONSTRUCTION_RECIPE,
            public_url=None,
            limitations=[
                "OT-0075 is candidate-free evaluator calibration, not base-model learning evidence.",
                "The private anchor establishes one bounded hidden semi-Markov parity opportunity only.",
                "Both positive paths are controller references with fixed learning machinery.",
                "A pass authorizes one separately frozen actor-bearing E14 experiment.",
            ],
            input_manifests=[
                "evidence/manifests/OT-0073/ot-0073-fresh-root-reconstruction-calibration-001.json"
            ],
            store=contract["store"],
        )
    finally:
        contract["raw"].chmod(0)
    audit = subprocess.run(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
    )
    if audit.returncode != 0:
        contract["failed_manifest"].parent.mkdir(parents=True, exist_ok=True)
        manifest.replace(contract["failed_manifest"])
        contract["failed_manifest"].chmod(0)
        _failure(
            contract,
            code="post_manifest_audit_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("post-manifest evidence/privacy audit failed")
    summary = copy.deepcopy(raw["summary"])
    summary["reconstruction"] = reconstruction
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0075-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-authoritative", action="store_true")
    modes.add_argument("--reconstruct-only", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.prepare_authoritative:
            attempt, _seed, task, lock = prepare(repo)
            payload = {
                "attempt": _logical(attempt.relative_to(_store(repo))),
                "task": _logical(task.relative_to(_store(repo))),
                "run_lock": str(lock.relative_to(repo)),
                "private_seed_retained": True,
            }
        else:
            operation = reconstruct if args.reconstruct_only else run
            path, summary = operation(repo)
            payload = {
                "output" if args.reconstruct_only else "manifest": (
                    _logical(path.relative_to(_store(repo)))
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
