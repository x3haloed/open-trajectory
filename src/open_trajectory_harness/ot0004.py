from __future__ import annotations

import argparse
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
    base_app_server_command,
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
from .ot0004_world import (
    EXPERIMENT_ID,
    PolicyLedger,
    archive_through_stage,
    fixed_selection,
    generate_task_manifest,
    protected_consequence_receipt,
    render_events,
    render_queries,
    score_predictions,
    selected_events,
    validate_task_manifest,
)


FIXTURE_ROOT = Path("fixtures/ot-0004")
ACCEPTANCE_PATH = Path("spec/ot-0004-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0004-run-lock.json")
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
        raise RuntimeError("OT-0004 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def validate_counterbalance(task_order: dict[str, Any], expected_count: int) -> None:
    conditions = task_order.get("conditions")
    phases = task_order.get("phases")
    if not isinstance(conditions, list) or len(conditions) != 6 or len(set(conditions)) != 6:
        raise ValueError("OT-0004 counterbalance requires six distinct conditions")
    counts = {condition: Counter() for condition in conditions}
    for phase in phases or []:
        orders = phase.get("condition_order") if isinstance(phase, dict) else None
        if not isinstance(orders, dict) or set(orders) != {"worker-1", "worker-2"}:
            raise ValueError("each stage requires two worker-specific orders")
        for order in orders.values():
            if not isinstance(order, list) or len(order) != 6 or set(order) != set(conditions):
                raise ValueError("heldout condition order is not an exact permutation")
            for position, condition in enumerate(order):
                counts[condition][position] += 1
    expected = Counter({position: expected_count for position in range(6)})
    if any(value != expected for value in counts.values()):
        raise ValueError("heldout condition positions are not exactly counterbalanced")


def fixed_input_paths() -> dict[str, Path]:
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "deployment_proxy_sha256": PROXY_PATH,
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "world_sha256": Path("src/open_trajectory_harness/ot0004_world.py"),
        "harness_sha256": Path("src/open_trajectory_harness/ot0004.py"),
    }
    for name in (
        "selector-seed.txt",
        "selector-update-prompt.txt",
        "selector-update-output.schema.json",
        "selector-apply-prompt.txt",
        "selector-apply-output.schema.json",
        "predictor-prompt.txt",
        "predictor-output.schema.json",
        "novelty-rubric.txt",
        "novelty-output.schema.json",
    ):
        paths[f"fixture_{name.replace('.', '_').replace('-', '_')}_sha256"] = FIXTURE_ROOT / name
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
        raise RuntimeError("frozen input identity differs from the OT-0004 run lock")
    protected = [
        "src/open_trajectory_harness/app_server.py",
        "src/open_trajectory_harness/deployment_proxy.py",
        "src/open_trajectory_harness/ot0002.py",
        "src/open_trajectory_harness/ot0003.py",
        "src/open_trajectory_harness/ot0004.py",
        "src/open_trajectory_harness/ot0004_world.py",
        "experiments/ot_0004_harness.py",
        "fixtures/ot-0004",
        str(ACCEPTANCE_PATH),
        str(TOOL_RECEIPT_PATCH_PATH),
        str(LOCK_PATH),
    ]
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
        raise RuntimeError("pinned Codex executable or sibling code-mode host is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from frozen identity")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from frozen identity")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex executable version differs from run lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from frozen identity")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    validate_counterbalance(
        task_order,
        acceptance["deployment_epoch"]["condition_position_count_across_workers"],
    )
    return lock


def instrumented_command(codex_bin: Path, proxy_base_url: str) -> list[str]:
    command = base_app_server_command()
    command[0] = str(codex_bin)
    provider = (
        "{name=\"OpenAI\"," f"base_url=\"{proxy_base_url}codex\","
        "wire_api=\"responses\",requires_openai_auth=true,"
        "supports_websockets=false,http_headers={version=\"0.149.0\"}}"
    )
    command.extend(
        [
            "-c",
            'model_provider="ot_hosted"',
            "-c",
            f"model_providers.ot_hosted={provider}",
            "-c",
            f'chatgpt_base_url="{proxy_base_url}"',
        ]
    )
    return command


def _exact_string_object(value: Any, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys and all(
        isinstance(value[key], str) and bool(value[key].strip()) for key in keys
    )


def run_actor_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    role: str,
    prompt: str,
    output_schema: dict[str, Any],
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
            "serviceName": "open_trajectory_ot0004",
        }
    )
    deployment_before = len(proxy.collector.snapshot())
    inventories_before = len(client.model_visible_tool_inventories())
    turn = client.run_turn(
        thread_id=thread["id"],
        input_text=prompt,
        output_schema=output_schema,
        sandbox_policy={"type": "readOnly", "networkAccess": False},
        timeout=180,
    )
    output, parse_error = final_agent_json(turn)
    if turn.get("status") != "completed":
        parse_error = parse_error or "actor turn did not complete"
    receipts = proxy.collector.snapshot()[deployment_before:]
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
        "inventory_receipts": len(client.model_visible_tool_inventories()) - inventories_before,
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


def selector_prompt(template: str, policy: str, archive: list[dict[str, Any]], queries: list[list[int]]) -> str:
    return (
        template.replace("{{POLICY}}", policy)
        .replace("{{EVENTS}}", render_events(archive))
        .replace("{{QUERIES}}", render_queries(queries))
    )


def predictor_prompt(template: str, events: list[dict[str, Any]], queries: list[list[int]]) -> str:
    return template.replace("{{SELECTED_EVENTS}}", render_events(events)).replace(
        "{{QUERIES}}", render_queries(queries)
    )


def update_prompt(template: str, policy: str, receipt: dict[str, Any]) -> str:
    return template.replace("{{POLICY}}", policy).replace(
        "{{RECEIPT}}", json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    )


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
    templates = {
        name: (repo / FIXTURE_ROOT / f"{name}.txt").read_text(encoding="utf-8")
        for name in ("selector-update-prompt", "selector-apply-prompt", "predictor-prompt")
    }
    schemas = {
        name: load_json(repo / FIXTURE_ROOT / f"{name}.schema.json")
        for name in (
            "selector-update-output",
            "selector-apply-output",
            "predictor-output",
            "novelty-output",
        )
    }
    rubric = (repo / FIXTURE_ROOT / "novelty-rubric.txt").read_text(encoding="utf-8")
    actor_model = acceptance["deployment_epoch"]["actor_model"]
    reviewer_model = acceptance["deployment_epoch"]["reviewer_model"]
    selection_limit = acceptance["candidate"]["selected_events_per_prediction"]
    ledger = PolicyLedger(seed, acceptance["candidate"]["policy_bytes"])
    workspace_root.mkdir(parents=True, exist_ok=False)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    stage_records: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    started = time.monotonic()
    client: AppServerClient | None = None
    proxy: SanitizedResponsesProxy | None = None

    def encounter(
        active_client: AppServerClient,
        active_proxy: SanitizedResponsesProxy,
        role: str,
        prompt: str,
        schema_name: str,
        model: str = actor_model,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        result, output = run_actor_turn(
            client=active_client,
            proxy=active_proxy,
            model=model,
            workspace=workspace_root / f"encounter-{len(actor_results):03d}-{role}",
            role=role,
            prompt=prompt,
            output_schema=schemas[schema_name],
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
                available = {item.get("id") for item in models}
                if not {actor_model, reviewer_model} <= available:
                    raise RuntimeError("one or more frozen OT-0004 models are unavailable")
                catalog_payload_sha256 = sha256_bytes(canonical_json(models))
                for stage_index, phase_spec in enumerate(task_order["phases"]):
                    stage = manifest["stages"][stage_index]
                    archive = archive_through_stage(manifest, stage_index)
                    current = ledger.current
                    parent = ledger.snapshots[-2] if len(ledger.snapshots) > 1 else current

                    contact_selector, contact_output = encounter(
                        client,
                        proxy,
                        f"stage-{stage_index}-contact-selector",
                        selector_prompt(
                            templates["selector-apply-prompt"],
                            current.policy,
                            archive,
                            stage["contact"]["queries"],
                        ),
                        "selector-apply-output",
                    )
                    contact_ids = (
                        contact_output.get("selected_event_ids")
                        if isinstance(contact_output, dict)
                        else None
                    )
                    if contact_selector["parse_error"] or not isinstance(contact_ids, list) or len(contact_ids) != selection_limit:
                        raise RuntimeError("contact selector failed exact output validation")
                    contact_events = selected_events(archive, contact_ids)
                    contact_predictor, contact_prediction = encounter(
                        client,
                        proxy,
                        f"stage-{stage_index}-contact-predictor",
                        predictor_prompt(
                            templates["predictor-prompt"],
                            contact_events,
                            stage["contact"]["queries"],
                        ),
                        "predictor-output",
                    )
                    predictions = (
                        contact_prediction.get("predictions")
                        if isinstance(contact_prediction, dict)
                        else None
                    )
                    contact_errors, prediction_error = score_predictions(
                        predictions, stage["contact"]["outcomes"]
                    )
                    if contact_predictor["parse_error"] or prediction_error:
                        raise RuntimeError("contact predictor failed exact output validation")
                    receipt = protected_consequence_receipt(
                        stage_index=stage_index,
                        policy_sha256=current.sha256,
                        archive=archive,
                        selected_ids=contact_ids,
                        queries=stage["contact"]["queries"],
                        predictions=predictions,
                        outcomes=stage["contact"]["outcomes"],
                    )
                    branches: dict[str, dict[str, Any]] = {}
                    for condition in phase_spec["condition_order"][worker_id]:
                        selector_result = None
                        policy_sha = None
                        if condition in {"changed-policy", "frozen-predecessor"}:
                            policy = current if condition == "changed-policy" else parent
                            policy_sha = policy.sha256
                            selector_result, output = encounter(
                                client,
                                proxy,
                                f"stage-{stage_index}-{condition}-selector",
                                selector_prompt(
                                    templates["selector-apply-prompt"],
                                    policy.policy,
                                    archive,
                                    stage["heldout"]["queries"],
                                ),
                                "selector-apply-output",
                            )
                            selected_ids = (
                                output.get("selected_event_ids")
                                if isinstance(output, dict)
                                else None
                            )
                            if selector_result["parse_error"] or not isinstance(selected_ids, list) or len(selected_ids) != selection_limit:
                                raise RuntimeError(f"{condition} selector failed exact output validation")
                            selected = selected_events(archive, selected_ids)
                        else:
                            selected_ids = fixed_selection(
                                condition,
                                archive,
                                stage["heldout"]["queries"],
                                selection_limit,
                            )
                            selected = selected_events(archive, selected_ids)
                        predictor_result, output = encounter(
                            client,
                            proxy,
                            f"stage-{stage_index}-{condition}-predictor",
                            predictor_prompt(
                                templates["predictor-prompt"],
                                selected,
                                stage["heldout"]["queries"],
                            ),
                            "predictor-output",
                        )
                        branch_predictions = (
                            output.get("predictions") if isinstance(output, dict) else None
                        )
                        errors, parse_error = score_predictions(
                            branch_predictions, stage["heldout"]["outcomes"]
                        )
                        if predictor_result["parse_error"] or parse_error:
                            raise RuntimeError(f"{condition} predictor failed exact output validation")
                        branches[condition] = {
                            "condition": condition,
                            "policy_sha256": policy_sha,
                            "selected_event_ids": selected_ids,
                            "selected_event_ids_sha256": sha256_bytes(canonical_json(selected_ids)),
                            "predictions": branch_predictions,
                            "errors": errors,
                            "selector_actor_result_index": (
                                actor_results.index(selector_result) if selector_result else None
                            ),
                            "predictor_actor_result_index": actor_results.index(predictor_result),
                        }

                    update_result, proposal = encounter(
                        client,
                        proxy,
                        f"stage-{stage_index}-selector-update",
                        update_prompt(templates["selector-update-prompt"], current.policy, receipt),
                        "selector-update-output",
                    )
                    if (
                        update_result["parse_error"]
                        or not _exact_string_object(
                            proposal,
                            {"policy", "expected_effect", "cheapest_falsifier"},
                        )
                        or len(proposal["expected_effect"]) > 384
                        or len(proposal["cheapest_falsifier"]) > 384
                    ):
                        raise RuntimeError("selector update failed exact output validation")
                    next_policy = ledger.commit(proposal)
                    proposals.append(
                        {
                            "source_stage": stage_index,
                            "proposal": proposal,
                            "committed_policy": next_policy.public_identity(),
                            "actor_result_index": actor_results.index(update_result),
                        }
                    )
                    stage_records.append(
                        {
                            "stage": stage_index,
                            "current_policy": current.public_identity(),
                            "parent_policy": parent.public_identity(),
                            "contact": {
                                "selected_event_ids_sha256": sha256_bytes(canonical_json(contact_ids)),
                                "errors": contact_errors,
                                "receipt": receipt,
                            },
                            "heldout_condition_order": phase_spec["condition_order"][worker_id],
                            "branches": branches,
                            "next_policy": next_policy.public_identity(),
                        }
                    )

                review_candidates = []
                for record in stage_records[1:]:
                    changed = record["branches"]["changed-policy"]
                    frozen = record["branches"]["frozen-predecessor"]
                    if (
                        changed["selected_event_ids"] != frozen["selected_event_ids"]
                        and frozen["errors"] - changed["errors"]
                        >= acceptance["scoring"]["changed_over_frozen_error_advantage_per_revision"]
                    ):
                        review_candidates.append(
                            {
                                "stage": record["stage"],
                                "proposal": proposals[record["stage"] - 1]["proposal"],
                                "changed_selected_event_ids": changed["selected_event_ids"],
                                "frozen_selected_event_ids": frozen["selected_event_ids"],
                                "changed_errors": changed["errors"],
                                "frozen_errors": frozen["errors"],
                            }
                        )
                review_packet = {
                    "seed": seed,
                    "candidate_revisions": review_candidates,
                }
                reviews = []
                for review_index in range(2):
                    result, output = encounter(
                        client,
                        proxy,
                        f"novelty-review-{review_index + 1}",
                        rubric
                        + "\n\nBlinded controller packet:\n"
                        + json.dumps(review_packet, sort_keys=True, separators=(",", ":")),
                        "novelty-output",
                        reviewer_model,
                    )
                    if (
                        result["parse_error"]
                        or not isinstance(output, dict)
                        or set(output) != {"pass", "operation_summary", "seed_overlap"}
                        or type(output["pass"]) is not bool
                        or not isinstance(output["operation_summary"], str)
                        or not isinstance(output["seed_overlap"], str)
                    ):
                        raise RuntimeError("novelty review failed exact output validation")
                    reviews.append(output)

                inventories = client.model_visible_tool_inventories()
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

    inventory_bytes = canonical_json(inventories[0]) if inventories else b""
    worker = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": "completed",
        "worker_id": worker_id,
        "execution_git_commit": execution_commit,
        "task_manifest_sha256": sha256_bytes(task_bytes),
        "actor_results": actor_results,
        "stage_records": stage_records,
        "proposals": proposals,
        "policy_snapshots": [snapshot.__dict__ for snapshot in ledger.snapshots],
        "reviews": reviews,
        "direct_inventory": {
            "sha256": sha256_bytes(inventory_bytes) if inventories else None,
            "tool_count": len(inventories[0]) if inventories else 0,
            "receipt_count": len(inventories),
            "stable": bool(inventories) and all(item == inventories[0] for item in inventories),
        },
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


def behavioral_worker_summary(worker: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    scoring = acceptance["scoring"]
    stages = worker["stage_records"]
    comparisons = []
    for record in stages:
        changed = record["branches"]["changed-policy"]
        frozen = record["branches"]["frozen-predecessor"]
        comparisons.append(
            {
                "stage": record["stage"],
                "changed_errors": changed["errors"],
                "frozen_errors": frozen["errors"],
                "advantage": frozen["errors"] - changed["errors"],
                "selection_changed": changed["selected_event_ids"] != frozen["selected_event_ids"],
            }
        )
    chains = []
    for harm in comparisons[1:]:
        if harm["changed_errors"] - harm["frozen_errors"] < scoring["learned_policy_harm_over_protected_predecessor_required"]:
            continue
        useful_before = [
            item
            for item in comparisons[1 : harm["stage"]]
            if item["selection_changed"]
            and item["advantage"] >= scoring["changed_over_frozen_error_advantage_per_revision"]
        ]
        for correction in comparisons[harm["stage"] + 1 :]:
            if not (
                correction["selection_changed"]
                and correction["advantage"] >= scoring["correction_error_recovery_required"]
                and correction["changed_errors"] <= scoring["corrected_policy_errors_allowed"]
            ):
                continue
            canaries = [
                item
                for item in comparisons[correction["stage"] + 1 :]
                if item["selection_changed"]
                and item["advantage"] >= scoring["post_correction_canary_advantage_required"]
            ]
            if canaries:
                chains.append(
                    {
                        "harm_stage": harm["stage"],
                        "correction_stage": correction["stage"],
                        "canary_stage": canaries[0]["stage"],
                        "useful_before_harm": len(useful_before),
                    }
                )
    lineage_errors = sum(item["changed_errors"] for item in comparisons)
    fixed_conditions = [
        "fixed-most-recent",
        "fixed-first-seen-verbatim",
        "fixed-naive-nearest",
        "no-persistence",
    ]
    fixed_errors = {
        condition: sum(record["branches"][condition]["errors"] for record in stages)
        for condition in fixed_conditions
    }
    actor_results = worker["actor_results"]
    freshness = {
        "thread_ids": len({item["thread_id"] for item in actor_results}) == len(actor_results),
        "workspaces": len({item["workspace"] for item in actor_results}) == len(actor_results),
    }
    gates = {
        "turn_count": len(actor_results) == acceptance["resource_budget"]["actor_turns_total_per_worker"],
        "parse": sum(item.get("parse_error") is not None for item in actor_results) <= scoring["actor_parse_failures_allowed"],
        "tools": sum(item.get("tool_calls", 0) for item in actor_results) <= scoring["actor_tool_calls_allowed"],
        "freshness": all(freshness.values()),
        "policy_chain": len(worker["policy_snapshots"]) == acceptance["world"]["stages"] + 1,
        "temporal_corrigibility_chain": any(
            item["useful_before_harm"] >= scoring["useful_non_correction_revisions_required"]
            for item in chains
        ),
        "novelty_unanimity": len(worker["reviews"]) == 2 and all(item.get("pass") is True for item in worker["reviews"]),
        "lineage_absolute": lineage_errors <= scoring["changed_lineage_errors_allowed"],
        "lineage_comparative": all(
            errors - lineage_errors >= scoring["changed_lineage_advantage_over_each_fixed_control_required"]
            for errors in fixed_errors.values()
        ),
        "input_budget": worker["usage"]["input_tokens"] <= acceptance["resource_budget"]["actor_input_tokens_total_per_worker"],
        "output_budget": worker["usage"]["output_tokens"] <= acceptance["resource_budget"]["actor_output_tokens_total_per_worker"],
        "wall_budget": worker["elapsed_seconds"] <= acceptance["resource_budget"]["wall_seconds_per_worker"],
    }
    return {
        "worker_id": worker["worker_id"],
        "comparisons": comparisons,
        "corrigibility_chains": chains,
        "changed_lineage_errors": lineage_errors,
        "fixed_control_errors": fixed_errors,
        "freshness": freshness,
        "gates": gates,
        "behavioral_pass": all(gates.values()),
    }


def deployment_worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    results = worker["actor_results"]
    receipts = worker["deployment"]["receipts"]
    response_ids = [
        item["deployment_response_ids"][0]
        for item in results
        if item.get("deployment_response_ids")
    ]
    per_turn_valid = all(
        item.get("deployment_effective_models") == [item.get("model")]
        and len(item.get("deployment_response_ids", [])) == 1
        for item in results
    )
    effective_models = sorted(
        {item["value"] for item in receipts if item["kind"] == "effective_model"}
    )
    expected_models = sorted(
        {
            acceptance["deployment_epoch"]["actor_model"],
            acceptance["deployment_epoch"]["reviewer_model"],
        }
    )
    model_etags = sorted({item["value"] for item in receipts if item["kind"] == "models_etag"})
    epoch_fields = {
        "effective_models": effective_models,
        "catalog_payload_sha256": worker["deployment"]["catalog_payload_sha256"],
        "models_etag_sha256": sha256_bytes(canonical_json(model_etags)) if model_etags else None,
    }
    observed_order = [record["heldout_condition_order"] for record in worker["stage_records"]]
    expected_order = [
        phase["condition_order"][worker["worker_id"]] for phase in task_order["phases"]
    ]
    inventory = worker["direct_inventory"]
    gates = {
        "collector_integrity": worker["deployment"].get("collector_errors") == [],
        "effective_models": effective_models == expected_models,
        "catalog_payload": bool(re.fullmatch(r"[0-9a-f]{64}", worker["deployment"]["catalog_payload_sha256"])),
        "catalog_etag": len(model_etags) == 1,
        "per_turn_receipts": per_turn_valid,
        "distinct_response_ids": len(response_ids) == len(set(response_ids)) == acceptance["resource_budget"]["actor_turns_total_per_worker"],
        "counterbalanced_order": observed_order == expected_order,
        "direct_inventory": inventory.get("sha256") == acceptance["direct_inventory"]["sha256"]
        and inventory.get("tool_count") == acceptance["direct_inventory"]["tool_count"]
        and inventory.get("receipt_count") == len(results)
        and inventory.get("stable") is True,
    }
    return {
        "effective_models": effective_models,
        "catalog_payload_sha256": worker["deployment"]["catalog_payload_sha256"],
        "models_etag_sha256": epoch_fields["models_etag_sha256"],
        "response_receipts_sha256": sha256_bytes(
            canonical_json([sha256_bytes(value.encode()) for value in response_ids])
        ),
        "response_count": len(response_ids),
        "epoch_identity_sha256": sha256_bytes(canonical_json(epoch_fields)),
        "gates": gates,
        "valid": all(gates.values()),
    }


def worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    summary = behavioral_worker_summary(worker, acceptance)
    deployment = deployment_worker_summary(worker, acceptance, task_order)
    summary["deployment_epoch"] = deployment
    summary["scientific_pass"] = summary["behavioral_pass"] and deployment["valid"]
    return summary


def combined_summary(raw: dict[str, Any]) -> dict[str, Any]:
    acceptance = raw["acceptance"]
    workers = [
        worker_summary(worker, acceptance, raw["task_order"]) for worker in raw["workers"]
    ]
    validity = {
        "worker_deployment_receipts": len(workers) == 2
        and all(worker["deployment_epoch"]["valid"] for worker in workers),
        "same_deployment_epoch": len(workers) == 2
        and len({worker["deployment_epoch"]["epoch_identity_sha256"] for worker in workers}) == 1,
        "same_task_manifest": raw.get("same_task_manifest", False),
        "two_worker_window": raw["two_worker_window_seconds"]
        <= acceptance["deployment_epoch"]["maximum_two_worker_window_seconds"],
    }
    behavioral_reproduction = len(workers) == 2 and all(
        worker["behavioral_pass"] for worker in workers
    )
    promotion = {
        "clean_predating_implementation": raw.get("implementation_clean", False),
        "original_behavioral_gates": bool(workers and workers[0]["behavioral_pass"]),
        "clean_behavioral_reproduction": behavioral_reproduction,
        "deployment_epoch_validity": all(validity.values()),
        "audit_and_tests": raw.get("audit_and_tests", False),
    }
    if not all(validity.values()):
        disposition = "invalidated"
    elif not behavioral_reproduction:
        disposition = "rejected"
    elif all(promotion.values()):
        disposition = "promoted"
    else:
        disposition = "conditional"
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_epoch": acceptance["evaluation_epoch"],
        "run_id": raw["run_id"],
        "implementation_git_commit": raw["implementation_git_commit"],
        "task_manifest_sha256": raw["task_manifest_sha256"],
        "two_worker_window_seconds": raw["two_worker_window_seconds"],
        "workers": workers,
        "validity_gates": validity,
        "promotion_gates": promotion,
        "disposition": disposition,
        "evidence_horizon": "private, time-bounded, single generated family OT-1 evidence only",
    }


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
                    "open_trajectory_harness.ot0004",
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
    for index, process in enumerate(processes, start=1):
        stdout, stderr = process.communicate()
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
        kind="emergent-corrigible-selector-hosted-epoch-run",
        evidence_class="private-reproducible",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0004 "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The task, policies, selections, actor events, reviews, catalog ETag, and Response IDs remain private.",
            "The result is limited to one generated family and a time-bounded hosted deployment epoch.",
        ],
        input_manifests=[],
    )
    return manifest_path, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0004-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0004-hosted-epoch-001")
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
    except (AppServerError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
