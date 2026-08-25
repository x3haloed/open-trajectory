from __future__ import annotations

import argparse
import ast
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
from .ot0048 import complete_contact, score
from .ot0049 import _turn_usage
from .ot0049_world import counterbalanced_split, validate_counterbalance_config
from .ot0056 import (
    all_real_weight_certificate,
    exact_rows,
    public_split,
    verbatim_selections,
)
from .ot0057 import build_task as build_categorical_world
from .ot0057 import structural_calibration
from .ot0059 import (
    INHERITANCE_LIMIT,
    MAX_AST_NODES,
    MAX_SOURCE_BYTES,
    PUBLIC_EVENT_KEYS,
    PredicateSnapshot,
    _fixed_sources,
    _snapshot,
    attempt_update,
    initial_snapshot,
    parse_source,
    predicate_selections,
    project_snapshot,
    reference_source,
    restore_snapshot,
    snapshot_selections,
)


EXPERIMENT_ID = "OT-0060"
ACCEPTANCE_PATH = Path("spec/ot-0060-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0060-run-lock.json")
PROMPT_PATH = Path("fixtures/ot-0060/actor-prompt.txt")
ORIENTATION_PATH = Path("fixtures/ot-0059/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0059/actor-output.schema.json")
COUNTERBALANCE_PATH = Path("fixtures/ot-0049/counterbalance.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
OT59_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0059/ot-0059-categorical-predicate-carrier-calibration-001.json"
)
OT57_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0057/ot-0057-categorical-description-application-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0060-categorical-predicate-representation-escape-candidate-001"


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0060 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-categorical-predicate-candidate-task",
            }
        )
    )


def build_task(task_seed: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("OT-0060 task seed is malformed")
    world = build_categorical_world(task_seed)
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "task_seed": task_seed,
        "world": world,
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def validate_task(task: dict[str, Any]) -> None:
    if (
        task.get("schema_version") != 1
        or task.get("experiment_id") != EXPERIMENT_ID
        or not re.fullmatch(r"[0-9a-f]{64}", task.get("task_seed", ""))
        or canonical_json(build_task(task.get("task_seed", ""))) != canonical_json(task)
    ):
        raise ValueError("OT-0060 task differs from its mechanical derivation")


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": PROMPT_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "counterbalance_sha256": COUNTERBALANCE_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0060.py"),
        "carrier_calibration_sha256": Path("src/open_trajectory_harness/ot0059.py"),
        "world_derivation_sha256": Path("src/open_trajectory_harness/ot0057.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path(
            "src/open_trajectory_harness/deployment_proxy.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0060_harness.py"),
        "test_sha256": Path("tests/test_ot0060.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "tool_receipt_patch_sha256": PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0059_manifest_sha256": OT59_MANIFEST_PATH,
        "ot0057_manifest_sha256": OT57_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def prepare_task_manifest(path: Path, implementation_commit: str) -> dict[str, Any]:
    task = build_task(expected_task_seed(implementation_commit))
    validate_task(task)
    structural = structural_calibration(task["world"])
    if not structural["pass"]:
        raise RuntimeError("OT-0060 private world failed structural calibration")
    write_sealed_json(path, task)
    raw = canonical_json(task)
    return {
        "task_seed": task["task_seed"],
        "task_sha256": sha256_bytes(raw),
        "task_bytes": len(raw),
        "world_structural_receipt_sha256": structural["receipt_sha256"],
    }


def validate_run_lock(repo: Path, execution: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0060 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0060 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0060 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0060 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"OT-0060 implementation changed after lock: {changed}")
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
        raise RuntimeError("OT-0060 backend or TLS identity differs")
    return lock


def actor_view(
    contact: dict[str, Any],
    choices: list[str],
    receipt: dict[str, Any],
    current: PredicateSnapshot,
) -> dict[str, Any]:
    return {
        "current_snapshot": project_snapshot(current),
        "encounter": public_split(contact),
        "prior_choices": choices,
        "completed_contact": receipt,
    }


def _collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(
            *(_collect_keys(item) for item in value.values()), set()
        )
    if isinstance(value, list):
        return set().union(*(_collect_keys(item) for item in value), set())
    return set()


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    prompt = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    task = build_task("0" * 64)
    regime = task["world"]["regimes"][0]
    current = initial_snapshot()
    choices = snapshot_selections(current, regime["contact"])
    receipt = complete_contact(regime["contact"], choices)
    view = actor_view(regime["contact"], choices, receipt, current)
    forbidden_keys = sorted(
        {"preferred_event_id", "target_flag", "target_index", "polarity"}
        & _collect_keys(view)
    )
    surface = prompt + orientation + canonical_json(schema).decode()
    body = {
        "prompt_sha256": sha256_bytes(prompt.encode()),
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "concrete_flag_hits": re.findall(r"flag-[0-9a-f]{10,}", surface),
        "reference_expression_hits": re.findall(r"(?:in|not in)\s+event\s*\[", surface),
        "serialized_forbidden_keys": forbidden_keys,
        "probe_sha256": sha256_bytes(canonical_json(view)),
    }
    return {
        **body,
        "pass": not body["concrete_flag_hits"]
        and not body["reference_expression_hits"]
        and not forbidden_keys,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def _actor_literals(source: str) -> list[str]:
    tree = parse_source(source)
    return sorted(
        {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in PUBLIC_EVENT_KEYS
        }
    )


class _DeleteActorLiterals(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str) and node.value not in PUBLIC_EVENT_KEYS:
            return ast.copy_location(ast.Constant(value=""), node)
        return node


def literal_deleted_source(source: str) -> str:
    tree = parse_source(source)
    transformed = _DeleteActorLiterals().visit(tree)
    ast.fix_missing_locations(transformed)
    deleted = ast.unparse(transformed)
    parse_source(deleted)
    return deleted


def source_novelty(
    repo: Path, source: str, parent: PredicateSnapshot
) -> dict[str, Any]:
    try:
        tree = parse_source(source)
        literals = _actor_literals(source)
        structure_sha256 = sha256_bytes(
            ast.dump(tree, include_attributes=False).encode()
        )
        safe = True
    except ValueError:
        literals = []
        structure_sha256 = None
        safe = False
    normalized = "".join(source.split())
    collision_paths = []
    for path in (PROMPT_PATH, ORIENTATION_PATH, SCHEMA_PATH):
        text = (repo / path).read_text(encoding="utf-8")
        if normalized and normalized in "".join(text.split()):
            collision_paths.append(str(path))
    parent_source = parent.state.get("source")
    body = {
        "source_sha256": sha256_bytes(source.encode()),
        "structure_sha256": structure_sha256,
        "actor_literal_sha256s": [sha256_bytes(value.encode()) for value in literals],
        "actor_literal_count": len(literals),
        "parent_source_sha256": (
            sha256_bytes(parent_source.encode()) if parent_source is not None else None
        ),
        "source_differs_from_parent": parent_source != source,
        "collision_paths": collision_paths,
        "safe": safe,
    }
    return {
        **body,
        "pass": safe
        and bool(literals)
        and body["source_differs_from_parent"]
        and not collision_paths,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_actor_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    prompt_template: str,
    orientation: str,
    schema: dict[str, Any],
    view: dict[str, Any],
    worker: str,
    regime_index: int,
    hidden_markers: list[str],
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Author one bounded predicate source and return only schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0060",
        }
    )
    prompt = prompt_template.replace("{{ORIENTATION}}", orientation).replace(
        "{{ACTOR_VIEW}}", canonical_json(view).decode()
    )
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
        or set(output) != {"source"}
        or not isinstance(output["source"], str)
    ):
        parse_error = parse_error or "actor output failed its exact source envelope"
        output = None
    source = output["source"] if output is not None else ""
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
            "current_projection_bytes": len(canonical_json(view["current_snapshot"])),
            "turn": turn,
        },
        source,
        inventory,
    )


def _ablation_snapshot(source: str, basis: PredicateSnapshot) -> PredicateSnapshot:
    return _snapshot(
        basis.revision,
        basis.parent_sha256,
        basis.outcome_receipt_sha256,
        {"source": source},
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
    orientation: str,
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[list[dict[str, Any]]]]:
    world = task["world"]
    current = initial_snapshot()
    initial = current
    snapshots = {current.sha256: current}
    first_learned = None
    second_learned = None
    turns = []
    inventories = []
    regimes = []
    fixed_sources = _fixed_sources(world)
    fixed_lineages = {name: [] for name in fixed_sources}
    for regime in world["regimes"]:
        index = regime["index"]
        before = current
        contact = counterbalanced_split(regime["contact"], worker)
        canary = counterbalanced_split(regime["canary"], worker)
        choices = snapshot_selections(before, contact)
        receipt = complete_contact(contact, choices)
        view = actor_view(contact, choices, receipt, before)
        hidden = [
            *[pair["preferred_event_id"] for pair in canary["pairs"]],
            '"preferred_event_id"',
            '"target_flag"',
            '"target_index"',
            '"polarity"',
        ]
        turn, source, inventory = run_actor_turn(
            client=client,
            proxy=proxy,
            model=model,
            workspace=workspace_root / worker / f"regime-{index}",
            prompt_template=prompt_template,
            orientation=orientation,
            schema=schema,
            view=view,
            worker=worker,
            regime_index=index,
            hidden_markers=hidden,
        )
        after, update_reason = attempt_update(before, source, receipt, contact)
        snapshots[after.sha256] = after
        no_credit, no_credit_reason = attempt_update(before, source, None, contact)
        invalid, invalid_reason = attempt_update(
            before, 'event["on_flags"].append("x") == True', receipt, contact
        )
        oversized, oversized_reason = attempt_update(
            before, "True" + " " * MAX_SOURCE_BYTES, receipt, contact
        )
        opposite = "off" if regime["polarity"] == "on" else "on"
        imperfect, imperfect_reason = attempt_update(
            before,
            reference_source(regime["target_flag"], opposite),
            receipt,
            contact,
        )
        if after.sha256 != before.sha256:
            constant_ablation = _ablation_snapshot("True", after)
            source_deletion = _ablation_snapshot("False", after)
            try:
                deleted = literal_deleted_source(source)
                literal_ablation = _ablation_snapshot(deleted, after)
            except ValueError:
                deleted = source
                literal_ablation = after
            parent = restore_snapshot(project_snapshot(snapshots[after.parent_sha256]))
        else:
            constant_ablation = source_deletion = literal_ablation = before
            deleted = source
            parent = before
        if index == 1:
            first_learned = after
        elif index == 2:
            second_learned = after
        for name, fixed_source in fixed_sources.items():
            fixed_lineages[name].append(
                score(canary, predicate_selections(fixed_source, canary))
            )
        rows = exact_rows(contact, choices, receipt)
        pre_errors = score(canary, snapshot_selections(before, canary))
        candidate_errors = score(canary, snapshot_selections(after, canary))
        novelty = source_novelty(repo, source, before)
        replay_errors = score(
            canary,
            snapshot_selections(restore_snapshot(project_snapshot(after)), canary),
        )
        regime_result = {
            "index": index,
            "pre_update_errors": pre_errors,
            "candidate_errors": candidate_errors,
            "update_reason": update_reason,
            "source_sha256": sha256_bytes(source.encode()),
            "source_bytes": len(source.encode()),
            "source_ast_nodes": (
                sum(1 for _ in ast.walk(parse_source(source)))
                if update_reason == "committed"
                else None
            ),
            "committed_bytes": len(canonical_json(project_snapshot(after))),
            "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
            "no_credit_reason": no_credit_reason,
            "unchanged_errors": pre_errors,
            "no_persistence_errors": score(
                canary, snapshot_selections(initial, canary)
            ),
            "digest_errors": score(canary, snapshot_selections(initial, canary)),
            "verbatim_errors": score(canary, verbatim_selections(rows, canary)),
            "constant_ast_ablation_errors": score(
                canary, snapshot_selections(constant_ablation, canary)
            ),
            "literal_deletion_ablation_errors": score(
                canary, snapshot_selections(literal_ablation, canary)
            ),
            "source_deletion_ablation_errors": score(
                canary, snapshot_selections(source_deletion, canary)
            ),
            "literal_deleted_source_sha256": sha256_bytes(deleted.encode()),
            "frozen_first_errors": score(
                canary,
                snapshot_selections(
                    first_learned if first_learned is not None else after, canary
                ),
            ),
            "frozen_second_errors": score(
                canary,
                snapshot_selections(
                    second_learned if second_learned is not None else after, canary
                ),
            ),
            "all_real_weight_certificate": all_real_weight_certificate(canary),
            "invalid_preserved_parent": invalid.sha256 == before.sha256,
            "invalid_reason": invalid_reason,
            "oversized_preserved_parent": oversized.sha256 == before.sha256,
            "oversized_reason": oversized_reason,
            "contact_imperfect_preserved_parent": imperfect.sha256 == before.sha256,
            "contact_imperfect_reason": imperfect_reason,
            "parent_exact": parent.sha256 == before.sha256,
            "successor_exact": restore_snapshot(project_snapshot(after)).sha256
            == after.sha256,
            "rollback_errors": score(canary, snapshot_selections(parent, canary)),
            "expected_rollback_errors": pre_errors,
            "replay_errors": replay_errors,
            "novelty": novelty,
        }
        turn.update(
            {
                "update_reason": update_reason,
                "committed_snapshot": project_snapshot(after),
                "candidate_errors": candidate_errors,
                "novelty": novelty,
            }
        )
        turns.append(turn)
        inventories.append(inventory)
        regimes.append(regime_result)
        current = after
    body = {
        "worker": worker,
        "regimes": regimes,
        "candidate_errors": [item["candidate_errors"] for item in regimes],
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "frozen_first_errors": [item["frozen_first_errors"] for item in regimes],
        "frozen_second_errors": [item["frozen_second_errors"] for item in regimes],
        "fixed_lineages": fixed_lineages,
    }
    body["pass"] = (
        body["candidate_errors"] == [0, 0, 0]
        and body["pre_update_errors"][0] == 4
        and body["pre_update_errors"][1] == 8
        and body["pre_update_errors"][2] >= 1
        and body["frozen_first_errors"][1] == 8
        and body["frozen_second_errors"][2] >= 1
        and all(sum(errors) >= 1 for errors in fixed_lineages.values())
        and all(
            item["update_reason"] == "committed"
            and item["source_bytes"] <= MAX_SOURCE_BYTES
            and item["source_ast_nodes"] <= MAX_AST_NODES
            and item["committed_bytes"] <= INHERITANCE_LIMIT
            and item["no_credit_preserved_parent"]
            and item["no_credit_reason"] == "no-credit"
            and item["unchanged_errors"] >= 1
            and item["no_persistence_errors"] == 4
            and item["digest_errors"] == 4
            and item["verbatim_errors"] == 4
            and item["constant_ast_ablation_errors"] >= 1
            and item["literal_deletion_ablation_errors"] >= 1
            and item["source_deletion_ablation_errors"] >= 1
            and item["all_real_weight_certificate"]["pass"]
            and item["invalid_preserved_parent"]
            and item["invalid_reason"] == "invalid"
            and item["oversized_preserved_parent"]
            and item["oversized_reason"] == "invalid"
            and item["contact_imperfect_preserved_parent"]
            and item["contact_imperfect_reason"] == "contact-imperfect"
            and item["parent_exact"]
            and item["successor_exact"]
            and item["rollback_errors"] == item["expected_rollback_errors"]
            and item["replay_errors"] == item["candidate_errors"]
            and item["novelty"]["pass"]
            for item in regimes
        )
    )
    return (
        turns,
        {**body, "receipt_sha256": sha256_bytes(canonical_json(body))},
        inventories,
    )


def summarize(
    *,
    repo: Path,
    acceptance: dict[str, Any],
    structural: dict[str, Any],
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
    surface = actor_surface_authority(repo)
    candidate_endpoint = len(mechanisms) == 2 and all(
        mechanism["pass"] for mechanism in mechanisms
    )
    gates = {
        "complete": len(turns) == expected and len(mechanisms) == 2,
        "structural_calibration": structural["pass"],
        "candidate_endpoint": candidate_endpoint,
        "actor_surface": surface["pass"],
        "schema_subset": unsupported_keywords(schema) == set(),
        "parse": all(turn["parse_error"] is None for turn in turns),
        "tools": all(turn["tool_calls"] == 0 for turn in turns),
        "hidden_authority": all(not turn["hidden_task_leakage"] for turn in turns),
        "fresh_threads": len({turn["thread_id"] for turn in turns}) == expected,
        "fresh_workspaces": len({turn["workspace"] for turn in turns}) == expected,
        "responses": all(len(values) == 1 for values in response_ids)
        and len(distinct_responses) == expected
        and distinct_responses == proxy_responses,
        "model": models == [acceptance["deployment_epoch"]["requested_model"]]
        and all(turn["deployment_effective_models"] == models for turn in turns),
        "catalog": len(catalogs) == 2
        and bool(catalogs[0])
        and catalogs[0] == catalogs[1],
        "etag": len(etags) == 1,
        "inventory": inventory_valid
        and all(turn["inventory_receipts"] == 1 for turn in turns),
        "collector": collector_errors == [],
        "usage_receipts": all(turn["usage"]["receipt_count"] >= 1 for turn in turns),
        "projection_budget": all(
            turn["current_projection_bytes"] <= INHERITANCE_LIMIT for turn in turns
        ),
        "per_turn_output_budget": all(
            turn["usage"]["output_tokens"]
            <= acceptance["resource_budget"]["output_tokens_per_turn"]
            for turn in turns
        ),
        "input_budget": usage["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total"],
        "wall_budget": elapsed <= acceptance["resource_budget"]["wall_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    validity_names = {
        "complete",
        "structural_calibration",
        "actor_surface",
        "schema_subset",
        "parse",
        "tools",
        "hidden_authority",
        "fresh_threads",
        "fresh_workspaces",
        "responses",
        "model",
        "catalog",
        "etag",
        "inventory",
        "collector",
        "usage_receipts",
        "projection_budget",
        "per_turn_output_budget",
        "input_budget",
        "output_budget",
        "wall_budget",
        "tests",
        "audit",
        "no_runtime_failure",
    }
    validity_pass = all(gates[name] for name in validity_names)
    disposition = (
        "invalidated"
        if not validity_pass
        else "promoted"
        if candidate_endpoint
        else "rejected"
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "candidate_errors": {
            mechanism["worker"]: mechanism["candidate_errors"]
            for mechanism in mechanisms
        },
        "pre_update_errors": {
            mechanism["worker"]: mechanism["pre_update_errors"]
            for mechanism in mechanisms
        },
        "frozen_first_errors": {
            mechanism["worker"]: mechanism["frozen_first_errors"]
            for mechanism in mechanisms
        },
        "frozen_second_errors": {
            mechanism["worker"]: mechanism["frozen_second_errors"]
            for mechanism in mechanisms
        },
        "structural_calibration": structural,
        "actor_surface": surface,
        "response_count": len(distinct_responses),
        "effective_models": models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed,
        "failure_type": failure_type,
        "validity_pass": validity_pass,
        "gates": gates,
        "disposition": disposition,
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
        raise RuntimeError("OT-0060 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution, codex_bin)
    task, task_bytes = read_sealed_json(task_manifest)
    validate_task(task)
    structural = structural_calibration(task["world"])
    if (
        sha256_bytes(task_bytes) != lock.get("task_sha256")
        or task["task_seed"] != lock.get("task_seed")
        or structural["receipt_sha256"] != lock.get("world_structural_receipt_sha256")
        or not structural["pass"]
    ):
        raise RuntimeError("OT-0060 private task or structural receipt differs")
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0060 output or workspace exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_counterbalance_config(load_json(repo / COUNTERBALANCE_PATH))
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
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
                        raise RuntimeError("OT-0060 frozen model unavailable")
                    worker_turns, mechanism, worker_inventories = execute_worker(
                        repo=repo,
                        task=task,
                        worker=worker,
                        client=active,
                        proxy=proxy,
                        model=model,
                        workspace_root=workspace,
                        prompt_template=prompt_template,
                        orientation=orientation,
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
            structural=structural,
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
            kind="categorical-predicate-representation-escape-candidate",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Private task, actor-authored predicates, hosted outputs, and deployment receipts remain private.",
                "A pass is one bounded representation-escape foothold and not developmental transfer or widened OT-2 evidence.",
                "The generic safe interpreter remains a researcher-built causal exoskeleton.",
            ],
            input_manifests=[
                str(OT59_MANIFEST_PATH),
                str(OT57_MANIFEST_PATH),
                str(OT48_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0060-harness")
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
