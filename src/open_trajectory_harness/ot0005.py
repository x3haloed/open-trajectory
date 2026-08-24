from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
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
from .ot0005_world import (
    EXPERIMENT_ID,
    ProgramLedger,
    archive_through_stage,
    deterministic_predictions,
    deterministic_selection,
    fixed_selection,
    generate_task_manifest,
    protected_consequence_receipt,
    score_predictions,
    selected_events,
    validate_task_manifest,
)


FIXTURE_ROOT = Path("fixtures/ot-0005")
ACCEPTANCE_PATH = Path("spec/ot-0005-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0005-run-lock.json")
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
        raise RuntimeError("OT-0005 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def validate_counterbalance(task_order: dict[str, Any], expected_count: int) -> None:
    conditions = task_order.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 6 or len(set(conditions)) != 6:
        raise ValueError("OT-0005 requires six distinct conditions")
    counts = {condition: Counter() for condition in conditions}
    for phase in task_order.get("phases", []):
        orders = phase.get("condition_order") if isinstance(phase, dict) else None
        if not isinstance(orders, dict) or set(orders) != {"worker-1", "worker-2"}:
            raise ValueError("each stage requires two worker orders")
        for order in orders.values():
            if not isinstance(order, list) or len(order) != 6 or set(order) != set(conditions):
                raise ValueError("condition order is not an exact permutation")
            for position, condition in enumerate(order):
                counts[condition][position] += 1
    expected = Counter({position: expected_count for position in range(6)})
    if any(value != expected for value in counts.values()):
        raise ValueError("condition positions are not exactly counterbalanced")


def fixed_input_paths() -> dict[str, Path]:
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "deployment_proxy_sha256": PROXY_PATH,
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "world_sha256": Path("src/open_trajectory_harness/ot0005_world.py"),
        "harness_sha256": Path("src/open_trajectory_harness/ot0005.py"),
    }
    for name in (
        "selector-seed.txt",
        "selector-update-prompt.txt",
        "selector-update-output.schema.json",
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
        raise RuntimeError("frozen input identity differs from the OT-0005 run lock")
    protected = [
        "src/open_trajectory_harness/app_server.py",
        "src/open_trajectory_harness/deployment_proxy.py",
        "src/open_trajectory_harness/ot0002.py",
        "src/open_trajectory_harness/ot0003.py",
        "src/open_trajectory_harness/ot0005.py",
        "src/open_trajectory_harness/ot0005_world.py",
        "experiments/ot_0005_harness.py",
        "fixtures/ot-0005",
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
            "serviceName": "open_trajectory_ot0005",
        }
    )
    receipt_start = len(proxy.collector.snapshot())
    inventory_start = len(client.model_visible_tool_inventories())
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
    receipts = proxy.collector.snapshot()[receipt_start:]
    return (
        {
            "role": role,
            "model": model,
            "workspace": str(workspace.resolve()),
            "thread_id": thread["id"],
            "thread_session_id": thread.get("sessionId"),
            "parse_error": parse_error,
            "tool_calls": client.completed_turn_tool_calls(
                thread_id=thread["id"], turn_id=turn["id"]
            ),
            "inventory_receipts": len(client.model_visible_tool_inventories())
            - inventory_start,
            "deployment_receipts": receipts,
            "deployment_effective_models": sorted(
                {item["value"] for item in receipts if item["kind"] == "effective_model"}
            ),
            "deployment_response_ids": sorted(
                {item["value"] for item in receipts if item["kind"] == "response_id"}
            ),
            "turn": turn,
        },
        output,
    )


def deterministic_branch(
    *,
    condition: str,
    expression: str | None,
    expression_sha256: str | None,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
    allow_empty: bool = False,
) -> dict[str, Any]:
    if expression is None:
        selected_ids = fixed_selection(condition, archive, queries, limit)
    else:
        selected_ids = deterministic_selection(
            expression, archive, queries, limit, allow_empty=allow_empty
        )
    selected = selected_events(archive, selected_ids)
    predictions = deterministic_predictions(selected, queries)
    replay = deterministic_predictions(selected_events(archive, list(selected_ids)), queries)
    if predictions != replay:
        raise RuntimeError("deterministic predictor replay changed")
    errors, parse_error = score_predictions(predictions, outcomes)
    if parse_error:
        raise RuntimeError("deterministic predictor produced invalid output")
    return {
        "condition": condition,
        "expression_sha256": expression_sha256,
        "selected_event_ids": selected_ids,
        "selected_event_ids_sha256": sha256_bytes(canonical_json(selected_ids)),
        "predictions": predictions,
        "predictions_sha256": sha256_bytes(canonical_json(predictions)),
        "errors": errors,
        "deterministic_replay": True,
    }


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
    seed_orientation = (repo / FIXTURE_ROOT / "selector-seed.txt").read_text(
        encoding="utf-8"
    )
    update_template = (repo / FIXTURE_ROOT / "selector-update-prompt.txt").read_text(
        encoding="utf-8"
    )
    update_schema = load_json(repo / FIXTURE_ROOT / "selector-update-output.schema.json")
    rubric = (repo / FIXTURE_ROOT / "novelty-rubric.txt").read_text(encoding="utf-8")
    novelty_schema = load_json(repo / FIXTURE_ROOT / "novelty-output.schema.json")
    actor_model = acceptance["deployment_epoch"]["actor_model"]
    reviewer_model = acceptance["deployment_epoch"]["reviewer_model"]
    limit = acceptance["candidate"]["selected_events_per_prediction"]
    ledger = ProgramLedger(
        acceptance["candidate"]["seed_expression"],
        acceptance["candidate"]["expression_bytes"],
    )
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
        schema: dict[str, Any],
        model: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        result, output = run_actor_turn(
            client=active_client,
            proxy=active_proxy,
            model=model,
            workspace=workspace_root / f"encounter-{len(actor_results):02d}-{role}",
            role=role,
            prompt=prompt,
            output_schema=schema,
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
                    raise RuntimeError("one or more frozen OT-0005 models are unavailable")
                catalog_payload_sha256 = sha256_bytes(canonical_json(models))
                for stage_index, phase in enumerate(task_order["phases"]):
                    stage = manifest["stages"][stage_index]
                    archive = archive_through_stage(manifest, stage_index)
                    current = ledger.current
                    parent = ledger.snapshots[-2] if len(ledger.snapshots) > 1 else current
                    current_allow_empty = current.revision == 0
                    parent_allow_empty = parent.revision == 0
                    contact = deterministic_branch(
                        condition="current-contact",
                        expression=current.expression,
                        expression_sha256=current.sha256,
                        archive=archive,
                        queries=stage["contact"]["queries"],
                        outcomes=stage["contact"]["outcomes"],
                        limit=limit,
                        allow_empty=current_allow_empty,
                    )
                    receipt = protected_consequence_receipt(
                        stage_index=stage_index,
                        policy_sha256=current.sha256,
                        archive=archive,
                        selected_ids=contact["selected_event_ids"],
                        queries=stage["contact"]["queries"],
                        predictions=contact["predictions"],
                        outcomes=stage["contact"]["outcomes"],
                    )
                    branches: dict[str, dict[str, Any]] = {}
                    for condition in phase["condition_order"][worker_id]:
                        if condition == "changed-program":
                            branch = deterministic_branch(
                                condition=condition,
                                expression=current.expression,
                                expression_sha256=current.sha256,
                                archive=archive,
                                queries=stage["heldout"]["queries"],
                                outcomes=stage["heldout"]["outcomes"],
                                limit=limit,
                                allow_empty=current_allow_empty,
                            )
                        elif condition == "frozen-parent":
                            branch = deterministic_branch(
                                condition=condition,
                                expression=parent.expression,
                                expression_sha256=parent.sha256,
                                archive=archive,
                                queries=stage["heldout"]["queries"],
                                outcomes=stage["heldout"]["outcomes"],
                                limit=limit,
                                allow_empty=parent_allow_empty,
                            )
                        else:
                            branch = deterministic_branch(
                                condition=condition,
                                expression=None,
                                expression_sha256=None,
                                archive=archive,
                                queries=stage["heldout"]["queries"],
                                outcomes=stage["heldout"]["outcomes"],
                                limit=limit,
                            )
                        branches[condition] = branch
                    update_prompt = (
                        seed_orientation
                        + "\n\n"
                        + update_template.replace("{{EXPRESSION}}", current.expression).replace(
                            "{{RECEIPT}}",
                            json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                        )
                    )
                    update_result, proposal = encounter(
                        client,
                        proxy,
                        f"stage-{stage_index}-selector-update",
                        update_prompt,
                        update_schema,
                        actor_model,
                    )
                    if (
                        update_result["parse_error"]
                        or not isinstance(proposal, dict)
                        or set(proposal)
                        != {"expression", "expected_effect", "cheapest_falsifier"}
                    ):
                        raise RuntimeError("selector update failed exact output validation")
                    deterministic_selection(
                        proposal["expression"],
                        archive,
                        stage["contact"]["queries"],
                        limit,
                    )
                    next_program = ledger.commit(proposal)
                    proposals.append(
                        {
                            "source_stage": stage_index,
                            "proposal": proposal,
                            "committed_program": next_program.public_identity(),
                            "actor_result_index": len(actor_results) - 1,
                        }
                    )
                    stage_records.append(
                        {
                            "stage": stage_index,
                            "current_program": current.public_identity(),
                            "parent_program": parent.public_identity(),
                            "contact": contact,
                            "contact_receipt": receipt,
                            "heldout_condition_order": phase["condition_order"][worker_id],
                            "branches": branches,
                            "next_program": next_program.public_identity(),
                        }
                    )

                review_candidates = []
                threshold = acceptance["scoring"][
                    "changed_over_parent_error_advantage_per_revision"
                ]
                for record in stage_records[1:]:
                    changed = record["branches"]["changed-program"]
                    parent = record["branches"]["frozen-parent"]
                    if (
                        changed["selected_event_ids"] != parent["selected_event_ids"]
                        and parent["errors"] - changed["errors"] >= threshold
                    ):
                        review_candidates.append(
                            {
                                "stage": record["stage"],
                                "proposal": proposals[record["stage"] - 1]["proposal"],
                                "changed_selected_event_ids": changed["selected_event_ids"],
                                "parent_selected_event_ids": parent["selected_event_ids"],
                                "changed_errors": changed["errors"],
                                "parent_errors": parent["errors"],
                            }
                        )
                review_packet = {
                    "seed_expression": acceptance["candidate"]["seed_expression"],
                    "carrier_contract": seed_orientation,
                    "candidate_revisions": review_candidates,
                }
                reviews = []
                for index in range(2):
                    result, output = encounter(
                        client,
                        proxy,
                        f"novelty-review-{index + 1}",
                        rubric
                        + "\n\nBlinded controller packet:\n"
                        + json.dumps(review_packet, sort_keys=True, separators=(",", ":")),
                        novelty_schema,
                        reviewer_model,
                    )
                    if (
                        result["parse_error"]
                        or not isinstance(output, dict)
                        or set(output) != {"pass", "operation_summary", "seed_overlap"}
                        or type(output["pass"]) is not bool
                    ):
                        raise RuntimeError("novelty review failed exact output validation")
                    reviews.append(output)

                inventories = client.model_visible_tool_inventories()
                if len(inventories) != len(actor_results):
                    raise RuntimeError("direct inventory receipt count differs from actor turns")
                inventory_by_model: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
                for result, inventory in zip(actor_results, inventories):
                    inventory_by_model[result["model"]].append(inventory)
                direct_inventory_by_model = {}
                for model, values in inventory_by_model.items():
                    first = values[0]
                    direct_inventory_by_model[model] = {
                        "sha256": sha256_bytes(canonical_json(first)),
                        "tool_count": len(first),
                        "receipt_count": len(values),
                        "stable": all(value == first for value in values),
                    }
                deployment_receipts = proxy.collector.snapshot()
                deployment_errors = proxy.collector.errors()
                deployment_diagnostics = proxy.collector.diagnostics()
                events = client.raw_events
                stderr = client.stderr_lines
                usage = token_usage(events)
                catalog_payload = models
    except Exception as error:
        write_sealed_json(
            output_path,
            {
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
            },
        )
        raise

    write_sealed_json(
        output_path,
        {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "worker_id": worker_id,
            "execution_git_commit": execution_commit,
            "task_manifest_sha256": sha256_bytes(task_bytes),
            "actor_results": actor_results,
            "stage_records": stage_records,
            "proposals": proposals,
            "program_snapshots": [snapshot.__dict__ for snapshot in ledger.snapshots],
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
        },
    )


def behavioral_worker_summary(worker: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    scoring = acceptance["scoring"]
    comparisons = []
    for record in worker["stage_records"]:
        changed = record["branches"]["changed-program"]
        parent = record["branches"]["frozen-parent"]
        comparisons.append(
            {
                "stage": record["stage"],
                "changed_errors": changed["errors"],
                "parent_errors": parent["errors"],
                "advantage": parent["errors"] - changed["errors"],
                "selection_changed": changed["selected_event_ids"]
                != parent["selected_event_ids"],
            }
        )
    chains = []
    for harm in comparisons[1:]:
        harm_delta = harm["changed_errors"] - harm["parent_errors"]
        if harm_delta < scoring["learned_program_harm_over_protected_parent_required"]:
            continue
        useful = [
            item
            for item in comparisons[1 : harm["stage"]]
            if item["selection_changed"]
            and item["advantage"]
            >= scoring["changed_over_parent_error_advantage_per_revision"]
        ]
        for correction in comparisons[harm["stage"] + 1 :]:
            if not (
                correction["selection_changed"]
                and correction["advantage"] >= scoring["correction_error_recovery_required"]
                and correction["changed_errors"] <= scoring["corrected_program_errors_allowed"]
            ):
                continue
            canaries = [
                item
                for item in comparisons[correction["stage"] + 1 :]
                if item["selection_changed"]
                and item["advantage"]
                >= scoring["post_correction_canary_advantage_required"]
            ]
            if canaries:
                chains.append(
                    {
                        "harm_stage": harm["stage"],
                        "correction_stage": correction["stage"],
                        "canary_stage": canaries[0]["stage"],
                        "useful_before_harm": len(useful),
                    }
                )
    first = worker["stage_records"][0]["branches"]
    placebo = {
        "selection": first["changed-program"]["selected_event_ids"]
        == first["frozen-parent"]["selected_event_ids"],
        "prediction": first["changed-program"]["predictions"]
        == first["frozen-parent"]["predictions"],
        "score": first["changed-program"]["errors"] == first["frozen-parent"]["errors"],
    }
    lineage_errors = sum(item["changed_errors"] for item in comparisons)
    fixed_conditions = [
        "fixed-most-recent",
        "fixed-first-seen-verbatim",
        "fixed-naive-nearest",
        "no-persistence",
    ]
    fixed_errors = {
        condition: sum(
            record["branches"][condition]["errors"] for record in worker["stage_records"]
        )
        for condition in fixed_conditions
    }
    results = worker["actor_results"]
    freshness = {
        "threads": len({item["thread_id"] for item in results}) == len(results),
        "workspaces": len({item["workspace"] for item in results}) == len(results),
    }
    gates = {
        "turn_count": len(results)
        == acceptance["resource_budget"]["actor_turns_total_per_worker"],
        "parse": sum(item.get("parse_error") is not None for item in results)
        <= scoring["actor_parse_failures_allowed"],
        "tools": sum(item.get("tool_calls", 0) for item in results)
        <= scoring["actor_tool_calls_allowed"],
        "freshness": all(freshness.values()),
        "program_chain": len(worker["program_snapshots"])
        == acceptance["world"]["stages"] + 1,
        "deterministic_replay": all(
            branch["deterministic_replay"]
            for record in worker["stage_records"]
            for branch in [record["contact"], *record["branches"].values()]
        ),
        "identity_placebo": all(placebo.values()),
        "temporal_corrigibility_chain": any(
            chain["useful_before_harm"]
            >= scoring["useful_non_correction_revisions_required"]
            for chain in chains
        ),
        "novelty_unanimity": len(worker["reviews"]) == 2
        and all(review.get("pass") is True for review in worker["reviews"]),
        "lineage_absolute": lineage_errors <= scoring["changed_lineage_errors_allowed"],
        "lineage_comparative": all(
            errors - lineage_errors
            >= scoring["changed_lineage_advantage_over_each_fixed_control_required"]
            for errors in fixed_errors.values()
        ),
        "input_budget": worker["usage"]["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total_per_worker"],
        "output_budget": worker["usage"]["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total_per_worker"],
        "wall_budget": worker["elapsed_seconds"]
        <= acceptance["resource_budget"]["wall_seconds_per_worker"],
    }
    return {
        "worker_id": worker["worker_id"],
        "comparisons": comparisons,
        "corrigibility_chains": chains,
        "identity_placebo": placebo,
        "changed_lineage_errors": lineage_errors,
        "fixed_control_errors": fixed_errors,
        "gates": gates,
        "behavioral_pass": all(gates.values()),
    }


def deployment_worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    results = worker["actor_results"]
    deployment = worker["deployment"]
    response_ids = [
        item["deployment_response_ids"][0]
        for item in results
        if item.get("deployment_response_ids")
    ]
    per_turn = all(
        item.get("deployment_effective_models") == [item.get("model")]
        and len(item.get("deployment_response_ids", [])) == 1
        for item in results
    )
    receipts = deployment["receipts"]
    effective_models = sorted(
        {item["value"] for item in receipts if item["kind"] == "effective_model"}
    )
    expected_models = sorted(acceptance["direct_inventory_by_model"])
    etags = sorted({item["value"] for item in receipts if item["kind"] == "models_etag"})
    observed_inventories = worker["direct_inventory_by_model"]
    expected_inventories = acceptance["direct_inventory_by_model"]
    inventory_valid = set(observed_inventories) == set(expected_inventories)
    if inventory_valid:
        for model, expected in expected_inventories.items():
            observed = observed_inventories[model]
            inventory_valid = inventory_valid and (
                observed["sha256"] == expected["sha256"]
                and observed["tool_count"] == expected["tool_count"]
                and observed["stable"] is True
            )
    epoch_fields = {
        "effective_models": effective_models,
        "catalog_payload_sha256": deployment["catalog_payload_sha256"],
        "models_etag_sha256": sha256_bytes(canonical_json(etags)) if etags else None,
    }
    gates = {
        "collector_integrity": deployment.get("collector_errors") == [],
        "effective_models": effective_models == expected_models,
        "catalog_payload": bool(
            re.fullmatch(r"[0-9a-f]{64}", deployment["catalog_payload_sha256"])
        ),
        "catalog_etag": len(etags) == 1,
        "per_turn_receipts": per_turn,
        "distinct_response_ids": len(response_ids)
        == len(set(response_ids))
        == acceptance["resource_budget"]["actor_turns_total_per_worker"],
        "counterbalanced_order": [
            record["heldout_condition_order"] for record in worker["stage_records"]
        ]
        == [phase["condition_order"][worker["worker_id"]] for phase in task_order["phases"]],
        "direct_inventory_by_model": inventory_valid,
    }
    return {
        **epoch_fields,
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
    workers = [
        worker_summary(worker, raw["acceptance"], raw["task_order"])
        for worker in raw["workers"]
    ]
    validity = {
        "worker_deployment_receipts": len(workers) == 2
        and all(worker["deployment_epoch"]["valid"] for worker in workers),
        "same_deployment_epoch": len(workers) == 2
        and len({worker["deployment_epoch"]["epoch_identity_sha256"] for worker in workers})
        == 1,
        "same_task_manifest": raw.get("same_task_manifest", False),
        "two_worker_window": raw["two_worker_window_seconds"]
        <= raw["acceptance"]["deployment_epoch"]["maximum_two_worker_window_seconds"],
    }
    reproduction = len(workers) == 2 and all(worker["behavioral_pass"] for worker in workers)
    promotion = {
        "clean_predating_implementation": raw.get("implementation_clean", False),
        "original_behavioral_gates": bool(workers and workers[0]["behavioral_pass"]),
        "clean_behavioral_reproduction": reproduction,
        "deployment_epoch_validity": all(validity.values()),
        "audit_and_tests": raw.get("audit_and_tests", False),
    }
    if not all(validity.values()):
        disposition = "invalidated"
    elif not reproduction:
        disposition = "rejected"
    elif all(promotion.values()):
        disposition = "promoted"
    else:
        disposition = "conditional"
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_epoch": raw["acceptance"]["evaluation_epoch"],
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
                    "open_trajectory_harness.ot0005",
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
    receipts = []
    for index, process in enumerate(processes, start=1):
        stdout, stderr = process.communicate()
        receipts.append(
            {
                "worker_id": f"worker-{index}",
                "returncode": process.returncode,
                "stdout_sha256": sha256_bytes(stdout.encode()),
                "stderr_sha256": sha256_bytes(stderr.encode()),
                "stderr_lines": len(stderr.splitlines()),
            }
        )
    window = time.monotonic() - started
    if any(receipt["returncode"] != 0 for receipt in receipts):
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
        "worker_receipts": receipts,
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
        kind="deterministic-executable-selector-hosted-epoch-run",
        evidence_class="private-reproducible",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0005 "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The task, expressions, selections, actor events, reviews, ETag, and Response IDs remain private.",
            "The result is limited to one generated family and a time-bounded hosted epoch.",
        ],
        input_manifests=[],
    )
    return manifest_path, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0005-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0005-hosted-epoch-001")
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
