from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
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
from .ot0048 import task_family
from .ot0050 import evaluate_case, run_calibration as predecessor_calibration


EXPERIMENT_ID = "OT-0051"
ACCEPTANCE_PATH = Path("spec/ot-0051-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0051-run-lock.json")
OT50_CORE_PATH = Path("src/open_trajectory_harness/ot0050.py")
OT50_ACCEPTANCE_PATH = Path("spec/ot-0050-acceptance.json")
ORIENTATION_PATH = Path("fixtures/ot-0050/staged-orientation.txt")
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
OT49_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0049/ot-0049-e12-representation-escape-candidate-001.json"
)
OT50_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0050/ot-0050-staged-operation-calibration-001-invalidated.json"
)
DEFAULT_RUN_ID = "ot-0051-staged-operation-calibration-001"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "predecessor_acceptance_sha256": OT50_ACCEPTANCE_PATH,
        "calibration_wrapper_sha256": Path("src/open_trajectory_harness/ot0051.py"),
        "calibration_core_sha256": OT50_CORE_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "entrypoint_sha256": Path("experiments/ot_0051_harness.py"),
        "test_sha256": Path("tests/test_ot0051.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
        "ot0049_manifest_sha256": OT49_MANIFEST_PATH,
        "ot0050_invalidated_manifest_sha256": OT50_MANIFEST_PATH,
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    summary = dict(predecessor_calibration(repo))
    summary["experiment_id"] = EXPERIMENT_ID
    summary["future_candidate_experiment_id"] = "OT-0052"
    summary["predecessor_invalidated"] = "OT-0050"
    return summary


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0051 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0051 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0051 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution_commit}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"OT-0051 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0051 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    if output.exists():
        raise RuntimeError("OT-0051 raw output already exists")
    first = run_calibration(repo)
    second = run_calibration(repo)
    deterministic = canonical_json(first) == canonical_json(second)
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
        "deterministic_replay": deterministic,
        "tests": tests.returncode == 0,
        "audit": audit.returncode == 0,
    }
    summary["disposition"] = (
        "promoted" if all(summary["gates"].values()) else "rejected"
    )
    summary["pilot_pass"] = all(summary["gates"].values())
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "summary": summary,
        "cases": [
            evaluate_case(index, case) for index, case in enumerate(task_family())
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
            kind="staged-operation-candidate-free-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0051_harness.py --output $EVIDENCE/runs/OT-0051/ot-0051-staged-operation-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate actor outputs and hosted model calls are forbidden.",
                "A pass authorizes at most one fresh OT-0052 candidate and is not representation-escape evidence.",
                "OT-0050 remains operationally invalidated and is not rescored by this distinct run.",
            ],
            input_manifests=[
                str(OT48_MANIFEST_PATH),
                str(OT49_MANIFEST_PATH),
                str(OT50_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0051-harness")
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
