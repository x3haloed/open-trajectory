from __future__ import annotations

import argparse
import ast
import copy
import json
import re
import subprocess
from itertools import permutations, product
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import canonical_json, git_output, load_json, sha256_bytes, sha256_file
from .ot0003 import write_sealed_json
from .ot0033_weighted_selector import (
    DIMENSION_COUNT,
    PATTERN_COUNT,
    WeightedSelectorSnapshot,
    _snapshot,
    build_split,
    score_snapshot,
)


EXPERIMENT_ID = "OT-0034"
ACCEPTANCE_PATH = Path("spec/ot-0034-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0034-run-lock.json")
CANDIDATE_PATH = Path("src/open_trajectory_harness/ot0033_weighted_selector.py")
PREDECESSOR_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0033/ot-0033-blind-weighted-selector-001.json"
)
DEFAULT_RUN_ID = "ot-0034-e5-weighted-selector-calibration-001"
FORBIDDEN_REACHABLE = {
    "_hidden_weights",
    "build_split",
    "build_task",
    "expected_task_seed",
    "validate_run_lock",
    "run_protocol",
    "record_sealed_result",
    "main",
    "globals",
    "locals",
    "vars",
    "getattr",
    "__import__",
    "open",
    "eval",
    "exec",
}


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "calibration_core_sha256": Path(
            "src/open_trajectory_harness/ot0034_e5_calibration.py"
        ),
        "candidate_carrier_sha256": CANDIDATE_PATH,
        "entrypoint_sha256": Path("experiments/ot_0034_harness.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path(
            "src/open_trajectory_harness/ot0003.py"
        ),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_PATH,
    }


def criteria() -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(
            magnitude * sign
            for magnitude, sign in zip(magnitudes, signs, strict=True)
        )
        for magnitudes in permutations((1, 5, 25, 125))
        for signs in product((-1, 1), repeat=DIMENSION_COUNT)
    )


def _controller_snapshot(
    name: str, weights: tuple[int, ...]
) -> WeightedSelectorSnapshot:
    receipt = sha256_bytes(canonical_json({"controller_state": name, "weights": weights}))
    return _snapshot(0, None, receipt, weights)


def _opposite_world(split: dict[str, Any]) -> dict[str, Any]:
    return {
        "archive": copy.deepcopy(split["archive"]),
        "outcomes": [
            {"pattern_id": item["pattern_id"], "outcome": 1 - item["outcome"]}
            for item in split["outcomes"]
        ],
    }


def _world_sha256(split: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(split))


def _raw_projection_sha256(split: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({"archive": split["archive"]}))


def _preference_gate(split: dict[str, Any], criterion: tuple[int, ...]) -> bool:
    outcomes = {item["pattern_id"]: item["outcome"] for item in split["outcomes"]}
    grouped: dict[int, list[dict[str, Any]]] = {}
    for event in split["archive"]:
        grouped.setdefault(event["pattern_id"], []).append(event)
    if set(grouped) != set(range(PATTERN_COUNT)):
        return False
    for pattern_id, pair in grouped.items():
        preferred = [event for event in pair if event["label"] == outcomes[pattern_id]]
        if len(preferred) != 1:
            return False
        if sum(
            weight * feature
            for weight, feature in zip(
                criterion, preferred[0]["selector_features"], strict=True
            )
        ) <= 0:
            return False
    return True


def candidate_authority(repo: Path) -> dict[str, Any]:
    source = (repo / CANDIDATE_PATH).read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    learner = definitions.get("learn")
    if learner is None:
        raise RuntimeError("OT-0034 cannot locate the candidate learner")
    parameters = [argument.arg for argument in learner.args.args]
    reachable = set()
    observed_calls = set()
    observed_names = set()
    frontier = ["learn"]
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        node = definitions[name]
        observed_names.update(
            item.id for item in ast.walk(node) if isinstance(item, ast.Name)
        )
        for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
            if isinstance(call.func, ast.Name):
                called = call.func.id
                observed_calls.add(called)
                if called in definitions and called not in reachable:
                    frontier.append(called)
            elif isinstance(call.func, ast.Attribute):
                observed_calls.add(call.func.attr)
    forbidden = sorted(
        (reachable | observed_calls | observed_names) & FORBIDDEN_REACHABLE
    )
    body = {
        "parameters": parameters,
        "reachable_functions": sorted(reachable),
        "forbidden_reachable": forbidden,
        "candidate_source_sha256": sha256_file(repo / CANDIDATE_PATH),
    }
    return {
        **body,
        "pass": parameters == ["current", "completed"] and not forbidden,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def evaluate_criterion(index: int, criterion: tuple[int, ...]) -> dict[str, Any]:
    prefix = f"e5-criterion-{index:03d}"
    contact = build_split(f"{prefix}-contact", criterion)
    canary = build_split(f"{prefix}-canary", criterion)
    further_contact = build_split(f"{prefix}-further-contact", criterion)
    further_canary = build_split(f"{prefix}-further-canary", criterion)
    opposite_contact = _opposite_world(contact)
    opposite_canary = _opposite_world(canary)
    rescued_contact = {
        "archive": copy.deepcopy(opposite_contact["archive"]),
        "outcomes": copy.deepcopy(contact["outcomes"]),
    }
    deleted = {"archive": copy.deepcopy(contact["archive"]), "outcomes": []}

    positive = _controller_snapshot(f"criterion-{index}", criterion)
    negative_weights = tuple(-value for value in criterion)
    negative = _controller_snapshot(f"criterion-{index}-opposite", negative_weights)
    original_score = score_snapshot(positive, contact)
    original_canary = score_snapshot(positive, canary)
    contradiction = score_snapshot(positive, opposite_contact)
    corrected = score_snapshot(negative, opposite_canary)
    further_contradiction = score_snapshot(negative, further_contact)
    further_correction = score_snapshot(positive, further_canary)

    anchors = {
        "zero": (0, 0, 0, 0),
        **{
            f"axis-{dimension}-{sign}": tuple(
                sign if axis == dimension else 0
                for axis in range(DIMENSION_COUNT)
            )
            for dimension in range(DIMENSION_COUNT)
            for sign in (-1, 1)
        },
    }
    fixed_pair_errors = []
    for name, weights in anchors.items():
        snapshot = _controller_snapshot(name, weights)
        fixed_pair_errors.append(
            score_snapshot(snapshot, contact)["errors"]
            + score_snapshot(snapshot, opposite_contact)["errors"]
        )

    shuffled_contact = {
        "archive": list(reversed(contact["archive"])),
        "outcomes": list(reversed(contact["outcomes"])),
    }
    shuffled_score = score_snapshot(positive, shuffled_contact)
    checks = {
        "raw_indistinguishability": _raw_projection_sha256(contact)
        == _raw_projection_sha256(opposite_contact),
        "outcome_complement": all(
            left["pattern_id"] == right["pattern_id"]
            and left["outcome"] == 1 - right["outcome"]
            for left, right in zip(
                contact["outcomes"], opposite_contact["outcomes"], strict=True
            )
        ),
        "preference_identification": _preference_gate(contact, criterion)
        and _preference_gate(opposite_contact, negative_weights),
        "oracle_path": original_score["errors"] == 0
        and original_canary["errors"] == 0
        and contradiction["errors"] == PATTERN_COUNT
        and corrected["errors"] == 0
        and further_contradiction["errors"] == PATTERN_COUNT
        and further_correction["errors"] == 0,
        "fixed_state_symmetry": all(
            errors == PATTERN_COUNT for errors in fixed_pair_errors
        ),
        "outcome_deletion": deleted["outcomes"] == []
        and _raw_projection_sha256(deleted) == _raw_projection_sha256(contact),
        "paired_rescue": _world_sha256(rescued_contact) == _world_sha256(contact)
        and score_snapshot(positive, rescued_contact)["receipt_sha256"]
        == original_score["receipt_sha256"],
        "order_placebo": shuffled_score["receipt_sha256"]
        == original_score["receipt_sha256"],
    }
    body = {
        "criterion_index": index,
        "criterion_sha256": sha256_bytes(canonical_json(criterion)),
        "original_world_sha256": _world_sha256(contact),
        "opposite_world_sha256": _world_sha256(opposite_contact),
        "checks": checks,
    }
    return {
        **body,
        "pass": all(checks.values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    family = criteria()
    results = [
        evaluate_criterion(index, criterion)
        for index, criterion in enumerate(family)
    ]
    authority = candidate_authority(repo)
    check_counts = {
        name: sum(result["checks"][name] for result in results)
        for name in results[0]["checks"]
    }
    gates = {
        "criterion_family": len(family) == acceptance["criterion_count"]
        and len(set(family)) == len(family),
        "all_criteria": all(result["pass"] for result in results),
        "raw_indistinguishability": check_counts["raw_indistinguishability"]
        == len(family),
        "outcome_complement": check_counts["outcome_complement"] == len(family),
        "preference_identification": check_counts["preference_identification"]
        == len(family),
        "oracle_path": check_counts["oracle_path"] == len(family),
        "fixed_state_symmetry": check_counts["fixed_state_symmetry"]
        == len(family),
        "deletion_rescue": check_counts["outcome_deletion"] == len(family)
        and check_counts["paired_rescue"] == len(family),
        "order_placebo": check_counts["order_placebo"] == len(family),
        "candidate_authority": authority["pass"],
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_transition": acceptance["evaluation_transition"],
        "claim_limit": acceptance["claim_limit"],
        "candidate_actor_outputs": False,
        "criterion_count": len(family),
        "criterion_family_sha256": sha256_bytes(canonical_json(family)),
        "criterion_receipts_sha256": sha256_bytes(
            canonical_json([result["receipt_sha256"] for result in results])
        ),
        "check_counts": check_counts,
        "candidate_authority": authority,
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
        raise RuntimeError("OT-0034 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0034 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0034 fixed input identity differs")
    return lock


def record_sealed_result(repo: Path, output: Path, run_id: str) -> Path:
    output.chmod(0o600)
    try:
        return record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="controller-only-e5-weighted-selector-calibration",
            evidence_class="public-reconstructible",
            recipe=(
                "PYTHONPATH=src python3 experiments/ot_0034_harness.py "
                "--output $EVIDENCE/ot-0034-result.json"
            ),
            public_url=None,
            limitations=[
                "This is controller calibration, not OT-1 evidence.",
                "A pass authorizes at most one fresh integration candidate.",
                "The calibrated family remains one synthetic weighted-selector domain.",
            ],
            input_manifests=[str(PREDECESSOR_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0034-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0034 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("OT-0034 output already exists")
    result = run_calibration(repo)
    raw = {
        **result,
        "run_id": args.run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
    }
    write_sealed_json(output, raw)
    manifest = record_sealed_result(repo, output, args.run_id)
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(repo)), "summary": result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0
