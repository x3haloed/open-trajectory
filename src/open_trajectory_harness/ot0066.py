from __future__ import annotations

import argparse
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
from .ot0049 import _turn_usage
from .ot0061 import require_hosted_schema
from .ot0065 import (
    INHERITANCE_LIMIT,
    MAX_MACHINE_STATES,
    SIDES,
    TARGET_RULES,
    MachineSnapshot,
    _fixed_control_vectors,
    _output_only_certificate,
    _overbudget_machine,
    attempt_update,
    complete_contact,
    compression_certificate,
    diagnostic_sequences,
    heldout_sequences,
    initial_snapshot,
    machine_errors,
    machine_output,
    project_snapshot,
    public_contact,
    reference_machine,
    restore_snapshot,
    snapshot_errors,
    stateless_certificate,
    topology_fingerprint,
    validate_machine,
)


EXPERIMENT_ID = "OT-0066"
ACCEPTANCE_PATH = Path("spec/ot-0066-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0066-run-lock.json")
PROMPT_PATH = Path("fixtures/ot-0066/actor-prompt.txt")
ORIENTATION_PATH = Path("fixtures/ot-0063/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0063/actor-output.schema.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
OT65_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0065/ot-0065-temporal-state-topology-calibration-001.json"
)
OT62_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0062/ot-0062-categorical-predicate-representation-escape-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0066-disjoint-temporal-topology-candidate-001"


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0066 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-disjoint-temporal-topology-candidate-task",
            }
        )
    )


def _ordered(task_seed: str, label: str, values: list[Any]) -> list[Any]:
    return sorted(
        values,
        key=lambda value: sha256_bytes(
            canonical_json(
                {"task_seed": task_seed, "label": label, "value": value}
            )
        ),
    )


def _private_cues(task_seed: str) -> tuple[str, str]:
    cues = [
        "cue-" + sha256_bytes(f"ot-0066:{task_seed}:cue:{index}".encode())[:12]
        for index in range(2)
    ]
    return cues[0], cues[1]


def _encode_sequence(bits: tuple[int, ...], cues: tuple[str, str]) -> list[str]:
    return [cues[value] for value in bits]


def _events(order: tuple[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": side,
            "selector_features": [0, 0, 0, 0],
            "on_flags": [f"side-{side}"],
        }
        for side in order
    ]


def _private_bundle(
    task_seed: str,
    regime_index: int,
    bundle_index: int,
    bits: tuple[int, ...],
    cues: tuple[str, str],
    target_rule: str,
) -> dict[str, Any]:
    from .ot0065 import _rule

    correct = _rule(target_rule, bits)
    presentations = []
    for trial in range(4):
        order = (
            SIDES
            if (bundle_index + trial + regime_index) % 2 == 0
            else tuple(reversed(SIDES))
        )
        presentations.append(
            {
                "presentation_id": sha256_bytes(
                    f"ot-0066:{task_seed}:{regime_index}:{bundle_index}:{trial}".encode()
                )[:20],
                "events": _events(order),
                "correct_side": correct,
            }
        )
    return {
        "bundle_id": "bundle-" + sha256_bytes(
            f"ot-0066:{task_seed}:{regime_index}:{bundle_index}".encode()
        )[:16],
        "cue_sequence": _encode_sequence(bits, cues),
        "presentations": presentations,
    }


def build_task(task_seed: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("OT-0066 task seed is malformed")
    from .ot0065 import _rule

    cues = _private_cues(task_seed)
    regimes = []
    for regime_index, target_rule in enumerate(TARGET_RULES, start=1):
        heldout_bits = heldout_sequences(regime_index)
        diagnostics = _ordered(
            task_seed,
            f"diagnostic-{regime_index}",
            diagnostic_sequences(target_rule, heldout_bits),
        )
        heldout_bits = _ordered(
            task_seed, f"heldout-{regime_index}", heldout_bits
        )
        regimes.append(
            {
                "index": regime_index,
                "target_rule": target_rule,
                "cues": cues,
                "contact": {
                    "cues": cues,
                    "bundles": [
                        _private_bundle(
                            task_seed,
                            regime_index,
                            index,
                            bits,
                            cues,
                            target_rule,
                        )
                        for index, bits in enumerate(diagnostics)
                    ],
                },
                "diagnostic_bits": diagnostics,
                "heldout": [
                    {
                        "cue_sequence": _encode_sequence(bits, cues),
                        "correct_side": _rule(target_rule, bits),
                    }
                    for bits in heldout_bits
                ],
                "heldout_bits": heldout_bits,
            }
        )
    world = {"cues": cues, "regimes": regimes}
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
        raise ValueError("OT-0066 task differs from its mechanical derivation")


def task_compression_certificate(
    regime: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    normalized = copy.deepcopy(regime)
    normalized["diagnostic_bits"] = [
        tuple(item) for item in normalized["diagnostic_bits"]
    ]
    normalized["heldout_bits"] = [
        tuple(item) for item in normalized["heldout_bits"]
    ]
    return compression_certificate(normalized, receipt)


def structural_calibration(task: dict[str, Any]) -> dict[str, Any]:
    validate_task(task)
    references = [
        reference_machine(regime["target_rule"], regime["cues"])
        for regime in task["world"]["regimes"]
    ]
    regimes = []
    for index, (regime, reference) in enumerate(
        zip(task["world"]["regimes"], references, strict=True)
    ):
        receipt = complete_contact(
            regime["contact"], ["left"] * len(regime["contact"]["bundles"])
        )
        overlap = {
            tuple(item) for item in regime["diagnostic_bits"]
        } & {tuple(item) for item in regime["heldout_bits"]}
        result = {
            "index": regime["index"],
            "reference_errors": machine_errors(
                reference, regime["heldout"], regime["cues"]
            ),
            "stateless": stateless_certificate(regime),
            "compression": task_compression_certificate(regime, receipt),
            "heldout_overlap_count": len(overlap),
            "topology_sha256": topology_fingerprint(reference, regime["cues"]),
            "output_only": (
                {"pass": True, "minimum_contact_errors": None}
                if index == 0
                else _output_only_certificate(references[index - 1], regime)
            ),
        }
        result["pass"] = (
            result["reference_errors"] == 0
            and result["stateless"]["pass"]
            and result["compression"]["pass"]
            and result["heldout_overlap_count"] == 0
            and result["output_only"]["pass"]
        )
        regimes.append(result)
    frozen_first = [
        machine_errors(references[0], regime["heldout"], regime["cues"])
        for regime in task["world"]["regimes"]
    ]
    frozen_second = [
        machine_errors(references[1], regime["heldout"], regime["cues"])
        for regime in task["world"]["regimes"]
    ]
    fixed = _fixed_control_vectors(task["world"], references)
    body = {
        "regimes": regimes,
        "reference_errors": [item["reference_errors"] for item in regimes],
        "frozen_first_errors": frozen_first,
        "frozen_second_errors": frozen_second,
        "fixed_controls": fixed,
    }
    body["pass"] = (
        all(item["pass"] for item in regimes)
        and body["reference_errors"] == [0, 0, 0]
        and frozen_first[1] == 8
        and frozen_second[2] == 8
        and fixed["pass"]
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": PROMPT_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0066.py"),
        "carrier_calibration_sha256": Path("src/open_trajectory_harness/ot0065.py"),
        "preflight_calibration_sha256": Path("src/open_trajectory_harness/ot0061.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path(
            "src/open_trajectory_harness/deployment_proxy.py"
        ),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0066_harness.py"),
        "test_sha256": Path("tests/test_ot0066.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "tool_receipt_patch_sha256": PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0065_manifest_sha256": OT65_MANIFEST_PATH,
        "ot0062_manifest_sha256": OT62_MANIFEST_PATH,
    }


def prepare_task_manifest(path: Path, implementation_commit: str) -> dict[str, Any]:
    task = build_task(expected_task_seed(implementation_commit))
    validate_task(task)
    structural = structural_calibration(task)
    if not structural["pass"]:
        raise RuntimeError("OT-0066 private world failed structural calibration")
    raw = canonical_json(task)
    task_sha256 = sha256_bytes(raw)
    write_sealed_json(path, task)
    return {
        "task_seed": task["task_seed"],
        "task_sha256": task_sha256,
        "task_bytes": len(raw),
        "world_structural_receipt_sha256": structural["receipt_sha256"],
    }


def validate_run_lock(repo: Path, execution: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0066 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0066 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0066 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0066 fixed input identity differs")
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
        raise RuntimeError(f"OT-0066 implementation changed after lock: {changed}")
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
        raise RuntimeError("OT-0066 backend or TLS identity differs")
    return lock


def actor_view(
    contact: dict[str, Any],
    choices: list[str],
    receipt: dict[str, Any],
    current: MachineSnapshot,
) -> dict[str, Any]:
    return {
        "current_snapshot": project_snapshot(current),
        "encounter": public_contact(contact),
        "prior_choices": choices,
        "completed_contact": receipt,
    }


def worker_contact(contact: dict[str, Any], worker: str) -> dict[str, Any]:
    transformed = copy.deepcopy(contact)
    if worker == "worker-2":
        transformed["bundles"].reverse()
        for bundle in transformed["bundles"]:
            bundle["presentations"].reverse()
            for presentation in bundle["presentations"]:
                presentation["events"].reverse()
    elif worker != "worker-1":
        raise ValueError("OT-0066 worker identity is unavailable")
    return transformed


def snapshot_choices(snapshot: MachineSnapshot, contact: dict[str, Any]) -> list[str]:
    machine = snapshot.state.get("machine")
    if machine is None:
        return ["left"] * len(contact["bundles"])
    return [
        machine_output(machine, bundle["cue_sequence"], contact["cues"])
        for bundle in contact["bundles"]
    ]


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
    choices = snapshot_choices(current, regime["contact"])
    receipt = complete_contact(regime["contact"], choices)
    view = actor_view(regime["contact"], choices, receipt, current)
    forbidden_keys = sorted(
        {"correct_side", "target_rule", "heldout", "heldout_bits"}
        & _collect_keys(view)
    )
    surface = prompt + orientation + canonical_json(schema).decode()
    forbidden_terms = sorted(
        term
        for term in ("parity", "suffix", "modulo", "mod3", "odd-a", "suffix-ab", "mod3-b-1")
        if term in surface.lower()
    )
    body = {
        "prompt_sha256": sha256_bytes(prompt.encode()),
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "concrete_cue_hits": re.findall(r"cue-[0-9a-f]{8,}", surface),
        "forbidden_terms": forbidden_terms,
        "serialized_forbidden_keys": forbidden_keys,
        "probe_sha256": sha256_bytes(canonical_json(view)),
    }
    return {
        **body,
        "pass": not body["concrete_cue_hits"]
        and not forbidden_terms
        and not forbidden_keys,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def machine_novelty(
    repo: Path,
    machine: dict[str, Any],
    parent: MachineSnapshot,
    cues: tuple[str, str],
) -> dict[str, Any]:
    try:
        validate_machine(machine, cues)
        machine_sha256 = sha256_bytes(canonical_json(machine))
        topology_sha256 = topology_fingerprint(machine, cues)
        valid = True
    except ValueError:
        machine_sha256 = None
        topology_sha256 = None
        valid = False
    serialized = canonical_json(machine).decode() if isinstance(machine, dict) else ""
    normalized = "".join(serialized.split())
    collision_paths = []
    for path in (PROMPT_PATH, ORIENTATION_PATH, SCHEMA_PATH):
        text = (repo / path).read_text(encoding="utf-8")
        if normalized and normalized in "".join(text.split()):
            collision_paths.append(str(path))
    parent_machine = parent.state.get("machine")
    body = {
        "machine_sha256": machine_sha256,
        "topology_sha256": topology_sha256,
        "parent_machine_sha256": (
            sha256_bytes(canonical_json(parent_machine))
            if parent_machine is not None
            else None
        ),
        "machine_differs_from_parent": canonical_json(parent_machine)
        != canonical_json(machine),
        "collision_paths": collision_paths,
        "valid": valid,
    }
    return {
        **body,
        "pass": valid
        and body["machine_differs_from_parent"]
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
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Author one bounded deterministic state machine and return only schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0066",
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
        or set(output) != {"start", "states"}
        or not isinstance(output["start"], str)
        or not isinstance(output["states"], list)
    ):
        parse_error = parse_error or "actor output failed its exact machine envelope"
        output = None
    machine = output if output is not None else {}
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
        machine,
        inventory,
    )


def _one_state_machine(machine: dict[str, Any], cues: tuple[str, str]) -> dict[str, Any]:
    states = {state["id"]: state for state in machine["states"]}
    output = states[machine["start"]]["output"]
    return {
        "start": "only",
        "states": [
            {
                "id": "only",
                "output": output,
                "edges": [{"cue": cue, "next": "only"} for cue in cues],
            }
        ],
    }


def _rewired_errors(
    machine: dict[str, Any], regime: dict[str, Any]
) -> int:
    states = {state["id"]: state for state in machine["states"]}
    start_output = states[machine["start"]]["output"]
    return sum(
        item["correct_side"] != start_output for item in regime["heldout"]
    )


def _fixed_output_errors(
    machine: dict[str, Any], regime: dict[str, Any], output: str
) -> int:
    replaced = copy.deepcopy(machine)
    for state in replaced["states"]:
        state["output"] = output
    return machine_errors(replaced, regime["heldout"], regime["cues"])


def safe_attempt_update(
    current: MachineSnapshot,
    machine: dict[str, Any],
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[MachineSnapshot, str]:
    try:
        return attempt_update(current, machine, receipt, contact)
    except ValueError:
        return current, "invalid"


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
    references = [
        reference_machine(regime["target_rule"], regime["cues"])
        for regime in world["regimes"]
    ]
    fixed_controls = _fixed_control_vectors(world, references)
    for regime in world["regimes"]:
        index = regime["index"]
        before = current
        contact = worker_contact(regime["contact"], worker)
        choices = snapshot_choices(before, contact)
        receipt = complete_contact(contact, choices)
        view = actor_view(contact, choices, receipt, before)
        hidden = [
            *[
                canonical_json(item["cue_sequence"]).decode()
                for item in regime["heldout"]
            ],
            regime["target_rule"],
            '"correct_side"',
            '"target_rule"',
            '"heldout"',
            '"heldout_bits"',
        ]
        turn, machine, inventory = run_actor_turn(
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
        after, update_reason = safe_attempt_update(before, machine, receipt, contact)
        snapshots[after.sha256] = after
        no_credit, no_credit_reason = safe_attempt_update(before, machine, None, contact)
        invalid, invalid_reason = safe_attempt_update(
            before, {"start": 0, "states": []}, receipt, contact
        )
        incomplete_machine = {
            "start": "only",
            "states": [
                {
                    "id": "only",
                    "output": "left",
                    "edges": [{"cue": contact["cues"][0], "next": "only"}],
                }
            ],
        }
        incomplete, incomplete_reason = safe_attempt_update(
            before, incomplete_machine, receipt, contact
        )
        unreachable_machine = {
            "start": "start",
            "states": [
                {
                    "id": state_id,
                    "output": "left",
                    "edges": [{"cue": cue, "next": state_id} for cue in contact["cues"]],
                }
                for state_id in ("start", "unreachable")
            ],
        }
        unreachable, unreachable_reason = safe_attempt_update(
            before, unreachable_machine, receipt, contact
        )
        oversized, oversized_reason = safe_attempt_update(
            before, _overbudget_machine(contact["cues"]), receipt, contact
        )
        imperfect_machine = {
            "start": "only",
            "states": [
                {
                    "id": "only",
                    "output": "left",
                    "edges": [
                        {"cue": cue, "next": "only"} for cue in contact["cues"]
                    ],
                }
            ],
        }
        imperfect, imperfect_reason = safe_attempt_update(
            before, imperfect_machine, receipt, contact
        )
        if after.sha256 != before.sha256:
            parent = restore_snapshot(project_snapshot(snapshots[after.parent_sha256]))
        else:
            parent = before
        if index == 1:
            first_learned = after
        elif index == 2:
            second_learned = after
        pre_errors = snapshot_errors(before, regime)
        candidate_errors = snapshot_errors(after, regime)
        novelty = machine_novelty(repo, machine, before, regime["cues"])
        replay_errors = snapshot_errors(restore_snapshot(project_snapshot(after)), regime)
        compression = task_compression_certificate(regime, receipt)
        try:
            validate_machine(machine, regime["cues"])
            machine_bytes = len(canonical_json(machine))
            machine_states = len(machine["states"])
            candidate_topology = topology_fingerprint(machine, regime["cues"])
            parent_machine = before.state.get("machine")
            topology_changed = parent_machine is None or candidate_topology != topology_fingerprint(
                parent_machine, regime["cues"]
            )
            output_only = (
                {"pass": True, "minimum_contact_errors": None}
                if parent_machine is None
                else _output_only_certificate(parent_machine, regime)
            )
            one_state_errors = machine_errors(
                _one_state_machine(machine, regime["cues"]),
                regime["heldout"],
                regime["cues"],
            )
            rewired_errors = _rewired_errors(machine, regime)
            fixed_output_errors = [
                _fixed_output_errors(machine, regime, side) for side in SIDES
            ]
        except (KeyError, TypeError, ValueError):
            machine_bytes = len(canonical_json(machine)) if isinstance(machine, dict) else 0
            machine_states = None
            candidate_topology = None
            topology_changed = False
            output_only = {"pass": False, "minimum_contact_errors": None}
            one_state_errors = rewired_errors = None
            fixed_output_errors = []
        regime_result = {
            "index": index,
            "pre_update_errors": pre_errors,
            "candidate_errors": candidate_errors,
            "update_reason": update_reason,
            "machine_sha256": sha256_bytes(canonical_json(machine)),
            "machine_bytes": machine_bytes,
            "machine_states": machine_states,
            "topology_sha256": candidate_topology,
            "topology_changed": topology_changed,
            "output_only_correction": output_only,
            "committed_bytes": len(canonical_json(project_snapshot(after))),
            "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
            "no_credit_reason": no_credit_reason,
            "unchanged_errors": pre_errors,
            "no_persistence_errors": snapshot_errors(initial, regime),
            "digest_errors": snapshot_errors(initial, regime),
            "verbatim_error_vector": compression["allowed_replay_errors"],
            "complete_deletion_errors": snapshot_errors(initial, regime),
            "one_state_ablation_errors": one_state_errors,
            "rewired_ablation_errors": rewired_errors,
            "fixed_output_ablation_errors": fixed_output_errors,
            "frozen_first_errors": snapshot_errors(
                first_learned if first_learned is not None else after, regime
            ),
            "frozen_second_errors": snapshot_errors(
                second_learned if second_learned is not None else after, regime
            ),
            "stateless_certificate": stateless_certificate(regime),
            "invalid_preserved_parent": invalid.sha256 == before.sha256,
            "invalid_reason": invalid_reason,
            "incomplete_preserved_parent": incomplete.sha256 == before.sha256,
            "incomplete_reason": incomplete_reason,
            "unreachable_preserved_parent": unreachable.sha256 == before.sha256,
            "unreachable_reason": unreachable_reason,
            "oversized_preserved_parent": oversized.sha256 == before.sha256,
            "oversized_reason": oversized_reason,
            "contact_imperfect_preserved_parent": imperfect.sha256 == before.sha256,
            "contact_imperfect_reason": imperfect_reason,
            "parent_exact": parent.sha256 == before.sha256,
            "successor_exact": restore_snapshot(project_snapshot(after)).sha256
            == after.sha256,
            "rollback_errors": snapshot_errors(parent, regime),
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
        "fixed_controls": fixed_controls,
    }
    body["pass"] = (
        body["candidate_errors"] == [0, 0, 0]
        and body["pre_update_errors"][0] == 4
        and body["pre_update_errors"][1] == 8
        and body["pre_update_errors"][2] == 8
        and body["frozen_first_errors"][1] == 8
        and body["frozen_second_errors"][2] == 8
        and fixed_controls["pass"]
        and all(
            item["update_reason"] == "committed"
            and item["machine_bytes"] <= INHERITANCE_LIMIT
            and item["machine_states"] <= MAX_MACHINE_STATES
            and item["committed_bytes"] <= INHERITANCE_LIMIT
            and item["no_credit_preserved_parent"]
            and item["no_credit_reason"] == "no-credit"
            and item["unchanged_errors"] >= 1
            and item["no_persistence_errors"] == 4
            and item["digest_errors"] == 4
            and all(value == 4 for value in item["verbatim_error_vector"])
            and item["complete_deletion_errors"] >= 1
            and item["one_state_ablation_errors"] >= 1
            and item["rewired_ablation_errors"] >= 1
            and all(value >= 1 for value in item["fixed_output_ablation_errors"])
            and item["stateless_certificate"]["pass"]
            and item["topology_changed"]
            and item["output_only_correction"]["pass"]
            and item["invalid_preserved_parent"]
            and item["invalid_reason"] == "invalid"
            and item["incomplete_preserved_parent"]
            and item["incomplete_reason"] == "invalid"
            and item["unreachable_preserved_parent"]
            and item["unreachable_reason"] == "invalid"
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
    preflight: dict[str, Any],
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
        "prehosted_preflight": preflight["pass"],
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
        "prehosted_preflight",
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
        "prehosted_preflight": preflight,
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
        raise RuntimeError("OT-0066 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution, codex_bin)
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task, task_bytes = read_sealed_json(task_manifest)
    validate_task(task)
    structural = structural_calibration(task)
    if (
        sha256_bytes(task_bytes) != lock.get("task_sha256")
        or task["task_seed"] != lock.get("task_seed")
        or structural["receipt_sha256"] != lock.get("world_structural_receipt_sha256")
        or not structural["pass"]
    ):
        raise RuntimeError("OT-0066 private task or structural receipt differs")
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0066 output or workspace exists")
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    preflight = require_hosted_schema(schema)
    surface_preflight = actor_surface_authority(repo)
    if not surface_preflight["pass"]:
        raise RuntimeError("OT-0066 actor surface failed before hosted execution")
    preflight_tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    preflight_audit = subprocess.run(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    preflight = {
        **preflight,
        "actor_surface_receipt_sha256": surface_preflight["receipt_sha256"],
        "tests_returncode": preflight_tests.returncode,
        "tests_stdout_sha256": sha256_bytes(preflight_tests.stdout.encode()),
        "tests_stderr_sha256": sha256_bytes(preflight_tests.stderr.encode()),
        "audit_returncode": preflight_audit.returncode,
        "audit_stdout_sha256": sha256_bytes(preflight_audit.stdout.encode()),
        "audit_stderr_sha256": sha256_bytes(preflight_audit.stderr.encode()),
    }
    preflight["pass"] = (
        preflight["pass"]
        and preflight_tests.returncode == 0
        and preflight_audit.returncode == 0
    )
    if not preflight["pass"]:
        raise RuntimeError("OT-0066 local preflight failed before hosted execution")
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
                        raise RuntimeError("OT-0066 frozen model unavailable")
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
            preflight=preflight,
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
            kind="disjoint-temporal-topology-representation-escape-candidate",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Private task, actor-authored machines, hosted outputs, and deployment receipts remain private.",
                "A pass is one bounded representation-escape foothold and not developmental transfer or widened OT-2 evidence.",
                "The generic finite-state interpreter remains a researcher-built causal exoskeleton.",
            ],
            input_manifests=[
                str(OT65_MANIFEST_PATH),
                str(OT62_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0066-harness")
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
