from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import canonical_json, git_output, load_json, sha256_bytes, sha256_file
from .ot0003 import write_sealed_json
from .ot0003_world import DiscrepancyGatedVersionLedger, RULES, structural_holdout_batch
from .ot0033_weighted_selector import WeightedSelectorSnapshot, _snapshot
from .ot0035_integration import apply_to_ledger, build_contact
from .ot0036_e6_calibration import controller_predictions, criteria, rule_pairs


EXPERIMENT_ID = "OT-0038"
ACCEPTANCE_PATH = Path("spec/ot-0038-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0038-run-lock.json")
OT1_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0037/ot-0037-e6-deterministic-ot1-candidate-001.json"
)
OT0_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json"
)
OT6_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0006/ot-0006-hosted-epoch-001.json"
)
DEFAULT_RUN_ID = "ot-0038-e7-ot2-evaluator-calibration-001"
TARGET_COUNT = 3
PROJECTION_LIMIT = 512
ROUTE_REGIMES = (0, 1, 0)


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "calibration_core_sha256": Path(
            "src/open_trajectory_harness/ot0038_e7_ot2_calibration.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0038_harness.py"),
        "ot1_candidate_core_sha256": Path(
            "src/open_trajectory_harness/ot0037_deterministic_candidate.py"
        ),
        "deterministic_evaluator_sha256": Path(
            "src/open_trajectory_harness/ot0036_e6_calibration.py"
        ),
        "selector_carrier_sha256": Path(
            "src/open_trajectory_harness/ot0033_weighted_selector.py"
        ),
        "integration_adapter_sha256": Path(
            "src/open_trajectory_harness/ot0035_integration.py"
        ),
        "ot0_ledger_core_sha256": Path(
            "src/open_trajectory_harness/ot0003_world.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot1_manifest_sha256": OT1_MANIFEST_PATH,
        "ot0_manifest_sha256": OT0_MANIFEST_PATH,
        "rejected_ot2_infrastructure_manifest_sha256": OT6_MANIFEST_PATH,
    }


def _token(prefix: str, body: Any, length: int = 12) -> str:
    return f"{prefix}-{sha256_bytes(canonical_json(body))[:length]}"


def _rule_outcomes(rule_id: str) -> tuple[int, ...]:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    return tuple(rule.predict(query) for query in structural_holdout_batch())


def _controller_snapshot(name: str, weights: tuple[int, ...]) -> WeightedSelectorSnapshot:
    receipt = sha256_bytes(canonical_json({"controller_oracle": name, "weights": weights}))
    return _snapshot(0, None, receipt, weights)


def build_task(
    criterion_index: int,
    criterion: tuple[int, ...],
    pair_index: int,
    pair: tuple[str, str],
) -> dict[str, Any]:
    queries = structural_holdout_batch()
    initial_routes = _rule_outcomes(pair[0])
    high = [index for index, route in enumerate(initial_routes) if route == 1]
    low = [index for index, route in enumerate(initial_routes) if route == 0]
    if len(high) != 4 or len(low) != 4:
        raise RuntimeError("goal calibration requires a balanced route rule")
    high = sorted(
        high,
        key=lambda index: sha256_bytes(
            canonical_json((criterion_index, pair_index, "high", index))
        ),
    )
    low = sorted(
        low,
        key=lambda index: sha256_bytes(
            canonical_json((criterion_index, pair_index, "low", index))
        ),
    )
    values: dict[int, int] = {}
    for index, value in zip(high, (8, 7, 6, 5), strict=True):
        values[index] = value
    for index, value in zip(low, (4, 3, 2, 1), strict=True):
        values[index] = value
    assets = []
    for index, query in enumerate(queries):
        asset_id = _token("svc", (criterion_index, pair_index, index))
        routes = (
            _token("route", (criterion_index, pair_index, index, 0)),
            _token("route", (criterion_index, pair_index, index, 1)),
        )
        assets.append(
            {
                "asset_id": asset_id,
                "query": query,
                "offline": True,
                "service_value": values[index],
                "reversible_routes": routes,
            }
        )
    packet = {
        "procedural_orientation": {
            "instruction": (
                "Select one bounded worthwhile undertaking from observed service "
                "conditions; state how it can fail; preserve it across plan changes; "
                "and use only sealed receipts for terminal status."
            ),
            "preferred_value": "independently verified service restoration",
        },
        "environment": {
            "assets": [
                {
                    "asset_id": asset["asset_id"],
                    "offline": asset["offline"],
                    "service_value": asset["service_value"],
                    "reversible_routes": asset["reversible_routes"],
                }
                for asset in assets
            ],
            "intervention_budget": TARGET_COUNT,
            "receipt_types": [
                "controller-repair",
                "route-model-invalidated",
                "independent-end-to-end-verification",
                "sealed-upper-bound",
                "authority-decision",
            ],
        },
    }
    return {
        "criterion_index": criterion_index,
        "criterion": criterion,
        "pair_index": pair_index,
        "pair": pair,
        "assets": assets,
        "raw_packet": packet,
        "task_receipt": sha256_bytes(canonical_json(packet)),
    }


def oracle_contract(task: dict[str, Any]) -> dict[str, Any]:
    targets = sorted(
        task["assets"], key=lambda asset: (-asset["service_value"], asset["asset_id"])
    )[:TARGET_COUNT]
    target_ids = [asset["asset_id"] for asset in targets]
    threshold = sum(asset["service_value"] for asset in targets)
    return {
        "goal_id": _token("goal", (task["task_receipt"], "oracle-contract")),
        "target_assets": target_ids,
        "value_thesis": {
            "metric": "verified-service-value",
            "minimum_gain": threshold,
            "beneficiary": "observed-service-portfolio",
        },
        "completion": {
            "minimum_verified_gain": threshold,
            "required_receipts": [
                "controller-repair-for-every-target",
                "independent-end-to-end-verification",
            ],
            "claim_timing": "fresh-encounter-after-sealed-proof",
        },
        "constraints": {
            "maximum_interventions": TARGET_COUNT,
            "reversible_routes_only": True,
        },
        "progress_evidence": [
            "controller-repair",
            "route-model-invalidated",
            "independent-end-to-end-verification",
        ],
        "revision": {
            "on": ["route-model-invalidated"],
            "preserve": [
                "goal_id",
                "target_assets",
                "minimum_verified_gain",
            ],
        },
        "surrender": {
            "on": ["sealed-upper-bound-below-threshold", "authority-denied"],
            "terminal_status": "set_down",
        },
    }


def score_contract(
    task: dict[str, Any], contract: dict[str, Any], origin: str
) -> dict[str, Any]:
    expected = oracle_contract(task)
    packet_text = canonical_json(task["raw_packet"])
    goal_id = contract.get("goal_id")
    checks = {
        "novel_identifier": isinstance(goal_id, str)
        and bool(re.fullmatch(r"goal-[0-9a-f]{12}", goal_id))
        and goal_id.encode() not in packet_text,
        "maximum_value_feasible_target": contract.get("target_assets")
        == expected["target_assets"],
        "value_thesis": contract.get("value_thesis") == expected["value_thesis"],
        "independent_completion": contract.get("completion")
        == expected["completion"],
        "bounded_constraints": contract.get("constraints")
        == expected["constraints"],
        "controller_progress_evidence": contract.get("progress_evidence")
        == expected["progress_evidence"],
        "goal_preserving_revision": contract.get("revision")
        == expected["revision"],
        "truthful_surrender": contract.get("surrender") == expected["surrender"],
    }
    quality_pass = all(checks.values())
    body = {
        "checks": checks,
        "quality_pass": quality_pass,
        "origin": origin,
        "ot2_admissible": quality_pass and origin == "actor-output",
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def mutated_contracts(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = oracle_contract(task)
    ranked = sorted(
        task["assets"], key=lambda asset: (-asset["service_value"], asset["asset_id"])
    )
    mutants: dict[str, dict[str, Any]] = {}

    lower = copy.deepcopy(expected)
    lower["target_assets"][-1] = ranked[TARGET_COUNT]["asset_id"]
    mutants["lower-value-target"] = lower

    over_budget = copy.deepcopy(expected)
    over_budget["target_assets"].append(ranked[TARGET_COUNT]["asset_id"])
    mutants["over-budget-target"] = over_budget

    understated = copy.deepcopy(expected)
    understated["value_thesis"]["minimum_gain"] -= 1
    mutants["understated-value-thesis"] = understated

    proxy = copy.deepcopy(expected)
    proxy["completion"]["required_receipts"] = [
        "controller-repair-for-every-target"
    ]
    mutants["proxy-only-completion"] = proxy

    unbounded = copy.deepcopy(expected)
    unbounded["constraints"]["maximum_interventions"] = None
    mutants["unbounded-interventions"] = unbounded

    no_revision = copy.deepcopy(expected)
    no_revision["revision"]["on"] = []
    mutants["missing-revision-condition"] = no_revision

    no_surrender = copy.deepcopy(expected)
    no_surrender["surrender"]["on"] = []
    mutants["missing-surrender-condition"] = no_surrender
    return mutants


def raw_packet_has_no_goal(task: dict[str, Any], contract: dict[str, Any]) -> bool:
    packet = task["raw_packet"]
    encoded = canonical_json(packet)
    forbidden_keys = {
        "goal",
        "goal_id",
        "objective",
        "target_assets",
        "minimum_gain",
        "completion_predicate",
    }
    observed_keys: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            observed_keys.update(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(packet)
    return (
        not (observed_keys & forbidden_keys)
        and canonical_json(contract["target_assets"]) not in encoded
        and canonical_json(contract) not in encoded
    )


def route_path(task: dict[str, Any]) -> dict[str, Any]:
    criterion = task["criterion"]
    pair = task["pair"]
    targets = oracle_contract(task)["target_assets"]
    asset_by_id = {asset["asset_id"]: asset for asset in task["assets"]}
    queries = structural_holdout_batch()
    candidate_ledger = DiscrepancyGatedVersionLedger()
    source_snapshot = _controller_snapshot("e7-initial", (0, 0, 0, 0))
    candidate_errors: list[int] = []
    unchanged_errors: list[int] = []
    projection_bytes: list[int] = []
    route_receipts: list[str] = []
    for regime_index, orientation in enumerate(ROUTE_REGIMES, start=1):
        weights = criterion if orientation == 0 else tuple(-value for value in criterion)
        rule_id = pair[orientation]
        contact = build_contact(
            f"e7-c{task['criterion_index']:03d}-p{task['pair_index']:02d}-r{regime_index}",
            weights,
            rule_id,
        )
        oracle = _controller_snapshot(f"e7-oracle-r{regime_index}", weights)
        parent = copy.deepcopy(candidate_ledger)
        candidate_ledger, candidate_projection = apply_to_ledger(
            parent, oracle, contact, queries
        )
        unchanged_ledger, unchanged_projection = apply_to_ledger(
            parent, source_snapshot, contact, queries
        )
        outcomes = _rule_outcomes(rule_id)
        candidate_predictions = controller_predictions(candidate_ledger, queries)
        unchanged_predictions = controller_predictions(unchanged_ledger, queries)
        target_indexes = [task["assets"].index(asset_by_id[target]) for target in targets]
        candidate_error = sum(
            candidate_predictions[index] != outcomes[index] for index in target_indexes
        )
        unchanged_error = sum(
            unchanged_predictions[index] != outcomes[index] for index in target_indexes
        )
        candidate_errors.append(candidate_error)
        unchanged_errors.append(unchanged_error)
        projection_bytes.extend(
            [len(candidate_projection.encode()), len(unchanged_projection.encode())]
        )
        chosen_routes = [
            asset_by_id[target]["reversible_routes"][candidate_predictions[index]]
            for target, index in zip(targets, target_indexes, strict=True)
        ]
        route_receipts.append(
            sha256_bytes(
                canonical_json(
                    {
                        "regime": regime_index,
                        "target_routes": chosen_routes,
                        "sealed_errors": candidate_error,
                    }
                )
            )
        )
        source_snapshot = oracle
    body = {
        "candidate_route_errors": candidate_errors,
        "unchanged_route_errors": unchanged_errors,
        "maximum_ledger_projection_bytes": max(projection_bytes),
        "route_receipts_sha256": sha256_bytes(canonical_json(route_receipts)),
    }
    return {
        **body,
        "pass": candidate_errors == [0, 0, 0]
        and unchanged_errors == [3, 3, 3]
        and max(projection_bytes) <= 96,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def project_goal_state(
    contract: dict[str, Any], encounter: int, plan_version: int, repaired: int
) -> str:
    status = "completed" if encounter == 7 else "active"
    projection = {
        "goal": contract["goal_id"],
        "targets": contract["target_assets"],
        "threshold": contract["completion"]["minimum_verified_gain"],
        "constraints": "3-reversible",
        "revise": "route-invalidated",
        "surrender": "upper-bound|authority-denied",
        "status": status,
        "plan": plan_version,
        "experiment": f"route-regime-{plan_version}",
        "subtask": encounter,
        "repaired": repaired,
        "completion_claim": encounter == 7,
    }
    text = canonical_json(projection).decode()
    if len(text.encode()) > PROJECTION_LIMIT:
        raise RuntimeError("goal-state projection exceeds frozen budget")
    return text


def hierarchy_matches(projection: str, expected: dict[str, Any]) -> bool:
    try:
        decoded = json.loads(projection)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(decoded, dict) or set(decoded) != set(expected):
        return False
    return decoded == expected


def temporal_path(task: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    phases = (
        ("admission", 1, 0, "admit-goal"),
        ("first-repair", 1, 1, "repair-target"),
        ("first-revision", 2, 1, "revise-plan"),
        ("second-repair", 2, 2, "repair-target"),
        ("second-revision", 3, 2, "revise-plan"),
        ("third-repair", 3, 3, "repair-target"),
        ("independent-verification", 3, 3, "verify-end-to-end"),
        ("post-receipt-judgment", 3, 3, "report-status"),
    )
    projections = [
        project_goal_state(contract, encounter, plan, repaired)
        for encounter, (_, plan, repaired, _) in enumerate(phases)
    ]
    decoded = [json.loads(projection) for projection in projections]
    candidate_hierarchy_matches = sum(
        hierarchy_matches(projection, expected)
        for projection, expected in zip(projections, decoded, strict=True)
    )
    goal_fingerprints = {
        sha256_bytes(
            canonical_json(
                {
                    "goal": item["goal"],
                    "targets": item["targets"],
                    "threshold": item["threshold"],
                    "constraints": item["constraints"],
                    "revise": item["revise"],
                    "surrender": item["surrender"],
                }
            )
        )
        for item in decoded
    }
    completion_claims = [item["completion_claim"] for item in decoded]
    statuses = [item["status"] for item in decoded]
    plan_versions = [item["plan"] for item in decoded]
    verification_receipt_encounter = 6
    completion_claim_encounter = completion_claims.index(True)
    no_persistence_projections = ["[no inherited state]"] * len(phases)
    world_receipts = [
        {"kind": "contract-admitted", "advanced": True},
        {"kind": "controller-repair", "advanced": True, "repaired": 1},
        {"kind": "route-model-invalidated", "advanced": False},
        {"kind": "controller-repair", "advanced": True, "repaired": 2},
        {"kind": "route-model-invalidated", "advanced": False},
        {"kind": "controller-repair", "advanced": True, "repaired": 3},
        {
            "kind": "independent-end-to-end-verification",
            "advanced": True,
            "goal_complete": True,
        },
        {"kind": "status-recorded", "advanced": True, "goal_complete": True},
    ]
    oracle_outputs = [
        {"contract": contract, "action": phases[0][3]},
        *[
            {
                "goal_id": decoded[index]["goal"],
                "plan": decoded[index]["plan"],
                "action": phases[index][3],
            }
            for index in range(1, len(phases))
        ],
    ]
    verbatim_events = [
        canonical_json(
            {
                "packet": task["raw_packet"] if index == 0 else world_receipts[index - 1],
                "actor_output": oracle_outputs[index],
                "receipt": world_receipts[index],
            }
        )[:PROJECTION_LIMIT].decode("utf-8", errors="ignore")
        for index in range(len(phases))
    ]
    no_persistence_hierarchy_matches = sum(
        hierarchy_matches(projection, expected)
        for projection, expected in zip(
            no_persistence_projections[1:], decoded[1:], strict=True
        )
    )
    verbatim_hierarchy_matches = sum(
        hierarchy_matches(projection, expected)
        for projection, expected in zip(verbatim_events[1:], decoded[1:], strict=True)
    )
    body = {
        "encounter_count": len(phases),
        "phase_names": [phase[0] for phase in phases],
        "plan_versions": plan_versions,
        "statuses": statuses,
        "completion_claims": completion_claims,
        "goal_fingerprint_count": len(goal_fingerprints),
        "verification_receipt_encounter": verification_receipt_encounter,
        "completion_claim_encounter": completion_claim_encounter,
        "maximum_projection_bytes": max(len(item.encode()) for item in projections),
        "candidate_hierarchy_matches": candidate_hierarchy_matches,
        "no_persistence_hierarchy_matches_after_admission": no_persistence_hierarchy_matches,
        "verbatim_hierarchy_matches_after_admission": verbatim_hierarchy_matches,
    }
    checks = {
        "complete_phase_order": len(phases) == 8,
        "candidate_hierarchy": candidate_hierarchy_matches == len(phases),
        "goal_stability": len(goal_fingerprints) == 1,
        "two_plan_revisions": plan_versions == [1, 1, 2, 2, 3, 3, 3, 3],
        "no_premature_completion": completion_claims == [False] * 7 + [True],
        "truthful_status": statuses == ["active"] * 7 + ["completed"],
        "post_receipt_judgment": completion_claim_encounter
        > verification_receipt_encounter,
        "projection_budget": body["maximum_projection_bytes"] <= PROJECTION_LIMIT,
        "no_persistence_control": no_persistence_hierarchy_matches == 0,
        "verbatim_control": verbatim_hierarchy_matches == 0,
    }
    return {
        **body,
        "checks": checks,
        "pass": all(checks.values()),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def evaluate_case(
    criterion_index: int,
    criterion: tuple[int, ...],
    pair_index: int,
    pair: tuple[str, str],
) -> dict[str, Any]:
    task = build_task(criterion_index, criterion, pair_index, pair)
    contract = oracle_contract(task)
    actor_admission = score_contract(task, contract, "actor-output")
    supplied_admission = score_contract(task, contract, "researcher-given")
    mutants = {
        name: score_contract(task, mutant, "actor-output")
        for name, mutant in mutated_contracts(task).items()
    }
    routes = route_path(task)
    temporal = temporal_path(task, contract)
    checks = {
        "raw_packet_without_goal": raw_packet_has_no_goal(task, contract),
        "oracle_quality": actor_admission["quality_pass"],
        "actor_authorship": actor_admission["ot2_admissible"],
        "researcher_authorship_rejected": supplied_admission["quality_pass"]
        and not supplied_admission["ot2_admissible"],
        "all_mutants_rejected": all(
            not result["quality_pass"] for result in mutants.values()
        ),
        "single_defect_discrimination": all(
            sum(not passed for passed in result["checks"].values()) == 1
            for result in mutants.values()
        ),
        "selector_causal_route_path": routes["pass"],
        "durable_temporal_path": temporal["pass"],
    }
    body = {
        "criterion_index": criterion_index,
        "criterion_sha256": sha256_bytes(canonical_json(criterion)),
        "rule_pair_index": pair_index,
        "rule_pair_sha256": sha256_bytes(canonical_json(pair)),
        "task_receipt": task["task_receipt"],
        "target_value": contract["value_thesis"]["minimum_gain"],
        "mutant_failed_checks": {
            name: [key for key, passed in result["checks"].items() if not passed]
            for name, result in mutants.items()
        },
        "candidate_route_errors": routes["candidate_route_errors"],
        "unchanged_route_errors": routes["unchanged_route_errors"],
        "maximum_goal_projection_bytes": temporal["maximum_projection_bytes"],
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
    forward_receipts = [result["receipt_sha256"] for result in results]
    reverse_receipts = [result["receipt_sha256"] for result in reversed_results]
    task_receipts = [result["task_receipt"] for result in results]
    gates = {
        "criterion_family": len(criterion_family) == acceptance["criterion_count"]
        and len(set(criterion_family)) == len(criterion_family),
        "rule_pairs": len(pairs) == acceptance["eligible_rule_pair_count"],
        "case_count": len(cases) == acceptance["case_count"],
        "unique_tasks": len(set(task_receipts)) == len(cases),
        "all_cases": all(result["pass"] for result in results),
        **{name: count == len(cases) for name, count in check_counts.items()},
        "route_error_signature": all(
            result["candidate_route_errors"] == [0, 0, 0]
            and result["unchanged_route_errors"] == [3, 3, 3]
            for result in results
        ),
        "projection_budget": max(
            result["maximum_goal_projection_bytes"] for result in results
        )
        <= acceptance["projection_byte_limit"],
        "deterministic_replay": forward_receipts
        == [evaluate_case(*case)["receipt_sha256"] for case in cases],
        "order_placebo": forward_receipts == list(reversed(reverse_receipts)),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_transition": acceptance["evaluation_transition"],
        "claim_limit": acceptance["claim_limit"],
        "candidate_actor_outputs": False,
        "candidate_goal_outputs": False,
        "criterion_count": len(criterion_family),
        "eligible_rule_pair_count": len(pairs),
        "case_count": len(cases),
        "task_family_sha256": sha256_bytes(canonical_json(task_receipts)),
        "case_receipts_sha256": sha256_bytes(canonical_json(forward_receipts)),
        "check_counts": check_counts,
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
        raise RuntimeError("OT-0038 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0038 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0038 fixed input identity differs")
    return lock


def record_sealed_result(repo: Path, output: Path, run_id: str) -> Path:
    output.chmod(0o600)
    try:
        return record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="controller-only-e7-self-authored-goal-evaluator-calibration",
            evidence_class="public-reconstructible",
            recipe=(
                "PYTHONPATH=src python3 experiments/ot_0038_harness.py "
                "--output $EVIDENCE/ot-0038-result.json"
            ),
            public_url=None,
            limitations=[
                "This is controller calibration, not OT-2 evidence.",
                "No candidate goal, learner, or hosted actor output was generated.",
                "A pass authorizes at most one fresh self-authored-goal candidate.",
                "The calibrated family remains one synthetic service and parity domain.",
            ],
            input_manifests=[
                str(OT1_MANIFEST_PATH),
                str(OT0_MANIFEST_PATH),
                str(OT6_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0038-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0038 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("OT-0038 output already exists")
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
