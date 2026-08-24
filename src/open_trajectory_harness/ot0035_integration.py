from __future__ import annotations

import argparse
import ast
import copy
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import certifi

from open_trajectory_evidence.evidence import record_artifact

from .app_server import AppServerClient, AppServerError
from .deployment_proxy import SanitizedResponsesProxy
from .ot0002 import (
    app_server_version,
    canonical_json,
    child_environment,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import write_sealed_json
from .ot0003_world import (
    RULES,
    DiscrepancyGatedVersionLedger,
    Observation,
    eligible_hidden_rules,
    structural_holdout_batch,
)
from .ot0014 import instrumented_command, run_actor_turn
from .ot0033_weighted_selector import (
    DIRECTIONS,
    WeightedSelectorSnapshot,
    _hidden_weights,
    _snapshot,
    complete_encounter,
    initial_snapshot,
    learn,
    neutralize_outcome_credit,
    project,
    restore,
    select_events,
)


EXPERIMENT_ID = "OT-0035"
ACCEPTANCE_PATH = Path("spec/ot-0035-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0035-run-lock.json")
TASK_ORDER_PATH = Path("fixtures/ot-0035/task-order.json")
PROMPT_PATH = Path("fixtures/ot-0014/actor-prompt.txt")
OUTPUT_SCHEMA_PATH = Path("fixtures/ot-0014/actor-output.schema.json")
TOOL_RECEIPT_PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
E5_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0034/ot-0034-e5-weighted-selector-calibration-001.json"
)
OT0_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json"
)
DEFAULT_RUN_ID = "ot-0035-e5-ot0-ledger-integration-001"
PROJECTION_LIMIT = 96


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0035 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-e5-ot0-integration-task",
            }
        )
    )


def _complement_rule(rule_id: str) -> str:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    complement = next(
        candidate
        for candidate in RULES
        if candidate.mask == rule.mask and candidate.bias == 1 - rule.bias
    )
    return complement.rule_id


def build_task(task_seed: str) -> dict[str, Any]:
    criterion = _hidden_weights(task_seed)
    eligible = tuple(sorted(eligible_hidden_rules(), key=lambda rule: rule.rule_id))
    rule_index = int(sha256_bytes(f"{task_seed}:rule".encode()), 16) % len(eligible)
    first_rule = eligible[rule_index].rule_id
    second_rule = _complement_rule(first_rule)
    regimes = (
        (criterion, first_rule),
        (tuple(-value for value in criterion), second_rule),
        (criterion, first_rule),
    )
    task_regimes = [
        {
            "index": index,
            "contact": build_contact(f"regime-{index}-contact", weights, rule_id),
            "canary_queries": [list(query) for query in structural_holdout_batch()],
            "canary_outcomes": [
                next(rule for rule in RULES if rule.rule_id == rule_id).predict(query)
                for query in structural_holdout_batch()
            ],
            "rule_id": rule_id,
        }
        for index, (weights, rule_id) in enumerate(regimes, start=1)
    ]
    body = {"schema_version": 1, "regimes": task_regimes}
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def build_contact(
    prefix: str, criterion: tuple[int, ...], rule_id: str
) -> dict[str, Any]:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    basis = (
        (0, 0, 0, 0),
        (1, 0, 0, 0),
        (0, 1, 0, 0),
        (0, 0, 1, 0),
        (0, 0, 0, 1),
    )
    archive = []
    outcomes = []
    for pattern_id, direction in enumerate(DIRECTIONS):
        predictor_features = basis[pattern_id % len(basis)]
        outcome = rule.predict(predictor_features)
        a_correct = sum(
            weight * feature
            for weight, feature in zip(criterion, direction, strict=True)
        ) > 0
        for variant, selector_features, correct in (
            ("a", direction, a_correct),
            ("b", tuple(-value for value in direction), not a_correct),
        ):
            archive.append(
                {
                    "event_id": f"{prefix}-pattern-{pattern_id:03d}-{variant}",
                    "pattern_id": pattern_id,
                    "selector_features": list(selector_features),
                    "predictor_features": list(predictor_features),
                    "label": outcome if correct else 1 - outcome,
                }
            )
        outcomes.append({"pattern_id": pattern_id, "outcome": outcome})
    return {"archive": archive, "outcomes": outcomes}


def selected_observations(
    snapshot: WeightedSelectorSnapshot, contact: dict[str, Any]
) -> tuple[Observation, ...]:
    return tuple(
        Observation(tuple(event["predictor_features"]), event["label"])
        for event in select_events(snapshot, contact["archive"])
    )


def apply_to_ledger(
    parent: DiscrepancyGatedVersionLedger,
    snapshot: WeightedSelectorSnapshot,
    contact: dict[str, Any],
    queries: tuple[tuple[int, int, int, int], ...],
) -> tuple[DiscrepancyGatedVersionLedger, str]:
    ledger = copy.deepcopy(parent)
    observations = selected_observations(snapshot, contact)
    if len(observations) != len(DIRECTIONS):
        raise RuntimeError("OT-0035 active inheritance budget differs")
    ledger.observe(observations)
    projection_text = ledger.project(queries, PROJECTION_LIMIT)
    return ledger, projection_text


def fixed_snapshots() -> dict[str, WeightedSelectorSnapshot]:
    weights = {"fixed-zero": (0, 0, 0, 0)}
    for dimension in range(4):
        for name, sign in (("negative", -1), ("positive", 1)):
            weights[f"fixed-axis-{dimension}-{name}"] = tuple(
                sign if index == dimension else 0 for index in range(4)
            )
    return {
        name: _snapshot(
            0,
            None,
            sha256_bytes(canonical_json({"fixed_selector": name, "weights": value})),
            value,
        )
        for name, value in weights.items()
    }


def deterministic_ledger_errors(
    ledger: DiscrepancyGatedVersionLedger,
    queries: tuple[tuple[int, int, int, int], ...],
    outcomes: tuple[int, ...],
) -> int:
    if len(ledger.hypotheses) != 1:
        return len(outcomes)
    return sum(
        ledger.hypotheses[0].predict(query) != outcome
        for query, outcome in zip(queries, outcomes, strict=True)
    )


def run_core(task_seed: str) -> dict[str, Any]:
    task = build_task(task_seed)
    selector = initial_snapshot()
    candidate_ledger = DiscrepancyGatedVersionLedger()
    controls = fixed_snapshots()
    control_ledgers = {
        name: DiscrepancyGatedVersionLedger() for name in controls
    }
    frozen_first_snapshot: WeightedSelectorSnapshot | None = None
    frozen_first_ledger: DiscrepancyGatedVersionLedger | None = None
    regimes = []
    for regime in task["regimes"]:
        source = restore(project(selector))
        completed = complete_encounter(source, regime["contact"])
        neutralized, neutralized_receipt = learn(
            source, neutralize_outcome_credit(completed)
        )
        learned, update = learn(source, completed)
        queries = tuple(tuple(query) for query in regime["canary_queries"])
        outcomes = tuple(regime["canary_outcomes"])
        candidate_parent = copy.deepcopy(candidate_ledger)
        candidate_ledger, candidate_projection = apply_to_ledger(
            candidate_parent, learned, regime["contact"], queries
        )
        unchanged_ledger, unchanged_projection = apply_to_ledger(
            candidate_parent, source, regime["contact"], queries
        )
        control_projections = {}
        control_errors = {}
        for name, snapshot in controls.items():
            ledger, projection_text = apply_to_ledger(
                control_ledgers[name], snapshot, regime["contact"], queries
            )
            control_ledgers[name] = ledger
            control_projections[name] = projection_text
            control_errors[name] = deterministic_ledger_errors(
                ledger, queries, outcomes
            )
        if frozen_first_snapshot is None:
            frozen_first_snapshot = learned
            frozen_first_ledger = copy.deepcopy(candidate_ledger)
            frozen_projection = candidate_projection
        else:
            assert frozen_first_ledger is not None
            frozen_first_ledger, frozen_projection = apply_to_ledger(
                frozen_first_ledger,
                frozen_first_snapshot,
                regime["contact"],
                queries,
            )
        frozen_errors = deterministic_ledger_errors(
            frozen_first_ledger, queries, outcomes
        )
        control_projections["frozen-first-learned"] = frozen_projection
        control_errors["frozen-first-learned"] = frozen_errors
        regimes.append(
            {
                "index": regime["index"],
                "rule_id": regime["rule_id"],
                "source_snapshot": project(source),
                "learned_snapshot": project(learned),
                "update": update,
                "neutralized_changed": neutralized.sha256 != source.sha256,
                "neutralized_receipt": neutralized_receipt,
                "contact_errors": sum(
                    decision["error"] for decision in completed["decisions"]
                ),
                "candidate_projection": candidate_projection,
                "candidate_ledger_errors": deterministic_ledger_errors(
                    candidate_ledger, queries, outcomes
                ),
                "unchanged_projection": unchanged_projection,
                "unchanged_ledger_errors": deterministic_ledger_errors(
                    unchanged_ledger, queries, outcomes
                ),
                "control_projections": control_projections,
                "control_ledger_errors": control_errors,
                "queries": queries,
                "outcomes": outcomes,
            }
        )
        selector = learned
    return {
        "task_sha256": task["task_sha256"],
        "regimes": regimes,
        "candidate_aggregate_ledger_errors": sum(
            regime["candidate_ledger_errors"] for regime in regimes
        ),
        "best_fixed_aggregate_ledger_errors": min(
            sum(regime["control_ledger_errors"][name] for regime in regimes)
            for name in (*controls, "frozen-first-learned")
        ),
    }


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": TASK_ORDER_PATH,
        "prompt_sha256": PROMPT_PATH,
        "output_schema_sha256": OUTPUT_SCHEMA_PATH,
        "integration_core_sha256": Path(
            "src/open_trajectory_harness/ot0035_integration.py"
        ),
        "selector_core_sha256": Path(
            "src/open_trajectory_harness/ot0033_weighted_selector.py"
        ),
        "ot0_ledger_core_sha256": Path(
            "src/open_trajectory_harness/ot0003_world.py"
        ),
        "ot0_hosted_core_sha256": Path("src/open_trajectory_harness/ot0014.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": PROXY_PATH,
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0035_harness.py"),
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "e5_manifest_sha256": E5_MANIFEST_PATH,
        "ot0_manifest_sha256": OT0_MANIFEST_PATH,
    }


def validate_task_order(order: dict[str, Any], acceptance: dict[str, Any]) -> None:
    conditions = order.get("conditions")
    phases = order.get("phases")
    if (
        not isinstance(conditions, list)
        or len(conditions) != acceptance["conditions_per_regime"]
        or len(set(conditions)) != len(conditions)
        or not isinstance(phases, list)
        or len(phases) != acceptance["regime_count"]
    ):
        raise ValueError("OT-0035 task order has the wrong shape")
    positions = {condition: [] for condition in conditions}
    for phase in phases:
        worker_1 = phase.get("worker-1")
        worker_2 = phase.get("worker-2")
        if (
            not isinstance(worker_1, list)
            or not isinstance(worker_2, list)
            or set(worker_1) != set(conditions)
            or set(worker_2) != set(conditions)
            or worker_2 != list(reversed(worker_1))
        ):
            raise ValueError("OT-0035 phase is not an exact reversed counterbalance")
        for order_values in (worker_1, worker_2):
            for position, condition in enumerate(order_values):
                positions[condition].append(position)
    expected_sum = (len(conditions) - 1) * len(phases)
    if any(
        len(values) != 2 * len(phases) or sum(values) != expected_sum
        for values in positions.values()
    ):
        raise ValueError("OT-0035 condition positions are not time-balanced")
    if order.get("ablation_order") != ["worker-2", "worker-1"]:
        raise ValueError("OT-0035 ablation order differs")


def validate_run_lock(repo: Path, execution_commit: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0035 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0035 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0035 fixed input identity differs")
    task_seed = lock.get("task_seed", "")
    if task_seed != expected_task_seed(implementation):
        raise RuntimeError("OT-0035 task seed is not mechanically derived")
    if build_task(task_seed)["task_sha256"] != lock.get("task_sha256"):
        raise RuntimeError("OT-0035 task identity differs")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("OT-0035 backend executable is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("OT-0035 backend executable differs")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("OT-0035 code-mode host differs")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("OT-0035 backend version differs")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("OT-0035 TLS bundle differs")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_task_order(load_json(repo / TASK_ORDER_PATH), acceptance)
    return lock


def _branch_state(
    *,
    task: dict[str, Any],
    task_order: dict[str, Any],
    worker_id: str,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    workspace_root: Path,
    model: str,
    prompt_template: str,
    output_schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[list[dict[str, Any]]]]:
    selector = initial_snapshot()
    candidate_ledger = DiscrepancyGatedVersionLedger()
    controls = fixed_snapshots()
    control_ledgers = {name: DiscrepancyGatedVersionLedger() for name in controls}
    frozen_first_snapshot: WeightedSelectorSnapshot | None = None
    frozen_first_ledger: DiscrepancyGatedVersionLedger | None = None
    actor_results = []
    mechanisms = []
    inventories = []
    for regime, phase_order in zip(task["regimes"], task_order["phases"], strict=True):
        source = restore(project(selector))
        completed = complete_encounter(source, regime["contact"])
        neutralized, neutralized_receipt = learn(
            source, neutralize_outcome_credit(completed)
        )
        learned, update = learn(source, completed)
        queries = tuple(tuple(query) for query in regime["canary_queries"])
        outcomes = tuple(regime["canary_outcomes"])
        parent = copy.deepcopy(candidate_ledger)
        candidate_ledger, candidate_projection = apply_to_ledger(
            parent, learned, regime["contact"], queries
        )
        _, unchanged_projection = apply_to_ledger(
            parent, source, regime["contact"], queries
        )
        projections = {
            "candidate": candidate_projection,
            "unchanged-selector": unchanged_projection,
        }
        for name, snapshot in controls.items():
            ledger, projection_text = apply_to_ledger(
                control_ledgers[name], snapshot, regime["contact"], queries
            )
            control_ledgers[name] = ledger
            projections[name] = projection_text
        if frozen_first_snapshot is None:
            frozen_first_snapshot = learned
            frozen_first_ledger = copy.deepcopy(candidate_ledger)
            projections["frozen-first-learned"] = candidate_projection
        else:
            assert frozen_first_ledger is not None
            frozen_first_ledger, projections["frozen-first-learned"] = apply_to_ledger(
                frozen_first_ledger,
                frozen_first_snapshot,
                regime["contact"],
                queries,
            )
        mechanisms.append(
            {
                "worker": worker_id,
                "regime": regime["index"],
                "source_snapshot_sha256": source.sha256,
                "learned_snapshot_sha256": learned.sha256,
                "learned_weights": list(learned.weights),
                "changed": learned.sha256 != source.sha256,
                "neutralized_changed": neutralized.sha256 != source.sha256,
                "contact_errors": sum(
                    decision["error"] for decision in completed["decisions"]
                ),
                "completed_receipt_sha256": completed["receipt_sha256"],
                "update_receipt_sha256": update["receipt_sha256"],
                "neutralized_receipt_sha256": neutralized_receipt["receipt_sha256"],
                "candidate_projection_sha256": sha256_bytes(candidate_projection.encode()),
                "unchanged_projection_sha256": sha256_bytes(unchanged_projection.encode()),
            }
        )
        for condition in phase_order[worker_id]:
            result = run_actor_turn(
                client=client,
                proxy=proxy,
                model=model,
                workspace=workspace_root / worker_id / f"regime-{regime['index']}-{condition}",
                prompt_template=prompt_template,
                output_schema=output_schema,
                projection=projections[condition],
                batch=queries,
                outcomes=outcomes,
                condition=condition,
                phase=f"regime-{regime['index']}",
                score_kind="heldout",
            )
            result["worker"] = worker_id
            actor_results.append(result)
            inventories.append(client.model_visible_tool_inventories()[-1])
        selector = learned
    return actor_results, mechanisms, inventories


def _result_map(actor_results: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (item["worker"], item["phase"], item["condition"]): item
        for item in actor_results
    }


def summarize(
    *,
    acceptance: dict[str, Any],
    actor_results: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    inventories: list[list[dict[str, Any]]],
    proxy_receipts: list[dict[str, Any]],
    collector_errors: list[str],
    usage: dict[str, int],
    elapsed_seconds: float,
    verification: dict[str, int],
    failure_type: str | None,
    task_order: dict[str, Any],
    catalog_payloads: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    expected_turns = acceptance["resource_budget"]["actor_turns"]
    results = _result_map(actor_results)
    fixed = acceptance["fixed_selector_conditions"]
    candidate_errors = {
        worker: [
            results[(worker, f"regime-{index}", "candidate")]["errors"]
            for index in (1, 2, 3)
        ]
        for worker in ("worker-1", "worker-2")
    }
    unchanged_errors = {
        worker: [
            results[(worker, f"regime-{index}", "unchanged-selector")]["errors"]
            for index in (1, 2, 3)
        ]
        for worker in ("worker-1", "worker-2")
    }
    fixed_aggregates = {
        worker: {
            name: sum(
                results[(worker, f"regime-{index}", name)]["errors"]
                for index in (1, 2, 3)
            )
            for name in fixed
        }
        for worker in ("worker-1", "worker-2")
    }
    paired_candidate = all(
        results[("worker-1", f"regime-{index}", "candidate")]["predictions"]
        == results[("worker-2", f"regime-{index}", "candidate")]["predictions"]
        for index in (1, 2, 3)
    )
    paired_unchanged = all(
        results[("worker-1", f"regime-{index}", "unchanged-selector")]["predictions"]
        == results[("worker-2", f"regime-{index}", "unchanged-selector")]["predictions"]
        for index in (1, 2, 3)
    )
    response_ids = [item["deployment_response_ids"] for item in actor_results]
    distinct_response_ids = {value for values in response_ids for value in values}
    proxy_response_ids = {
        item["value"] for item in proxy_receipts if item["kind"] == "response_id"
    }
    effective_models = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "effective_model"}
    )
    etags = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "models_etag"}
    )
    expected_inventory = acceptance["direct_inventory"]
    inventory_valid = len(inventories) == expected_turns and bool(inventories)
    if inventory_valid:
        inventory_valid = (
            all(value == inventories[0] for value in inventories)
            and sha256_bytes(canonical_json(inventories[0])) == expected_inventory["sha256"]
            and len(inventories[0]) == expected_inventory["tool_count"]
        )
    mechanism_gate = len(mechanisms) == 6 and all(
        item["changed"] and not item["neutralized_changed"] for item in mechanisms
    ) and all(
        [item["contact_errors"] for item in mechanisms if item["worker"] == worker]
        == [40, 80, 80]
        for worker in ("worker-1", "worker-2")
    )
    observed_orders = {
        (worker, f"regime-{index}"): [
            item["condition"]
            for item in actor_results
            if item["worker"] == worker
            and item["phase"] == f"regime-{index}"
            and item["condition"] != "candidate-projection-ablation"
        ]
        for worker in ("worker-1", "worker-2")
        for index in (1, 2, 3)
    }
    expected_orders = {
        (worker, phase["phase"]): phase[worker]
        for phase in task_order["phases"]
        for worker in ("worker-1", "worker-2")
    }
    observed_ablation_order = [
        item["worker"]
        for item in actor_results
        if item["condition"] == "candidate-projection-ablation"
    ]
    scoring = acceptance["scoring"]
    gates = {
        "complete": len(actor_results) == expected_turns and len(results) == expected_turns,
        "order": observed_orders == expected_orders
        and observed_ablation_order == task_order["ablation_order"],
        "mechanism": mechanism_gate,
        "candidate": all(errors == [0, 0, 0] for errors in candidate_errors.values()),
        "unchanged": all(
            errors[0] >= scoring["minimum_initial_unchanged_errors"]
            and errors[1:] == [scoring["minimum_later_unchanged_errors"]] * 2
            for errors in unchanged_errors.values()
        ),
        "fixed_controls": all(
            min(values.values()) - sum(candidate_errors[worker])
            >= scoring["minimum_candidate_advantage_over_best_fixed_aggregate"]
            for worker, values in fixed_aggregates.items()
        ),
        "projection_ablation": all(
            results[(worker, "regime-3", "candidate-projection-ablation")]["errors"]
            >= scoring["minimum_projection_ablation_errors"]
            for worker in ("worker-1", "worker-2")
        ),
        "identity_placebo": paired_candidate and paired_unchanged,
        "parse": all(item["parse_error"] is None for item in actor_results),
        "tools": all(
            item["tool_calls"] == scoring["actor_tool_calls_allowed"]
            for item in actor_results
        ),
        "fresh_threads": len({item["thread_id"] for item in actor_results})
        == expected_turns,
        "fresh_workspaces": len({item["workspace"] for item in actor_results})
        == expected_turns,
        "responses": all(len(values) == 1 for values in response_ids)
        and len(distinct_response_ids) == expected_turns
        and distinct_response_ids == proxy_response_ids,
        "model": effective_models == [acceptance["deployment_epoch"]["requested_model"]]
        and all(
            item["deployment_effective_models"]
            == [acceptance["deployment_epoch"]["requested_model"]]
            for item in actor_results
        ),
        "catalog": len(catalog_payloads) == 2
        and bool(catalog_payloads[0])
        and catalog_payloads[0] == catalog_payloads[1],
        "etag": len(etags) == 1,
        "inventory": inventory_valid
        and all(item["inventory_receipts"] == 1 for item in actor_results),
        "collector": collector_errors == [],
        "input_budget": usage["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total"],
        "wall_budget": elapsed_seconds <= acceptance["resource_budget"]["wall_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "candidate_errors": candidate_errors,
        "unchanged_errors": unchanged_errors,
        "best_fixed_aggregate_errors": {
            worker: min(values.values()) for worker, values in fixed_aggregates.items()
        },
        "projection_ablation_errors": {
            worker: results[(worker, "regime-3", "candidate-projection-ablation")]["errors"]
            for worker in ("worker-1", "worker-2")
        },
        "paired_candidate_predictions": paired_candidate,
        "paired_unchanged_predictions": paired_unchanged,
        "response_count": len(distinct_response_ids),
        "effective_models": effective_models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed_seconds,
        "failure_type": failure_type,
        "gates": gates,
        "pilot_pass": all(gates.values()),
        "claim_limit": acceptance["claim_limit"],
    }


def _novelty_gate(repo: Path, mechanisms: list[dict[str, Any]]) -> dict[str, Any]:
    source = (repo / Path("src/open_trajectory_harness/ot0033_weighted_selector.py")).read_text(
        encoding="utf-8"
    )
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
    learned = {tuple(item["learned_weights"]) for item in mechanisms}
    body = {
        "learned_weight_identities": sorted(
            sha256_bytes(canonical_json(weights)) for weights in learned
        ),
        "literal_collision_count": len(learned & literal_sequences),
        "candidate_source_sha256": sha256_bytes(source.encode()),
        "e5_manifest_sha256": sha256_file(repo / E5_MANIFEST_PATH),
    }
    return {
        **body,
        "pass": len(learned) == 2 and body["literal_collision_count"] == 0,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run(
    *,
    repo: Path,
    run_id: str,
    codex_bin: Path,
    output_path: Path,
    workspace_root: Path,
) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0035 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0035 output or workspace already exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / TASK_ORDER_PATH)
    task = build_task(lock["task_seed"])
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    output_schema = load_json(repo / OUTPUT_SCHEMA_PATH)
    workspace_root.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    proxy_receipts: list[dict[str, Any]] = []
    collector_errors: list[str] = []
    catalog_payloads: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []
    stderr: list[str] = []
    failure_type: str | None = None
    failure: str | None = None
    started = time.monotonic()
    active_proxy: SanitizedResponsesProxy | None = None
    client: AppServerClient | None = None
    try:
        with SanitizedResponsesProxy() as proxy:
            active_proxy = proxy
            with AppServerClient(
                command=instrumented_command(codex_bin, proxy.base_url),
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as active_client:
                client = active_client
                model = acceptance["deployment_epoch"]["requested_model"]
                for worker_id in ("worker-1", "worker-2"):
                    catalog_payload = client.request(
                        "model/list", {"includeHidden": False}
                    )["data"]
                    catalog_payloads.append(catalog_payload)
                    if model not in {item.get("id") for item in catalog_payload}:
                        raise RuntimeError("OT-0035 frozen hosted model is unavailable")
                    results, worker_mechanisms, worker_inventories = _branch_state(
                        task=task,
                        task_order=task_order,
                        worker_id=worker_id,
                        client=client,
                        proxy=proxy,
                        workspace_root=workspace_root,
                        model=model,
                        prompt_template=prompt_template,
                        output_schema=output_schema,
                    )
                    actor_results.extend(results)
                    mechanisms.extend(worker_mechanisms)
                    inventories.extend(worker_inventories)
                final = task["regimes"][-1]
                for worker_id in task_order["ablation_order"]:
                    ablation = run_actor_turn(
                        client=client,
                        proxy=proxy,
                        model=model,
                        workspace=workspace_root
                        / worker_id
                        / "candidate-projection-ablation",
                        prompt_template=prompt_template,
                        output_schema=output_schema,
                        projection="[candidate projection ablated]",
                        batch=tuple(
                            tuple(query) for query in final["canary_queries"]
                        ),
                        outcomes=tuple(final["canary_outcomes"]),
                        condition="candidate-projection-ablation",
                        phase="regime-3",
                        score_kind="ablation",
                    )
                    ablation["worker"] = worker_id
                    actor_results.append(ablation)
                    inventories.append(client.model_visible_tool_inventories()[-1])
                events = client.raw_events
                stderr = client.stderr_lines
            proxy_receipts = proxy.collector.snapshot()
            collector_errors = proxy.collector.errors()
    except Exception as error:
        failure_type = type(error).__name__
        failure = str(error)
        if client is not None:
            events = client.raw_events
            stderr = client.stderr_lines
        if active_proxy is not None:
            proxy_receipts = active_proxy.collector.snapshot()
            collector_errors = active_proxy.collector.errors()
    elapsed_seconds = time.monotonic() - started
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    audit = subprocess.run(
        [sys.executable, "-m", "open_trajectory_evidence.cli", "audit"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    verification = {
        "tests_returncode": tests.returncode,
        "tests_stdout_sha256": sha256_bytes(tests.stdout.encode()),
        "tests_stderr_sha256": sha256_bytes(tests.stderr.encode()),
        "audit_returncode": audit.returncode,
        "audit_stdout_sha256": sha256_bytes(audit.stdout.encode()),
        "audit_stderr_sha256": sha256_bytes(audit.stderr.encode()),
    }
    try:
        summary = summarize(
            acceptance=acceptance,
            actor_results=actor_results,
            mechanisms=mechanisms,
            inventories=inventories,
            proxy_receipts=proxy_receipts,
            collector_errors=collector_errors,
            usage=token_usage(events),
            elapsed_seconds=elapsed_seconds,
            verification=verification,
            failure_type=failure_type,
            task_order=task_order,
            catalog_payloads=catalog_payloads,
        )
    except Exception as summary_error:
        failure_type = failure_type or type(summary_error).__name__
        failure = failure or str(summary_error)
        summary = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "pilot_pass": False,
            "failure_type": failure_type,
            "gates": {"summary": False},
            "claim_limit": acceptance["claim_limit"],
        }
    novelty = _novelty_gate(repo, mechanisms) if mechanisms else {"pass": False}
    summary["gates"]["novelty"] = novelty["pass"]
    summary["pilot_pass"] = all(summary["gates"].values())
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "task_sha256": task["task_sha256"],
        "summary": summary,
        "novelty": novelty,
        "mechanisms": mechanisms,
        "actor_results": actor_results,
        "catalog_payloads": catalog_payloads,
        "catalog_payloads_sha256": sha256_bytes(canonical_json(catalog_payloads)),
        "proxy_receipts": proxy_receipts,
        "collector_errors": collector_errors,
        "events": events,
        "stderr": stderr,
        "failure": failure,
        "verification": verification,
    }
    write_sealed_json(output_path, raw)
    output_path.chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=output_path,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="e5-learned-selector-ot0-ledger-hosted-run",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Hosted outputs and deployment identities remain private.",
                "A pass is time-bounded single-domain OT-1 evidence, not immutable reproduction.",
                "This run consumes E5's one-candidate authorization regardless of disposition.",
            ],
            input_manifests=[str(E5_MANIFEST_PATH), str(OT0_MANIFEST_PATH)],
        )
    finally:
        output_path.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0035-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, summary = run(
            repo=args.repo.resolve(),
            run_id=args.run_id,
            codex_bin=args.codex_bin.resolve(),
            output_path=args.output.resolve(),
            workspace_root=args.workspace_root.resolve(),
        )
    except (AppServerError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(args.repo.resolve())), "summary": summary},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
