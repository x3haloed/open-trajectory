from __future__ import annotations

import argparse
import ast
import copy
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
from .ot0003_world import RULES, DiscrepancyGatedVersionLedger, structural_holdout_batch
from .ot0033_weighted_selector import (
    _hidden_weights,
    complete_encounter,
    initial_snapshot,
    learn,
    neutralize_outcome_credit,
    project,
    restore,
    select_events,
)
from .ot0035_integration import (
    PROJECTION_LIMIT,
    apply_to_ledger,
    build_contact,
    fixed_snapshots,
    selected_observations,
)
from .ot0036_e6_calibration import controller_errors, rule_pairs


EXPERIMENT_ID = "OT-0037"
ACCEPTANCE_PATH = Path("spec/ot-0037-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0037-run-lock.json")
CANDIDATE_PATH = Path("src/open_trajectory_harness/ot0033_weighted_selector.py")
INTEGRATION_PATH = Path("src/open_trajectory_harness/ot0035_integration.py")
EVALUATOR_PATH = Path("src/open_trajectory_harness/ot0036_e6_calibration.py")
OT0_LEDGER_PATH = Path("src/open_trajectory_harness/ot0003_world.py")
E6_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0036/"
    "ot-0036-e6-deterministic-integration-calibration-001.json"
)
OT0_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json"
)
DEFAULT_RUN_ID = "ot-0037-e6-deterministic-ot1-candidate-001"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "candidate_protocol_sha256": Path(
            "src/open_trajectory_harness/ot0037_deterministic_candidate.py"
        ),
        "candidate_carrier_sha256": CANDIDATE_PATH,
        "integration_adapter_sha256": INTEGRATION_PATH,
        "deterministic_evaluator_sha256": EVALUATOR_PATH,
        "ot0_ledger_core_sha256": OT0_LEDGER_PATH,
        "entrypoint_sha256": Path("experiments/ot_0037_harness.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path(
            "src/open_trajectory_harness/ot0003.py"
        ),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "e6_manifest_sha256": E6_MANIFEST_PATH,
        "ot0_manifest_sha256": OT0_MANIFEST_PATH,
    }


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0037 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-e6-deterministic-ot1-task",
            }
        )
    )


def build_task(task_seed: str) -> dict[str, Any]:
    criterion = _hidden_weights(task_seed)
    pairs = rule_pairs()
    digest = sha256_bytes(f"{task_seed}:rule-pair".encode())
    pair = pairs[int(digest, 16) % len(pairs)]
    if int(digest[0], 16) % 2:
        pair = (pair[1], pair[0])
    regimes = (
        (criterion, pair[0]),
        (tuple(-value for value in criterion), pair[1]),
        (criterion, pair[0]),
    )
    body = {
        "schema_version": 1,
        "regimes": [
            {
                "index": index,
                "contact": build_contact(
                    f"ot-0037-regime-{index}-contact", weights, rule_id
                ),
                "rule_id": rule_id,
            }
            for index, (weights, rule_id) in enumerate(regimes, start=1)
        ],
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def _rule_outcomes(rule_id: str) -> tuple[int, ...]:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    return tuple(rule.predict(query) for query in structural_holdout_batch())


def _novelty_gate(repo: Path, regimes: list[dict[str, Any]]) -> dict[str, Any]:
    source = (repo / CANDIDATE_PATH).read_text(encoding="utf-8")
    tree = ast.parse(source)
    literal_sequences = {
        tuple(
            -item.operand.value
            if isinstance(item, ast.UnaryOp)
            and isinstance(item.op, ast.USub)
            and isinstance(item.operand, ast.Constant)
            and type(item.operand.value) is int
            else item.value
            for item in node.elts
        )
        for node in ast.walk(tree)
        if isinstance(node, (ast.List, ast.Tuple))
        and len(node.elts) == 4
        and all(
            (isinstance(item, ast.Constant) and type(item.value) is int)
            or (
                isinstance(item, ast.UnaryOp)
                and isinstance(item.op, ast.USub)
                and isinstance(item.operand, ast.Constant)
                and type(item.operand.value) is int
            )
            for item in node.elts
        )
    }
    learned = {tuple(regime["learned_weights"]) for regime in regimes}
    body = {
        "learned_weight_identities": sorted(
            sha256_bytes(canonical_json(weights)) for weights in learned
        ),
        "literal_collision_count": len(learned & literal_sequences),
        "candidate_source_sha256": sha256_bytes(source.encode()),
        "e6_manifest_sha256": sha256_file(repo / E6_MANIFEST_PATH),
    }
    return {
        **body,
        "pass": len(learned) == 2 and body["literal_collision_count"] == 0,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_lineage(task_seed: str) -> dict[str, Any]:
    acceptance = load_json(ACCEPTANCE_PATH)
    task = build_task(task_seed)
    selector = initial_snapshot()
    candidate_ledger = DiscrepancyGatedVersionLedger()
    controls = fixed_snapshots()
    control_ledgers = {
        name: DiscrepancyGatedVersionLedger() for name in controls
    }
    frozen_first_snapshot = None
    frozen_first_ledger = None
    regimes = []
    control_errors = {name: [] for name in (*controls, "frozen-first-learned")}
    for regime in task["regimes"]:
        source = restore(project(selector))
        completed = complete_encounter(source, regime["contact"])
        neutralized, neutralized_receipt = learn(
            source, neutralize_outcome_credit(completed)
        )
        learned, update = learn(source, completed)
        queries = structural_holdout_batch()
        outcomes = _rule_outcomes(regime["rule_id"])
        parent = copy.deepcopy(candidate_ledger)
        candidate_ledger, candidate_projection = apply_to_ledger(
            parent, learned, regime["contact"], queries
        )
        unchanged_ledger, unchanged_projection = apply_to_ledger(
            parent, source, regime["contact"], queries
        )
        selected = select_events(learned, regime["contact"]["archive"])
        regime_control_errors = {}
        projection_bytes = [
            len(candidate_projection.encode()),
            len(unchanged_projection.encode()),
        ]
        budgets = [
            len(selected_observations(learned, regime["contact"])),
            len(selected_observations(source, regime["contact"])),
        ]
        for name, snapshot in controls.items():
            ledger, projection_text = apply_to_ledger(
                control_ledgers[name], snapshot, regime["contact"], queries
            )
            control_ledgers[name] = ledger
            errors = controller_errors(ledger, queries, outcomes)
            control_errors[name].append(errors)
            regime_control_errors[name] = errors
            projection_bytes.append(len(projection_text.encode()))
            budgets.append(len(selected_observations(snapshot, regime["contact"])))
        if frozen_first_snapshot is None:
            frozen_first_snapshot = learned
            frozen_first_ledger = copy.deepcopy(candidate_ledger)
            frozen_projection = candidate_projection
        else:
            frozen_first_ledger, frozen_projection = apply_to_ledger(
                frozen_first_ledger,
                frozen_first_snapshot,
                regime["contact"],
                queries,
            )
            budgets.append(
                len(selected_observations(frozen_first_snapshot, regime["contact"]))
            )
        frozen_errors = controller_errors(frozen_first_ledger, queries, outcomes)
        control_errors["frozen-first-learned"].append(frozen_errors)
        regime_control_errors["frozen-first-learned"] = frozen_errors
        projection_bytes.append(len(frozen_projection.encode()))
        regimes.append(
            {
                "index": regime["index"],
                "rule_id_sha256": sha256_bytes(regime["rule_id"].encode()),
                "source_snapshot_sha256": source.sha256,
                "learned_snapshot_sha256": learned.sha256,
                "learned_weights": list(learned.weights),
                "contact_errors": sum(
                    decision["error"] for decision in completed["decisions"]
                ),
                "candidate_errors": controller_errors(
                    candidate_ledger, queries, outcomes
                ),
                "unchanged_errors": controller_errors(
                    unchanged_ledger, queries, outcomes
                ),
                "control_errors": regime_control_errors,
                "changed": learned.sha256 != source.sha256,
                "fresh_restored": restore(project(learned)).sha256
                == learned.sha256,
                "receipt_identity": learned.parent_sha256 == source.sha256
                and learned.update_receipt_sha256
                == update["learning_receipt_sha256"],
                "neutralized_changed": neutralized.sha256 != source.sha256,
                "completed_receipt_sha256": completed["receipt_sha256"],
                "update_receipt_sha256": update["receipt_sha256"],
                "neutralized_receipt_sha256": neutralized_receipt["receipt_sha256"],
                "selected_event_ids_sha256": sha256_bytes(
                    canonical_json([event["event_id"] for event in selected])
                ),
                "candidate_projection_sha256": sha256_bytes(
                    candidate_projection.encode()
                ),
                "unchanged_projection_sha256": sha256_bytes(
                    unchanged_projection.encode()
                ),
                "projection_bytes_max": max(projection_bytes),
                "active_budgets": budgets,
            }
        )
        selector = learned
    candidate_errors = [regime["candidate_errors"] for regime in regimes]
    unchanged_errors = [regime["unchanged_errors"] for regime in regimes]
    contact_errors = [regime["contact_errors"] for regime in regimes]
    fixed_aggregates = {
        name: sum(values) for name, values in control_errors.items()
    }
    candidate_aggregate = sum(candidate_errors)
    best_fixed_aggregate = min(fixed_aggregates.values())
    assert frozen_first_snapshot is not None
    gates = {
        "task_shape": len(regimes) == acceptance["regime_count"],
        "contact_pressure": contact_errors == acceptance["expected_contact_errors"],
        "learned_change": all(regime["changed"] for regime in regimes),
        "receipt_identity": all(
            regime["receipt_identity"] for regime in regimes
        ),
        "outcome_credit_ablation": all(
            not regime["neutralized_changed"] for regime in regimes
        ),
        "candidate_path": candidate_errors == acceptance["expected_candidate_errors"],
        "unchanged_ablation": unchanged_errors
        == acceptance["expected_unchanged_errors"],
        "harmful_correction": unchanged_errors[1:] == [8, 8]
        and candidate_errors[1:] == [0, 0],
        "fixed_controls": best_fixed_aggregate - candidate_aggregate
        >= acceptance["minimum_candidate_advantage_over_best_fixed_aggregate"],
        "fixed_control_identity": set(fixed_aggregates)
        == set(acceptance["fixed_selector_conditions"]),
        "active_budget": all(
            value == acceptance["active_inheritance_budget"]
            for regime in regimes
            for value in regime["active_budgets"]
        ),
        "projection_budget": all(
            regime["projection_bytes_max"] <= acceptance["projection_byte_limit"]
            for regime in regimes
        ),
        "fresh_restoration": all(
            regime["fresh_restored"] for regime in regimes
        )
        and all(
            restore(project(snapshot)).sha256 == snapshot.sha256
            for snapshot in (selector, frozen_first_snapshot, *controls.values())
        ),
    }
    body = {
        "task_sha256": task["task_sha256"],
        "regimes": regimes,
        "candidate_errors": candidate_errors,
        "unchanged_errors": unchanged_errors,
        "contact_errors": contact_errors,
        "candidate_aggregate_errors": candidate_aggregate,
        "best_fixed_aggregate_errors": best_fixed_aggregate,
        "fixed_aggregate_errors": fixed_aggregates,
        "gates": gates,
    }
    return {
        **body,
        "pass": all(gates.values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def _run_reconstruction(repo: Path, task_seed: str) -> dict[str, Any]:
    worker = subprocess.run(
        [
            sys.executable,
            "-m",
            "open_trajectory_harness.ot0037_deterministic_candidate",
            "--internal-worker",
            "--task-seed",
            task_seed,
        ],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    if worker.returncode:
        raise RuntimeError("OT-0037 clean reconstruction process failed")
    try:
        result = json.loads(worker.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("OT-0037 reconstruction output is malformed") from error
    if not isinstance(result, dict):
        raise RuntimeError("OT-0037 reconstruction output has the wrong shape")
    return result


def run_protocol(repo: Path, task_seed: str) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    reconstructions = [
        _run_reconstruction(repo, task_seed)
        for _ in range(acceptance["clean_reconstructions_required"])
    ]
    primary = reconstructions[0]
    novelty = _novelty_gate(repo, primary["regimes"])
    reconstruction_receipts = [
        reconstruction["receipt_sha256"] for reconstruction in reconstructions
    ]
    gates = {
        **primary["gates"],
        "lineage": all(reconstruction["pass"] for reconstruction in reconstructions),
        "clean_reconstruction": len(reconstructions)
        == acceptance["clean_reconstructions_required"]
        and len(set(reconstruction_receipts)) == 1
        and canonical_json(reconstructions[0]) == canonical_json(reconstructions[1]),
        "novelty": novelty["pass"],
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "task_sha256": primary["task_sha256"],
        "candidate_visible_authority": [
            "paired_raw_events",
            "source_snapshot",
            "prior_selections",
            "released_completed_outcomes",
        ],
        "primary": primary,
        "reconstruction_receipts": reconstruction_receipts,
        "novelty": novelty,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0037 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0037 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0037 fixed input identity differs")
    task_seed = lock.get("task_seed", "")
    if task_seed != expected_task_seed(implementation):
        raise RuntimeError("OT-0037 task seed is not mechanically derived")
    if build_task(task_seed)["task_sha256"] != lock.get("task_sha256"):
        raise RuntimeError("OT-0037 task identity differs")
    return lock


def record_sealed_result(repo: Path, output: Path, run_id: str) -> Path:
    output.chmod(0o600)
    try:
        return record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="e6-deterministic-ot1-candidate",
            evidence_class="public-reconstructible",
            recipe=(
                "PYTHONPATH=src python3 experiments/ot_0037_harness.py "
                "--output $EVIDENCE/ot-0037-result.json"
            ),
            public_url=None,
            limitations=[
                "A pass is single synthetic-domain OT-1 evidence.",
                "This result does not establish OT-2 or cross-domain generality.",
                "OT-0035 remains failed and is not rescored.",
                "This run consumes E6 authorization regardless of disposition.",
            ],
            input_manifests=[str(E6_MANIFEST_PATH), str(OT0_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0037-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--internal-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--task-seed", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.internal_worker:
        if not isinstance(args.task_seed, str) or not re.fullmatch(
            r"[0-9a-f]{64}", args.task_seed
        ):
            raise RuntimeError("OT-0037 internal worker requires a task seed")
        print(json.dumps(run_lineage(args.task_seed), sort_keys=True))
        return 0
    if args.output is None:
        raise RuntimeError("OT-0037 output is required")
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0037 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("OT-0037 output already exists")
    result = run_protocol(repo, lock["task_seed"])
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


if __name__ == "__main__":
    raise SystemExit(main())
