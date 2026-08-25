from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from jsonschema import Draft202012Validator
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
from .ot0059 import MAX_SOURCE_BYTES, parse_source, run_calibration as run_ot0059


EXPERIMENT_ID = "OT-0061"
ACCEPTANCE_PATH = Path("spec/ot-0061-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0061-run-lock.json")
OLD_SCHEMA_PATH = Path("fixtures/ot-0059/actor-output.schema.json")
REPAIRED_SCHEMA_PATH = Path("fixtures/ot-0061/actor-output.schema.json")
OT59_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0059/ot-0059-categorical-predicate-carrier-calibration-001.json"
)
OT60_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0060/ot-0060-categorical-predicate-representation-escape-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0061-hosted-schema-preflight-repair-calibration-001"
T = TypeVar("T")


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "old_schema_sha256": OLD_SCHEMA_PATH,
        "repaired_schema_sha256": REPAIRED_SCHEMA_PATH,
        "repair_harness_sha256": Path("src/open_trajectory_harness/ot0061.py"),
        "carrier_harness_sha256": Path("src/open_trajectory_harness/ot0059.py"),
        "schema_dialect_sha256": Path("src/open_trajectory_harness/ot0040.py"),
        "entrypoint_sha256": Path("experiments/ot_0061_harness.py"),
        "test_sha256": Path("tests/test_ot0061.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0059_manifest_sha256": OT59_MANIFEST_PATH,
        "ot0060_manifest_sha256": OT60_MANIFEST_PATH,
    }


def schema_repair_receipt(old: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    expected = copy.deepcopy(old)
    removed = expected.get("properties", {}).get("source", {}).pop("maxLength", None)
    exact = removed == MAX_SOURCE_BYTES and canonical_json(expected) == canonical_json(repaired)
    return {
        "required_removed_path": "properties.source.maxLength",
        "removed_value": removed,
        "exact_single_deletion": exact,
        "old_unsupported_keywords": sorted(unsupported_keywords(old)),
        "repaired_unsupported_keywords": sorted(unsupported_keywords(repaired)),
        "old_schema_sha256": sha256_bytes(canonical_json(old)),
        "repaired_schema_sha256": sha256_bytes(canonical_json(repaired)),
        "pass": exact
        and unsupported_keywords(old) == {"maxLength"}
        and unsupported_keywords(repaired) == set(),
    }


def schema_validation_receipt(schema: dict[str, Any]) -> dict[str, Any]:
    validator = Draft202012Validator(schema)
    probes = {
        "valid": {"source": "True"},
        "missing": {},
        "non_string": {"source": 1},
        "extra": {"source": "True", "mode": "supplied"},
    }
    accepted = {
        name: not list(validator.iter_errors(value)) for name, value in probes.items()
    }
    expected = {"valid": True, "missing": False, "non_string": False, "extra": False}
    return {"accepted": accepted, "pass": accepted == expected}


def interpreter_boundary_receipt() -> dict[str, Any]:
    safe = "True" + " " * (MAX_SOURCE_BYTES - len("True"))
    oversized = safe + " "
    safe_accepted = oversized_rejected = False
    try:
        parse_source(safe)
        safe_accepted = True
    except ValueError:
        pass
    try:
        parse_source(oversized)
    except ValueError:
        oversized_rejected = True
    return {
        "safe_source_bytes": len(safe.encode()),
        "oversized_source_bytes": len(oversized.encode()),
        "safe_accepted": safe_accepted,
        "oversized_rejected": oversized_rejected,
        "pass": safe_accepted
        and oversized_rejected
        and len(safe.encode()) == MAX_SOURCE_BYTES
        and len(oversized.encode()) == MAX_SOURCE_BYTES + 1,
    }


def require_hosted_schema(schema: dict[str, Any]) -> dict[str, Any]:
    unsupported = sorted(unsupported_keywords(schema))
    if unsupported:
        raise ValueError(f"unsupported hosted schema keywords: {unsupported}")
    return {
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "unsupported_keywords": unsupported,
        "pass": True,
    }


def start_after_schema_preflight(
    schema: dict[str, Any], start: Callable[[], T]
) -> tuple[dict[str, Any], T]:
    receipt = require_hosted_schema(schema)
    return receipt, start()


def sequencing_receipt(old: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    old_starts = 0
    repaired_starts = 0

    def old_start() -> None:
        nonlocal old_starts
        old_starts += 1

    def repaired_start() -> str:
        nonlocal repaired_starts
        repaired_starts += 1
        return "started"

    old_rejected = False
    try:
        start_after_schema_preflight(old, old_start)
    except ValueError:
        old_rejected = True
    receipt, result = start_after_schema_preflight(repaired, repaired_start)
    return {
        "old_schema_rejected": old_rejected,
        "old_start_count": old_starts,
        "repaired_start_count": repaired_starts,
        "repaired_result": result,
        "repaired_receipt": receipt,
        "pass": old_rejected
        and old_starts == 0
        and repaired_starts == 1
        and result == "started"
        and receipt["pass"],
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    old = load_json(repo / OLD_SCHEMA_PATH)
    repaired = load_json(repo / REPAIRED_SCHEMA_PATH)
    repair = schema_repair_receipt(old, repaired)
    validation = schema_validation_receipt(repaired)
    boundary = interpreter_boundary_receipt()
    sequencing = sequencing_receipt(old, repaired)
    first = run_ot0059(repo)
    second = run_ot0059(repo)
    carrier = {
        "case_count": first["case_count"],
        "passing_case_count": first["passing_case_count"],
        "disposition": first["disposition"],
        "hidden_reference_errors": first["reference_error_vectors"],
        "old_carrier_errors": first["no_state_error_vectors"],
        "minimum_surviving_hypotheses": first["minimum_surviving_hypotheses"],
        "maximum_allowed_rows": first["maximum_allowed_rows"],
        "deterministic_replay": canonical_json(first) == canonical_json(second),
    }
    carrier["pass"] = (
        carrier["case_count"] == acceptance["carrier_case_count"]
        and carrier["passing_case_count"] == acceptance["carrier_case_count"]
        and carrier["disposition"] == "promoted"
        and carrier["hidden_reference_errors"] == [(0, 0, 0)]
        and carrier["old_carrier_errors"] == [(4, 4, 4)]
        and carrier["deterministic_replay"]
    )
    body = {
        "schema_repair": repair,
        "schema_validation": validation,
        "interpreter_boundary": boundary,
        "preflight_sequencing": sequencing,
        "carrier_regression": carrier,
        "candidate_outputs": False,
        "hosted_model_calls": 0,
        "future_candidate_authorization": 1,
    }
    gates = {
        "exact_single_deletion": repair["pass"],
        "schema_validation": validation["pass"],
        "interpreter_boundary": boundary["pass"],
        "prehosted_fail_closed": sequencing["pass"],
        "carrier_regression": carrier["pass"],
        "candidate_free": not body["candidate_outputs"],
        "hosted_free": body["hosted_model_calls"] == 0,
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
        raise RuntimeError("OT-0061 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0061 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0061 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo, "diff", "--name-only", f"{implementation}..{execution}", "--", *protected
    )
    if changed:
        raise RuntimeError(f"OT-0061 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0061 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution)
    if output.exists():
        raise RuntimeError("OT-0061 raw output already exists")
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
            kind="hosted-schema-preflight-candidate-free-repair-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0061_harness.py --output $EVIDENCE/runs/OT-0061/ot-0061-hosted-schema-preflight-repair-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate output and hosted model calls are forbidden.",
                "A pass repairs protocol validity only and does not rescore OT-0060.",
                "A pass authorizes at most one fresh OT-0062 learner under unchanged scientific gates.",
            ],
            input_manifests=[str(OT59_MANIFEST_PATH), str(OT60_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0061-harness")
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
