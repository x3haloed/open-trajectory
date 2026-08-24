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
from .ot0036_e6_calibration import criteria, rule_pairs
from .ot0038_e7_ot2_calibration import evaluate_case


EXPERIMENT_ID = "OT-0044"
ACCEPTANCE_PATH = Path("spec/ot-0044-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0044-run-lock.json")
E9_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0043/ot-0043-e9-split-interface-calibration-001.json"
)
OT42_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0042/ot-0042-e8b-self-authored-goal-candidate-001.json"
)
E7_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0038/ot-0038-e7-ot2-evaluator-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0044-e10-causal-advantage-calibration-001"
SHARED_ACTION_COUNT = 5
REPAIR_ACTION_COUNT = 3


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "calibration_harness_sha256": Path(
            "src/open_trajectory_harness/ot0044.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0044_harness.py"),
        "e7_evaluator_sha256": Path(
            "src/open_trajectory_harness/ot0038_e7_ot2_calibration.py"
        ),
        "deterministic_evaluator_sha256": Path(
            "src/open_trajectory_harness/ot0036_e6_calibration.py"
        ),
        "goal_world_core_sha256": Path(
            "src/open_trajectory_harness/ot0039_world.py"
        ),
        "e9_calibration_core_sha256": Path(
            "src/open_trajectory_harness/ot0043.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "e9_manifest_sha256": E9_MANIFEST_PATH,
        "rejected_candidate_manifest_sha256": OT42_MANIFEST_PATH,
        "e7_manifest_sha256": E7_MANIFEST_PATH,
    }


def evaluate_advantage_case(
    criterion_index: int,
    criterion: tuple[int, ...],
    pair_index: int,
    pair: tuple[str, str],
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    semantic = evaluate_case(criterion_index, criterion, pair_index, pair)
    candidate_repairs = sum(
        error_count == 0 for error_count in semantic["candidate_route_errors"]
    )
    unchanged_repairs = sum(
        error_count == 0 for error_count in semantic["unchanged_route_errors"]
    )
    candidate_actions = SHARED_ACTION_COUNT + candidate_repairs
    unchanged_actions = SHARED_ACTION_COUNT + unchanged_repairs
    perfect_advantage = candidate_actions - unchanged_actions
    one_defect_actions = candidate_actions - 1
    one_defect_advantage = one_defect_actions - unchanged_actions
    old_threshold = acceptance["old_advantage_threshold"]
    new_threshold = acceptance["new_advantage_threshold"]
    checks = {
        "semantic_case": semantic["pass"],
        "repair_count": len(semantic["candidate_route_errors"])
        == REPAIR_ACTION_COUNT
        and len(semantic["unchanged_route_errors"]) == REPAIR_ACTION_COUNT,
        "route_signature": semantic["candidate_route_errors"] == [0, 0, 0]
        and semantic["unchanged_route_errors"] == [3, 3, 3],
        "candidate_actions": candidate_actions
        == acceptance["candidate_action_successes"],
        "unchanged_actions": unchanged_actions
        == acceptance["unchanged_control_action_successes"],
        "exact_advantage": perfect_advantage == new_threshold,
        "old_threshold_impossible": perfect_advantage < old_threshold,
        "new_threshold_accepts": perfect_advantage >= new_threshold,
        "one_defect_rejected": one_defect_actions
        == acceptance["one_repair_defect_action_successes"]
        and one_defect_advantage < new_threshold,
    }
    body = {
        "criterion_index": criterion_index,
        "pair_index": pair_index,
        "semantic_receipt_sha256": semantic["receipt_sha256"],
        "candidate_actions": candidate_actions,
        "unchanged_actions": unchanged_actions,
        "perfect_advantage": perfect_advantage,
        "one_defect_advantage": one_defect_advantage,
        "checks": checks,
    }
    return {
        **body,
        "pass": all(checks.values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    cases = [
        (criterion_index, criterion, pair_index, pair)
        for criterion_index, criterion in enumerate(criteria())
        for pair_index, pair in enumerate(rule_pairs())
    ]
    results = [evaluate_advantage_case(*case, acceptance) for case in cases]
    replay = [evaluate_advantage_case(*case, acceptance) for case in cases]
    reverse = [
        evaluate_advantage_case(*case, acceptance) for case in reversed(cases)
    ]
    receipts = [result["receipt_sha256"] for result in results]
    gates = {
        "case_count": len(cases) == acceptance["case_count"],
        "all_cases": all(result["pass"] for result in results),
        "candidate_actions": all(
            result["candidate_actions"] == acceptance["candidate_action_successes"]
            for result in results
        ),
        "unchanged_actions": all(
            result["unchanged_actions"]
            == acceptance["unchanged_control_action_successes"]
            for result in results
        ),
        "exact_advantage": all(
            result["perfect_advantage"] == acceptance["new_advantage_threshold"]
            for result in results
        ),
        "old_threshold_impossible": all(
            result["perfect_advantage"] < acceptance["old_advantage_threshold"]
            for result in results
        ),
        "new_threshold_accepts": all(
            result["perfect_advantage"] >= acceptance["new_advantage_threshold"]
            for result in results
        ),
        "one_defect_rejected": all(
            result["one_defect_advantage"]
            < acceptance["new_advantage_threshold"]
            for result in results
        ),
        "deterministic_replay": receipts
        == [result["receipt_sha256"] for result in replay],
        "order_placebo": receipts
        == list(reversed([result["receipt_sha256"] for result in reverse])),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_transition": acceptance["evaluation_transition"],
        "claim_limit": acceptance["claim_limit"],
        "candidate_goal_outputs": False,
        "case_count": len(cases),
        "case_receipts_sha256": sha256_bytes(canonical_json(receipts)),
        "old_advantage_threshold": acceptance["old_advantage_threshold"],
        "new_advantage_threshold": acceptance["new_advantage_threshold"],
        "candidate_action_successes": acceptance["candidate_action_successes"],
        "unchanged_control_action_successes": acceptance[
            "unchanged_control_action_successes"
        ],
        "one_repair_defect_action_successes": acceptance[
            "one_repair_defect_action_successes"
        ],
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "authorized_candidate_count": (
            acceptance["authorized_candidate_count"] if all(gates.values()) else 0
        ),
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0044 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0044 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0044 fixed input identity differs")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0044 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    if output.exists():
        raise RuntimeError("OT-0044 output already exists")
    summary = run_calibration(repo)
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
    summary["gates"]["tests"] = tests.returncode == 0
    summary["gates"]["audit"] = audit.returncode == 0
    summary["disposition"] = (
        "promoted" if all(summary["gates"].values()) else "rejected"
    )
    summary["authorized_candidate_count"] = (
        load_json(repo / ACCEPTANCE_PATH)["authorized_candidate_count"]
        if all(summary["gates"].values())
        else 0
    )
    summary["pilot_pass"] = all(summary["gates"].values())
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
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
    manifest = record_artifact(
        repo=repo,
        input_path=output,
        experiment_id=EXPERIMENT_ID,
        artifact_id=run_id,
        kind="e10-causal-advantage-calibration",
        evidence_class="public-reproducible",
        recipe=(
            "PYTHONPATH=src python3 experiments/ot_0044_harness.py "
            "--output $EVIDENCE/ot-0044-e10-causal-advantage-calibration-001.json"
        ),
        public_url=None,
        limitations=[
            "This is evaluator calibration, not OT-2 evidence.",
            "No candidate task, goal, or hosted actor output was generated.",
            "A pass authorizes at most one fresh E10 candidate.",
        ],
        input_manifests=[
            str(E9_MANIFEST_PATH),
            str(OT42_MANIFEST_PATH),
            str(E7_MANIFEST_PATH),
        ],
    )
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0044-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        manifest, summary = run(repo, args.run_id, args.output.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(repo)), "summary": summary},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
