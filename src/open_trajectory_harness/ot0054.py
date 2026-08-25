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
    build_task as build_calibration_task,
    complete_contact,
    future_task_case,
    promoted_weight_family,
    public_contact,
    score,
    structural_certificate,
    verbatim_raw_selections,
    verbatim_raw_update,
    weighted_selections,
)
from .ot0049 import _fixed_control_receipt, _turn_usage
from .ot0049_world import counterbalanced_split, validate_counterbalance_config
from .ot0050 import neutralize_validation
from .ot0053 import (
    COMMITTED_PROJECTION_LIMIT,
    MAX_BRANCHES,
    PROVISIONAL_PROJECTION_LIMIT,
    active_source,
    commit_branch_set,
    initial_snapshot,
    project_snapshot,
    provisional_projection,
    restore_snapshot,
    snapshot_selections,
    validate_branch_set,
)


EXPERIMENT_ID = "OT-0054"
ACCEPTANCE_PATH = Path("spec/ot-0054-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0054-run-lock.json")
PROMPT_PATH = Path("fixtures/ot-0054/branching-actor-prompt.txt")
SCHEMA_PATH = Path("fixtures/ot-0054/branching-output.schema.json")
COUNTERBALANCE_PATH = Path("fixtures/ot-0049/counterbalance.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
OT53_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0053/ot-0053-branching-ledger-calibration-001.json"
)
OT52_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0052/ot-0052-staged-representation-escape-candidate-001.json"
)
OT1_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0037/ot-0037-e6-deterministic-ot1-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0054-branching-ledger-candidate-001"


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0054 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-branching-ledger-representation-escape-task",
            }
        )
    )


def build_task(task_seed: str) -> dict[str, Any]:
    calibration = build_calibration_task(future_task_case(task_seed))
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "task_seed": task_seed,
        "regimes": calibration["regimes"],
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def validate_task(task: dict[str, Any]) -> None:
    if (
        task.get("schema_version") != 1
        or task.get("experiment_id") != EXPERIMENT_ID
        or not re.fullmatch(r"[0-9a-f]{64}", task.get("task_seed", ""))
        or canonical_json(build_task(task.get("task_seed", ""))) != canonical_json(task)
    ):
        raise ValueError("OT-0054 task differs from its mechanical derivation")


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": PROMPT_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "counterbalance_sha256": COUNTERBALANCE_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0054.py"),
        "branching_core_sha256": Path("src/open_trajectory_harness/ot0053.py"),
        "staged_expression_core_sha256": Path("src/open_trajectory_harness/ot0050.py"),
        "world_calibration_sha256": Path("src/open_trajectory_harness/ot0048.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path(
            "src/open_trajectory_harness/deployment_proxy.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0054_harness.py"),
        "test_sha256": Path("tests/test_ot0054.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "tool_receipt_patch_sha256": PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0053_manifest_sha256": OT53_MANIFEST_PATH,
        "ot0052_manifest_sha256": OT52_MANIFEST_PATH,
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


def validate_run_lock(repo: Path, execution: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0054 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0054 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0054 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0054 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo, "diff", "--name-only", f"{implementation}..{execution}", "--", *protected
    )
    if changed:
        raise RuntimeError(f"OT-0054 implementation changed after lock: {changed}")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if (
        not codex_bin.is_file()
        or not sidecar.is_file()
        or sha256_file(codex_bin) != binary.get("codex_sha256")
        or sha256_file(sidecar) != binary.get("code_mode_host_sha256")
        or app_server_version(str(codex_bin)) != binary.get("version")
        or sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256")
    ):
        raise RuntimeError("OT-0054 backend or TLS identity differs")
    return lock


def actor_view(
    stage: str,
    contact: dict[str, Any],
    choices: list[str],
    receipt: dict[str, Any],
    current: dict[str, Any],
    provisional: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "encounter": public_contact(contact),
        "prior_choices": choices,
        "completed_contact": receipt,
        "current_ledger": current,
        "provisional_ledger": provisional,
    }


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    prompt = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    task = build_task("0" * 64)
    regime = task["regimes"][0]
    current = initial_snapshot()
    choices = snapshot_selections(current, regime["contact"])
    receipt = complete_contact(regime["contact"], choices)
    view = actor_view(
        "proposal", regime["contact"], choices, receipt, project_snapshot(current), None
    )
    forbidden_terms = {"preferred_event_id", "relation", "polarity", "solution"}

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(
                *(keys(item) for item in value.values()), set()
            )
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()

    hits = sorted(term for term in forbidden_terms if term in prompt.lower())
    body = {
        "prompt_sha256": sha256_bytes(prompt.encode()),
        "prompt_forbidden_hits": hits,
        "serialized_forbidden_keys": sorted(forbidden_terms & keys(view)),
        "probe_sha256": sha256_bytes(canonical_json(view)),
    }
    return {
        **body,
        "pass": not hits and not body["serialized_forbidden_keys"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def source_novelty(repo: Path, source: str) -> dict[str, Any]:
    normalized = "".join(source.split())
    collisions = []
    for path in fixed_input_paths().values():
        text = (repo / path).read_text(encoding="utf-8")
        if normalized and normalized in "".join(text.split()):
            collisions.append(str(path))
    return {
        "pass": not collisions,
        "source_sha256": sha256_bytes(source.encode()),
        "collision_paths": collisions,
    }


def run_actor_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    prompt_template: str,
    schema: dict[str, Any],
    view: dict[str, Any],
    worker: str,
    regime_index: int,
    stage: str,
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
            "baseInstructions": "Author one bounded branching ledger and return only schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0054",
        }
    )
    prompt = prompt_template.replace("{{ACTOR_VIEW}}", canonical_json(view).decode())
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
    deployment = proxy.collector.snapshot()[deployment_before:]
    inventories = client.model_visible_tool_inventories()
    inventory = inventories[-1] if len(inventories) > inventory_before else []
    output, parse_error = final_agent_json(turn)
    if turn.get("status") != "completed":
        parse_error = parse_error or "actor turn did not complete"
    if (
        not isinstance(output, dict)
        or set(output) != {"branches", "active_index"}
        or not isinstance(output["branches"], list)
        or not all(isinstance(item, str) for item in output["branches"])
        or not 1 <= len(output["branches"]) <= MAX_BRANCHES
        or type(output["active_index"]) is not int
    ):
        parse_error = parse_error or "actor output failed its exact branching envelope"
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
            "stage": stage,
            "workspace": str(workspace.resolve()),
            "thread_id": thread["id"],
            "thread_session_id": thread.get("sessionId"),
            "actor_view": view,
            "actor_output": output,
            "parse_error": parse_error,
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
            "usage": _turn_usage(client.raw_events[event_before:], thread["id"]),
            "current_projection_bytes": len(canonical_json(view["current_ledger"])),
            "provisional_projection_bytes": len(
                canonical_json(view["provisional_ledger"])
            )
            if view["provisional_ledger"]
            else 0,
            "turn": turn,
        },
        output,
        inventory,
    )


def execute_worker(
    *,
    repo: Path,
    task: dict[str, Any],
    worker: str,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace_root: Path,
    prompt_template: str,
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[list[dict[str, Any]]]]:
    current = initial_snapshot()
    initial = current
    snapshots = {current.sha256: current}
    turns = []
    inventories = []
    regimes = []
    prior_canary = None
    for offset, regime in enumerate(task["regimes"]):
        index = offset + 1
        before = current
        prior_active = active_source(before)
        contact = counterbalanced_split(regime["contact"], worker)
        canary = counterbalanced_split(regime["canary"], worker)
        choices = snapshot_selections(before, contact)
        receipt = complete_contact(contact, choices)
        hidden = [
            *[pair["preferred_event_id"] for pair in canary["pairs"]],
            '"preferred_event_id"',
            '"relation"',
            '"polarity"',
        ]
        proposal_view = actor_view(
            "proposal", contact, choices, receipt, project_snapshot(before), None
        )
        proposal_turn, proposal, proposal_inventory = run_actor_turn(
            client=client,
            proxy=proxy,
            model=model,
            workspace=workspace_root / worker / f"regime-{index}-proposal",
            prompt_template=prompt_template,
            schema=schema,
            view=proposal_view,
            worker=worker,
            regime_index=index,
            stage="proposal",
            hidden_markers=hidden,
        )
        proposal_sources = proposal["branches"] if proposal else [""]
        proposal_active = proposal["active_index"] if proposal else -1
        proposal_validations = validate_branch_set(proposal_sources, contact, receipt)
        provisional = provisional_projection(
            before, proposal_sources, proposal_validations
        )
        adjudication_view = actor_view(
            "adjudication",
            contact,
            choices,
            receipt,
            project_snapshot(before),
            provisional,
        )
        adjudication_turn, adjudication, adjudication_inventory = run_actor_turn(
            client=client,
            proxy=proxy,
            model=model,
            workspace=workspace_root / worker / f"regime-{index}-adjudication",
            prompt_template=prompt_template,
            schema=schema,
            view=adjudication_view,
            worker=worker,
            regime_index=index,
            stage="adjudication",
            hidden_markers=hidden,
        )
        final_sources = adjudication["branches"] if adjudication else [""]
        final_active = adjudication["active_index"] if adjudication else -1
        final_validations = validate_branch_set(final_sources, contact, receipt)
        after = commit_branch_set(
            before, final_sources, final_validations, final_active
        )
        one_shot = commit_branch_set(
            before, proposal_sources, proposal_validations, proposal_active
        )
        no_credit = commit_branch_set(
            before,
            final_sources,
            [neutralize_validation(item) for item in final_validations],
            final_active,
        )
        deletion_sources = [
            source
            for position, source in enumerate(final_sources)
            if position != final_active
        ]
        deletion_validations = [
            validation
            for position, validation in enumerate(final_validations)
            if position != final_active
        ]
        active_deleted = commit_branch_set(
            before, deletion_sources, deletion_validations, -1
        )
        snapshots[after.sha256] = after
        pre_error = score(canary, snapshot_selections(before, canary))
        candidate_error = score(canary, snapshot_selections(after, canary))
        one_shot_error = score(canary, snapshot_selections(one_shot, canary))
        raw_entries = verbatim_raw_update(contact, receipt)
        proposal_active_source = (
            proposal_sources[proposal_active]
            if proposal_active in range(len(proposal_sources))
            else None
        )
        final_active_source = (
            active_source(after) if after.sha256 != before.sha256 else None
        )
        branch_sources = [item["source"] for item in after.state.get("branches", [])]
        committed = after.sha256 != before.sha256
        restored_parent = (
            restore_snapshot(project_snapshot(snapshots[after.parent_sha256]))
            if committed
            else before
        )
        replay = canonical_json(snapshot_selections(after, canary)) == canonical_json(
            snapshot_selections(restore_snapshot(project_snapshot(after)), canary)
        )
        rollback_split = prior_canary if prior_canary is not None else contact
        proposal_turn.update(
            {
                "validation_receipts": proposal_validations,
                "validation_replay": canonical_json(proposal_validations)
                == canonical_json(
                    validate_branch_set(proposal_sources, contact, receipt)
                ),
                "provisional_projection": provisional,
            }
        )
        adjudication_turn.update(
            {
                "validation_receipts": final_validations,
                "validation_replay": canonical_json(final_validations)
                == canonical_json(validate_branch_set(final_sources, contact, receipt)),
                "parent_projection": project_snapshot(before),
                "committed_projection": project_snapshot(after),
                "pre_update_errors": pre_error,
                "candidate_errors": candidate_error,
                "one_shot_errors": one_shot_error,
                "no_persistence_errors": score(
                    canary, snapshot_selections(initial, canary)
                ),
                "verbatim_errors": score(
                    canary, verbatim_raw_selections(raw_entries, canary)
                ),
                "old_carrier_projection_errors": min(
                    score(canary, weighted_selections(weights, canary))
                    for weights in promoted_weight_family()
                ),
                "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
                "active_deletion_preserved_parent": active_deleted.sha256
                == before.sha256,
                "active_deletion_errors": score(
                    canary, snapshot_selections(active_deleted, canary)
                ),
                "committed": committed,
                "proposal_origin": final_active_source is not None
                and final_active_source in proposal_sources,
                "proposal_active_changed": final_active_source is not None
                and final_active_source != proposal_active_source,
                "competing_branches": len(branch_sources) >= 2,
                "prior_active_retained": index == 1 or prior_active in branch_sources,
                "later_active_changed": index == 1
                or final_active_source != prior_active,
                "active_novelty": source_novelty(repo, final_active_source)
                if final_active_source
                else {"pass": False},
                "parent_exact": committed and restored_parent.sha256 == before.sha256,
                "successor_exact": restore_snapshot(project_snapshot(after)).sha256
                == after.sha256,
                "rollback_errors": score(
                    rollback_split, snapshot_selections(restored_parent, rollback_split)
                ),
                "expected_rollback_errors": score(
                    rollback_split, snapshot_selections(before, rollback_split)
                ),
                "controller_replay": replay,
                "certificate": structural_certificate(
                    tuple(regime["relation"]),
                    regime["polarity"],
                    regime["canary_scale"],
                ),
            }
        )
        turns.extend([proposal_turn, adjudication_turn])
        inventories.extend([proposal_inventory, adjudication_inventory])
        regimes.append(
            {
                "index": index,
                "pre_update_errors": pre_error,
                "candidate_errors": candidate_error,
                "one_shot_errors": one_shot_error,
                "no_persistence_errors": adjudication_turn["no_persistence_errors"],
                "verbatim_errors": adjudication_turn["verbatim_errors"],
                "old_carrier_projection_errors": adjudication_turn[
                    "old_carrier_projection_errors"
                ],
                "proposal_active_changed": adjudication_turn["proposal_active_changed"],
                "proposal_origin": adjudication_turn["proposal_origin"],
                "competing_branches": adjudication_turn["competing_branches"],
                "prior_active_retained": adjudication_turn["prior_active_retained"],
                "later_active_changed": adjudication_turn["later_active_changed"],
            }
        )
        current = after
        prior_canary = canary
    body = {
        "worker": worker,
        "regimes": regimes,
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "candidate_errors": [item["candidate_errors"] for item in regimes],
        "one_shot_errors": [item["one_shot_errors"] for item in regimes],
        "no_persistence_errors": [item["no_persistence_errors"] for item in regimes],
        "verbatim_errors": [item["verbatim_errors"] for item in regimes],
        "old_carrier_projection_errors": [
            item["old_carrier_projection_errors"] for item in regimes
        ],
    }
    return (
        turns,
        {**body, "receipt_sha256": sha256_bytes(canonical_json(body))},
        inventories,
    )


def summarize(
    *,
    repo: Path,
    acceptance: dict[str, Any],
    task: dict[str, Any],
    turns: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    inventories: list[list[dict[str, Any]]],
    receipts: list[dict[str, Any]],
    collector_errors: list[str],
    catalogs: list[list[dict[str, Any]]],
    usage: dict[str, int],
    elapsed: float,
    verification: dict[str, int],
    failure_type: str | None,
    schema: dict[str, Any],
) -> dict[str, Any]:
    expected = acceptance["resource_budget"]["actor_turns"]
    revisions = [turn for turn in turns if turn["stage"] == "adjudication"]
    response_ids = [turn["deployment_response_ids"] for turn in turns]
    distinct_responses = {value for values in response_ids for value in values}
    proxy_responses = {
        item["value"] for item in receipts if item["kind"] == "response_id"
    }
    models = sorted(
        {item["value"] for item in receipts if item["kind"] == "effective_model"}
    )
    etags = sorted(
        {item["value"] for item in receipts if item["kind"] == "models_etag"}
    )
    inventory_expected = acceptance["direct_inventory"]
    inventory_valid = (
        len(inventories) == expected
        and bool(inventories)
        and all(item == inventories[0] for item in inventories)
        and sha256_bytes(canonical_json(inventories[0])) == inventory_expected["sha256"]
        and len(inventories[0]) == inventory_expected["tool_count"]
    )
    fixed = _fixed_control_receipt(task)
    endpoint = len(mechanisms) == 2 and all(
        item["pre_update_errors"] == [4, 8, 4]
        and item["candidate_errors"] == [0, 0, 0]
        and item["no_persistence_errors"] == [4, 4, 4]
        and all(value >= 1 for value in item["verbatim_errors"])
        and all(value >= 1 for value in item["old_carrier_projection_errors"])
        and all(
            regime["proposal_origin"]
            and regime["competing_branches"]
            and regime["prior_active_retained"]
            and regime["later_active_changed"]
            for regime in item["regimes"]
        )
        for item in mechanisms
    )
    staged_advantage = (
        endpoint
        and sum(sum(item["one_shot_errors"]) for item in mechanisms) >= 1
        and any(
            regime["proposal_active_changed"]
            for item in mechanisms
            for regime in item["regimes"]
        )
    )
    surface = actor_surface_authority(repo)
    gates = {
        "complete": len(turns) == expected and len(mechanisms) == 2,
        "candidate_endpoint": endpoint,
        "branch_selection_advantage": staged_advantage,
        "consequence_causation": all(
            item["no_credit_preserved_parent"] for item in revisions
        ),
        "active_deletion": all(
            item["active_deletion_preserved_parent"]
            and item["active_deletion_errors"] >= 1
            for item in revisions
        ),
        "old_carrier_impossibility": all(
            item["certificate"]["pass"] for item in revisions
        ),
        "fixed_controls": fixed["best_weighted_aggregate_errors"] >= 1
        and all(sum(errors) >= 1 for errors in fixed["lineages"].values()),
        "novelty": surface["pass"]
        and all(item["active_novelty"]["pass"] for item in revisions),
        "correction": all(
            item["pre_update_errors"][1] == 8 and item["candidate_errors"] == [0, 0, 0]
            for item in mechanisms
        ),
        "rollback": all(
            item["parent_exact"]
            and item["successor_exact"]
            and item["rollback_errors"] == item["expected_rollback_errors"]
            for item in revisions
        ),
        "controller_replay": all(item["controller_replay"] for item in revisions)
        and all(item["validation_replay"] for item in turns),
        "projection_budget": all(
            item["current_projection_bytes"] <= COMMITTED_PROJECTION_LIMIT
            and item["provisional_projection_bytes"] <= PROVISIONAL_PROJECTION_LIMIT
            for item in turns
        ),
        "equal_active_budget": fixed["active_choices_per_regime"] == 8
        and all(len(item["actor_view"]["encounter"]["pairs"]) == 8 for item in turns),
        "schema_subset": unsupported_keywords(schema) == set(),
        "parse": all(item["parse_error"] is None for item in turns),
        "tools": all(item["tool_calls"] == 0 for item in turns),
        "fresh_threads": len({item["thread_id"] for item in turns}) == expected,
        "fresh_workspaces": len({item["workspace"] for item in turns}) == expected,
        "responses": all(len(values) == 1 for values in response_ids)
        and len(distinct_responses) == expected
        and distinct_responses == proxy_responses,
        "model": models == [acceptance["deployment_epoch"]["requested_model"]]
        and all(item["deployment_effective_models"] == models for item in turns),
        "catalog": len(catalogs) == 2
        and bool(catalogs[0])
        and catalogs[0] == catalogs[1],
        "etag": len(etags) == 1,
        "inventory": inventory_valid
        and all(item["inventory_receipts"] == 1 for item in turns),
        "collector": collector_errors == [],
        "usage_receipts": all(item["usage"]["receipt_count"] >= 1 for item in turns),
        "per_turn_output_budget": all(
            item["usage"]["output_tokens"]
            <= acceptance["resource_budget"]["output_tokens_per_turn"]
            for item in turns
        ),
        "validation_authority": all(
            item["actor_output"] is not None
            and len(item["validation_receipts"])
            == len(item["actor_output"]["branches"])
            and all(
                receipt["outcome_credit"] is True
                and receipt["proposal_sha256"] == sha256_bytes(source.encode())
                for source, receipt in zip(
                    item["actor_output"]["branches"],
                    item["validation_receipts"],
                    strict=True,
                )
            )
            for item in turns
        ),
        "hidden_authority": all(not item["hidden_task_leakage"] for item in turns),
        "input_budget": usage["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total"],
        "wall_budget": elapsed <= acceptance["resource_budget"]["wall_seconds"],
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
        "one_shot_errors": {
            item["worker"]: item["one_shot_errors"] for item in mechanisms
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
        "fixed_controls": fixed,
        "actor_surface": surface,
        "response_count": len(distinct_responses),
        "effective_models": models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed,
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
        raise RuntimeError("OT-0054 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution, codex_bin)
    task, task_bytes = read_sealed_json(task_manifest)
    validate_task(task)
    if sha256_bytes(task_bytes) != lock.get("task_sha256") or task[
        "task_seed"
    ] != lock.get("task_seed"):
        raise RuntimeError("OT-0054 private task differs from lock")
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0054 output or workspace exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_counterbalance_config(load_json(repo / COUNTERBALANCE_PATH))
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    workspace.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    turns: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    receipts: list[dict[str, Any]] = []
    errors: list[str] = []
    catalogs: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []
    stderr: list[str] = []
    failure_type = failure = proxy_ref = client = None
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
                        raise RuntimeError("OT-0054 frozen model unavailable")
                    worker_turns, mechanism, worker_inventories = execute_worker(
                        repo=repo,
                        task=task,
                        worker=worker,
                        client=active,
                        proxy=proxy,
                        model=model,
                        workspace_root=workspace,
                        prompt_template=prompt_template,
                        schema=schema,
                    )
                    turns.extend(worker_turns)
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
            turns=turns,
            mechanisms=mechanisms,
            inventories=inventories,
            receipts=receipts,
            collector_errors=errors,
            catalogs=catalogs,
            usage=token_usage(events),
            elapsed=elapsed,
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
        "execution_git_commit": execution,
        "task_sha256": task["task_sha256"],
        "summary": summary,
        "mechanisms": mechanisms,
        "actor_results": turns,
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
            kind="branching-ledger-representation-escape-hosted-epoch-run",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Hosted outputs, task identities, world states, and deployment receipts remain private.",
                "This valid execution consumes OT-0053's single OT-0054 authorization regardless of disposition.",
                "A pass is one bounded branching representation-escape foothold, not transfer, widened OT-2, or integrated development.",
            ],
            input_manifests=[
                str(OT53_MANIFEST_PATH),
                str(OT52_MANIFEST_PATH),
                str(OT1_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0054-harness")
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
            parser.error("--implementation-commit is required")
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
