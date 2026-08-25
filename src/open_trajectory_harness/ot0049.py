from __future__ import annotations

import argparse
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
    final_agent_json,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import read_sealed_json, write_sealed_json
from .ot0014 import instrumented_command
from .ot0040 import unsupported_keywords
from .ot0048 import (
    WITNESS_TERMS,
    constant_selections,
    neutralize_receipt,
    promoted_weight_family,
    score,
    structural_certificate,
    verbatim_raw_selections,
    verbatim_raw_update,
    weighted_selections,
)
from .ot0049_world import (
    EXPERIMENT_ID,
    build_task,
    commit_proposal,
    completed_contact_for_snapshot,
    counterbalanced_split,
    expected_task_seed,
    initial_snapshot,
    project_snapshot,
    public_actor_view,
    restore_snapshot,
    score_snapshot,
    source_absent_before_contact,
    validate_actor_output,
    validate_counterbalance_config,
    validate_task,
)


ACCEPTANCE_PATH = Path("spec/ot-0049-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0049-run-lock.json")
ORIENTATION_PATH = Path("fixtures/ot-0049/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0049/candidate-output.schema.json")
COUNTERBALANCE_PATH = Path("fixtures/ot-0049/counterbalance.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
OT1_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0037/ot-0037-e6-deterministic-ot1-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0049-e12-representation-escape-candidate-001"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "counterbalance_sha256": COUNTERBALANCE_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0049.py"),
        "candidate_world_sha256": Path("src/open_trajectory_harness/ot0049_world.py"),
        "calibration_core_sha256": Path("src/open_trajectory_harness/ot0048.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path(
            "src/open_trajectory_harness/deployment_proxy.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0049_harness.py"),
        "test_sha256": Path("tests/test_ot0049.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "tool_receipt_patch_sha256": PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
        "ot1_manifest_sha256": OT1_MANIFEST_PATH,
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


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0049 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0049 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0049 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0049 fixed input identity differs")
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
        raise RuntimeError(f"OT-0049 implementation changed after freezing: {changed}")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("OT-0049 pinned backend pair is absent")
    if (
        sha256_file(codex_bin) != binary.get("codex_sha256")
        or sha256_file(sidecar) != binary.get("code_mode_host_sha256")
        or app_server_version(str(codex_bin)) != binary.get("version")
    ):
        raise RuntimeError("OT-0049 backend identity differs")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("OT-0049 TLS authority differs")
    return lock


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    witness_hits = sorted(term for term in WITNESS_TERMS if term in orientation.lower())
    menu_hits = sorted(
        term
        for term in ("choose one", "option 1", "option 2", "strategy a", "strategy b")
        if term in orientation.lower()
    )
    body = {
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "witness_hits": witness_hits,
        "menu_hits": menu_hits,
        "schema_fields": sorted(schema.get("properties", {})),
    }
    return {
        **body,
        "pass": not witness_hits
        and not menu_hits
        and body["schema_fields"] == ["state"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def _turn_usage(events: list[dict[str, Any]], thread_id: str) -> dict[str, int]:
    latest: dict[str, int] = {}
    receipt_count = 0
    for event in events:
        message = event.get("message")
        if (
            not isinstance(message, dict)
            or message.get("method") != "thread/tokenUsage/updated"
        ):
            continue
        params = message.get("params", {})
        if params.get("threadId") == thread_id and isinstance(
            params.get("tokenUsage", {}).get("total"), dict
        ):
            latest = params["tokenUsage"]["total"]
            receipt_count += 1
    return {
        "input_tokens": latest.get("inputTokens", 0),
        "output_tokens": latest.get("outputTokens", 0),
        "total_tokens": latest.get("totalTokens", 0),
        "receipt_count": receipt_count,
    }


def run_actor_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    orientation: str,
    schema: dict[str, Any],
    actor_view: dict[str, Any],
    worker: str,
    regime_index: int,
    hidden_markers: list[str],
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Construct one bounded replacement selection state and return only schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0049",
        }
    )
    prompt = orientation.replace("{{ACTOR_VIEW}}", canonical_json(actor_view).decode())
    deployment_before = len(proxy.collector.snapshot())
    inventory_before = len(client.model_visible_tool_inventories())
    event_before = len(client.raw_events)
    turn = client.run_turn(
        thread_id=thread["id"],
        input_text=prompt,
        output_schema=schema,
        sandbox_policy={"type": "readOnly", "networkAccess": False},
        timeout=180,
    )
    turn_events = client.raw_events[event_before:]
    deployment = proxy.collector.snapshot()[deployment_before:]
    inventories = client.model_visible_tool_inventories()
    inventory = inventories[-1] if len(inventories) > inventory_before else []
    output, parse_error = final_agent_json(turn)
    if turn.get("status") != "completed":
        parse_error = parse_error or "actor turn did not complete"
    try:
        validate_actor_output(output)
    except ValueError as error:
        parse_error = parse_error or str(error)
        output = None
    response_ids = sorted(
        {item["value"] for item in deployment if item["kind"] == "response_id"}
    )
    models = sorted(
        {item["value"] for item in deployment if item["kind"] == "effective_model"}
    )
    return (
        {
            "worker": worker,
            "regime_index": regime_index,
            "workspace": str(workspace.resolve()),
            "thread_id": thread["id"],
            "thread_session_id": thread.get("sessionId"),
            "actor_view": actor_view,
            "actor_output": output,
            "parse_error": parse_error,
            "turn_status": turn.get("status"),
            "tool_calls": client.completed_turn_tool_calls(
                thread_id=thread["id"], turn_id=turn["id"]
            ),
            "inventory_receipts": len(inventories) - inventory_before,
            "deployment_receipts": deployment,
            "deployment_effective_models": models,
            "deployment_response_ids": response_ids,
            "hidden_task_leakage": [
                marker for marker in hidden_markers if marker in prompt
            ],
            "usage": _turn_usage(turn_events, thread["id"]),
            "turn": turn,
        },
        output,
        inventory,
    )


def _fixed_control_receipt(task: dict[str, Any]) -> dict[str, Any]:
    splits = [regime["canary"] for regime in task["regimes"]]
    lineages: dict[str, list[int]] = {
        "fixed-canonical": [
            score(split, constant_selections(split, 1)) for split in splits
        ],
        "fixed-anticanonical": [
            score(split, constant_selections(split, -1)) for split in splits
        ],
        "fixed-zero": [
            score(split, weighted_selections((0, 0, 0, 0), split)) for split in splits
        ],
    }
    weights = [
        *(
            (0,) * index + (sign,) + (0,) * (3 - index)
            for index in range(4)
            for sign in (-1, 1)
        ),
        *promoted_weight_family(),
    ]
    aggregates = [
        sum(score(split, weighted_selections(weight, split)) for split in splits)
        for weight in weights
    ]
    body = {
        "lineages": lineages,
        "weighted_lineage_count": len(weights),
        "best_weighted_aggregate_errors": min(aggregates),
        "active_choices_per_regime": 8,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def execute_worker(
    *,
    repo: Path,
    task: dict[str, Any],
    worker: str,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace_root: Path,
    orientation: str,
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[list[dict[str, Any]]]]:
    current = initial_snapshot()
    initial = current
    results: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    snapshots = {current.sha256: current}
    prior_canary: dict[str, Any] | None = None
    first_learned = None
    frozen_first_errors: list[int] = []
    novelty_paths = list(fixed_input_paths().values())
    for offset, regime in enumerate(task["regimes"]):
        regime_index = offset + 1
        contact = counterbalanced_split(regime["contact"], worker)
        canary = counterbalanced_split(regime["canary"], worker)
        choices, receipt = completed_contact_for_snapshot(current, contact)
        view = public_actor_view(contact, current, choices, receipt)
        hidden = [
            *[pair["preferred_event_id"] for pair in canary["pairs"]],
            '"preferred_event_id"',
            '"relation"',
            '"polarity"',
        ]
        actor_result, output, inventory = run_actor_turn(
            client=client,
            proxy=proxy,
            model=model,
            workspace=workspace_root / worker / f"regime-{regime_index}",
            orientation=orientation,
            schema=schema,
            actor_view=view,
            worker=worker,
            regime_index=regime_index,
            hidden_markers=hidden,
        )
        inventories.append(inventory)
        before = current
        if output is None:
            after = before
            commit_error = actor_result["parse_error"] or "invalid actor output"
        else:
            try:
                after = commit_proposal(before, receipt, output)
                commit_error = None
            except ValueError as error:
                after = before
                commit_error = str(error)
        snapshots[after.sha256] = after
        pre_error = score_snapshot(before, canary)
        candidate_error = score_snapshot(after, canary)
        no_credit = (
            commit_proposal(before, neutralize_receipt(receipt), output)
            if output is not None
            else before
        )
        replay_one = canonical_json(completed_contact_for_snapshot(after, canary)[0])
        replay_two = canonical_json(
            completed_contact_for_snapshot(
                restore_snapshot(project_snapshot(after)), canary
            )[0]
        )
        projection_error = min(
            score(canary, weighted_selections(weights, canary))
            for weights in promoted_weight_family()
        )
        raw_entries = verbatim_raw_update(contact, receipt)
        verbatim_error = score(canary, verbatim_raw_selections(raw_entries, canary))
        restored_parent = (
            restore_snapshot(project_snapshot(snapshots[after.parent_sha256]))
            if after.parent_sha256
            else before
        )
        rollback_split = prior_canary if prior_canary is not None else contact
        rollback_error = score_snapshot(restored_parent, rollback_split)
        expected_rollback_error = score_snapshot(before, rollback_split)
        novelty = (
            source_absent_before_contact(repo, output["state"], novelty_paths)
            if output is not None
            else {"pass": False}
        )
        certificate = structural_certificate(
            tuple(regime["relation"]), regime["polarity"], regime["canary_scale"]
        )
        if first_learned is None and after.sha256 != before.sha256:
            first_learned = after
        frozen_first_errors.append(score_snapshot(first_learned or initial, canary))
        actor_result.update(
            {
                "contact_choices": choices,
                "contact_receipt": receipt,
                "parent_projection": project_snapshot(before),
                "committed_projection": project_snapshot(after),
                "commit_error": commit_error,
                "pre_update_errors": pre_error,
                "candidate_errors": candidate_error,
                "no_persistence_errors": score_snapshot(initial, canary),
                "verbatim_errors": verbatim_error,
                "old_carrier_projection_errors": projection_error,
                "structural_delta_deletion_errors": pre_error,
                "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
                "controller_replay_byte_identical": replay_one == replay_two,
                "restored_successor_exact": restore_snapshot(
                    project_snapshot(after)
                ).sha256
                == after.sha256,
                "restored_parent_exact": restored_parent.sha256 == before.sha256,
                "rollback_error": rollback_error,
                "expected_rollback_error": expected_rollback_error,
                "novelty": novelty,
                "old_carrier_impossibility": certificate,
            }
        )
        results.append(actor_result)
        current = after
        prior_canary = canary
    mechanism_body = {
        "worker": worker,
        "candidate_errors": [item["candidate_errors"] for item in results],
        "pre_update_errors": [item["pre_update_errors"] for item in results],
        "no_persistence_errors": [item["no_persistence_errors"] for item in results],
        "verbatim_errors": [item["verbatim_errors"] for item in results],
        "old_carrier_projection_errors": [
            item["old_carrier_projection_errors"] for item in results
        ],
        "frozen_first_errors": frozen_first_errors,
        "snapshot_sha256s": [
            item["committed_projection"]["sha256"] for item in results
        ],
        "syntax_sha256s": [
            item["committed_projection"]["state"].get("syntax_sha256")
            for item in results
        ],
    }
    mechanism = {
        **mechanism_body,
        "receipt_sha256": sha256_bytes(canonical_json(mechanism_body)),
    }
    return results, mechanism, inventories


def summarize(
    *,
    repo: Path,
    acceptance: dict[str, Any],
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
    schema: dict[str, Any],
) -> dict[str, Any]:
    expected_turns = acceptance["resource_budget"]["actor_turns"]
    response_ids = [item["deployment_response_ids"] for item in actor_results]
    distinct_responses = {value for values in response_ids for value in values}
    proxy_response_ids = {
        item["value"] for item in proxy_receipts if item["kind"] == "response_id"
    }
    models = sorted(
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
    fixed_controls = _fixed_control_receipt(task)
    surface = actor_surface_authority(repo)
    worker_passes = {
        mechanism["worker"]: (
            mechanism["candidate_errors"] == [0, 0, 0]
            and mechanism["pre_update_errors"][0] >= 1
            and mechanism["pre_update_errors"][1] == 8
            and mechanism["pre_update_errors"][2] >= 4
            and all(value >= 1 for value in mechanism["no_persistence_errors"])
            and all(value >= 1 for value in mechanism["verbatim_errors"])
            and all(value >= 1 for value in mechanism["old_carrier_projection_errors"])
            and mechanism["frozen_first_errors"][1] == 8
            and mechanism["frozen_first_errors"][2] >= 4
            and len(set(mechanism["syntax_sha256s"])) == 3
        )
        for mechanism in mechanisms
    }
    gates = {
        "complete": len(actor_results) == expected_turns and len(mechanisms) == 2,
        "candidate_endpoint": len(worker_passes) == 2 and all(worker_passes.values()),
        "consequence_causation": all(
            item["no_credit_preserved_parent"] for item in actor_results
        ),
        "structural_delta": all(
            item["structural_delta_deletion_errors"] >= 1 for item in actor_results
        ),
        "old_carrier_impossibility": all(
            item["old_carrier_impossibility"]["pass"] for item in actor_results
        ),
        "fixed_controls": fixed_controls["best_weighted_aggregate_errors"] >= 1
        and all(sum(errors) >= 1 for errors in fixed_controls["lineages"].values()),
        "novelty": surface["pass"]
        and all(item["novelty"]["pass"] for item in actor_results),
        "correction": all(
            mechanism["pre_update_errors"][1] == 8
            and mechanism["candidate_errors"][1] == 0
            and mechanism["pre_update_errors"][2] >= 4
            and mechanism["candidate_errors"][2] == 0
            for mechanism in mechanisms
        ),
        "rollback": all(
            item["restored_successor_exact"]
            and item["restored_parent_exact"]
            and item["rollback_error"] == item["expected_rollback_error"]
            for item in actor_results
        ),
        "controller_replay": all(
            item["controller_replay_byte_identical"] for item in actor_results
        ),
        "projection_budget": all(
            len(canonical_json(item["committed_projection"])) <= 512
            for item in actor_results
        ),
        "equal_active_budget": fixed_controls["active_choices_per_regime"] == 8
        and all(
            len(item["actor_view"]["encounter"]["pairs"]) == 8
            and len(item["contact_choices"]) == 8
            and len(item["contact_receipt"]["items"]) == 8
            for item in actor_results
        ),
        "hidden_authority": all(
            not item["hidden_task_leakage"] for item in actor_results
        ),
        "schema_subset": unsupported_keywords(schema) == set(),
        "parse": all(
            item["parse_error"] is None and item["commit_error"] is None
            for item in actor_results
        ),
        "tools": all(item["tool_calls"] == 0 for item in actor_results),
        "fresh_threads": len({item["thread_id"] for item in actor_results})
        == expected_turns,
        "fresh_workspaces": len({item["workspace"] for item in actor_results})
        == expected_turns,
        "responses": all(len(values) == 1 for values in response_ids)
        and len(distinct_responses) == expected_turns
        and distinct_responses == proxy_response_ids,
        "model": models == [acceptance["deployment_epoch"]["requested_model"]]
        and all(
            item["deployment_effective_models"] == models for item in actor_results
        ),
        "catalog": len(catalog_payloads) == 2
        and bool(catalog_payloads[0])
        and catalog_payloads[0] == catalog_payloads[1],
        "etag": len(etags) == 1,
        "inventory": inventory_valid
        and all(item["inventory_receipts"] == 1 for item in actor_results),
        "collector": collector_errors == [],
        "usage_receipts": all(
            item["usage"]["receipt_count"] >= 1 for item in actor_results
        ),
        "per_turn_output_budget": all(
            item["usage"]["output_tokens"]
            <= acceptance["resource_budget"]["output_tokens_per_turn"]
            for item in actor_results
        ),
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
        "claim_limit": acceptance["claim_limit"],
        "candidate_errors": {
            item["worker"]: item["candidate_errors"] for item in mechanisms
        },
        "pre_update_errors": {
            item["worker"]: item["pre_update_errors"] for item in mechanisms
        },
        "no_persistence_errors": {
            item["worker"]: item["no_persistence_errors"] for item in mechanisms
        },
        "verbatim_errors": {
            item["worker"]: item["verbatim_errors"] for item in mechanisms
        },
        "old_carrier_projection_errors": {
            item["worker"]: item["old_carrier_projection_errors"] for item in mechanisms
        },
        "fixed_controls": fixed_controls,
        "actor_surface": surface,
        "response_count": len(distinct_responses),
        "effective_models": models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed_seconds,
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
    task_manifest: Path,
    output: Path,
    workspace: Path,
) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0049 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    task, task_bytes = read_sealed_json(task_manifest)
    validate_task(task)
    if sha256_bytes(task_bytes) != lock.get("task_sha256") or task[
        "task_seed"
    ] != lock.get("task_seed"):
        raise RuntimeError("OT-0049 private task differs from the run lock")
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0049 output or workspace already exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_counterbalance_config(load_json(repo / COUNTERBALANCE_PATH))
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    workspace.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    receipts: list[dict[str, Any]] = []
    errors: list[str] = []
    catalogs: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []
    stderr: list[str] = []
    failure_type = None
    failure = None
    proxy_ref = None
    client = None
    started = time.monotonic()
    try:
        with SanitizedResponsesProxy() as proxy:
            proxy_ref = proxy
            with AppServerClient(
                command=instrumented_command(codex_bin, proxy.base_url),
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as active:
                client = active
                model = acceptance["deployment_epoch"]["requested_model"]
                for worker in ("worker-1", "worker-2"):
                    catalog = active.request("model/list", {"includeHidden": False})[
                        "data"
                    ]
                    catalogs.append(catalog)
                    if model not in {item.get("id") for item in catalog}:
                        raise RuntimeError("OT-0049 frozen hosted model is unavailable")
                    worker_results, mechanism, worker_inventories = execute_worker(
                        repo=repo,
                        task=task,
                        worker=worker,
                        client=active,
                        proxy=proxy,
                        model=model,
                        workspace_root=workspace,
                        orientation=orientation,
                        schema=schema,
                    )
                    actor_results.extend(worker_results)
                    mechanisms.append(mechanism)
                    inventories.extend(worker_inventories)
                events, stderr = active.raw_events, active.stderr_lines
            receipts, errors = proxy.collector.snapshot(), proxy.collector.errors()
    except Exception as error:
        failure_type, failure = type(error).__name__, str(error)
        if client is not None:
            events, stderr = client.raw_events, client.stderr_lines
        if proxy_ref is not None:
            receipts, errors = (
                proxy_ref.collector.snapshot(),
                proxy_ref.collector.errors(),
            )
    elapsed = time.monotonic() - started
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
            task=task,
            actor_results=actor_results,
            mechanisms=mechanisms,
            inventories=inventories,
            proxy_receipts=receipts,
            collector_errors=errors,
            catalog_payloads=catalogs,
            usage=token_usage(events),
            elapsed_seconds=elapsed,
            verification=verification,
            failure_type=failure_type,
            schema=schema,
        )
    except Exception as error:
        failure_type = failure_type or type(error).__name__
        failure = failure or str(error)
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
        "catalog_payloads": catalogs,
        "catalog_payloads_sha256": sha256_bytes(canonical_json(catalogs)),
        "proxy_receipts": receipts,
        "collector_errors": errors,
        "events": events,
        "stderr": stderr,
        "failure": failure,
        "verification": verification,
    }
    write_sealed_json(output, raw)
    output.chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="e12-representation-escape-hosted-epoch-run",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Hosted outputs, task identities, world states, and deployment receipts remain private.",
                "This valid execution consumes OT-0048's single OT-0049 authorization regardless of disposition.",
                "A pass is one bounded representation-escape foothold, not developmental transfer, widened OT-2, or Open Developmental Trajectory success.",
            ],
            input_manifests=[str(OT48_MANIFEST_PATH), str(OT1_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0049-harness")
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
    if None in (args.codex_bin, args.task_manifest, args.output, args.workspace_root):
        parser.error(
            "--codex-bin, --task-manifest, --output, and --workspace-root are required"
        )
    try:
        manifest, summary = run(
            repo=repo,
            run_id=args.run_id,
            codex_bin=args.codex_bin.resolve(),
            task_manifest=args.task_manifest.resolve(),
            output=args.output.resolve(),
            workspace=args.workspace_root.resolve(),
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
