from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
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
from .ot0048 import (
    WITNESS_TERMS,
    build_task,
    complete_contact,
    promoted_weight_family,
    public_contact,
    score,
    structural_certificate,
    task_family,
    verbatim_raw_selections,
    verbatim_raw_update,
    weighted_selections,
)
from .ot0049_world import INITIAL_WEIGHTS
from .ot0049 import _fixed_control_receipt
from .ot0050 import (
    neutralize_validation,
    overfit_source,
    reference_source,
    source_fingerprint,
    validate_proposal,
)


EXPERIMENT_ID = "OT-0053"
ACCEPTANCE_PATH = Path("spec/ot-0053-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0053-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0053/branching-ledger-orientation.txt")
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
OT52_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0052/ot-0052-staged-representation-escape-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0053-branching-ledger-calibration-001"
MAX_BRANCHES = 3
COMMITTED_PROJECTION_LIMIT = 1536
PROVISIONAL_PROJECTION_LIMIT = 3072


@dataclass(frozen=True)
class LedgerSnapshot:
    revision: int
    parent_sha256: str | None
    validation_receipt_sha256: str
    state: dict[str, Any]
    sha256: str


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "calibration_harness_sha256": Path(
            "src/open_trajectory_harness/ot0053.py"
        ),
        "staged_expression_core_sha256": Path(
            "src/open_trajectory_harness/ot0050.py"
        ),
        "world_calibration_sha256": Path("src/open_trajectory_harness/ot0048.py"),
        "entrypoint_sha256": Path("experiments/ot_0053_harness.py"),
        "test_sha256": Path("tests/test_ot0053.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
        "ot0052_manifest_sha256": OT52_MANIFEST_PATH,
    }


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    validation_receipt_sha256: str,
    state: dict[str, Any],
) -> LedgerSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "validation_receipt_sha256": validation_receipt_sha256,
        "state": state,
    }
    return LedgerSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        validation_receipt_sha256=validation_receipt_sha256,
        state=state,
        sha256=sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> LedgerSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0053-seed"}))
    return _snapshot(0, None, receipt, {"weights": list(INITIAL_WEIGHTS)})


def project_snapshot(snapshot: LedgerSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "validation_receipt_sha256": snapshot.validation_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > COMMITTED_PROJECTION_LIMIT:
        raise ValueError("OT-0053 committed ledger exceeds its projection bound")
    return value


def restore_snapshot(value: dict[str, Any]) -> LedgerSnapshot:
    expected = {
        "revision",
        "parent_sha256",
        "validation_receipt_sha256",
        "state",
        "sha256",
    }
    if set(value) != expected:
        raise ValueError("OT-0053 ledger projection has unexpected authority")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["validation_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0053 ledger identity differs")
    if set(restored.state) == {"weights"}:
        if restored.state["weights"] != list(INITIAL_WEIGHTS):
            raise ValueError("OT-0053 seed weights differ")
        return restored
    if set(restored.state) != {"branches", "active_sha256"}:
        raise ValueError("OT-0053 ledger state shape differs")
    branches = restored.state["branches"]
    if not isinstance(branches, list) or not 1 <= len(branches) <= MAX_BRANCHES:
        raise ValueError("OT-0053 branch count differs")
    identities = []
    for branch in branches:
        if set(branch) != {"source", "syntax_sha256"}:
            raise ValueError("OT-0053 branch shape differs")
        if source_fingerprint(branch["source"]) != branch["syntax_sha256"]:
            raise ValueError("OT-0053 branch identity differs")
        identities.append(branch["syntax_sha256"])
    if len(set(identities)) != len(identities):
        raise ValueError("OT-0053 ledger repeats a branch")
    if restored.state["active_sha256"] not in identities:
        raise ValueError("OT-0053 active branch is absent")
    return restored


def active_source(snapshot: LedgerSnapshot) -> str | None:
    if "weights" in snapshot.state:
        return None
    active = snapshot.state["active_sha256"]
    return next(
        branch["source"]
        for branch in snapshot.state["branches"]
        if branch["syntax_sha256"] == active
    )


def snapshot_selections(
    snapshot: LedgerSnapshot, split: dict[str, Any]
) -> list[str]:
    source = active_source(snapshot)
    if source is None:
        return weighted_selections(tuple(snapshot.state["weights"]), split)
    from .ot0050 import _source_selections

    return _source_selections(source, split)


def validate_branch_set(
    sources: list[str], contact: dict[str, Any], receipt: dict[str, Any]
) -> list[dict[str, Any]]:
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_BRANCHES:
        raise ValueError("OT-0053 proposal branch count differs")
    return [validate_proposal(source, contact, receipt) for source in sources]


def provisional_projection(
    current: LedgerSnapshot,
    sources: list[str],
    validations: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(sources) != len(validations):
        raise ValueError("OT-0053 provisional branch receipts differ")
    branches = []
    for source, validation in zip(sources, validations, strict=True):
        source_value = source if validation["admissible"] else None
        branches.append(
            {
                "source": source_value,
                "rejected_source_sha256": (
                    None if source_value is not None else sha256_bytes(source.encode())
                ),
                "source_bytes": len(source.encode()),
                "validation": {
                    "outcome_credit": validation["outcome_credit"],
                    "admissible": validation["admissible"],
                    "failure": validation["failure"],
                    "success_bits": validation["success_bits"],
                    "error_count": validation["error_count"],
                    "receipt_sha256": validation["receipt_sha256"],
                },
            }
        )
    value = {"parent_sha256": current.sha256, "branches": branches}
    value["sha256"] = sha256_bytes(canonical_json(value))
    if len(canonical_json(value)) > PROVISIONAL_PROJECTION_LIMIT:
        raise ValueError("OT-0053 provisional ledger exceeds its projection bound")
    return value


def commit_branch_set(
    current: LedgerSnapshot,
    sources: list[str],
    validations: list[dict[str, Any]],
    active_index: int,
) -> LedgerSnapshot:
    if (
        len(sources) != len(validations)
        or type(active_index) is not int
        or active_index not in range(len(sources))
    ):
        return current
    for source, validation in zip(sources, validations, strict=True):
        body = {key: value for key, value in validation.items() if key != "receipt_sha256"}
        if (
            sha256_bytes(canonical_json(body)) != validation.get("receipt_sha256")
            or validation.get("proposal_sha256") != sha256_bytes(source.encode())
        ):
            raise ValueError("OT-0053 branch receipt identity differs")
    if any(validation.get("outcome_credit") is not True for validation in validations):
        return current
    selected = validations[active_index]
    if not selected["admissible"] or selected["error_count"] != 0:
        return current
    branches = []
    seen = set()
    for source, validation in zip(sources, validations, strict=True):
        if not validation["admissible"]:
            continue
        identity = source_fingerprint(source)
        if identity in seen:
            continue
        seen.add(identity)
        branches.append({"source": source, "syntax_sha256": identity})
    active_sha256 = source_fingerprint(sources[active_index])
    if active_sha256 not in seen or not 1 <= len(branches) <= MAX_BRANCHES:
        return current
    state = {"branches": branches, "active_sha256": active_sha256}
    aggregate = sha256_bytes(canonical_json(validations))
    successor = _snapshot(current.revision + 1, current.sha256, aggregate, state)
    project_snapshot(successor)
    return successor


def actor_view(
    encounter: dict[str, Any],
    current: dict[str, Any] | None,
    provisional: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "encounter": encounter,
        "current_ledger": current,
        "provisional_ledger": provisional,
    }


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    hits = sorted(term for term in WITNESS_TERMS if term in orientation.lower())
    task = build_task(task_family()[0])
    view = actor_view(
        public_contact(task["regimes"][0]["contact"]),
        project_snapshot(initial_snapshot()),
        None,
    )

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()), set())
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()

    forbidden = {"preferred_event_id", "relation", "polarity", "solution"}
    body = {
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "orientation_witness_hits": hits,
        "serialized_forbidden_keys": sorted(forbidden & keys(view)),
        "probe_sha256": sha256_bytes(canonical_json(view)),
    }
    return {
        **body,
        "pass": not hits and not body["serialized_forbidden_keys"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def evaluate_case(
    case_index: int, case: tuple[tuple[int, ...], int, tuple[int, ...], int]
) -> dict[str, Any]:
    task = build_task(case)
    current = initial_snapshot()
    initial = current
    snapshots = {current.sha256: current}
    regimes = []
    for regime in task["regimes"]:
        before = current
        contact = regime["contact"]
        canary = regime["canary"]
        choices = snapshot_selections(before, contact)
        receipt = complete_contact(contact, choices)
        pre_errors = score(canary, snapshot_selections(before, canary))
        prior = active_source(before) or "x[0]"
        overfit = overfit_source(
            tuple(regime["relation"]), regime["polarity"], regime["contact_scale"]
        )
        correct = reference_source(tuple(regime["relation"]), regime["polarity"])
        sources = [prior, overfit, correct]
        validations = validate_branch_set(sources, contact, receipt)
        provisional = provisional_projection(before, sources, validations)
        corrected = commit_branch_set(before, sources, validations, 2)
        no_credit = commit_branch_set(
            before,
            sources,
            [neutralize_validation(item) for item in validations],
            2,
        )
        deletion = commit_branch_set(before, sources[:2], validations[:2], 1)
        invalid_source = "+".join("x[0]" for _ in range(80))
        invalid_validation = validate_branch_set([invalid_source], contact, receipt)
        invalid_provisional = provisional_projection(
            before, [invalid_source], invalid_validation
        )
        rejected = commit_branch_set(before, [invalid_source], invalid_validation, 0)
        snapshots[corrected.sha256] = corrected
        parent = restore_snapshot(project_snapshot(snapshots[corrected.parent_sha256]))
        successor = restore_snapshot(project_snapshot(corrected))
        raw_entries = verbatim_raw_update(contact, receipt)
        old_projection_error = min(
            score(canary, weighted_selections(weights, canary))
            for weights in promoted_weight_family()
        )
        regimes.append(
            {
                "index": regime["index"],
                "pre_update_errors": pre_errors,
                "candidate_errors": score(
                    canary, snapshot_selections(corrected, canary)
                ),
                "no_persistence_errors": score(
                    canary, snapshot_selections(initial, canary)
                ),
                "verbatim_errors": score(
                    canary, verbatim_raw_selections(raw_entries, canary)
                ),
                "old_carrier_projection_errors": old_projection_error,
                "branch_validation_errors": [
                    item["error_count"] for item in validations
                ],
                "provisional_bytes": len(canonical_json(provisional)),
                "committed_bytes": len(canonical_json(project_snapshot(corrected))),
                "competing_branches_retained": len(corrected.state["branches"]) == 3,
                "selected_branch_exact": active_source(corrected) == correct,
                "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
                "selected_branch_deletion_errors": score(
                    canary, snapshot_selections(deletion, canary)
                ),
                "rejected_update_preserved_parent": rejected.sha256 == before.sha256,
                "invalid_provisional_uses_digest": invalid_provisional["branches"][0][
                    "source"
                ]
                is None
                and invalid_provisional["branches"][0]["rejected_source_sha256"]
                == sha256_bytes(invalid_source.encode()),
                "invalid_provisional_bytes": len(canonical_json(invalid_provisional)),
                "committed_parent_exact": parent.sha256 == before.sha256,
                "committed_successor_exact": successor.sha256 == corrected.sha256,
                "rollback_errors": score(canary, snapshot_selections(parent, canary)),
                "expected_rollback_errors": pre_errors,
                "certificate": structural_certificate(
                    tuple(regime["relation"]),
                    regime["polarity"],
                    regime["canary_scale"],
                ),
            }
        )
        current = corrected
    body = {
        "case_index": case_index,
        "task_sha256": task["task_sha256"],
        "regimes": regimes,
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "candidate_errors": [item["candidate_errors"] for item in regimes],
        "fixed_controls": _fixed_control_receipt(task),
    }
    body["pass"] = body["pre_update_errors"] == [4, 8, 4] and body[
        "candidate_errors"
    ] == [0, 0, 0] and all(
        item["branch_validation_errors"] == [item["pre_update_errors"], 0, 0]
        and item["no_persistence_errors"] == 4
        and item["verbatim_errors"] == 4
        and item["old_carrier_projection_errors"] == 4
        and item["provisional_bytes"] <= PROVISIONAL_PROJECTION_LIMIT
        and item["committed_bytes"] <= COMMITTED_PROJECTION_LIMIT
        and item["competing_branches_retained"]
        and item["selected_branch_exact"]
        and item["no_credit_preserved_parent"]
        and item["selected_branch_deletion_errors"] == 8
        and item["rejected_update_preserved_parent"]
        and item["invalid_provisional_uses_digest"]
        and item["invalid_provisional_bytes"] <= PROVISIONAL_PROJECTION_LIMIT
        and item["committed_parent_exact"]
        and item["committed_successor_exact"]
        and item["rollback_errors"] == item["expected_rollback_errors"]
        and item["certificate"]["pass"]
        for item in regimes
    ) and body["fixed_controls"]["best_weighted_aggregate_errors"] >= 1 and all(
        sum(errors) >= 1 for errors in body["fixed_controls"]["lineages"].values()
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def run_calibration(repo: Path) -> dict[str, Any]:
    cases = [evaluate_case(index, case) for index, case in enumerate(task_family())]
    reverse = [
        evaluate_case(index, case)
        for index, case in reversed(list(enumerate(task_family())))
    ]
    reverse_by_index = {item["case_index"]: item for item in reverse}
    order_independent = all(
        canonical_json({key: value for key, value in item.items() if key != "receipt_sha256"})
        == canonical_json(
            {
                key: value
                for key, value in reverse_by_index[item["case_index"]].items()
                if key != "receipt_sha256"
            }
        )
        for item in cases
    )
    surface = actor_surface_authority(repo)
    body = {
        "case_count": len(cases),
        "passing_case_count": sum(item["pass"] for item in cases),
        "pre_update_error_vectors": sorted(
            {tuple(item["pre_update_errors"]) for item in cases}
        ),
        "candidate_error_vectors": sorted(
            {tuple(item["candidate_errors"]) for item in cases}
        ),
        "reverse_order_placebo": order_independent,
        "actor_surface": surface,
        "candidate_actor_outputs": False,
        "hosted_model_calls": 0,
        "future_candidate_authorization": 1,
        "case_receipt_sha256": sha256_bytes(canonical_json(cases)),
    }
    gates = {
        "complete": body["case_count"] == 48 and body["passing_case_count"] == 48,
        "branching_opportunity": body["candidate_error_vectors"] == [(0, 0, 0)],
        "later_correction": body["pre_update_error_vectors"] == [(4, 8, 4)],
        "reverse_order_placebo": order_independent,
        "actor_surface": surface["pass"],
        "candidate_free": not body["candidate_actor_outputs"]
        and body["hosted_model_calls"] == 0,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        **body,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0053 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0053 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0053 fixed input identity differs")
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
        raise RuntimeError(f"OT-0053 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0053 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    if output.exists():
        raise RuntimeError("OT-0053 raw output already exists")
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
            kind="branching-ledger-candidate-free-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0053_harness.py --output $EVIDENCE/runs/OT-0053/ot-0053-branching-ledger-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate actor outputs and hosted model calls are forbidden.",
                "Controller-private reference branches prove opportunity only and are not candidate evidence.",
                "A pass authorizes at most one fresh OT-0054 candidate and is not representation-escape evidence.",
            ],
            input_manifests=[str(OT48_MANIFEST_PATH), str(OT52_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0053-harness")
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
