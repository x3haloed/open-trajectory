from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
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
from .ot0004_world import archive_through_stage, fixed_selection, score_predictions, selected_events
from .ot0005 import instrumented_command
from .ot0005_world import (
    ProgramLedger,
    ProgramSnapshot,
    deterministic_predictions,
    deterministic_selection,
)
from .ot0016 import combined_summary, validate_counterbalance
from .ot0016_credit import (
    CounterfactualSelectorLedger,
    DecisionRuleLedger,
    DecisionRuleSnapshot,
    execute_credit_neutralized_rule,
    execute_decision_rule,
)
from .ot0016_world import EXPERIMENT_ID, generate_task_manifest, validate_task_manifest


FIXTURE_ROOT = Path("fixtures/ot-0016")
ACCEPTANCE_PATH = Path("spec/ot-0016-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0016-run-lock.json")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
TOOL_RECEIPT_PATCH_PATH = Path(
    "patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch"
)


def prepare_task_manifest(path: Path) -> dict[str, Any]:
    manifest = generate_task_manifest()
    validate_task_manifest(manifest)
    write_sealed_json(path, manifest)
    encoded = canonical_json(manifest)
    return {"sha256": sha256_bytes(encoded), "bytes": len(encoded)}


def require_clean_commit(repo: Path) -> str:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0016 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def fixed_input_paths() -> dict[str, Path]:
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "deployment_proxy_sha256": PROXY_PATH,
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "inherited_world_sha256": Path("src/open_trajectory_harness/ot0004_world.py"),
        "hosted_command_sha256": Path("src/open_trajectory_harness/ot0005.py"),
        "expression_world_sha256": Path("src/open_trajectory_harness/ot0005_world.py"),
        "world_sha256": Path("src/open_trajectory_harness/ot0016_world.py"),
        "credit_sha256": Path("src/open_trajectory_harness/ot0016_credit.py"),
        "evaluator_sha256": Path("src/open_trajectory_harness/ot0016.py"),
        "harness_sha256": Path("src/open_trajectory_harness/ot0016_live.py"),
        "entrypoint_sha256": Path("experiments/ot_0016_harness.py"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
    }
    for name in (
        "selector-seed.txt",
        "challenger-prompt.txt",
        "challenger-output.schema.json",
        "novelty-rubric.txt",
        "novelty-output.schema.json",
    ):
        key = f"fixture_{name.replace('.', '_').replace('-', '_')}_sha256"
        paths[key] = FIXTURE_ROOT / name
    return paths


def validate_run_lock(repo: Path, execution_commit: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    for name in ("implementation_git_commit", "protocol_origin_git_commit"):
        commit = lock.get(name, "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise RuntimeError(f"run lock omits a full {name}")
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, execution_commit], cwd=repo
        ).returncode:
            raise RuntimeError(f"frozen {name} is not an ancestor of execution HEAD")
    observed = {name: sha256_file(repo / path) for name, path in fixed_input_paths().items()}
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("frozen input identity differs from the OT-0016 run lock")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{lock['implementation_git_commit']}..{execution_commit}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"implementation changed after run lock: {changed}")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("pinned Codex executable or code-mode host is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from frozen identity")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from frozen identity")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex executable version differs from run lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from frozen identity")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_counterbalance(
        load_json(repo / FIXTURE_ROOT / "task-order.json"),
        acceptance["deployment_epoch"]["condition_position_count_across_workers"],
    )
    return lock


def _actor_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    role: str,
    prompt: str,
    output_schema: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Perform only the supplied role and return schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0016",
        }
    )
    receipt_start = len(proxy.collector.snapshot())
    inventory_start = len(client.model_visible_tool_inventories())
    turn = client.run_turn(
        thread_id=thread["id"],
        input_text=prompt,
        output_schema=output_schema,
        sandbox_policy={"type": "readOnly", "networkAccess": False},
        timeout=timeout,
    )
    output, parse_error = final_agent_json(turn)
    if turn.get("status") != "completed":
        parse_error = parse_error or "actor turn did not complete"
    receipts = proxy.collector.snapshot()[receipt_start:]
    result = {
        "role": role,
        "model": model,
        "workspace": str(workspace.resolve()),
        "thread_id": thread["id"],
        "thread_session_id": thread.get("sessionId"),
        "parse_error": parse_error,
        "tool_calls": client.completed_turn_tool_calls(
            thread_id=thread["id"], turn_id=turn["id"]
        ),
        "inventory_receipts": len(client.model_visible_tool_inventories()) - inventory_start,
        "deployment_receipts": receipts,
        "deployment_effective_models": sorted(
            {item["value"] for item in receipts if item["kind"] == "effective_model"}
        ),
        "deployment_response_ids": sorted(
            {item["value"] for item in receipts if item["kind"] == "response_id"}
        ),
        "turn": turn,
    }
    return result, output


def deterministic_branch(
    *,
    condition: str,
    snapshot: ProgramSnapshot | None,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
    iteration_depth_limit: int,
) -> dict[str, Any]:
    if snapshot is None:
        selected_ids = fixed_selection(condition, archive, queries, limit)
        program_sha256 = None
    else:
        selected_ids = deterministic_selection(
            snapshot.expression,
            archive,
            queries,
            limit,
            allow_empty=snapshot.expression == "[]",
            iteration_depth_limit=iteration_depth_limit,
        )
        program_sha256 = snapshot.sha256
    predictions = deterministic_predictions(selected_events(archive, selected_ids), queries)
    replay_ids = list(selected_ids)
    replay = deterministic_predictions(selected_events(archive, replay_ids), queries)
    errors, parse_error = score_predictions(predictions, outcomes)
    if predictions != replay or parse_error:
        raise RuntimeError("OT-0016 deterministic branch replay failed")
    return {
        "condition": condition,
        "program_sha256": program_sha256,
        "selected_event_ids": selected_ids,
        "selected_event_ids_sha256": sha256_bytes(canonical_json(selected_ids)),
        "predictions": predictions,
        "predictions_sha256": sha256_bytes(canonical_json(predictions)),
        "errors": errors,
        "deterministic_replay": True,
    }


def proposal_prompt(
    seed: str,
    template: str,
    selector_expression: str,
    decision_expression: str,
    prior_receipt: dict[str, Any],
) -> str:
    body = (
        template.replace("{{SELECTOR_EXPRESSION}}", selector_expression)
        .replace("{{DECISION_EXPRESSION}}", decision_expression)
        .replace(
            "{{PRIOR_RECEIPT}}",
            json.dumps(prior_receipt, sort_keys=True, separators=(",", ":")),
        )
    )
    return f"{seed}\n\n{body}"


def _proposal(value: Any) -> tuple[dict[str, str], dict[str, str]]:
    expected = {
        "selector_expression",
        "decision_expression",
        "expected_effect",
        "cheapest_falsifier",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("challenger output failed exact schema authority check")
    if any(not isinstance(value[name], str) or not value[name].strip() for name in expected):
        raise ValueError("challenger output contains invalid text")
    common = {
        "expected_effect": value["expected_effect"],
        "cheapest_falsifier": value["cheapest_falsifier"],
    }
    return (
        {"expression": value["selector_expression"], **common},
        {"expression": value["decision_expression"], **common},
    )


def _program_identity_placebo(
    snapshot: ProgramSnapshot,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
    iteration_depth_limit: int,
) -> bool:
    placebo = ProgramLedger(
        snapshot.expression,
        byte_limit=2048,
        iteration_depth_limit=iteration_depth_limit,
    ).commit(
        {
            "expression": snapshot.expression,
            "expected_effect": "identity-only replay",
            "cheapest_falsifier": "behavior differs",
        }
    )
    left = deterministic_branch(
        condition="identity-program-source",
        snapshot=snapshot,
        archive=archive,
        queries=queries,
        outcomes=outcomes,
        limit=limit,
        iteration_depth_limit=iteration_depth_limit,
    )
    right = deterministic_branch(
        condition="identity-program-placebo",
        snapshot=placebo,
        archive=archive,
        queries=queries,
        outcomes=outcomes,
        limit=limit,
        iteration_depth_limit=iteration_depth_limit,
    )
    return (
        snapshot.sha256 != placebo.sha256
        and left["selected_event_ids"] == right["selected_event_ids"]
        and left["predictions"] == right["predictions"]
        and left["errors"] == right["errors"]
    )


def _decision_identity_placebo(
    rule: DecisionRuleSnapshot, comparison_receipt: dict[str, Any]
) -> bool:
    placebo = DecisionRuleLedger(rule.expression).commit(
        {
            "expression": rule.expression,
            "expected_effect": "identity-only replay",
            "cheapest_falsifier": "choice differs",
        }
    )
    left = execute_decision_rule(rule, comparison_receipt)
    right = execute_decision_rule(placebo, comparison_receipt)
    return rule.sha256 != placebo.sha256 and left["choice"] == right["choice"]


def _next_receipt(
    stage_index: int,
    comparison: dict[str, Any],
    true_application: dict[str, Any],
    neutralized_application: dict[str, Any],
    commit: dict[str, Any],
    committed_branch: dict[str, Any],
    unchanged_branch: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "schema_version": 1,
        "source_stage": stage_index,
        "contact_comparison": comparison,
        "decision": {
            "true_choice": true_application["choice"],
            "credit_neutralized_choice": neutralized_application["choice"],
            "rule_sha256": true_application["decision_rule_sha256"],
        },
        "commit": commit,
        "heldout": {
            "committed_program_sha256": committed_branch["program_sha256"],
            "committed_selected_event_ids": committed_branch["selected_event_ids"],
            "committed_predictions": committed_branch["predictions"],
            "unchanged_program_sha256": unchanged_branch["program_sha256"],
            "unchanged_selected_event_ids": unchanged_branch["selected_event_ids"],
            "unchanged_predictions": unchanged_branch["predictions"],
            "outcomes": comparison.get("released_heldout_outcomes", []),
            "committed_errors": committed_branch["errors"],
            "unchanged_errors": unchanged_branch["errors"],
        },
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def execute_worker(
    *,
    repo: Path,
    task_manifest_path: Path,
    output_path: Path,
    workspace_root: Path,
    codex_bin: Path,
    worker_id: str,
) -> None:
    execution_commit = require_clean_commit(repo)
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    manifest, task_bytes = read_sealed_json(task_manifest_path)
    validate_task_manifest(manifest)
    if sha256_bytes(task_bytes) != lock.get("task_manifest_sha256"):
        raise RuntimeError("private task manifest differs from frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    seed = (repo / FIXTURE_ROOT / "selector-seed.txt").read_text(encoding="utf-8")
    template = (repo / FIXTURE_ROOT / "challenger-prompt.txt").read_text(encoding="utf-8")
    challenger_schema = load_json(repo / FIXTURE_ROOT / "challenger-output.schema.json")
    rubric = (repo / FIXTURE_ROOT / "novelty-rubric.txt").read_text(encoding="utf-8")
    novelty_schema = load_json(repo / FIXTURE_ROOT / "novelty-output.schema.json")
    actor_model = acceptance["deployment_epoch"]["actor_model"]
    reviewer_model = acceptance["deployment_epoch"]["reviewer_model"]
    limit = acceptance["candidate"]["selected_events_per_prediction"]
    depth = acceptance["candidate"]["selector_expression_iteration_depth"]
    selector_ledger = CounterfactualSelectorLedger(
        acceptance["candidate"]["seed_selector_expression"],
        acceptance["candidate"]["selector_expression_bytes"],
        depth,
    )
    decision_ledger = DecisionRuleLedger(
        acceptance["candidate"]["seed_decision_expression"],
        acceptance["candidate"]["decision_expression_bytes"],
    )
    workspace_root.mkdir(parents=True, exist_ok=False)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    stage_records: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    identity_placebos: dict[str, dict[str, bool]] = {}
    prior_receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "seed",
        "released_prior_contact": [],
        "candidate_task_outcomes": False,
    }
    started = time.monotonic()
    deadline = started + acceptance["resource_budget"]["wall_seconds_per_worker"]
    client: AppServerClient | None = None
    proxy: SanitizedResponsesProxy | None = None

    def encounter(
        active_client: AppServerClient,
        active_proxy: SanitizedResponsesProxy,
        role: str,
        prompt: str,
        schema: dict[str, Any],
        model: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            raise TimeoutError("OT-0016 worker exhausted its frozen wall budget")
        result, output = _actor_turn(
            client=active_client,
            proxy=active_proxy,
            model=model,
            workspace=workspace_root / f"encounter-{len(actor_results):02d}-{role}",
            role=role,
            prompt=prompt,
            output_schema=schema,
            timeout=min(180.0, remaining),
        )
        actor_results.append(result)
        return result, output

    try:
        with SanitizedResponsesProxy() as active_proxy:
            proxy = active_proxy
            with AppServerClient(
                command=instrumented_command(codex_bin, proxy.base_url),
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as active_client:
                client = active_client
                models = client.request("model/list", {"includeHidden": False})["data"]
                if not {actor_model, reviewer_model} <= {item.get("id") for item in models}:
                    raise RuntimeError("one or more frozen OT-0016 models are unavailable")
                catalog_payload_sha256 = sha256_bytes(canonical_json(models))
                inventory_by_model: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)

                for stage_index, phase in enumerate(task_order["phases"]):
                    stage = manifest["stages"][stage_index]
                    archive = archive_through_stage(manifest, stage_index)
                    current = selector_ledger.current
                    protected_parent = (
                        selector_ledger.snapshots[-2]
                        if len(selector_ledger.snapshots) > 1
                        else current
                    )
                    current_rule = decision_ledger.current
                    result, output = encounter(
                        client,
                        proxy,
                        f"stage-{stage_index}-prospective-challenger",
                        proposal_prompt(
                            seed,
                            template,
                            current.expression,
                            current_rule.expression,
                            prior_receipt,
                        ),
                        challenger_schema,
                        actor_model,
                    )
                    inventory_by_model[actor_model].append(
                        client.model_visible_tool_inventories()[-1]
                    )
                    if result["parse_error"]:
                        raise ValueError("challenger actor output did not parse")
                    selector_proposal, decision_proposal = _proposal(output)
                    challenger = selector_ledger.propose(selector_proposal)
                    rule = decision_ledger.commit(decision_proposal)
                    comparison = selector_ledger.compare(
                        challenger,
                        archive=archive,
                        queries=stage["contact"]["queries"],
                        outcomes=stage["contact"]["outcomes"],
                        limit=limit,
                        stage=stage_index,
                        split_identity="contact",
                    )
                    true_application = execute_decision_rule(rule, comparison)
                    neutralized_application = execute_credit_neutralized_rule(rule, comparison)
                    before = selector_ledger.current
                    after = selector_ledger.decide_with_rule(challenger, comparison, rule)
                    commit = selector_ledger.decisions[-1]

                    branches: dict[str, dict[str, Any]] = {}
                    for condition in phase["condition_order"][worker_id]:
                        if condition == "committed-program":
                            snapshot = after
                        elif condition == "unchanged-current":
                            snapshot = before
                        else:
                            snapshot = None
                        branches[condition] = deterministic_branch(
                            condition=condition,
                            snapshot=snapshot,
                            archive=archive,
                            queries=stage["heldout"]["queries"],
                            outcomes=stage["heldout"]["outcomes"],
                            limit=limit,
                            iteration_depth_limit=depth,
                        )
                    parent_branch = deterministic_branch(
                        condition="protected-preupdate-parent",
                        snapshot=protected_parent,
                        archive=archive,
                        queries=stage["heldout"]["queries"],
                        outcomes=stage["heldout"]["outcomes"],
                        limit=limit,
                        iteration_depth_limit=depth,
                    )
                    identity_placebos[f"stage-{stage_index}"] = {
                        "program": _program_identity_placebo(
                            after,
                            archive,
                            stage["heldout"]["queries"],
                            stage["heldout"]["outcomes"],
                            limit,
                            depth,
                        ),
                        "decision_rule": _decision_identity_placebo(rule, comparison),
                    }
                    proposals.append(
                        {
                            "stage": stage_index,
                            "actor_result_index": len(actor_results) - 1,
                            "selector": selector_proposal,
                            "selector_challenger": challenger.public_identity(),
                            "decision_rule": decision_proposal,
                            "decision_rule_snapshot": rule.public_identity(),
                            "prior_receipt_sha256": prior_receipt.get("receipt_sha256"),
                        }
                    )
                    record = {
                        "stage": stage_index,
                        "current_program": current.public_identity(),
                        "protected_parent_program": protected_parent.public_identity(),
                        "challenger": challenger.public_identity(),
                        "contact_comparison": comparison,
                        "decision": {
                            "rule": rule.public_identity(),
                            "true_application": true_application,
                            "credit_neutralized_application": neutralized_application,
                        },
                        "commit": commit,
                        "heldout_condition_order": phase["condition_order"][worker_id],
                        "branches": branches,
                        "preupdate_parent_branch": parent_branch,
                    }
                    stage_records.append(record)
                    released_comparison = dict(comparison)
                    released_comparison["released_heldout_outcomes"] = stage["heldout"]["outcomes"]
                    prior_receipt = _next_receipt(
                        stage_index,
                        released_comparison,
                        true_application,
                        neutralized_application,
                        commit,
                        branches["committed-program"],
                        branches["unchanged-current"],
                    )

                review_candidates = []
                advantage_gate = acceptance["scoring"][
                    "committed_over_unchanged_error_advantage_per_revision"
                ]
                for proposal, record in zip(proposals, stage_records):
                    committed = record["branches"]["committed-program"]
                    unchanged = record["branches"]["unchanged-current"]
                    true_choice = record["decision"]["true_application"]["choice"]
                    neutralized_choice = record["decision"]["credit_neutralized_application"]["choice"]
                    if (
                        record["commit"]["changed"]
                        and unchanged["errors"] - committed["errors"] >= advantage_gate
                        and true_choice == "challenger"
                        and neutralized_choice == "current"
                    ):
                        review_candidates.append(
                            {
                                "stage": record["stage"],
                                "proposal": proposal["selector"],
                                "committed_selected_event_ids": committed["selected_event_ids"],
                                "unchanged_selected_event_ids": unchanged["selected_event_ids"],
                                "committed_errors": committed["errors"],
                                "unchanged_errors": unchanged["errors"],
                                "true_choice": true_choice,
                                "credit_neutralized_choice": neutralized_choice,
                            }
                        )
                review_packet = {
                    "null_seeds": {"selector": "[]", "decision": '"current"'},
                    "carrier_contract": seed,
                    "candidate_revisions": review_candidates,
                }
                for review_index in range(
                    acceptance["novelty_review"]["fresh_blinded_reviews_per_worker"]
                ):
                    result, output = encounter(
                        client,
                        proxy,
                        f"novelty-review-{review_index + 1}",
                        rubric
                        + "\n\nBlinded controller packet:\n"
                        + json.dumps(review_packet, sort_keys=True, separators=(",", ":")),
                        novelty_schema,
                        reviewer_model,
                    )
                    inventory_by_model[reviewer_model].append(
                        client.model_visible_tool_inventories()[-1]
                    )
                    if (
                        result["parse_error"]
                        or not isinstance(output, dict)
                        or set(output) != {"pass", "operation_summary", "seed_overlap"}
                        or type(output["pass"]) is not bool
                        or not isinstance(output["operation_summary"], str)
                        or not isinstance(output["seed_overlap"], str)
                    ):
                        raise ValueError("novelty review failed exact output validation")
                    reviews.append(output)

                time.sleep(acceptance["resource_budget"]["proxy_drain_seconds"])
                direct_inventory_by_model = {}
                for model, values in inventory_by_model.items():
                    encoded = canonical_json(values[0]) if values else b""
                    direct_inventory_by_model[model] = {
                        "sha256": sha256_bytes(encoded) if values else None,
                        "tool_count": len(values[0]) if values else 0,
                        "receipt_count": len(values),
                        "stable": bool(values) and all(value == values[0] for value in values),
                    }
                deployment_receipts = proxy.collector.snapshot()
                deployment_errors = proxy.collector.errors()
                deployment_diagnostics = proxy.collector.diagnostics()
                events = client.raw_events
                stderr = client.stderr_lines
                usage = token_usage(events)
                catalog_payload = models
    except Exception as error:
        failure = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "status": "failed",
            "worker_id": worker_id,
            "execution_git_commit": execution_commit,
            "task_manifest_sha256": sha256_bytes(task_bytes),
            "error_type": type(error).__name__,
            "error": str(error),
            "actor_results": actor_results,
            "stage_records": stage_records,
            "events": client.raw_events if client else [],
            "stderr": client.stderr_lines if client else [],
            "deployment_receipts": proxy.collector.snapshot() if proxy else [],
            "deployment_errors": proxy.collector.errors() if proxy else [],
            "elapsed_seconds": time.monotonic() - started,
        }
        write_sealed_json(output_path, failure)
        raise

    worker = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": "completed",
        "worker_id": worker_id,
        "execution_git_commit": execution_commit,
        "task_manifest_sha256": sha256_bytes(task_bytes),
        "actor_results": actor_results,
        "proposals": proposals,
        "stage_records": stage_records,
        "selector_snapshots": [snapshot.__dict__ for snapshot in selector_ledger.snapshots],
        "decision_rule_snapshots": [snapshot.__dict__ for snapshot in decision_ledger.snapshots],
        "identity_placebos": identity_placebos,
        "reviews": reviews,
        "direct_inventory_by_model": direct_inventory_by_model,
        "deployment": {
            "catalog_payload": catalog_payload,
            "catalog_payload_sha256": catalog_payload_sha256,
            "receipts": deployment_receipts,
            "collector_errors": deployment_errors,
            "diagnostics": deployment_diagnostics,
        },
        "usage": usage,
        "elapsed_seconds": time.monotonic() - started,
        "events": events,
        "stderr": stderr,
    }
    write_sealed_json(output_path, worker)


def run(
    repo: Path, run_id: str, codex_bin: Path, task_manifest_path: Path
) -> tuple[Path, dict[str, Any]]:
    execution_commit = require_clean_commit(repo)
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    task_manifest, task_bytes = read_sealed_json(task_manifest_path)
    validate_task_manifest(task_manifest)
    task_digest = sha256_bytes(task_bytes)
    if task_digest != lock.get("task_manifest_sha256"):
        raise RuntimeError("private task manifest differs from frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    run_root = repo / ".evidence" / "runs" / EXPERIMENT_ID / run_id
    if run_root.exists():
        raise RuntimeError(f"run id already exists: {run_id}")
    run_root.mkdir(parents=True)
    outputs = [run_root / "original.json", run_root / "reproduction.json"]
    workspaces = [
        repo / ".evidence" / "sandboxes" / f"{run_id}-original",
        repo / ".evidence" / "sandboxes" / f"{run_id}-reproduction",
    ]
    processes = []
    started = time.monotonic()
    for index, (output, workspace) in enumerate(zip(outputs, workspaces), start=1):
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "open_trajectory_harness.ot0016_live",
                    "--worker",
                    "--repo",
                    str(repo),
                    "--codex-bin",
                    str(codex_bin),
                    "--task-manifest",
                    str(task_manifest_path),
                    "--worker-output",
                    str(output),
                    "--workspace-root",
                    str(workspace),
                    "--worker-id",
                    f"worker-{index}",
                ],
                cwd=repo,
                env=child_environment(repo),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    worker_receipts = []
    window_limit = acceptance["deployment_epoch"]["maximum_two_worker_window_seconds"]
    deadline = started + window_limit
    for index, process in enumerate(processes, start=1):
        try:
            stdout, stderr = process.communicate(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            stderr += "\nworker exceeded frozen two-worker window"
        worker_receipts.append(
            {
                "worker_id": f"worker-{index}",
                "returncode": process.returncode,
                "stdout_sha256": sha256_bytes(stdout.encode()),
                "stderr_sha256": sha256_bytes(stderr.encode()),
                "stderr_lines": len(stderr.splitlines()),
            }
        )
    window = time.monotonic() - started
    if any(item["returncode"] != 0 for item in worker_receipts):
        raise RuntimeError("one or more workers failed before complete sealed evidence")
    workers = [read_sealed_json(path)[0] for path in outputs]
    raw: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "implementation_clean": True,
        "task_manifest_sha256": task_digest,
        "task_manifest": task_manifest,
        "same_task_manifest": all(
            worker["execution_git_commit"] == execution_commit
            and worker["task_manifest_sha256"] == task_digest
            for worker in workers
        ),
        "acceptance": acceptance,
        "task_order": task_order,
        "workers": workers,
        "worker_receipts": worker_receipts,
        "two_worker_window_seconds": window,
        "audit_and_tests": False,
    }
    test = subprocess.run(
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
    raw["execution_verification"] = {
        "tests": {"returncode": test.returncode, "stdout": test.stdout, "stderr": test.stderr},
        "audit": {"returncode": audit.returncode, "stdout": audit.stdout, "stderr": audit.stderr},
    }
    raw["audit_and_tests"] = test.returncode == 0 and audit.returncode == 0
    raw_path = run_root / "run.json"
    raw_path.write_bytes(canonical_json(raw))
    manifest_path = record_artifact(
        repo=repo,
        input_path=raw_path,
        experiment_id=EXPERIMENT_ID,
        artifact_id=run_id,
        kind="counterfactual-challenger-credit-hosted-epoch-run",
        evidence_class="private-reproducible",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0016_live "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The task, expressions, selections, actor events, reviews, ETag, and Response IDs remain private.",
            "The result is limited to one constrained family and a time-bounded hosted epoch.",
        ],
        input_manifests=[],
    )
    return manifest_path, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0016-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0016-hosted-epoch-001")
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--prepare-task-manifest", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--worker-id", choices=("worker-1", "worker-2"))
    parser.add_argument("--reconstruct", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.prepare_task_manifest:
        print(json.dumps(prepare_task_manifest(args.prepare_task_manifest.resolve()), sort_keys=True))
        return 0
    if args.reconstruct:
        sys.stdout.buffer.write(canonical_json(combined_summary(load_json(args.reconstruct))))
        return 0
    if args.codex_bin is None or args.task_manifest is None:
        parser.error("--codex-bin and --task-manifest are required")
    try:
        if args.worker:
            if args.worker_output is None or args.workspace_root is None or not args.worker_id:
                parser.error("worker output, workspace root, and worker id are required")
            execute_worker(
                repo=repo,
                task_manifest_path=args.task_manifest.resolve(),
                output_path=args.worker_output.resolve(),
                workspace_root=args.workspace_root.resolve(),
                codex_bin=args.codex_bin.resolve(),
                worker_id=args.worker_id,
            )
            return 0
        manifest, summary = run(
            repo, args.run_id, args.codex_bin.resolve(), args.task_manifest.resolve()
        )
    except (AppServerError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
