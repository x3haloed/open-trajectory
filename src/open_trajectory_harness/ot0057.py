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
from .ot0048 import complete_contact, score
from .ot0049 import _turn_usage
from .ot0049_world import counterbalanced_split, validate_counterbalance_config
from .ot0056 import (
    BALANCED_CODES,
    FLAG_COUNT,
    all_real_weight_certificate,
    compression_certificate,
    diagnostic_contact,
    exact_rows,
    initial_snapshot,
    project_snapshot,
    public_split,
    reference_snapshot,
    restore_snapshot,
    snapshot_selections,
)


EXPERIMENT_ID = "OT-0057"
ACCEPTANCE_PATH = Path("spec/ot-0057-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0057-run-lock.json")
PROMPT_PATH = Path("fixtures/ot-0057/application-prompt.txt")
SCHEMA_PATH = Path("fixtures/ot-0057/application-output.schema.json")
COUNTERBALANCE_PATH = Path("fixtures/ot-0049/counterbalance.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
OT56_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0056/ot-0056-categorical-compression-world-calibration-001.json"
)
OT55_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0055/ot-0055-descriptive-rule-application-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0057-categorical-description-application-calibration-001"
CONDITIONS = ("reference", "opaque", "verbatim")


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0057 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-categorical-description-application-task",
            }
        )
    )


def _private_flags(task_seed: str) -> tuple[str, ...]:
    return tuple(
        "flag-" + sha256_bytes(f"ot0057:{task_seed}:{index}".encode())[:12]
        for index in range(FLAG_COUNT)
    )


def build_task(task_seed: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("OT-0057 task seed is malformed")
    flags = _private_flags(task_seed)
    first_target = int(task_seed[:8], 16) % FLAG_COUNT
    first_polarity = "on" if int(task_seed[8], 16) % 2 == 0 else "off"
    third_target = (first_target + 1 + int(task_seed[9:17], 16) % 15) % FLAG_COUNT
    regimes_spec = (
        (first_target, first_polarity),
        (first_target, "off" if first_polarity == "on" else "on"),
        (third_target, first_polarity),
    )
    regimes = []
    for offset, (target_index, polarity) in enumerate(regimes_spec):
        regime_index = offset + 1
        regimes.append(
            {
                "index": regime_index,
                "target_flag": flags[target_index],
                "target_index": target_index,
                "polarity": polarity,
                "contact": diagnostic_contact(
                    flags, target_index, polarity, regime_index
                ),
                "canary": _categorical_canary(
                    flags, target_index, polarity, regime_index
                ),
            }
        )
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "task_seed": task_seed,
        "flags": list(flags),
        "regimes": regimes,
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def _categorical_canary(
    flags: tuple[str, ...], target_index: int, polarity: str, regime_index: int
) -> dict[str, Any]:
    target = flags[target_index]
    pairs = []
    for bit in range(len(BALANCED_CODES[0])):
        on_a = [
            flag for index, flag in enumerate(flags) if BALANCED_CODES[index][bit] == 1
        ]
        on_b = [flag for flag in flags if flag not in on_a]
        events = [
            {
                "event_id": f"r{regime_index}-c{bit:02d}-a",
                "selector_features": [0, 0, 0, 0],
                "on_flags": sorted(on_a),
            },
            {
                "event_id": f"r{regime_index}-c{bit:02d}-b",
                "selector_features": [0, 0, 0, 0],
                "on_flags": sorted(on_b),
            },
        ]
        desired = polarity == "on"
        preferred = next(
            event["event_id"]
            for event in events
            if (target in event["on_flags"]) is desired
        )
        pairs.append(
            {
                "pattern_id": f"r{regime_index}-canary-{bit:02d}",
                "events": events,
                "preferred_event_id": preferred,
            }
        )
    return {"pairs": pairs}


def validate_task(task: dict[str, Any]) -> None:
    if (
        task.get("schema_version") != 1
        or task.get("experiment_id") != EXPERIMENT_ID
        or not re.fullmatch(r"[0-9a-f]{64}", task.get("task_seed", ""))
        or canonical_json(build_task(task.get("task_seed", ""))) != canonical_json(task)
    ):
        raise ValueError("OT-0057 task differs from its mechanical derivation")


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": PROMPT_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "counterbalance_sha256": COUNTERBALANCE_PATH,
        "application_harness_sha256": Path("src/open_trajectory_harness/ot0057.py"),
        "world_calibration_sha256": Path("src/open_trajectory_harness/ot0056.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path(
            "src/open_trajectory_harness/deployment_proxy.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0057_harness.py"),
        "test_sha256": Path("tests/test_ot0057.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "tool_receipt_patch_sha256": PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0056_manifest_sha256": OT56_MANIFEST_PATH,
        "ot0055_manifest_sha256": OT55_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def structural_calibration(task: dict[str, Any]) -> dict[str, Any]:
    validate_task(task)
    current = initial_snapshot()
    initial = current
    first_learned = None
    second_learned = None
    regimes = []
    for regime in task["regimes"]:
        before = current
        choices = snapshot_selections(before, regime["contact"])
        receipt = complete_contact(regime["contact"], choices)
        rows = exact_rows(regime["contact"], choices, receipt)
        canary = regime["canary"]
        certificate = compression_certificate(task, regime, rows, canary)
        corrected = reference_snapshot(
            before, regime["target_flag"], regime["polarity"], receipt
        )
        parent = restore_snapshot(project_snapshot(before))
        if regime["index"] == 1:
            first_learned = corrected
        elif regime["index"] == 2:
            second_learned = corrected
        regimes.append(
            {
                "index": regime["index"],
                "pre_update_errors": score(canary, snapshot_selections(before, canary)),
                "reference_errors": score(
                    canary, snapshot_selections(corrected, canary)
                ),
                "no_state_errors": score(canary, snapshot_selections(initial, canary)),
                "frozen_first_errors": score(
                    canary,
                    snapshot_selections(
                        first_learned if first_learned is not None else corrected,
                        canary,
                    ),
                ),
                "frozen_second_errors": score(
                    canary,
                    snapshot_selections(
                        second_learned if second_learned is not None else corrected,
                        canary,
                    ),
                ),
                "all_real_weight_certificate": all_real_weight_certificate(canary),
                "compression_certificate": certificate,
                "parent_exact": parent.sha256 == before.sha256,
                "successor_exact": restore_snapshot(project_snapshot(corrected)).sha256
                == corrected.sha256,
                "rollback_errors": score(canary, snapshot_selections(parent, canary)),
            }
        )
        current = corrected
    body = {
        "task_sha256": task["task_sha256"],
        "regimes": regimes,
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "reference_errors": [item["reference_errors"] for item in regimes],
        "no_state_errors": [item["no_state_errors"] for item in regimes],
        "frozen_first_errors": [item["frozen_first_errors"] for item in regimes],
        "frozen_second_errors": [item["frozen_second_errors"] for item in regimes],
        "maximum_allowed_rows": max(
            item["compression_certificate"]["maximum_allowed_rows"] for item in regimes
        ),
        "minimum_surviving_hypotheses": min(
            item["compression_certificate"]["minimum_surviving_hypotheses"]
            for item in regimes
        ),
    }
    body["pass"] = (
        body["pre_update_errors"][0] == 4
        and body["pre_update_errors"][1] == 8
        and body["pre_update_errors"][2] >= 1
        and body["reference_errors"] == [0, 0, 0]
        and body["no_state_errors"] == [4, 4, 4]
        and body["frozen_first_errors"][1] == 8
        and body["frozen_second_errors"][2] >= 1
        and body["maximum_allowed_rows"] == 1
        and body["minimum_surviving_hypotheses"] >= 15
        and all(
            item["all_real_weight_certificate"]["pass"]
            and item["compression_certificate"]["pass"]
            and item["parent_exact"]
            and item["successor_exact"]
            and item["rollback_errors"] == item["pre_update_errors"]
            for item in regimes
        )
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def prepare_task_manifest(path: Path, implementation_commit: str) -> dict[str, Any]:
    task = build_task(expected_task_seed(implementation_commit))
    structural = structural_calibration(task)
    if not structural["pass"]:
        raise RuntimeError("OT-0057 private task failed structural calibration")
    write_sealed_json(path, task)
    raw = canonical_json(task)
    return {
        "task_seed": task["task_seed"],
        "task_sha256": sha256_bytes(raw),
        "task_bytes": len(raw),
        "structural_receipt_sha256": structural["receipt_sha256"],
    }


def validate_run_lock(repo: Path, execution: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0057 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0057 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0057 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0057 fixed input identity differs")
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
        raise RuntimeError(f"OT-0057 implementation changed after lock: {changed}")
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
        raise RuntimeError("OT-0057 backend or TLS identity differs")
    return lock


def _pad_projection(content: str, target: int) -> dict[str, str]:
    projection = {"content": content, "padding": ""}
    delta = target - len(canonical_json(projection))
    if delta < 0:
        raise ValueError("OT-0057 state projection target is too small")
    projection["padding"] = "p" * delta
    if len(canonical_json(projection)) != target:
        raise ValueError("OT-0057 state projection padding differs")
    return projection


def reference_description(target_flag: str, polarity: str) -> str:
    relation = "includes" if polarity == "on" else "does not include"
    return (
        "For every pair, select the event whose on_flags list "
        f'{relation} the exact flag "{target_flag}". '
        "If this does not distinguish the events, select the lexicographically "
        "earlier event identifier."
    )


def equal_state_projections(
    *,
    task_seed: str,
    worker: str,
    regime_index: int,
    target_flag: str,
    polarity: str,
    rows: list[dict[str, Any]],
    byte_limit: int,
) -> tuple[dict[str, dict[str, str]], int]:
    row_index = int(
        sha256_bytes(
            canonical_json(
                {
                    "task_seed": task_seed,
                    "worker": worker,
                    "regime_index": regime_index,
                    "kind": "one-row-verbatim-control",
                }
            )
        )[:8],
        16,
    ) % len(rows)
    contents = {
        "reference": reference_description(target_flag, polarity),
        "opaque": "Opaque retained material: "
        + sha256_bytes(
            canonical_json(
                {
                    "task_seed": task_seed,
                    "worker": worker,
                    "regime_index": regime_index,
                    "kind": "opaque-state-control",
                }
            )
        )
        * 3,
        "verbatim": canonical_json({"rows": [rows[row_index]]}).decode(),
    }
    target = (
        max(
            len(canonical_json({"content": value, "padding": ""}))
            for value in contents.values()
        )
        + 64
    )
    if target > byte_limit:
        raise ValueError("OT-0057 equal state projection exceeds its bound")
    projections = {
        condition: _pad_projection(content, target)
        for condition, content in contents.items()
    }
    if len({len(canonical_json(value)) for value in projections.values()}) != 1:
        raise ValueError("OT-0057 condition state bytes differ")
    return projections, row_index


def application_view(canary: dict[str, Any], state: dict[str, str]) -> dict[str, Any]:
    return {"state": state, "pairs": public_split(canary)["pairs"]}


def actor_surface_authority(repo: Path) -> dict[str, Any]:
    prompt = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    forbidden = {"preferred_event_id", "target_flag", '"polarity"', "solution"}
    hits = sorted(term for term in forbidden if term in prompt.lower())
    task = build_task("0" * 64)
    probe = application_view(
        task["regimes"][0]["canary"], {"content": "opaque", "padding": ""}
    )

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(
                *(keys(item) for item in value.values()), set()
            )
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()

    body = {
        "prompt_sha256": sha256_bytes(prompt.encode()),
        "prompt_forbidden_hits": hits,
        "serialized_forbidden_keys": sorted(
            {"preferred_event_id", "target_flag", "polarity"} & keys(probe)
        ),
        "probe_sha256": sha256_bytes(canonical_json(probe)),
    }
    return {
        **body,
        "pass": not hits and not body["serialized_forbidden_keys"],
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_application_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    prompt_template: str,
    schema: dict[str, Any],
    view: dict[str, Any],
    canary: dict[str, Any],
    worker: str,
    regime_index: int,
    condition: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Apply only the supplied state to the supplied pairs and return schema-conforming choices.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0057",
        }
    )
    prompt = prompt_template.replace(
        "{{APPLICATION_VIEW}}", canonical_json(view).decode()
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
        parse_error = parse_error or "application turn did not complete"
    choices = output.get("choices") if isinstance(output, dict) else None
    if (
        not isinstance(output, dict)
        or set(output) != {"choices"}
        or not isinstance(choices, list)
        or len(choices) != len(canary["pairs"])
        or not all(isinstance(item, str) for item in choices)
        or any(
            choice not in {event["event_id"] for event in pair["events"]}
            for choice, pair in zip(choices, canary["pairs"], strict=True)
        )
    ):
        parse_error = (
            parse_error or "application output failed its exact choice envelope"
        )
        choices = []
    response_ids = sorted(
        {item["value"] for item in deployment if item["kind"] == "response_id"}
    )
    models = sorted(
        {item["value"] for item in deployment if item["kind"] == "effective_model"}
    )
    hidden_keys = ['"preferred_event_id"', '"target_flag"', '"polarity"']
    return (
        {
            "worker": worker,
            "regime_index": regime_index,
            "condition": condition,
            "workspace": str(workspace.resolve()),
            "thread_id": thread["id"],
            "thread_session_id": thread.get("sessionId"),
            "application_view": view,
            "actor_output": output,
            "choices": choices,
            "errors": score(canary, choices) if choices else None,
            "parse_error": parse_error,
            "tool_calls": client.completed_turn_tool_calls(
                thread_id=thread["id"], turn_id=turn["id"]
            ),
            "inventory_receipts": len(inventories) - inventory_before,
            "deployment_receipts": deployment,
            "deployment_effective_models": models,
            "deployment_response_ids": response_ids,
            "hidden_task_leakage": [
                marker for marker in hidden_keys if marker in prompt
            ],
            "usage": _turn_usage(client.raw_events[event_before:], thread["id"]),
            "state_projection_bytes": len(canonical_json(view["state"])),
            "encounter_sha256": sha256_bytes(canonical_json(view["pairs"])),
            "turn": turn,
        },
        inventory,
    )


def execute_worker(
    *,
    task: dict[str, Any],
    worker: str,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace_root: Path,
    prompt_template: str,
    schema: dict[str, Any],
    byte_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[list[dict[str, Any]]]]:
    turns: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    regimes = []
    current = initial_snapshot()
    condition_order = (
        CONDITIONS if worker == "worker-1" else tuple(reversed(CONDITIONS))
    )
    for regime in task["regimes"]:
        index = regime["index"]
        contact = counterbalanced_split(regime["contact"], worker)
        canary = counterbalanced_split(regime["canary"], worker)
        choices = snapshot_selections(current, contact)
        receipt = complete_contact(contact, choices)
        rows = exact_rows(contact, choices, receipt)
        projections, row_index = equal_state_projections(
            task_seed=task["task_seed"],
            worker=worker,
            regime_index=index,
            target_flag=regime["target_flag"],
            polarity=regime["polarity"],
            rows=rows,
            byte_limit=byte_limit,
        )
        condition_errors = {}
        state_hashes = {}
        encounter_hashes = {}
        for condition in condition_order:
            view = application_view(canary, projections[condition])
            result, inventory = run_application_turn(
                client=client,
                proxy=proxy,
                model=model,
                workspace=workspace_root / worker / f"regime-{index}-{condition}",
                prompt_template=prompt_template,
                schema=schema,
                view=view,
                canary=canary,
                worker=worker,
                regime_index=index,
                condition=condition,
            )
            turns.append(result)
            inventories.append(inventory)
            condition_errors[condition] = result["errors"]
            state_hashes[condition] = sha256_bytes(
                canonical_json(projections[condition])
            )
            encounter_hashes[condition] = result["encounter_sha256"]
        regimes.append(
            {
                "index": index,
                "errors": condition_errors,
                "verbatim_row_index": row_index,
                "state_projection_bytes": {
                    condition: len(canonical_json(value))
                    for condition, value in projections.items()
                },
                "state_sha256s": state_hashes,
                "encounter_sha256s": encounter_hashes,
            }
        )
        current = reference_snapshot(
            current, regime["target_flag"], regime["polarity"], receipt
        )
    body = {
        "worker": worker,
        "condition_order": list(condition_order),
        "regimes": regimes,
        "reference_errors": [item["errors"]["reference"] for item in regimes],
        "opaque_errors": [item["errors"]["opaque"] for item in regimes],
        "verbatim_errors": [item["errors"]["verbatim"] for item in regimes],
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
    reference_endpoint = len(mechanisms) == 2 and all(
        item["reference_errors"] == [0, 0, 0] for item in mechanisms
    )
    controls_fail = len(mechanisms) == 2 and all(
        all(value is not None and value >= 1 for value in item["opaque_errors"])
        and all(value is not None and value >= 1 for value in item["verbatim_errors"])
        for item in mechanisms
    )
    equal_states = all(
        len(set(regime["state_projection_bytes"].values())) == 1
        and max(regime["state_projection_bytes"].values())
        <= acceptance["maximum_state_projection_bytes"]
        and len(set(regime["encounter_sha256s"].values())) == 1
        and len(set(regime["state_sha256s"].values())) == len(CONDITIONS)
        for item in mechanisms
        for regime in item["regimes"]
    )
    gates = {
        "complete": len(turns) == expected and len(mechanisms) == 2,
        "structural_calibration": structural["pass"]
        and structural["maximum_allowed_rows"] == acceptance["maximum_verbatim_rows"]
        and structural["minimum_surviving_hypotheses"]
        >= acceptance["minimum_surviving_hypotheses"],
        "reference_endpoint": reference_endpoint,
        "controls_fail": controls_fail,
        "equal_state_and_encounter": equal_states,
        "actor_surface": surface["pass"],
        "candidate_free": not any("learner_output" in item for item in turns),
        "schema_subset": unsupported_keywords(schema) == set(),
        "parse": all(item["parse_error"] is None for item in turns),
        "tools": all(item["tool_calls"] == 0 for item in turns),
        "hidden_authority": all(not item["hidden_task_leakage"] for item in turns),
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
        "input_budget": usage["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total"],
        "wall_budget": elapsed <= acceptance["resource_budget"]["wall_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    validity_gate_names = {
        "complete",
        "structural_calibration",
        "equal_state_and_encounter",
        "actor_surface",
        "candidate_free",
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
        "per_turn_output_budget",
        "input_budget",
        "output_budget",
        "wall_budget",
        "tests",
        "audit",
        "no_runtime_failure",
    }
    validity_pass = all(gates[name] for name in validity_gate_names)
    scientific_pass = gates["reference_endpoint"] and gates["controls_fail"]
    disposition = (
        "invalidated"
        if not validity_pass
        else "promoted"
        if scientific_pass
        else "rejected"
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "reference_errors": {
            item["worker"]: item["reference_errors"] for item in mechanisms
        },
        "opaque_errors": {item["worker"]: item["opaque_errors"] for item in mechanisms},
        "verbatim_errors": {
            item["worker"]: item["verbatim_errors"] for item in mechanisms
        },
        "structural_calibration": structural,
        "actor_surface": surface,
        "candidate_learner_outputs": False,
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
        raise RuntimeError("OT-0057 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution, codex_bin)
    task, task_bytes = read_sealed_json(task_manifest)
    validate_task(task)
    structural = structural_calibration(task)
    if (
        sha256_bytes(task_bytes) != lock.get("task_sha256")
        or task["task_seed"] != lock.get("task_seed")
        or structural["receipt_sha256"] != lock.get("structural_receipt_sha256")
        or not structural["pass"]
    ):
        raise RuntimeError("OT-0057 private task or structural receipt differs")
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0057 output or workspace exists")
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
                        raise RuntimeError("OT-0057 frozen model unavailable")
                    worker_turns, mechanism, worker_inventories = execute_worker(
                        task=task,
                        worker=worker,
                        client=active,
                        proxy=proxy,
                        model=model,
                        workspace_root=workspace,
                        prompt_template=prompt_template,
                        schema=schema,
                        byte_limit=acceptance["maximum_state_projection_bytes"],
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
        "application_results": turns,
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
            kind="categorical-description-application-candidate-free-hosted-calibration",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Private task, reference descriptions, hosted outputs, and deployment receipts remain private.",
                "Controller-authored descriptions prove carrier application only and are not endogenous evidence.",
                "A pass authorizes at most one fresh OT-0058 learner and is not representation-escape evidence.",
            ],
            input_manifests=[
                str(OT56_MANIFEST_PATH),
                str(OT55_MANIFEST_PATH),
                str(OT48_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0057-harness")
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
