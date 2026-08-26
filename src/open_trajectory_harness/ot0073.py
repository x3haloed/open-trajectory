"""OT-0073 fresh-root reconstruction repair around frozen OT-0071 science."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import default_store, record_artifact

from . import ot0071
from .ot0002 import canonical_json, child_environment, git_output, load_json, sha256_bytes, sha256_file
from .ot0003 import read_sealed_json, write_sealed_json


EXPERIMENT_ID = "OT-0073"
PROTOCOL_ORIGIN_COMMIT = "e71d7e4ec47d903c332aec0fcd45ea149430626d"
ACCEPTANCE_PATH = Path("spec/ot-0073-acceptance.json")
SCIENTIFIC_ACCEPTANCE_PATH = Path("spec/ot-0071-acceptance.json")
EXPERIMENT_PATH = Path("experiments/OT-0073-fresh-root-reconstruction-calibration.md")
RUN_LOCK_PATH = Path("spec/ot-0073-run-lock.json")
DEFAULT_RUN_ID = "ot-0073-fresh-root-reconstruction-calibration-001"
DERIVATION_ID = "ot-0073-derivation-001"
TASK_RELATIVE_PATH = Path("tasks/OT-0073/ot-0073-derivation-001.json")
DERIVATION_RELATIVE_PATH = Path("derivations/OT-0073/ot-0073-derivation-001.json")
RAW_RELATIVE_PATH = Path("runs/OT-0073") / f"{DEFAULT_RUN_ID}.json"
FAILURE_RELATIVE_PATH = Path("failures/OT-0073") / f"{DEFAULT_RUN_ID}-reconstruction.json"
FAILED_MANIFEST_RELATIVE_PATH = Path("failures/OT-0073") / f"{DEFAULT_RUN_ID}-manifest.json"
ACCEPTANCE_SHA256 = "7b324499e4c3af3700a87ead4446d69ff0ce001fa58ff711c80b40deafb15162"
EXPERIMENT_SHA256 = "c7cc5854e95a2ea758ea6b5813ee5499e07276c21fe9cf283414f91db9b02eb8"
CALIBRATION_SECONDS = 240
RECONSTRUCTION_SECONDS = 240
MAX_RAW_BYTES = 4_194_304
RECONSTRUCTION_RECIPE = (
    "At environment.git.commit with an empty $EVIDENCE, run "
    "OT_EVIDENCE_ROOT=$EVIDENCE PYTHONPATH=src python3 -m "
    "open_trajectory_harness.ot0073 --reconstruct-only"
)

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ProtocolError(ValueError):
    pass


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


def task_path(repo: Path) -> Path:
    return _store(repo) / TASK_RELATIVE_PATH


def receipt_path(repo: Path) -> Path:
    return _store(repo) / DERIVATION_RELATIVE_PATH


def raw_path(repo: Path) -> Path:
    return _store(repo) / RAW_RELATIVE_PATH


def manifest_path(repo: Path) -> Path:
    return repo.resolve() / "evidence" / "manifests" / EXPERIMENT_ID / f"{DEFAULT_RUN_ID}.json"


def validate_acceptance(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    scientific = load_json(repo / SCIENTIFIC_ACCEPTANCE_PATH)
    if sha256_file(repo / ACCEPTANCE_PATH) != ACCEPTANCE_SHA256:
        raise ProtocolError("OT-0073 acceptance bytes differ")
    if sha256_file(repo / EXPERIMENT_PATH) != EXPERIMENT_SHA256:
        raise ProtocolError("OT-0073 experiment bytes differ")
    if acceptance.get("experiment_id") != EXPERIMENT_ID or acceptance.get("candidate_outputs") is not False:
        raise ProtocolError("OT-0073 acceptance identity differs")
    frozen = acceptance["scientific_protocol"]
    for name in ("acceptance", "harness", "reset_worker"):
        path = Path(frozen[f"{name}_path"])
        if sha256_file(repo / path) != frozen[f"{name}_sha256"]:
            raise ProtocolError(f"frozen scientific {name} bytes differ")
    ot0071._validate_acceptance(repo, scientific)
    return acceptance, scientific


def build_task(implementation_commit: str) -> dict[str, Any]:
    return ot0071.build_task(_commit(implementation_commit, "implementation commit"))


def build_receipt(implementation_commit: str, task_bytes: bytes) -> dict[str, Any]:
    implementation_commit = _commit(implementation_commit, "implementation commit")
    try:
        task = json.loads(task_bytes)
    except json.JSONDecodeError as error:
        raise ProtocolError("task bytes are not JSON") from error
    if canonical_json(task) != task_bytes:
        raise ProtocolError("task bytes are not canonical")
    ot0071.validate_task(task)
    if task["implementation_commit"] != implementation_commit:
        raise ProtocolError("task is not derived from the named implementation")
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "derivation_id": DERIVATION_ID,
        "implementation_git_commit": implementation_commit,
        "task_path": _logical(TASK_RELATIVE_PATH),
        "task_sha256": sha256_bytes(task_bytes),
        "task_bytes": len(task_bytes),
    }


def derive(repo: Path, implementation_commit: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Write exact neutral task and receipt bytes to an empty destination."""

    task = build_task(implementation_commit)
    task_bytes = canonical_json(task)
    receipt = build_receipt(implementation_commit, task_bytes)
    write_sealed_json(task_path(repo), task)
    write_sealed_json(receipt_path(repo), receipt)
    return task, receipt


def read_derivation(repo: Path, implementation_commit: str) -> tuple[dict[str, Any], dict[str, Any]]:
    task, task_bytes = read_sealed_json(task_path(repo))
    receipt, receipt_bytes = read_sealed_json(receipt_path(repo))
    expected = build_receipt(implementation_commit, task_bytes)
    if receipt != expected or receipt_bytes != canonical_json(expected):
        raise ProtocolError("neutral derivation receipt differs from task bytes")
    return task, receipt


def ensure_derivation(
    repo: Path, implementation_commit: str, *, allow_regeneration: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    task_exists = task_path(repo).exists()
    receipt_exists = receipt_path(repo).exists()
    if task_exists != receipt_exists:
        raise ProtocolError("task and receipt presence differ")
    if not task_exists:
        if not allow_regeneration:
            raise ProtocolError("authoritative task and receipt are absent")
        derive(repo, implementation_commit)
    return read_derivation(repo, implementation_commit)


def fixed_input_paths(repo: Path | None = None) -> dict[str, Path]:
    repo = (repo or Path.cwd()).resolve()
    paths = {
        "acceptance_sha256": ACCEPTANCE_PATH,
        "experiment_sha256": EXPERIMENT_PATH,
        "scientific_acceptance_sha256": SCIENTIFIC_ACCEPTANCE_PATH,
        "scientific_harness_sha256": Path("src/open_trajectory_harness/ot0071.py"),
        "scientific_reset_worker_sha256": Path("src/open_trajectory_harness/ot0071_reset_worker.py"),
        "target_sha256": Path("TARGET.md"),
        "red_lines_sha256": Path("RED_LINES.md"),
        "program_sha256": Path("PROGRAM.md"),
        "epoch_sha256": Path("docs/TRAJECTORY_PROJECTION_EPOCH.md"),
        "evidence_contract_sha256": Path("docs/EVIDENCE.md"),
        "workflow_sha256": Path("docs/WORKFLOW.md"),
        "ot0073_harness_sha256": Path("src/open_trajectory_harness/ot0073.py"),
        "trajectory_sha256": Path("src/open_trajectory_harness/trajectory.py"),
        "canonical_helper_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_helper_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "ot0070_manifest_sha256": Path("evidence/manifests/OT-0070/ot-0070-trajectory-authority-calibration-001.json"),
    }
    for test in sorted((repo / "tests").glob("test_*.py")):
        relative = test.relative_to(repo)
        paths["test_" + relative.as_posix().replace("/", "_").replace(".", "_") + "_sha256"] = relative
    return paths


def protocol_frozen_paths(repo: Path) -> tuple[Path, ...]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    return tuple(Path(item) for item in acceptance["lock"]["protocol_frozen_paths"])


def assert_protocol_unchanged(repo: Path, commit: str) -> None:
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{PROTOCOL_ORIGIN_COMMIT}..{commit}",
        "--",
        *(path.as_posix() for path in protocol_frozen_paths(repo)),
    )
    if changed:
        raise ProtocolError(f"OT-0073 protocol changed after P: {changed}")


def build_run_lock(repo: Path, implementation: str, receipt: dict[str, Any]) -> dict[str, Any]:
    fixed = {name: sha256_file(repo / path) for name, path in fixed_input_paths(repo).items()}
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "protocol_origin_git_commit": PROTOCOL_ORIGIN_COMMIT,
        "implementation_git_commit": implementation,
        "implementation_git_tree": git_output(repo, "rev-parse", f"{implementation}^{{tree}}"),
        "derivation_id": DERIVATION_ID,
        "task_path": _logical(TASK_RELATIVE_PATH),
        "task_sha256": receipt["task_sha256"],
        "receipt_path": _logical(DERIVATION_RELATIVE_PATH),
        "receipt_sha256": sha256_bytes(canonical_json(receipt)),
        "run_id": DEFAULT_RUN_ID,
        "raw_path": _logical(RAW_RELATIVE_PATH),
        "manifest_path": f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json",
        "failure_path": _logical(FAILURE_RELATIVE_PATH),
        "reconstruction_recipe": RECONSTRUCTION_RECIPE,
        "fixed_inputs": fixed,
    }


def _write_tracked_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(canonical_json(value))
    except FileExistsError as error:
        raise RuntimeError(f"tracked output already exists: {path.name}") from error


def prepare(repo: Path) -> tuple[Path, Path, Path]:
    repo = repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0073 preparation requires clean I")
    implementation = _commit(git_output(repo, "rev-parse", "HEAD"), "implementation")
    assert_protocol_unchanged(repo, implementation)
    validate_acceptance(repo)
    destinations = [
        task_path(repo),
        receipt_path(repo),
        repo / RUN_LOCK_PATH,
        raw_path(repo),
        manifest_path(repo),
        _store(repo) / FAILURE_RELATIVE_PATH,
        _store(repo) / FAILED_MANIFEST_RELATIVE_PATH,
    ]
    if any(path.exists() for path in destinations):
        raise RuntimeError("OT-0073 preparation destination exists")
    task, receipt = derive(repo, implementation)
    del task
    lock = build_run_lock(repo, implementation, receipt)
    _write_tracked_once(repo / RUN_LOCK_PATH, lock)
    return task_path(repo), receipt_path(repo), repo / RUN_LOCK_PATH


def validate_run_lock(
    repo: Path, execution: str, *, allow_regeneration: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    lock = load_json(repo / RUN_LOCK_PATH)
    required = {
        "schema_version", "experiment_id", "protocol_origin_git_commit",
        "implementation_git_commit", "implementation_git_tree", "derivation_id",
        "task_path", "task_sha256", "receipt_path", "receipt_sha256", "run_id",
        "raw_path", "manifest_path", "failure_path", "reconstruction_recipe", "fixed_inputs",
    }
    _exact(lock, required, "run lock")
    if lock["schema_version"] != 1 or lock["experiment_id"] != EXPERIMENT_ID:
        raise ProtocolError("run lock identity differs")
    if lock["protocol_origin_git_commit"] != PROTOCOL_ORIGIN_COMMIT or lock["run_id"] != DEFAULT_RUN_ID:
        raise ProtocolError("run lock fixed identity differs")
    if lock["reconstruction_recipe"] != RECONSTRUCTION_RECIPE:
        raise ProtocolError("run lock reconstruction recipe differs")
    implementation = _commit(lock["implementation_git_commit"], "implementation")
    if git_output(repo, "rev-parse", f"{execution}^") != implementation:
        raise ProtocolError("L is not the direct child of I")
    if git_output(repo, "rev-parse", f"{implementation}^{{tree}}") != lock["implementation_git_tree"]:
        raise ProtocolError("I tree differs from lock")
    if git_output(repo, "diff", "--name-status", f"{implementation}..{execution}") != f"A\t{RUN_LOCK_PATH.as_posix()}":
        raise ProtocolError("L differs from I by more than the run lock")
    assert_protocol_unchanged(repo, execution)
    observed = {name: sha256_file(repo / path) for name, path in fixed_input_paths(repo).items()}
    if observed != lock["fixed_inputs"]:
        raise ProtocolError("fixed inputs differ from lock")
    task, receipt = ensure_derivation(repo, implementation, allow_regeneration=allow_regeneration)
    if lock["task_sha256"] != receipt["task_sha256"]:
        raise ProtocolError("task hash differs from lock")
    if lock["receipt_sha256"] != sha256_bytes(canonical_json(receipt)):
        raise ProtocolError("receipt hash differs from lock")
    return lock, task


def _bounded(command: list[str], repo: Path, deadline: float, stage: str) -> dict[str, Any]:
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
    return {"status": "passed" if process.returncode == 0 else f"{stage}_failed", "returncode": process.returncode}


def _stabilize(raw: dict[str, Any]) -> dict[str, Any]:
    for _ in range(16):
        size = len(canonical_json(raw))
        if raw["raw_artifact_bytes"] == size:
            return raw
        raw["raw_artifact_bytes"] = size
    raise RuntimeError("raw artifact size did not stabilize")


def build_raw(
    implementation: str,
    execution: str,
    scientific: dict[str, Any],
    tests: dict[str, Any],
    audit: dict[str, Any],
    within_bound: bool,
) -> dict[str, Any]:
    verification = tests["status"] == audit["status"] == "passed" and within_bound
    scientific_pass = scientific.get("calibration_pass") is True and scientific.get("disposition") == "promoted"
    promoted = verification and scientific_pass
    summary = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "scientific_protocol": "OT-0071",
        "scientific_summary": scientific,
        "scientific_summary_sha256": sha256_bytes(canonical_json(scientific)),
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "gates": {
            "scientific_calibration": scientific_pass,
            "tests": tests["status"] == "passed",
            "audit": audit["status"] == "passed",
            "within_wall_budget": within_bound,
            "candidate_free": True,
        },
        "calibration_pass": promoted,
        "disposition": "promoted" if promoted else "invalidated",
        "authorized_candidate_count": 1 if promoted else 0,
    }
    raw = _stabilize({
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": DEFAULT_RUN_ID,
        "implementation_git_commit": implementation,
        "execution_git_commit": execution,
        "evidence_class": "public-reconstructible" if promoted else "exploratory-only",
        "raw_artifact_bytes": 0,
        "summary": summary,
        "verification": {"tests": tests, "audit": audit},
    })
    if raw["raw_artifact_bytes"] > MAX_RAW_BYTES:
        raise RuntimeError("raw artifact exceeds frozen bound")
    return raw


def execute_raw(
    repo: Path,
    execution: str,
    lock: dict[str, Any],
    task: dict[str, Any],
    scientific_acceptance: dict[str, Any],
) -> dict[str, Any]:
    deadline = time.monotonic() + CALIBRATION_SECONDS
    try:
        scientific = ot0071.run_calibration(repo, task, scientific_acceptance, deadline=deadline)
    except (OSError, RuntimeError, ValueError):
        scientific = {
            "schema_version": 1,
            "experiment_id": "OT-0071",
            "calibration_pass": False,
            "disposition": "invalidated",
            "operational_failure": "calibration_failed",
        }
    tests = _bounded([sys.executable, "-m", "unittest", "discover", "-s", "tests"], repo, deadline, "tests")
    audit = _bounded([sys.executable, "-m", "open_trajectory_evidence", "audit"], repo, deadline, "audit")
    return build_raw(
        lock["implementation_git_commit"], execution, scientific, tests, audit,
        time.monotonic() <= deadline,
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def output_contract(repo: Path, *, allow_manifest: bool) -> dict[str, Path]:
    repo = repo.resolve()
    store = _store(repo)
    if _is_relative_to(store, repo) and not _is_relative_to(store, (repo / ".evidence").resolve()):
        raise RuntimeError("in-repository evidence root must be .evidence")
    raw = raw_path(repo)
    manifest = manifest_path(repo)
    failure = store / FAILURE_RELATIVE_PATH
    failed_manifest = store / FAILED_MANIFEST_RELATIVE_PATH
    if raw.exists():
        raise RuntimeError("raw output exists")
    if manifest.exists() and not allow_manifest:
        raise RuntimeError("public manifest exists")
    if failure.exists() or failed_manifest.exists():
        raise RuntimeError("failure authority exists")
    return {"store": store, "raw": raw, "manifest": manifest, "failure": failure, "failed_manifest": failed_manifest}


def locked_context(repo: Path, *, allow_regeneration: bool) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("execution requires clean L")
    execution = _commit(git_output(repo, "rev-parse", "HEAD"), "execution")
    _acceptance, scientific = validate_acceptance(repo)
    lock, task = validate_run_lock(repo, execution, allow_regeneration=allow_regeneration)
    return execution, lock, task, scientific


def reconstruct(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    contract = output_contract(repo, allow_manifest=True)
    execution, lock, task, scientific = locked_context(repo, allow_regeneration=True)
    raw = execute_raw(repo, execution, lock, task, scientific)
    write_sealed_json(contract["raw"], raw)
    return contract["raw"], raw["summary"]


def _failure(contract: dict[str, Path], code: str, authoritative_raw: Path) -> None:
    write_sealed_json(contract["failure"], {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": DEFAULT_RUN_ID,
        "operational_failure": code,
        "public_manifest_retained": False,
        "authoritative_raw_retained": authoritative_raw.exists(),
        "authorized_candidate_count": 0,
    })


def verify_fresh_root(repo: Path, authoritative_raw: Path) -> dict[str, Any]:
    authoritative_bytes = authoritative_raw.read_bytes()
    with tempfile.TemporaryDirectory(prefix="ot-0073-reconstruct-") as root:
        env = child_environment(repo)
        env["OT_EVIDENCE_ROOT"] = root
        try:
            process = subprocess.run(
                [sys.executable, "-m", "open_trajectory_harness.ot0073", "--reconstruct-only"],
                cwd=repo,
                env=env,
                capture_output=True,
                timeout=RECONSTRUCTION_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"pass": False, "status": "reconstruction_timeout"}
        reconstructed = Path(root) / RAW_RELATIVE_PATH
        if process.returncode != 0 or process.stderr or not reconstructed.exists():
            return {"pass": False, "status": "reconstruction_failed"}
        reconstructed.chmod(0o600)
        try:
            reconstructed_bytes = reconstructed.read_bytes()
        finally:
            reconstructed.chmod(0)
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
    execution, lock, task, scientific = locked_context(repo, allow_regeneration=False)
    raw = execute_raw(repo, execution, lock, task, scientific)
    write_sealed_json(contract["raw"], raw)
    if raw["summary"]["disposition"] != "promoted":
        _failure(contract, "authoritative_calibration_failed", contract["raw"])
        raise RuntimeError("authoritative calibration invalidated")
    contract["raw"].chmod(0o600)
    try:
        reconstruction = verify_fresh_root(repo, contract["raw"])
    finally:
        contract["raw"].chmod(0)
    if reconstruction.get("pass") is not True:
        _failure(contract, str(reconstruction.get("status")), contract["raw"])
        raise RuntimeError("fresh-root reconstruction failed")
    contract["raw"].chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=contract["raw"],
            experiment_id=EXPERIMENT_ID,
            artifact_id=DEFAULT_RUN_ID,
            kind="fresh-root-reconstruction-calibration",
            evidence_class="public-reconstructible",
            recipe=RECONSTRUCTION_RECIPE,
            public_url=None,
            limitations=[
                "OT-0073 changes reconstruction authority only and reruns frozen OT-0071 science.",
                "All actor-channel records are synthetic fixtures; no candidate output occurred.",
                "A pass authorizes one OT-0074 but is not representation-escape evidence.",
            ],
            input_manifests=["evidence/manifests/OT-0070/ot-0070-trajectory-authority-calibration-001.json"],
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
        _failure(contract, "post_manifest_audit_failed", contract["raw"])
        raise RuntimeError("post-manifest audit failed")
    return manifest, raw["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0073-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-authoritative", action="store_true")
    modes.add_argument("--reconstruct-only", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.prepare_authoritative:
            task, receipt, lock = prepare(repo)
            payload = {
                "task": _logical(task.relative_to(_store(repo))),
                "receipt": _logical(receipt.relative_to(_store(repo))),
                "run_lock": str(lock.relative_to(repo)),
            }
        else:
            operation = reconstruct if args.reconstruct_only else run
            path, summary = operation(repo)
            payload = {
                "output" if args.reconstruct_only else "manifest": (
                    _logical(path.relative_to(_store(repo))) if args.reconstruct_only else str(path.relative_to(repo))
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
