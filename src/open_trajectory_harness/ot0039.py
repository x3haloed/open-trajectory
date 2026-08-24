from __future__ import annotations

import argparse
import ast
import copy
import json
import re
import subprocess
import sys
import time
from collections import Counter
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
    final_agent_json,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import read_sealed_json, write_sealed_json
from .ot0014 import instrumented_command
from .ot0038_e7_ot2_calibration import oracle_contract, score_contract, temporal_path
from .ot0039_world import (
    EXPERIMENT_ID,
    GoalObservation,
    GoalWorld,
    admission_score,
    build_task,
    expected_task_seed,
    hierarchy_correct,
    public_evaluator_task,
    render_packet,
    selector_route_lineage,
    substrate_conditions,
    validate_task,
)


FIXTURE_ROOT = Path("fixtures/ot-0039")
ACCEPTANCE_PATH = Path("spec/ot-0039-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0039-run-lock.json")
TASK_ORDER_PATH = FIXTURE_ROOT / "task-order.json"
PROMPT_PATH = FIXTURE_ROOT / "actor-prompt.txt"
OUTPUT_SCHEMA_PATH = FIXTURE_ROOT / "actor-output.schema.json"
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
TOOL_RECEIPT_PATCH_PATH = Path(
    "patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch"
)
E7_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0038/ot-0038-e7-ot2-evaluator-calibration-001.json"
)
OT1_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0037/ot-0037-e6-deterministic-ot1-candidate-001.json"
)
OT0_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json"
)
OT6_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0006/ot-0006-hosted-epoch-001.json"
)
DEFAULT_RUN_ID = "ot-0039-e7-self-authored-goal-candidate-001"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": TASK_ORDER_PATH,
        "prompt_sha256": PROMPT_PATH,
        "output_schema_sha256": OUTPUT_SCHEMA_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0039.py"),
        "candidate_world_sha256": Path(
            "src/open_trajectory_harness/ot0039_world.py"
        ),
        "e7_evaluator_sha256": Path(
            "src/open_trajectory_harness/ot0038_e7_ot2_calibration.py"
        ),
        "ot1_candidate_core_sha256": Path(
            "src/open_trajectory_harness/ot0037_deterministic_candidate.py"
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
        "ot0_hosted_core_sha256": Path("src/open_trajectory_harness/ot0014.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": PROXY_PATH,
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0039_harness.py"),
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "e7_manifest_sha256": E7_MANIFEST_PATH,
        "ot1_manifest_sha256": OT1_MANIFEST_PATH,
        "ot0_manifest_sha256": OT0_MANIFEST_PATH,
        "rejected_ot2_infrastructure_manifest_sha256": OT6_MANIFEST_PATH,
    }


def substrate_authority(repo: Path) -> dict[str, Any]:
    path = repo / Path("src/open_trajectory_harness/ot0039_world.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    candidate = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DurableGoalContract"
    )
    definitions = {
        node.name: node
        for node in candidate.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    init_parameters = [argument.arg for argument in definitions["__init__"].args.args]
    project_parameters = [argument.arg for argument in definitions["project"].args.args]
    observed_names = {
        node.id
        for definition in definitions.values()
        for node in ast.walk(definition)
        if isinstance(node, ast.Name)
    }
    observed_attributes = {
        node.attr
        for definition in definitions.values()
        for node in ast.walk(definition)
        if isinstance(node, ast.Attribute)
    }
    forbidden = sorted(
        (observed_names | observed_attributes)
        & {
            "task",
            "criterion",
            "pair",
            "rule_id",
            "outcomes",
            "score_contract",
            "oracle_contract",
            "GoalWorld",
            "world",
            "open",
            "eval",
            "exec",
            "globals",
            "locals",
            "getattr",
            "__import__",
        }
    )
    body = {
        "init_parameters": init_parameters,
        "project_parameters": project_parameters,
        "forbidden_authority": forbidden,
        "source_sha256": sha256_file(path),
    }
    return {
        **body,
        "pass": init_parameters == ["self", "actions", "adaptive"]
        and project_parameters == ["self", "byte_limit"]
        and not forbidden,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def prepare_task_manifest(path: Path, implementation_commit: str) -> dict[str, Any]:
    task = build_task(expected_task_seed(implementation_commit))
    validate_task(task)
    write_sealed_json(path, task)
    raw = canonical_json(task)
    return {
        "task_seed": task["task_seed"],
        "task_sha256": sha256_bytes(raw),
        "bytes": len(raw),
    }


def validate_counterbalance(task_order: dict[str, Any], expected_count: int) -> None:
    conditions = task_order.get("conditions")
    phases = task_order.get("phases")
    if (
        not isinstance(conditions, list)
        or len(conditions) != 4
        or len(set(conditions)) != 4
    ):
        raise ValueError("OT-0039 requires four distinct hosted conditions")
    counts = {condition: Counter() for condition in conditions}
    for phase in phases or []:
        for worker in ("worker-1", "worker-2"):
            order = phase.get(worker) if isinstance(phase, dict) else None
            if not isinstance(order, list) or set(order) != set(conditions):
                raise ValueError("OT-0039 condition order is not a permutation")
            for position, condition in enumerate(order):
                counts[condition][position] += 1
    expected = Counter({position: expected_count for position in range(4)})
    if any(count != expected for count in counts.values()):
        raise ValueError("OT-0039 condition positions are not exactly balanced")


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0039 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0039 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0039 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0039 fixed input identity differs")
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
        raise RuntimeError(f"OT-0039 implementation changed after lock: {changed}")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("pinned Codex executable or code-mode host is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from the OT-0039 lock")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the OT-0039 lock")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex executable version differs from the OT-0039 lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from the OT-0039 lock")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_counterbalance(
        load_json(repo / TASK_ORDER_PATH),
        acceptance["deployment_epoch"]["condition_position_count_across_workers"],
    )
    return lock


def valid_actor_output(output: dict[str, Any] | None) -> bool:
    if not isinstance(output, dict) or set(output) != {
        "goal_contract",
        "goal_id",
        "goal_status",
        "plan_version",
        "experiment_id",
        "subtask_id",
        "action",
        "completion_claim",
    }:
        return False
    return (
        (output["goal_contract"] is None or isinstance(output["goal_contract"], dict))
        and (output["goal_id"] is None or isinstance(output["goal_id"], str))
        and output["goal_status"]
        in {
            "unknown",
            "active",
            "completed",
            "set_down",
            "superseded",
            "blocked",
            "invalidated",
        }
        and (output["plan_version"] is None or type(output["plan_version"]) is int)
        and (
            output["experiment_id"] is None
            or isinstance(output["experiment_id"], str)
        )
        and (output["subtask_id"] is None or isinstance(output["subtask_id"], str))
        and isinstance(output["action"], str)
        and type(output["completion_claim"]) is bool
    )


def run_actor_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    prompt_template: str,
    output_schema: dict[str, Any],
    projection: str,
    packet: dict[str, Any],
    condition: str,
    phase: str,
    encounter_index: int,
    task: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": (
                "Author or pursue the bounded service goal from the current "
                "prompt and return only schema-conforming JSON."
            ),
            "developerInstructions": (
                "Do not call tools or inspect files. Use only the current prompt."
            ),
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0039",
        }
    )
    prompt = prompt_template.replace("{{PROJECTION}}", projection).replace(
        "{{PACKET}}", render_packet(packet)
    )
    hidden_markers = [
        canonical_json(task["criterion"]).decode(),
        *task["pair"],
    ]
    hidden_task_leakage = [marker for marker in hidden_markers if marker in prompt]
    deployment_before = len(proxy.collector.snapshot())
    inventories_before = len(client.model_visible_tool_inventories())
    turn = client.run_turn(
        thread_id=thread["id"],
        input_text=prompt,
        output_schema=output_schema,
        sandbox_policy={"type": "readOnly", "networkAccess": False},
        timeout=180,
    )
    deployment_receipts = proxy.collector.snapshot()[deployment_before:]
    inventory_count = len(client.model_visible_tool_inventories()) - inventories_before
    output, parse_error = final_agent_json(turn)
    if turn.get("status") != "completed":
        parse_error = parse_error or "actor turn did not complete"
    if not valid_actor_output(output):
        parse_error = parse_error or "actor output failed exact structural validation"
        output = None
    response_ids = sorted(
        {item["value"] for item in deployment_receipts if item["kind"] == "response_id"}
    )
    effective_models = sorted(
        {
            item["value"]
            for item in deployment_receipts
            if item["kind"] == "effective_model"
        }
    )
    return (
        {
            "condition": condition,
            "phase": phase,
            "encounter_index": encounter_index,
            "workspace": str(workspace.resolve()),
            "thread_id": thread["id"],
            "thread_session_id": thread.get("sessionId"),
            "projection": projection,
            "projection_bytes": len(projection.encode()),
            "packet": packet,
            "actor_output": output,
            "parse_error": parse_error,
            "tool_calls": client.completed_turn_tool_calls(
                thread_id=thread["id"], turn_id=turn["id"]
            ),
            "inventory_receipts": inventory_count,
            "deployment_receipts": deployment_receipts,
            "deployment_effective_models": effective_models,
            "deployment_response_ids": response_ids,
            "hidden_task_leakage": hidden_task_leakage,
            "turn": turn,
        },
        output,
    )


def execute_worker(
    *,
    task: dict[str, Any],
    task_order: dict[str, Any],
    worker_id: str,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace_root: Path,
    prompt_template: str,
    output_schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[list[dict[str, Any]]]]:
    lineage = selector_route_lineage(task)
    worlds = {
        condition: GoalWorld(task, lineage) for condition in task_order["conditions"]
    }
    substrates = substrate_conditions(task, lineage)
    controllers: dict[str, dict[str, Any] | None] = {
        condition: None for condition in task_order["conditions"]
    }
    results: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    for encounter_index, phase in enumerate(task_order["phases"]):
        pending: dict[str, GoalObservation] = {}
        for condition in phase[worker_id]:
            world = worlds[condition]
            substrate = substrates[condition]
            before_step = world.step
            packet = world.packet(encounter_index)
            projection = substrate.project(512)
            result, output = run_actor_turn(
                client=client,
                proxy=proxy,
                model=model,
                workspace=workspace_root / worker_id / phase["phase"] / condition,
                prompt_template=prompt_template,
                output_schema=output_schema,
                projection=projection,
                packet=packet,
                condition=condition,
                phase=phase["phase"],
                encounter_index=encounter_index,
                task=task,
            )
            if before_step == 0:
                admission = admission_score(task, output)
                admission_valid = bool(admission["ot2_admissible"])
                if admission_valid and controllers[condition] is None:
                    assert output is not None
                    controllers[condition] = {
                        "contract": copy.deepcopy(output["goal_contract"]),
                        "initial_experiment_id": output["experiment_id"],
                        "initial_subtask_id": output["subtask_id"],
                    }
            else:
                admission = None
                admission_valid = False
            controller = controllers[condition]
            hierarchy_match = hierarchy_correct(
                controller["contract"] if controller else None,
                controller["initial_experiment_id"] if controller else None,
                controller["initial_subtask_id"] if controller else None,
                before_step,
                output,
            )
            receipt = world.apply(output, admission_valid)
            result.update(
                {
                    "worker": worker_id,
                    "world_step_before": before_step,
                    "world_step_after": world.step,
                    "world_receipt": receipt,
                    "admission_score": admission,
                    "hierarchy_correct": hierarchy_match,
                }
            )
            pending[condition] = GoalObservation(
                packet=packet,
                actor_output=output,
                receipt=receipt,
                admission_valid=admission_valid,
            )
            results.append(result)
            inventories.append(client.model_visible_tool_inventories()[-1])
        for condition, observation in pending.items():
            substrates[condition].observe(observation)
    mechanism = {
        "worker": worker_id,
        "lineage_receipt_sha256": lineage["receipt_sha256"],
        "candidate_route_errors": lineage["candidate_route_errors"],
        "unchanged_route_errors": lineage["unchanged_route_errors"],
        "regimes": lineage["regimes"],
        "pass": lineage["pass"],
    }
    return results, mechanism, inventories


def _result_map(
    actor_results: list[dict[str, Any]],
) -> dict[tuple[str, int, str], dict[str, Any]]:
    return {
        (item["worker"], item["encounter_index"], item["condition"]): item
        for item in actor_results
    }


def _goal_novelty(repo: Path, actor_results: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
    source = (repo / Path("src/open_trajectory_harness/ot0039.py")).read_text(
        encoding="utf-8"
    ) + (repo / Path("src/open_trajectory_harness/ot0039_world.py")).read_text(
        encoding="utf-8"
    )
    prompt = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    goal_ids = {
        item["actor_output"]["goal_id"]
        for item in actor_results
        if item["encounter_index"] == 0
        and isinstance(item.get("actor_output"), dict)
        and isinstance(item["actor_output"].get("goal_id"), str)
    }
    body = {
        "goal_id_count": len(goal_ids),
        "goal_id_literal_collisions": sorted(
            goal_id for goal_id in goal_ids if goal_id in source or goal_id in prompt
        ),
        "task_predates_actor": True,
        "task_sha256": task["task_sha256"],
    }
    return {
        **body,
        "pass": bool(goal_ids) and not body["goal_id_literal_collisions"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def summarize(
    *,
    repo: Path,
    acceptance: dict[str, Any],
    task_order: dict[str, Any],
    task: dict[str, Any],
    actor_results: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    inventories: list[list[dict[str, Any]]],
    proxy_receipts: list[dict[str, Any]],
    collector_errors: list[str],
    catalog_payloads: list[list[dict[str, Any]]],
    usage: dict[str, int],
    elapsed_seconds: float,
    verification: dict[str, int],
    failure_type: str | None,
) -> dict[str, Any]:
    expected_turns = acceptance["resource_budget"]["actor_turns"]
    conditions = task_order["conditions"]
    results = _result_map(actor_results)
    action_successes = {
        worker: {
            condition: sum(
                results[(worker, encounter, condition)]["world_receipt"]["advanced"]
                for encounter in range(8)
            )
            for condition in conditions
        }
        for worker in ("worker-1", "worker-2")
    }
    hierarchy_matches = {
        worker: {
            condition: sum(
                results[(worker, encounter, condition)]["hierarchy_correct"]
                for encounter in range(8)
            )
            for condition in conditions
        }
        for worker in ("worker-1", "worker-2")
    }
    candidate_outputs = {
        worker: [
            results[(worker, encounter, "adaptive-goal-contract")]["actor_output"]
            for encounter in range(8)
        ]
        for worker in ("worker-1", "worker-2")
    }
    candidate_plan_versions = {
        worker: [output["plan_version"] if output else None for output in outputs]
        for worker, outputs in candidate_outputs.items()
    }
    candidate_completion_claims = {
        worker: [output["completion_claim"] if output else None for output in outputs]
        for worker, outputs in candidate_outputs.items()
    }
    candidate_statuses = {
        worker: [output["goal_status"] if output else None for output in outputs]
        for worker, outputs in candidate_outputs.items()
    }
    admission_quality = {
        worker: {
            condition: bool(
                results[(worker, 0, condition)]["admission_score"]
                and results[(worker, 0, condition)]["admission_score"]["ot2_admissible"]
            )
            for condition in conditions
        }
        for worker in ("worker-1", "worker-2")
    }
    goal_stability = {
        worker: len(
            {
                output["goal_id"]
                for output in candidate_outputs[worker]
                if isinstance(output, dict)
            }
        )
        == 1
        for worker in ("worker-1", "worker-2")
    }
    observed_orders = {
        (worker, encounter): [
            item["condition"]
            for item in actor_results
            if item["worker"] == worker and item["encounter_index"] == encounter
        ]
        for worker in ("worker-1", "worker-2")
        for encounter in range(8)
    }
    expected_orders = {
        (worker, encounter): task_order["phases"][encounter][worker]
        for worker in ("worker-1", "worker-2")
        for encounter in range(8)
    }
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
    inventory_expected = acceptance["direct_inventory"]
    inventory_valid = len(inventories) == expected_turns and bool(inventories)
    if inventory_valid:
        inventory_valid = (
            all(inventory == inventories[0] for inventory in inventories)
            and sha256_bytes(canonical_json(inventories[0]))
            == inventory_expected["sha256"]
            and len(inventories[0]) == inventory_expected["tool_count"]
        )
    oracle = oracle_contract(public_evaluator_task(task))
    supplied = score_contract(
        public_evaluator_task(task), oracle, "researcher-given"
    )
    supplied_temporal = temporal_path(public_evaluator_task(task), oracle)
    scoring = acceptance["scoring"]
    candidate_condition = "adaptive-goal-contract"
    control_conditions = [condition for condition in conditions if condition != candidate_condition]
    mechanism_gate = len(mechanisms) == 2 and all(
        mechanism["pass"]
        and mechanism["candidate_route_errors"]
        == scoring["candidate_route_errors_required"]
        and mechanism["unchanged_route_errors"]
        == scoring["unchanged_route_errors_required"]
        for mechanism in mechanisms
    )
    authority = substrate_authority(repo)
    gates = {
        "complete": len(actor_results) == expected_turns
        and len(results) == expected_turns,
        "order": observed_orders == expected_orders,
        "equal_initial_goal_quality": all(
            all(values.values()) for values in admission_quality.values()
        ),
        "candidate_actions": all(
            action_successes[worker][candidate_condition]
            == scoring["candidate_action_successes_required"]
            for worker in action_successes
        ),
        "candidate_hierarchy": all(
            hierarchy_matches[worker][candidate_condition]
            == scoring["candidate_hierarchy_matches_required"]
            for worker in hierarchy_matches
        ),
        "candidate_goal_stability": all(goal_stability.values()),
        "candidate_plan_revisions": all(
            versions == scoring["candidate_plan_versions_required"]
            for versions in candidate_plan_versions.values()
        ),
        "candidate_completion": all(
            claims == [False] * 7 + [True]
            for claims in candidate_completion_claims.values()
        )
        and all(
            statuses == ["active"] * 7 + ["completed"]
            for statuses in candidate_statuses.values()
        ),
        "control_advantage": all(
            action_successes[worker][candidate_condition]
            - action_successes[worker][control]
            >= scoring["candidate_control_action_advantage_required"]
            for worker in action_successes
            for control in control_conditions
        ),
        "selector_mechanism": mechanism_gate,
        "researcher_positive_control": supplied["quality_pass"]
        and not supplied["ot2_admissible"]
        and supplied_temporal["pass"],
        "projection_budget": all(
            item["projection_bytes"]
            <= acceptance["active_inheritance_byte_limit"]
            for item in actor_results
        ),
        "hidden_authority": all(not item["hidden_task_leakage"] for item in actor_results),
        "substrate_authority": authority["pass"],
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
        "model": effective_models
        == [acceptance["deployment_epoch"]["requested_model"]]
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
        "wall_budget": elapsed_seconds
        <= acceptance["resource_budget"]["wall_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    novelty = _goal_novelty(repo, actor_results, task)
    gates["goal_novelty"] = novelty["pass"]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "admission_quality": admission_quality,
        "action_successes": action_successes,
        "hierarchy_matches": hierarchy_matches,
        "candidate_plan_versions": candidate_plan_versions,
        "candidate_completion_claims": candidate_completion_claims,
        "candidate_statuses": candidate_statuses,
        "candidate_goal_stability": goal_stability,
        "candidate_route_errors": {
            mechanism["worker"]: mechanism["candidate_route_errors"]
            for mechanism in mechanisms
        },
        "unchanged_route_errors": {
            mechanism["worker"]: mechanism["unchanged_route_errors"]
            for mechanism in mechanisms
        },
        "researcher_positive_control": {
            "quality_pass": supplied["quality_pass"],
            "ot2_admissible": supplied["ot2_admissible"],
            "temporal_pass": supplied_temporal["pass"],
        },
        "substrate_authority": authority,
        "response_count": len(distinct_response_ids),
        "effective_models": effective_models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed_seconds,
        "novelty": novelty,
        "failure_type": failure_type,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "pilot_pass": all(gates.values()),
    }


def run(
    *,
    repo: Path,
    run_id: str,
    codex_bin: Path,
    task_manifest_path: Path,
    output_path: Path,
    workspace_root: Path,
) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0039 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    task, task_bytes = read_sealed_json(task_manifest_path)
    validate_task(task)
    if sha256_bytes(task_bytes) != lock.get("task_sha256"):
        raise RuntimeError("OT-0039 private task differs from the run lock")
    if task["task_seed"] != lock.get("task_seed"):
        raise RuntimeError("OT-0039 private task seed differs from the run lock")
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0039 output or workspace already exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / TASK_ORDER_PATH)
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
                    catalog = client.request(
                        "model/list", {"includeHidden": False}
                    )["data"]
                    catalog_payloads.append(catalog)
                    if model not in {item.get("id") for item in catalog}:
                        raise RuntimeError("OT-0039 frozen hosted model is unavailable")
                    worker_results, mechanism, worker_inventories = execute_worker(
                        task=task,
                        task_order=task_order,
                        worker_id=worker_id,
                        client=client,
                        proxy=proxy,
                        model=model,
                        workspace_root=workspace_root,
                        prompt_template=prompt_template,
                        output_schema=output_schema,
                    )
                    actor_results.extend(worker_results)
                    mechanisms.append(mechanism)
                    inventories.extend(worker_inventories)
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
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
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
            repo=repo,
            acceptance=acceptance,
            task_order=task_order,
            task=task,
            actor_results=actor_results,
            mechanisms=mechanisms,
            inventories=inventories,
            proxy_receipts=proxy_receipts,
            collector_errors=collector_errors,
            catalog_payloads=catalog_payloads,
            usage=token_usage(events),
            elapsed_seconds=elapsed_seconds,
            verification=verification,
            failure_type=failure_type,
        )
    except Exception as summary_error:
        failure_type = failure_type or type(summary_error).__name__
        failure = failure or str(summary_error)
        summary = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "claim_limit": acceptance["claim_limit"],
            "failure_type": failure_type,
            "gates": {"summary": False},
            "disposition": "invalidated",
            "pilot_pass": False,
        }
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "task_sha256": task["task_sha256"],
        "summary": summary,
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
            kind="e7-self-authored-durable-goal-hosted-epoch-run",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Hosted outputs, task identities, world states, and deployment receipts remain private.",
                "A pass is time-bounded single-domain OT-2 evidence, not immutable reproduction.",
                "This run consumes E7's one-candidate authorization regardless of disposition.",
                "A pass does not establish OT-3 or cross-domain self-direction.",
            ],
            input_manifests=[
                str(E7_MANIFEST_PATH),
                str(OT1_MANIFEST_PATH),
                str(OT0_MANIFEST_PATH),
                str(OT6_MANIFEST_PATH),
            ],
        )
    finally:
        output_path.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0039-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--prepare-task-manifest", type=Path)
    parser.add_argument("--implementation-commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.prepare_task_manifest:
        if not args.implementation_commit:
            parser.error("--implementation-commit is required for task preparation")
        print(
            json.dumps(
                prepare_task_manifest(
                    args.prepare_task_manifest.resolve(), args.implementation_commit
                ),
                sort_keys=True,
            )
        )
        return 0
    if (
        args.codex_bin is None
        or args.task_manifest is None
        or args.output is None
        or args.workspace_root is None
    ):
        parser.error(
            "--codex-bin, --task-manifest, --output, and --workspace-root are required"
        )
    try:
        manifest, summary = run(
            repo=repo,
            run_id=args.run_id,
            codex_bin=args.codex_bin.resolve(),
            task_manifest_path=args.task_manifest.resolve(),
            output_path=args.output.resolve(),
            workspace_root=args.workspace_root.resolve(),
        )
    except (AppServerError, OSError, RuntimeError, ValueError) as error:
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
