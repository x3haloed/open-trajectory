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
from .ot0048 import complete_contact, score, weighted_selections
from .ot0049_world import INITIAL_WEIGHTS
from .ot0056 import (
    INHERITANCE_LIMIT,
    all_real_weight_certificate,
    build_case,
    compression_certificate,
    exact_rows,
    verbatim_selections,
)


EXPERIMENT_ID = "OT-0059"
ACCEPTANCE_PATH = Path("spec/ot-0059-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0059-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0059/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0059/actor-output.schema.json")
OT57_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0057/ot-0057-categorical-description-application-calibration-001.json"
)
OT56_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0056/ot-0056-categorical-compression-world-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0059-categorical-predicate-carrier-calibration-001"
MAX_SOURCE_BYTES = 256
MAX_AST_NODES = 31
PUBLIC_EVENT_KEYS = {"event_id", "selector_features", "on_flags"}


@dataclass(frozen=True)
class PredicateSnapshot:
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
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0059.py"),
        "world_calibration_sha256": Path("src/open_trajectory_harness/ot0056.py"),
        "entrypoint_sha256": Path("experiments/ot_0059_harness.py"),
        "test_sha256": Path("tests/test_ot0059.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0057_manifest_sha256": OT57_MANIFEST_PATH,
        "ot0056_manifest_sha256": OT56_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def _validate_node(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _validate_node(node.body)
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bool)):
        return
    if isinstance(node, ast.Name) and node.id == "event":
        return
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "event"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
        and node.slice.value in PUBLIC_EVENT_KEYS
    ):
        return
    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        if not isinstance(node.ops[0], (ast.In, ast.NotIn, ast.Eq, ast.NotEq)):
            raise ValueError("OT-0059 comparison operation is unavailable")
        _validate_node(node.left)
        _validate_node(node.comparators[0])
        return
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        if len(node.values) < 2:
            raise ValueError("OT-0059 Boolean composition is incomplete")
        for value in node.values:
            _validate_node(value)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        _validate_node(node.operand)
        return
    raise ValueError(f"OT-0059 syntax is unavailable: {type(node).__name__}")


def parse_source(source: str) -> ast.Expression:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("OT-0059 source must be nonempty text")
    if len(source.encode()) > MAX_SOURCE_BYTES:
        raise ValueError("OT-0059 source exceeds its byte limit")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise ValueError("OT-0059 source is not one expression") from error
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError("OT-0059 source exceeds its AST limit")
    _validate_node(tree)
    return tree


def _evaluate_node(node: ast.AST, event: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, event)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return event
    if isinstance(node, ast.Subscript):
        return event[node.slice.value]
    if isinstance(node, ast.Compare):
        left = _evaluate_node(node.left, event)
        right = _evaluate_node(node.comparators[0], event)
        operation = node.ops[0]
        if isinstance(operation, ast.In):
            return left in right
        if isinstance(operation, ast.NotIn):
            return left not in right
        if isinstance(operation, ast.Eq):
            return left == right
        return left != right
    if isinstance(node, ast.BoolOp):
        values = [_evaluate_node(value, event) for value in node.values]
        if not all(isinstance(value, bool) for value in values):
            raise ValueError("OT-0059 Boolean operands must be Boolean")
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp):
        value = _evaluate_node(node.operand, event)
        if not isinstance(value, bool):
            raise ValueError("OT-0059 not operand must be Boolean")
        return not value
    raise ValueError("OT-0059 evaluator received unavailable syntax")


def evaluate_source(source: str, event: dict[str, Any]) -> bool:
    result = _evaluate_node(parse_source(source), event)
    if not isinstance(result, bool):
        raise ValueError("OT-0059 source did not return Boolean")
    return result


def reference_source(target_flag: str, polarity: str) -> str:
    operation = "in" if polarity == "on" else "not in"
    return f'{json.dumps(target_flag)} {operation} event["on_flags"]'


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    receipt_sha256: str,
    state: dict[str, Any],
) -> PredicateSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": receipt_sha256,
        "state": state,
    }
    return PredicateSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        outcome_receipt_sha256=receipt_sha256,
        state=state,
        sha256=sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> PredicateSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0059-seed"}))
    return _snapshot(0, None, receipt, {"weights": list(INITIAL_WEIGHTS)})


def project_snapshot(snapshot: PredicateSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0059 snapshot exceeds its inheritance limit")
    return value


def restore_snapshot(value: dict[str, Any]) -> PredicateSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "outcome_receipt_sha256",
        "state",
        "sha256",
    }:
        raise ValueError("OT-0059 snapshot projection authority differs")
    if (
        type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["parent_sha256"], (str, type(None)))
        or not isinstance(value["outcome_receipt_sha256"], str)
        or not isinstance(value["state"], dict)
        or not isinstance(value["sha256"], str)
    ):
        raise ValueError("OT-0059 snapshot projection is malformed")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0059 snapshot identity differs")
    if set(restored.state) == {"weights"}:
        if restored.state["weights"] != list(INITIAL_WEIGHTS):
            raise ValueError("OT-0059 seed weights differ")
    elif set(restored.state) == {"source"}:
        parse_source(restored.state["source"])
    else:
        raise ValueError("OT-0059 snapshot state differs")
    project_snapshot(restored)
    return restored


def predicate_selections(source: str, split: dict[str, Any]) -> list[str]:
    return [
        min(
            pair["events"],
            key=lambda event: (-int(evaluate_source(source, event)), event["event_id"]),
        )["event_id"]
        for pair in split["pairs"]
    ]


def snapshot_selections(
    snapshot: PredicateSnapshot, split: dict[str, Any]
) -> list[str]:
    if "weights" in snapshot.state:
        return weighted_selections(tuple(snapshot.state["weights"]), split)
    return predicate_selections(snapshot.state["source"], split)


def attempt_update(
    current: PredicateSnapshot,
    source: str,
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[PredicateSnapshot, str]:
    if receipt is None:
        return current, "no-credit"
    try:
        parse_source(source)
        selections = predicate_selections(source, contact)
    except (KeyError, TypeError, ValueError):
        return current, "invalid"
    if score(contact, selections) != 0:
        return current, "contact-imperfect"
    successor = _snapshot(
        current.revision + 1,
        current.sha256,
        receipt["receipt_sha256"],
        {"source": source},
    )
    project_snapshot(successor)
    return successor, "committed"


def interpreter_rejection_receipt() -> dict[str, Any]:
    event = {
        "event_id": "event-a",
        "selector_features": [0, 0, 0, 0],
        "on_flags": ["opaque"],
    }
    cases = {
        "empty": "",
        "call": 'len(event["on_flags"]) == "1"',
        "attribute": 'event.on_flags == "opaque"',
        "arithmetic": '"a" + "b" == "ab"',
        "comprehension": '[value for value in event["on_flags"]] == "opaque"',
        "assignment": "value = True",
        "import": '__import__("os") == "unused"',
        "mutation": 'event["on_flags"].append("opaque") == True',
        "non_boolean": 'event["on_flags"]',
        "runtime_type_error": 'event["on_flags"] in "opaque"',
        "oversized_source": "True" + " " * MAX_SOURCE_BYTES,
        "oversized_ast": "not " * MAX_AST_NODES + "True",
    }
    rejected = {}
    for name, source in cases.items():
        try:
            evaluate_source(source, event)
        except (KeyError, TypeError, ValueError):
            rejected[name] = True
        else:
            rejected[name] = False
    valid = {
        "membership": evaluate_source('"opaque" in event["on_flags"]', event),
        "nonmembership": evaluate_source('"absent" not in event["on_flags"]', event),
        "equality": evaluate_source('event["event_id"] == "event-a"', event),
        "boolean": evaluate_source(
            'True and not (event["event_id"] != "event-a")', event
        ),
    }
    body = {
        "rejected": rejected,
        "valid": valid,
        "pass": all(rejected.values()) and all(valid.values()),
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    serialized = orientation + canonical_json(schema).decode()
    forbidden_patterns = {
        "concrete_flag": r"flag-[0-9a-f]{10,}",
        "target_field": r"target_flag",
        "polarity_field": r"\"polarity\"",
        "reference_expression": r"(?:in|not in)\s+event\s*\[",
        "solved_source": r"\"source\"\s*:\s*\"[^\"]+",
    }
    hits = sorted(
        name
        for name, pattern in forbidden_patterns.items()
        if re.search(pattern, serialized)
    )
    body = {
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "forbidden_hits": hits,
        "candidate_outputs": False,
        "hosted_model_calls": 0,
    }
    return {
        **body,
        "pass": not hits,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def _fixed_sources(task: dict[str, Any]) -> dict[str, str]:
    first_flag = task["flags"][0]
    missing = "flag-absent-fixed-control"
    return {
        "constant-true": "True",
        "constant-false": "False",
        "nonexistent-membership": f'{json.dumps(missing)} in event["on_flags"]',
        "first-flag-membership": f'{json.dumps(first_flag)} in event["on_flags"]',
        "first-flag-nonmembership": f'{json.dumps(first_flag)} not in event["on_flags"]',
    }


def evaluate_case(case_index: int) -> dict[str, Any]:
    task = build_case(case_index)
    current = initial_snapshot()
    initial = current
    snapshots = {current.sha256: current}
    first_learned = None
    second_learned = None
    fixed_sources = _fixed_sources(task)
    fixed_lineages = {name: [] for name in fixed_sources}
    regimes = []
    for regime in task["regimes"]:
        before = current
        contact = regime["contact"]
        canary = regime["canary"]
        contact_choices = snapshot_selections(before, contact)
        receipt = complete_contact(contact, contact_choices)
        rows = exact_rows(contact, contact_choices, receipt)
        certificate = compression_certificate(task, regime, rows, canary)
        source = reference_source(regime["target_flag"], regime["polarity"])
        corrected, update_reason = attempt_update(before, source, receipt, contact)
        snapshots[corrected.sha256] = corrected
        parent = restore_snapshot(project_snapshot(snapshots[corrected.parent_sha256]))
        no_credit, no_credit_reason = attempt_update(before, source, None, contact)
        invalid, invalid_reason = attempt_update(
            before, 'event["on_flags"].append("x") == True', receipt, contact
        )
        oversized, oversized_reason = attempt_update(
            before, "True" + " " * MAX_SOURCE_BYTES, receipt, contact
        )
        opposite = "off" if regime["polarity"] == "on" else "on"
        imperfect, imperfect_reason = attempt_update(
            before,
            reference_source(regime["target_flag"], opposite),
            receipt,
            contact,
        )
        if regime["index"] == 1:
            first_learned = corrected
        elif regime["index"] == 2:
            second_learned = corrected
        for name, fixed_source in fixed_sources.items():
            fixed_lineages[name].append(
                score(canary, predicate_selections(fixed_source, canary))
            )
        constant_ablation = _snapshot(
            corrected.revision,
            corrected.parent_sha256,
            corrected.outcome_receipt_sha256,
            {"source": "True"},
        )
        deleted_literal_source = source.replace(regime["target_flag"], "")
        literal_ablation = _snapshot(
            corrected.revision,
            corrected.parent_sha256,
            corrected.outcome_receipt_sha256,
            {"source": deleted_literal_source},
        )
        pre_errors = score(canary, snapshot_selections(before, canary))
        regimes.append(
            {
                "index": regime["index"],
                "pre_update_errors": pre_errors,
                "reference_errors": score(
                    canary, snapshot_selections(corrected, canary)
                ),
                "no_state_errors": score(canary, snapshot_selections(initial, canary)),
                "empty_errors": score(canary, snapshot_selections(initial, canary)),
                "digest_errors": score(canary, snapshot_selections(initial, canary)),
                "verbatim_errors": score(canary, verbatim_selections(rows, canary)),
                "frozen_first_errors": score(
                    canary,
                    snapshot_selections(
                        first_learned if first_learned is not None else corrected,
                        canary,
                    ),
                ),
                "frozen_second_errors": score(
                    canary,
                    snapshot_selections(
                        second_learned if second_learned is not None else corrected,
                        canary,
                    ),
                ),
                "constant_ast_ablation_errors": score(
                    canary, snapshot_selections(constant_ablation, canary)
                ),
                "literal_deletion_ablation_errors": score(
                    canary, snapshot_selections(literal_ablation, canary)
                ),
                "all_real_weight_certificate": all_real_weight_certificate(canary),
                "compression_certificate": certificate,
                "reference_source_bytes": len(source.encode()),
                "reference_ast_nodes": sum(1 for _ in ast.walk(parse_source(source))),
                "update_reason": update_reason,
                "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
                "no_credit_reason": no_credit_reason,
                "invalid_preserved_parent": invalid.sha256 == before.sha256,
                "invalid_reason": invalid_reason,
                "oversized_preserved_parent": oversized.sha256 == before.sha256,
                "oversized_reason": oversized_reason,
                "contact_imperfect_preserved_parent": imperfect.sha256 == before.sha256,
                "contact_imperfect_reason": imperfect_reason,
                "parent_exact": parent.sha256 == before.sha256,
                "successor_exact": restore_snapshot(project_snapshot(corrected)).sha256
                == corrected.sha256,
                "rollback_errors": score(canary, snapshot_selections(parent, canary)),
                "expected_rollback_errors": pre_errors,
                "committed_bytes": len(canonical_json(project_snapshot(corrected))),
            }
        )
        current = corrected
    body = {
        "case_index": case_index,
        "task_sha256": task["task_sha256"],
        "regimes": regimes,
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "reference_errors": [item["reference_errors"] for item in regimes],
        "no_state_errors": [item["no_state_errors"] for item in regimes],
        "frozen_first_errors": [item["frozen_first_errors"] for item in regimes],
        "frozen_second_errors": [item["frozen_second_errors"] for item in regimes],
        "fixed_lineages": fixed_lineages,
    }
    body["pass"] = (
        body["pre_update_errors"][0] == 4
        and body["pre_update_errors"][1] == 8
        and body["pre_update_errors"][2] >= 1
        and body["reference_errors"] == [0, 0, 0]
        and body["no_state_errors"] == [4, 4, 4]
        and body["frozen_first_errors"][1] == 8
        and body["frozen_second_errors"][2] >= 1
        and all(sum(errors) >= 1 for errors in fixed_lineages.values())
        and all(
            item["verbatim_errors"] == 4
            and item["empty_errors"] == 4
            and item["digest_errors"] == 4
            and item["constant_ast_ablation_errors"] == 4
            and item["literal_deletion_ablation_errors"] == 4
            and item["all_real_weight_certificate"]["pass"]
            and item["compression_certificate"]["pass"]
            and item["reference_source_bytes"] <= MAX_SOURCE_BYTES
            and item["reference_ast_nodes"] <= MAX_AST_NODES
            and item["update_reason"] == "committed"
            and item["no_credit_preserved_parent"]
            and item["no_credit_reason"] == "no-credit"
            and item["invalid_preserved_parent"]
            and item["invalid_reason"] == "invalid"
            and item["oversized_preserved_parent"]
            and item["oversized_reason"] == "invalid"
            and item["contact_imperfect_preserved_parent"]
            and item["contact_imperfect_reason"] == "contact-imperfect"
            and item["parent_exact"]
            and item["successor_exact"]
            and item["rollback_errors"] == item["expected_rollback_errors"]
            and item["committed_bytes"] <= INHERITANCE_LIMIT
            for item in regimes
        )
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    cases = [evaluate_case(index) for index in range(acceptance["scenario_count"])]
    reverse = [
        evaluate_case(index) for index in reversed(range(acceptance["scenario_count"]))
    ]
    reverse_by_index = {item["case_index"]: item for item in reverse}
    order_independent = all(
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
    safety = interpreter_rejection_receipt()
    surface = actor_surface_authority(repo)
    body = {
        "case_count": len(cases),
        "passing_case_count": sum(item["pass"] for item in cases),
        "pre_update_error_vectors": sorted(
            {tuple(item["pre_update_errors"]) for item in cases}
        ),
        "reference_error_vectors": sorted(
            {tuple(item["reference_errors"]) for item in cases}
        ),
        "no_state_error_vectors": sorted(
            {tuple(item["no_state_errors"]) for item in cases}
        ),
        "minimum_surviving_hypotheses": min(
            regime["compression_certificate"]["minimum_surviving_hypotheses"]
            for item in cases
            for regime in item["regimes"]
        ),
        "maximum_allowed_rows": max(
            regime["compression_certificate"]["maximum_allowed_rows"]
            for item in cases
            for regime in item["regimes"]
        ),
        "interpreter_safety": safety,
        "actor_surface": surface,
        "reverse_order_placebo": order_independent,
        "candidate_outputs": False,
        "hosted_model_calls": 0,
        "future_candidate_authorization": 1,
        "case_receipt_sha256": sha256_bytes(canonical_json(cases)),
    }
    gates = {
        "complete": body["case_count"] == acceptance["scenario_count"]
        and body["passing_case_count"] == acceptance["scenario_count"],
        "hidden_opportunity": body["reference_error_vectors"] == [(0, 0, 0)],
        "old_carrier_failure": body["no_state_error_vectors"] == [(4, 4, 4)],
        "compression": body["minimum_surviving_hypotheses"] >= 15
        and body["maximum_allowed_rows"] == 1,
        "interpreter_safety": safety["pass"],
        "actor_surface": surface["pass"],
        "reverse_order_placebo": order_independent,
        "candidate_free": not body["candidate_outputs"]
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


def validate_run_lock(repo: Path, execution: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0059 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0059 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0059 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"OT-0059 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0059 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution)
    if output.exists():
        raise RuntimeError("OT-0059 raw output already exists")
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
        "cases": [
            evaluate_case(index)
            for index in range(load_json(repo / ACCEPTANCE_PATH)["scenario_count"])
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
            kind="categorical-predicate-carrier-candidate-free-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0059_harness.py --output $EVIDENCE/runs/OT-0059/ot-0059-categorical-predicate-carrier-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate output and hosted model calls are forbidden.",
                "Controller-private reference programs prove opportunity only and are not endogenous evidence.",
                "A pass authorizes at most one fresh OT-0060 learner and is not representation-escape evidence.",
            ],
            input_manifests=[
                str(OT57_MANIFEST_PATH),
                str(OT56_MANIFEST_PATH),
                str(OT48_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0059-harness")
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
