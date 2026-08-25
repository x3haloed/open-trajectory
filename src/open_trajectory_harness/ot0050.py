from __future__ import annotations

import argparse
import ast
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
    public_contact,
    score,
    structural_certificate,
    task_family,
)
from .ot0049_world import INITIAL_WEIGHTS, _evaluate, _validate_expression_node


EXPERIMENT_ID = "OT-0050"
ACCEPTANCE_PATH = Path("spec/ot-0050-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0050-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0050/staged-orientation.txt")
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
OT49_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0049/ot-0049-e12-representation-escape-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0050-staged-operation-calibration-001"
MAX_SOURCE_BYTES = 160
MAX_SEMANTIC_NODES = 31
PROJECTION_BYTE_LIMIT = 512


@dataclass(frozen=True)
class StagedSnapshot:
    revision: int
    parent_sha256: str | None
    validation_receipt_sha256: str
    state: dict[str, Any]
    sha256: str


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0050.py"),
        "representation_world_sha256": Path(
            "src/open_trajectory_harness/ot0049_world.py"
        ),
        "world_calibration_sha256": Path("src/open_trajectory_harness/ot0048.py"),
        "entrypoint_sha256": Path("experiments/ot_0050_harness.py"),
        "test_sha256": Path("tests/test_ot0050.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
        "ot0049_manifest_sha256": OT49_MANIFEST_PATH,
    }


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    validation_receipt_sha256: str,
    state: dict[str, Any],
) -> StagedSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "validation_receipt_sha256": validation_receipt_sha256,
        "state": state,
    }
    return StagedSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        validation_receipt_sha256=validation_receipt_sha256,
        state=state,
        sha256=sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> StagedSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0050-seed"}))
    return _snapshot(0, None, receipt, {"weights": list(INITIAL_WEIGHTS)})


def _semantic_node_count(tree: ast.AST) -> int:
    return sum(
        isinstance(
            node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Subscript, ast.Constant)
        )
        for node in ast.walk(tree)
    )


def parse_staged_source(source: str) -> ast.Expression:
    if (
        not isinstance(source, str)
        or not source.strip()
        or len(source.encode()) > MAX_SOURCE_BYTES
    ):
        raise ValueError("bounded-source")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise ValueError("expression-syntax") from error
    _validate_expression_node(tree)
    if _semantic_node_count(tree) > MAX_SEMANTIC_NODES:
        raise ValueError("semantic-complexity")
    return tree


def source_fingerprint(source: str) -> str:
    tree = parse_staged_source(source)
    return sha256_bytes(
        ast.dump(tree, annotate_fields=True, include_attributes=False).encode()
    )


def project_snapshot(snapshot: StagedSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "validation_receipt_sha256": snapshot.validation_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > PROJECTION_BYTE_LIMIT:
        raise ValueError("committed projection exceeds its bound")
    return value


def restore_snapshot(value: dict[str, Any]) -> StagedSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "validation_receipt_sha256",
        "state",
        "sha256",
    }:
        raise ValueError("staged snapshot has unexpected authority")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["validation_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("staged snapshot identity differs")
    if set(restored.state) == {"weights"}:
        if restored.state["weights"] != list(INITIAL_WEIGHTS):
            raise ValueError("seed weights differ")
    elif set(restored.state) == {"source", "syntax_sha256"}:
        if (
            source_fingerprint(restored.state["source"])
            != restored.state["syntax_sha256"]
        ):
            raise ValueError("staged source identity differs")
    else:
        raise ValueError("staged state shape differs")
    return restored


def _source_selections(source: str, split: dict[str, Any]) -> list[str]:
    tree = parse_staged_source(source)
    return [
        min(
            pair["events"],
            key=lambda event: (
                -_evaluate(tree, tuple(event["selector_features"])),
                event["event_id"],
            ),
        )["event_id"]
        for pair in split["pairs"]
    ]


def snapshot_selections(snapshot: StagedSnapshot, split: dict[str, Any]) -> list[str]:
    if "weights" in snapshot.state:
        from .ot0048 import weighted_selections

        return weighted_selections(tuple(snapshot.state["weights"]), split)
    return _source_selections(snapshot.state["source"], split)


def validate_proposal(
    source: str, contact: dict[str, Any], contact_receipt: dict[str, Any]
) -> dict[str, Any]:
    contact_body = {
        key: value for key, value in contact_receipt.items() if key != "receipt_sha256"
    }
    if (
        sha256_bytes(canonical_json(contact_body))
        != contact_receipt.get("receipt_sha256")
        or contact_receipt.get("outcome_credit") is not True
        or len(contact_receipt.get("items", [])) != len(contact.get("pairs", []))
    ):
        raise ValueError("completed contact receipt authority differs")
    for pair, item in zip(contact["pairs"], contact_receipt["items"], strict=True):
        if (
            item.get("pattern_id") != pair.get("pattern_id")
            or item.get("selected_event_id")
            not in {event["event_id"] for event in pair.get("events", [])}
            or item.get("success")
            is not (item.get("selected_event_id") == pair.get("preferred_event_id"))
        ):
            raise ValueError("completed contact receipt content differs")
    body: dict[str, Any] = {
        "outcome_credit": True,
        "contact_receipt_sha256": contact_receipt["receipt_sha256"],
        "proposal_sha256": sha256_bytes(source.encode()),
        "admissible": False,
        "failure": None,
        "success_bits": None,
        "error_count": None,
    }
    try:
        choices = _source_selections(source, contact)
    except ValueError as error:
        body["failure"] = str(error)
    else:
        receipt = complete_contact(contact, choices)
        body.update(
            {
                "admissible": True,
                "success_bits": "".join(
                    "1" if item["success"] else "0" for item in receipt["items"]
                ),
                "error_count": sum(not item["success"] for item in receipt["items"]),
            }
        )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def neutralize_validation(receipt: dict[str, Any]) -> dict[str, Any]:
    body = {
        "outcome_credit": False,
        "contact_receipt_sha256": receipt["contact_receipt_sha256"],
        "proposal_sha256": receipt["proposal_sha256"],
        "admissible": receipt["admissible"],
        "failure": receipt["failure"],
        "success_bits": None,
        "error_count": None,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def provisional_projection(
    current: StagedSnapshot, source: str, receipt: dict[str, Any]
) -> dict[str, Any]:
    value = {
        "parent_sha256": current.sha256,
        "source": source,
        "validation": {
            "outcome_credit": receipt["outcome_credit"],
            "admissible": receipt["admissible"],
            "failure": receipt["failure"],
            "success_bits": receipt["success_bits"],
            "error_count": receipt["error_count"],
            "receipt_sha256": receipt["receipt_sha256"],
        },
    }
    value["sha256"] = sha256_bytes(canonical_json(value))
    if len(canonical_json(value)) > PROJECTION_BYTE_LIMIT:
        raise ValueError("provisional projection exceeds its bound")
    return value


def commit_validated(
    current: StagedSnapshot, source: str, receipt: dict[str, Any]
) -> StagedSnapshot:
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if sha256_bytes(canonical_json(body)) != receipt.get("receipt_sha256"):
        raise ValueError("validation receipt identity differs")
    if receipt.get("outcome_credit") is not True:
        return current
    if not receipt.get("admissible") or receipt.get("error_count") != 0:
        return current
    if receipt.get("proposal_sha256") != sha256_bytes(source.encode()):
        raise ValueError("validation proposal identity differs")
    state = {"source": source, "syntax_sha256": source_fingerprint(source)}
    return _snapshot(
        current.revision + 1, current.sha256, receipt["receipt_sha256"], state
    )


def reference_source(relation: tuple[int, ...], polarity: int) -> str:
    term = "*".join(f"x[{index}]" for index in relation)
    return term if polarity == 1 else f"-({term})"


def overfit_source(relation: tuple[int, ...], polarity: int, scale: int) -> str:
    reference = reference_source(relation, polarity)
    constant = f"({scale}+1)" if scale == 1 else f"({scale}*{scale}+1)"
    return f"({reference})*({constant}-x[0]*x[0])"


def staged_actor_view(
    encounter: dict[str, Any],
    current_projection: dict[str, Any] | None,
    provisional: dict[str, Any] | None,
) -> dict[str, Any]:
    if set(encounter) != {"pairs"}:
        raise ValueError("actor encounter has unexpected authority")
    return {
        "encounter": encounter,
        "current_snapshot": current_projection,
        "provisional_snapshot": provisional,
    }


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    source = (repo / Path("src/open_trajectory_harness/ot0050.py")).read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    definitions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    reachable = set()
    frontier = ["staged_actor_view"]
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        node = definitions[name]
        for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
            if isinstance(call.func, ast.Name) and call.func.id in definitions:
                frontier.append(call.func.id)
    forbidden = {
        "reference_source",
        "overfit_source",
        "validate_proposal",
        "commit_validated",
    }
    hits = sorted(term for term in WITNESS_TERMS if term in orientation.lower())
    probe_task = build_task(task_family()[0])
    probe_view = staged_actor_view(
        public_contact(probe_task["regimes"][0]["contact"]),
        project_snapshot(initial_snapshot()),
        None,
    )

    def collect_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(
                *(collect_keys(item) for item in value.values()), set()
            )
        if isinstance(value, list):
            return set().union(*(collect_keys(item) for item in value), set())
        return set()

    forbidden_keys = {"preferred_event_id", "relation", "polarity", "solution"}
    serialized_forbidden = sorted(forbidden_keys & collect_keys(probe_view))
    body = {
        "reachable": sorted(reachable),
        "forbidden_reachable": sorted(reachable & forbidden),
        "orientation_witness_hits": hits,
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "serialized_forbidden_keys": serialized_forbidden,
        "probe_sha256": sha256_bytes(canonical_json(probe_view)),
    }
    return {
        **body,
        "pass": not body["forbidden_reachable"]
        and not hits
        and not serialized_forbidden,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def evaluate_case(
    case_index: int, case: tuple[tuple[int, ...], int, tuple[int, ...], int]
) -> dict[str, Any]:
    task = build_task(case)
    current = initial_snapshot()
    snapshots = {current.sha256: current}
    regimes = []
    for regime in task["regimes"]:
        before = current
        contact_choices = snapshot_selections(before, regime["contact"])
        contact_receipt = complete_contact(regime["contact"], contact_choices)
        pre_errors = score(
            regime["canary"], snapshot_selections(before, regime["canary"])
        )
        correct = reference_source(tuple(regime["relation"]), regime["polarity"])
        old = "x[0]"
        invalid = "+".join("x[0]" for _ in range(40))
        overfit = overfit_source(
            tuple(regime["relation"]), regime["polarity"], regime["contact_scale"]
        )
        receipts = {
            "old_carrier": validate_proposal(old, regime["contact"], contact_receipt),
            "invalid": validate_proposal(invalid, regime["contact"], contact_receipt),
            "overfit": validate_proposal(overfit, regime["contact"], contact_receipt),
            "correct": validate_proposal(correct, regime["contact"], contact_receipt),
        }
        provisional = provisional_projection(before, old, receipts["old_carrier"])
        corrected = commit_validated(before, correct, receipts["correct"])
        no_credit = commit_validated(
            before, correct, neutralize_validation(receipts["correct"])
        )
        premature = commit_validated(before, overfit, receipts["overfit"])
        snapshots[corrected.sha256] = corrected
        restored_parent = restore_snapshot(
            project_snapshot(snapshots[corrected.parent_sha256])
        )
        regimes.append(
            {
                "index": regime["index"],
                "pre_update_errors": pre_errors,
                "old_carrier_validation_errors": receipts["old_carrier"]["error_count"],
                "invalid_rejected": not receipts["invalid"]["admissible"],
                "overfit_contact_errors": receipts["overfit"]["error_count"],
                "overfit_canary_errors": score(
                    regime["canary"], snapshot_selections(premature, regime["canary"])
                ),
                "correct_contact_errors": receipts["correct"]["error_count"],
                "correct_canary_errors": score(
                    regime["canary"], snapshot_selections(corrected, regime["canary"])
                ),
                "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
                "provisional_bytes": len(canonical_json(provisional)),
                "committed_bytes": len(canonical_json(project_snapshot(corrected))),
                "parent_exact": restored_parent.sha256 == before.sha256,
                "successor_exact": restore_snapshot(project_snapshot(corrected)).sha256
                == corrected.sha256,
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
        "candidate_errors": [item["correct_canary_errors"] for item in regimes],
    }
    body["pass"] = (
        body["pre_update_errors"] == [4, 8, 4]
        and body["candidate_errors"] == [0, 0, 0]
        and all(
            item["old_carrier_validation_errors"] == 4
            and item["invalid_rejected"]
            and item["overfit_contact_errors"] == 0
            and item["overfit_canary_errors"] == 8
            and item["correct_contact_errors"] == 0
            and item["no_credit_preserved_parent"]
            and item["provisional_bytes"] <= PROJECTION_BYTE_LIMIT
            and item["committed_bytes"] <= PROJECTION_BYTE_LIMIT
            and item["parent_exact"]
            and item["successor_exact"]
            and item["certificate"]["pass"]
            for item in regimes
        )
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def run_calibration(repo: Path) -> dict[str, Any]:
    cases = [evaluate_case(index, case) for index, case in enumerate(task_family())]
    reverse = [
        evaluate_case(index, case)
        for index, case in reversed(list(enumerate(task_family())))
    ]
    reverse_by_index = {item["case_index"]: item for item in reverse}
    placebo = all(
        canonical_json(
            {key: value for key, value in item.items() if key != "receipt_sha256"}
        )
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
        "reverse_order_placebo": placebo,
        "actor_surface": surface,
        "candidate_actor_outputs": False,
        "hosted_model_calls": 0,
        "future_candidate_authorization": 1,
        "case_receipt_sha256": sha256_bytes(canonical_json(cases)),
    }
    gates = {
        "complete": body["case_count"] == 48 and body["passing_case_count"] == 48,
        "staged_opportunity": body["candidate_error_vectors"] == [(0, 0, 0)],
        "later_correction": body["pre_update_error_vectors"] == [(4, 8, 4)],
        "reverse_order_placebo": placebo,
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
        raise RuntimeError("OT-0050 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0050 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0050 fixed input identity differs")
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
        raise RuntimeError(f"OT-0050 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0050 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    if output.exists():
        raise RuntimeError("OT-0050 raw output already exists")
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
            evidence_class="public",
            recipe="PYTHONPATH=src python3 experiments/ot_0050_harness.py --output $EVIDENCE/runs/OT-0050/ot-0050-staged-operation-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate actor outputs and hosted model calls are forbidden.",
                "A pass calibrates a staged update topology and authorizes at most one fresh OT-0051 candidate; it is not representation-escape evidence.",
                "The controller-private reference proves opportunity only and may not enter a future actor surface.",
            ],
            input_manifests=[str(OT48_MANIFEST_PATH), str(OT49_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0050-harness")
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
