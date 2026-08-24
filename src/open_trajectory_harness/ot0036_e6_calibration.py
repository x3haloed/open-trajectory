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
from .ot0003_world import (
    RULES,
    DiscrepancyGatedVersionLedger,
    eligible_hidden_rules,
    structural_holdout_batch,
)
from .ot0033_weighted_selector import (
    DIMENSION_COUNT,
    WeightedSelectorSnapshot,
    _snapshot,
)
from .ot0034_e5_calibration import candidate_authority
from .ot0035_integration import (
    PROJECTION_LIMIT,
    apply_to_ledger,
    build_contact,
    fixed_snapshots,
    selected_observations,
)


EXPERIMENT_ID = "OT-0036"
ACCEPTANCE_PATH = Path("spec/ot-0036-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0036-run-lock.json")
CANDIDATE_PATH = Path("src/open_trajectory_harness/ot0033_weighted_selector.py")
INTEGRATION_PATH = Path("src/open_trajectory_harness/ot0035_integration.py")
OT34_CORE_PATH = Path("src/open_trajectory_harness/ot0034_e5_calibration.py")
OT0_LEDGER_PATH = Path("src/open_trajectory_harness/ot0003_world.py")
E5_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0034/ot-0034-e5-weighted-selector-calibration-001.json"
)
OT35_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0035/ot-0035-e5-ot0-ledger-integration-001.json"
)
OT0_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json"
)
DEFAULT_RUN_ID = "ot-0036-e6-deterministic-integration-calibration-001"
FORBIDDEN_INTEGRATION_AUTHORITY = {
    "_hidden_weights",
    "build_contact",
    "build_task",
    "expected_task_seed",
    "run_core",
    "run_actor_turn",
    "summarize",
    "validate_run_lock",
    "record_artifact",
    "run",
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
            "src/open_trajectory_harness/ot0036_e6_calibration.py"
        ),
        "candidate_carrier_sha256": CANDIDATE_PATH,
        "integration_adapter_sha256": INTEGRATION_PATH,
        "e5_authority_core_sha256": OT34_CORE_PATH,
        "ot0_ledger_core_sha256": OT0_LEDGER_PATH,
        "entrypoint_sha256": Path("experiments/ot_0036_harness.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path(
            "src/open_trajectory_harness/ot0003.py"
        ),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "e5_manifest_sha256": E5_MANIFEST_PATH,
        "failed_candidate_manifest_sha256": OT35_MANIFEST_PATH,
        "ot0_manifest_sha256": OT0_MANIFEST_PATH,
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


def rule_pairs() -> tuple[tuple[str, str], ...]:
    eligible = eligible_hidden_rules()
    by_mask = {
        rule.mask: {
            candidate.bias: candidate.rule_id
            for candidate in eligible
            if candidate.mask == rule.mask
        }
        for rule in eligible
    }
    return tuple(
        (biases[0], biases[1]) for _, biases in sorted(by_mask.items())
    )


def _controller_snapshot(
    name: str, weights: tuple[int, ...]
) -> WeightedSelectorSnapshot:
    receipt = sha256_bytes(
        canonical_json({"controller_oracle": name, "weights": weights})
    )
    return _snapshot(0, None, receipt, weights)


def _rule_outcomes(rule_id: str) -> tuple[int, ...]:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    return tuple(rule.predict(query) for query in structural_holdout_batch())


def controller_predictions(
    ledger: DiscrepancyGatedVersionLedger,
    queries: tuple[tuple[int, int, int, int], ...],
) -> tuple[int, ...]:
    if len(ledger.hypotheses) == 1:
        return tuple(ledger.hypotheses[0].predict(query) for query in queries)
    return (0,) * len(queries)


def controller_errors(
    ledger: DiscrepancyGatedVersionLedger,
    queries: tuple[tuple[int, int, int, int], ...],
    outcomes: tuple[int, ...],
) -> int:
    return sum(
        prediction != outcome
        for prediction, outcome in zip(
            controller_predictions(ledger, queries), outcomes, strict=True
        )
    )


def integration_authority(repo: Path) -> dict[str, Any]:
    source = (repo / INTEGRATION_PATH).read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    root = "apply_to_ledger"
    parameters = [argument.arg for argument in definitions[root].args.args]
    reachable = set()
    observed_calls = set()
    observed_names = set()
    frontier = [root]
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
        (reachable | observed_calls | observed_names)
        & FORBIDDEN_INTEGRATION_AUTHORITY
    )
    body = {
        "parameters": parameters,
        "reachable_functions": sorted(reachable),
        "forbidden_reachable": forbidden,
        "integration_source_sha256": sha256_file(repo / INTEGRATION_PATH),
    }
    return {
        **body,
        "pass": parameters == ["parent", "snapshot", "contact", "queries"]
        and reachable == {"apply_to_ledger", "selected_observations"}
        and not forbidden,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def evaluate_case(
    criterion_index: int,
    criterion: tuple[int, ...],
    rule_pair_index: int,
    pair: tuple[str, str],
) -> dict[str, Any]:
    opposite = tuple(-value for value in criterion)
    oracle_weights = (criterion, opposite, criterion)
    rule_ids = (pair[0], pair[1], pair[0])
    queries = structural_holdout_batch()
    source_snapshot = _controller_snapshot(
        f"e6-c{criterion_index:03d}-p{rule_pair_index:02d}-initial",
        (0, 0, 0, 0),
    )
    candidate_ledger = DiscrepancyGatedVersionLedger()
    controls = fixed_snapshots()
    control_ledgers = {
        name: DiscrepancyGatedVersionLedger() for name in controls
    }
    frozen_first_ledger: DiscrepancyGatedVersionLedger | None = None
    frozen_first_snapshot: WeightedSelectorSnapshot | None = None
    candidate_errors = []
    unchanged_errors = []
    control_errors = {name: [] for name in (*controls, "frozen-first-oracle")}
    projection_bytes = []
    replay_receipts = []
    budgets = []
    for regime_index, (weights, rule_id) in enumerate(
        zip(oracle_weights, rule_ids, strict=True), start=1
    ):
        prefix = (
            f"e6-c{criterion_index:03d}-p{rule_pair_index:02d}-"
            f"r{regime_index}"
        )
        contact = build_contact(prefix, weights, rule_id)
        outcomes = _rule_outcomes(rule_id)
        oracle = _controller_snapshot(f"{prefix}-oracle", weights)
        parent = copy.deepcopy(candidate_ledger)
        candidate_ledger, candidate_projection = apply_to_ledger(
            parent, oracle, contact, queries
        )
        unchanged_ledger, unchanged_projection = apply_to_ledger(
            parent, source_snapshot, contact, queries
        )
        replay_ledger, replay_projection = apply_to_ledger(
            parent, oracle, contact, queries
        )
        candidate_errors.append(
            controller_errors(candidate_ledger, queries, outcomes)
        )
        unchanged_errors.append(
            controller_errors(unchanged_ledger, queries, outcomes)
        )
        projection_bytes.extend(
            [len(candidate_projection.encode()), len(unchanged_projection.encode())]
        )
        replay_receipts.append(
            sha256_bytes(
                canonical_json(
                    {
                        "projection": replay_projection,
                        "errors": controller_errors(replay_ledger, queries, outcomes),
                    }
                )
            )
            == sha256_bytes(
                canonical_json(
                    {
                        "projection": candidate_projection,
                        "errors": candidate_errors[-1],
                    }
                )
            )
        )
        budgets.extend(
            [
                len(selected_observations(snapshot, contact))
                for snapshot in (oracle, source_snapshot, *controls.values())
            ]
        )
        for name, snapshot in controls.items():
            ledger, projection_text = apply_to_ledger(
                control_ledgers[name], snapshot, contact, queries
            )
            control_ledgers[name] = ledger
            projection_bytes.append(len(projection_text.encode()))
            control_errors[name].append(
                controller_errors(ledger, queries, outcomes)
            )
        if frozen_first_ledger is None:
            frozen_first_ledger = copy.deepcopy(candidate_ledger)
            frozen_first_snapshot = oracle
            frozen_projection = candidate_projection
        else:
            assert frozen_first_snapshot is not None
            frozen_first_ledger, frozen_projection = apply_to_ledger(
                frozen_first_ledger, frozen_first_snapshot, contact, queries
            )
            budgets.append(
                len(selected_observations(frozen_first_snapshot, contact))
            )
        projection_bytes.append(len(frozen_projection.encode()))
        control_errors["frozen-first-oracle"].append(
            controller_errors(frozen_first_ledger, queries, outcomes)
        )
        source_snapshot = oracle
    fixed_aggregates = {
        name: sum(values) for name, values in control_errors.items()
    }
    checks = {
        "candidate_path": candidate_errors == [0, 0, 0],
        "unchanged_ablation": unchanged_errors == [4, 8, 8],
        "harmful_correction": unchanged_errors[1:] == [8, 8]
        and candidate_errors[1:] == [0, 0],
        "fixed_controls": min(fixed_aggregates.values()) == 8
        and fixed_aggregates["frozen-first-oracle"] == 8,
        "active_budget": budgets and all(value == 80 for value in budgets),
        "projection_budget": projection_bytes
        and max(projection_bytes) <= PROJECTION_LIMIT,
        "deterministic_replay": all(replay_receipts),
    }
    body = {
        "criterion_index": criterion_index,
        "criterion_sha256": sha256_bytes(canonical_json(criterion)),
        "rule_pair_index": rule_pair_index,
        "rule_pair_sha256": sha256_bytes(canonical_json(pair)),
        "candidate_errors": candidate_errors,
        "unchanged_errors": unchanged_errors,
        "best_fixed_aggregate_errors": min(fixed_aggregates.values()),
        "checks": checks,
    }
    return {
        **body,
        "pass": all(checks.values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    criterion_family = criteria()
    pairs = rule_pairs()
    cases = [
        (criterion_index, criterion, pair_index, pair)
        for criterion_index, criterion in enumerate(criterion_family)
        for pair_index, pair in enumerate(pairs)
    ]
    results = [evaluate_case(*case) for case in cases]
    reversed_results = [evaluate_case(*case) for case in reversed(cases)]
    check_counts = {
        name: sum(result["checks"][name] for result in results)
        for name in results[0]["checks"]
    }
    learner = candidate_authority(repo)
    integration = integration_authority(repo)
    forward_receipts = [result["receipt_sha256"] for result in results]
    reverse_receipts = [result["receipt_sha256"] for result in reversed_results]
    gates = {
        "criterion_family": len(criterion_family) == acceptance["criterion_count"]
        and len(set(criterion_family)) == len(criterion_family),
        "rule_pairs": len(pairs) == acceptance["eligible_rule_pair_count"]
        and len({rule for pair in pairs for rule in pair}) == 2 * len(pairs),
        "case_count": len(cases) == acceptance["case_count"],
        "all_cases": all(result["pass"] for result in results),
        "candidate_path": check_counts["candidate_path"] == len(cases),
        "unchanged_ablation": check_counts["unchanged_ablation"] == len(cases),
        "harmful_correction": check_counts["harmful_correction"] == len(cases),
        "fixed_controls": check_counts["fixed_controls"] == len(cases),
        "active_budget": check_counts["active_budget"] == len(cases),
        "projection_budget": check_counts["projection_budget"] == len(cases),
        "deterministic_replay": check_counts["deterministic_replay"] == len(cases),
        "order_placebo": forward_receipts == list(reversed(reverse_receipts)),
        "candidate_authority": learner["pass"],
        "integration_authority": integration["pass"],
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_transition": acceptance["evaluation_transition"],
        "claim_limit": acceptance["claim_limit"],
        "candidate_actor_outputs": False,
        "candidate_learner_outputs": False,
        "criterion_count": len(criterion_family),
        "eligible_rule_pair_count": len(pairs),
        "case_count": len(cases),
        "criterion_family_sha256": sha256_bytes(canonical_json(criterion_family)),
        "rule_pairs_sha256": sha256_bytes(canonical_json(pairs)),
        "case_receipts_sha256": sha256_bytes(canonical_json(forward_receipts)),
        "check_counts": check_counts,
        "candidate_authority": learner,
        "integration_authority": integration,
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
        raise RuntimeError("OT-0036 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0036 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0036 fixed input identity differs")
    return lock


def record_sealed_result(repo: Path, output: Path, run_id: str) -> Path:
    output.chmod(0o600)
    try:
        return record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="controller-only-e6-deterministic-integration-calibration",
            evidence_class="public-reconstructible",
            recipe=(
                "PYTHONPATH=src python3 experiments/ot_0036_harness.py "
                "--output $EVIDENCE/ot-0036-result.json"
            ),
            public_url=None,
            limitations=[
                "This is controller calibration, not OT-1 evidence.",
                "A pass authorizes at most one fresh deterministic integration candidate.",
                "OT-0035 remains failed and is not rescored under E6.",
                "The calibrated family remains one synthetic selector and parity domain.",
            ],
            input_manifests=[
                str(E5_MANIFEST_PATH),
                str(OT35_MANIFEST_PATH),
                str(OT0_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0036-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0036 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("OT-0036 output already exists")
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


if __name__ == "__main__":
    raise SystemExit(main())
