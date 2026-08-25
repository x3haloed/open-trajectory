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

from . import ot0066 as hosted
from . import ot0067 as relational
from . import ot0068 as calibrated
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


EXPERIMENT_ID = "OT-0069"
ACCEPTANCE_PATH = Path("spec/ot-0069-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0069-run-lock.json")
PROMPT_PATH = Path("fixtures/ot-0069/actor-prompt.txt")
ORIENTATION_PATH = Path("fixtures/ot-0069/actor-orientation.txt")
SCHEMA_PATH = Path("fixtures/ot-0069/actor-output.schema.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
OT68_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0068/ot-0068-identifiable-equivalence-calibration-001.json"
)
OT67_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0067/ot-0067-equivalence-partition-calibration-001.json"
)
OT66_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0066/ot-0066-disjoint-temporal-topology-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0069-equivalence-partition-candidate-001"
INHERITANCE_LIMIT = 620
SIDES = relational.SIDES
TARGET_LABELS = calibrated.TARGET_LABELS
HELDOUT_PAIRS = calibrated.HELDOUT_PAIRS
PARTITION_HYPOTHESES = relational.PARTITION_HYPOTHESES


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0069 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-equivalence-partition-candidate-task",
            }
        )
    )


def _ordered(task_seed: str, label: str, values: list[Any]) -> list[Any]:
    return sorted(
        values,
        key=lambda value: sha256_bytes(
            canonical_json({"task_seed": task_seed, "label": label, "value": value})
        ),
    )


def _private_symbols(task_seed: str) -> tuple[str, ...]:
    values = [
        "symbol-"
        + sha256_bytes(f"ot-0069:{task_seed}:symbol:{index}".encode())[:12]
        for index in range(8)
    ]
    return tuple(_ordered(task_seed, "symbols", values))


def _events(task_seed: str, regime_index: int, bundle_index: int) -> list[dict[str, Any]]:
    even = int(
        sha256_bytes(
            f"ot-0069:{task_seed}:{regime_index}:{bundle_index}:events".encode()
        )[:2],
        16,
    ) % 2 == 0
    order = SIDES if even else tuple(reversed(SIDES))
    return [
        {
            "event_id": side,
            "selector_features": [0, 0, 0, 0],
            "on_flags": [f"side-{side}"],
        }
        for side in order
    ]


def _bundle(
    task_seed: str,
    regime_index: int,
    bundle_index: int,
    pair: tuple[int, int],
    symbols: tuple[str, ...],
    target: tuple[int, ...],
) -> dict[str, Any]:
    return {
        "bundle_id": "bundle-"
        + sha256_bytes(
            f"ot-0069:{task_seed}:{regime_index}:{bundle_index}".encode()
        )[:16],
        "query_symbols": [symbols[pair[0]], symbols[pair[1]]],
        "presentations": [
            {
                "presentation_id": sha256_bytes(
                    f"ot-0069:{task_seed}:{regime_index}:{bundle_index}:0".encode()
                )[:20],
                "events": _events(task_seed, regime_index, bundle_index),
                "correct_side": relational.resolved_side(target, pair),
            }
        ],
    }


def build_task(task_seed: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("OT-0069 task seed is malformed")
    symbols = _private_symbols(task_seed)
    regimes = []
    for regime_index, target in enumerate(TARGET_LABELS, start=1):
        heldout_pairs = list(HELDOUT_PAIRS[regime_index])
        diagnostics = calibrated.diagnostic_pairs(target, heldout_pairs)
        diagnostics = _ordered(task_seed, f"diagnostics-{regime_index}", diagnostics)
        heldout_pairs = _ordered(task_seed, f"heldout-{regime_index}", heldout_pairs)
        regimes.append(
            {
                "index": regime_index,
                "target_labels": target,
                "symbols": symbols,
                "contact": {
                    "symbols": symbols,
                    "bundles": [
                        _bundle(
                            task_seed,
                            regime_index,
                            index,
                            tuple(pair),
                            symbols,
                            target,
                        )
                        for index, pair in enumerate(diagnostics)
                    ],
                },
                "diagnostic_pairs": diagnostics,
                "heldout": [
                    {
                        "query_symbols": [symbols[pair[0]], symbols[pair[1]]],
                        "correct_side": relational.resolved_side(target, pair),
                    }
                    for pair in heldout_pairs
                ],
                "heldout_pairs": heldout_pairs,
            }
        )
    world = {"symbols": symbols, "regimes": regimes}
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
        raise ValueError("OT-0069 task differs from its mechanical derivation")


def public_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbols": list(contact["symbols"]),
        "bundles": [
            {
                "bundle_id": bundle["bundle_id"],
                "query_symbols": bundle["query_symbols"],
                "presentations": [
                    {
                        "presentation_id": item["presentation_id"],
                        "events": item["events"],
                    }
                    for item in bundle["presentations"]
                ],
            }
            for bundle in contact["bundles"]
        ],
    }


def complete_contact(contact: dict[str, Any], choices: list[str]) -> dict[str, Any]:
    if len(choices) != len(contact["bundles"]) or any(choice not in SIDES for choice in choices):
        raise ValueError("OT-0069 contact choices are malformed")
    outcomes = []
    for bundle, choice in zip(contact["bundles"], choices, strict=True):
        correct = bundle["presentations"][0]["correct_side"]
        outcomes.append(
            {
                "bundle_id": bundle["bundle_id"],
                "selected_side": choice,
                "resolved_side": correct,
                "success": choice == correct,
            }
        )
    body = {"kind": "ot-0069-completed-contact", "outcomes": outcomes}
    return {**body, "sha256": sha256_bytes(canonical_json(body))}


def reference_partition(regime: dict[str, Any]) -> dict[str, Any]:
    return relational.reference_partition(regime)


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    receipt_sha256: str,
    state: dict[str, Any],
) -> relational.PartitionSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": receipt_sha256,
        "state": state,
    }
    return relational.PartitionSnapshot(
        revision,
        parent_sha256,
        receipt_sha256,
        state,
        sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> relational.PartitionSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0069-seed"}))
    return _snapshot(0, None, receipt, {"weights": [0.0, 0.0, 0.0, 0.0]})


def project_snapshot(snapshot: relational.PartitionSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > INHERITANCE_LIMIT:
        raise ValueError("OT-0069 snapshot exceeds inheritance budget")
    return value


def restore_snapshot(value: dict[str, Any]) -> relational.PartitionSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "outcome_receipt_sha256",
        "state",
        "sha256",
    }:
        raise ValueError("OT-0069 snapshot projection authority differs")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0069 snapshot identity differs")
    return restored


def snapshot_errors(snapshot: relational.PartitionSnapshot, regime: dict[str, Any]) -> int:
    partition = snapshot.state.get("partition")
    if partition is None:
        return sum(item["correct_side"] != "left" for item in regime["heldout"])
    return relational.partition_errors(partition, regime["heldout"], regime["symbols"])


def attempt_update(
    current: relational.PartitionSnapshot,
    partition: dict[str, Any],
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[relational.PartitionSnapshot, str]:
    if receipt is None:
        return current, "no-credit"
    try:
        expected = complete_contact(contact, [item["selected_side"] for item in receipt["outcomes"]])
        if canonical_json(expected) != canonical_json(receipt):
            raise ValueError("receipt differs")
        relational.validate_partition(partition, contact["symbols"])
    except (KeyError, TypeError, ValueError):
        return current, "invalid"
    if relational.partition_errors(
        partition, relational._contact_examples(contact), contact["symbols"]
    ):
        return current, "contact-imperfect"
    successor = _snapshot(
        current.revision + 1,
        current.sha256,
        receipt["sha256"],
        {"partition": copy.deepcopy(partition)},
    )
    try:
        project_snapshot(successor)
    except ValueError:
        return current, "invalid"
    return successor, "committed"


def safe_attempt_update(
    current: relational.PartitionSnapshot,
    partition: dict[str, Any],
    receipt: dict[str, Any] | None,
    contact: dict[str, Any],
) -> tuple[relational.PartitionSnapshot, str]:
    try:
        return attempt_update(current, partition, receipt, contact)
    except ValueError:
        return current, "invalid"


def snapshot_choices(snapshot: relational.PartitionSnapshot, contact: dict[str, Any]) -> list[str]:
    partition = snapshot.state.get("partition")
    if partition is None:
        return ["left"] * len(contact["bundles"])
    return [
        relational.partition_output(partition, bundle["query_symbols"], contact["symbols"])
        for bundle in contact["bundles"]
    ]


def _fixed_controls(world: dict[str, Any], references: list[dict[str, Any]]) -> dict[str, Any]:
    regimes = world["regimes"]
    symbols = world["symbols"]
    left = [sum(item["correct_side"] != "left" for item in r["heldout"]) for r in regimes]
    right = [sum(item["correct_side"] != "right" for item in r["heldout"]) for r in regimes]
    alternating = [
        sum(item["correct_side"] != SIDES[index % 2] for index, item in enumerate(r["heldout"]))
        for r in regimes
    ]
    all_one = {
        "groups": [{"id": "all", "members": list(symbols)}],
        "within_output": "left",
        "across_output": "right",
    }
    singleton = {
        "groups": [
            {"id": f"s{index}", "members": [symbol]}
            for index, symbol in enumerate(symbols)
        ],
        "within_output": "left",
        "across_output": "right",
    }
    adjacent = {
        "groups": [
            {"id": f"p{index // 2}", "members": list(symbols[index : index + 2])}
            for index in range(0, len(symbols), 2)
        ],
        "within_output": "left",
        "across_output": "right",
    }
    vectors = {
        "empty": left,
        "digest": left,
        "no_persistence": left,
        "always_left": left,
        "always_right": right,
        "alternating": alternating,
        "all_one": [relational.partition_errors(all_one, r["heldout"], symbols) for r in regimes],
        "all_singleton": [
            relational.partition_errors(singleton, r["heldout"], symbols) for r in regimes
        ],
        "adjacent_pairs": [
            relational.partition_errors(adjacent, r["heldout"], symbols) for r in regimes
        ],
        "fixed_references": [
            [relational.partition_errors(reference, r["heldout"], symbols) for r in regimes]
            for reference in references
        ],
    }
    complete = [
        left,
        right,
        alternating,
        vectors["all_one"],
        vectors["all_singleton"],
        vectors["adjacent_pairs"],
        *vectors["fixed_references"],
    ]
    return {
        **vectors,
        "pass": all(vector != [0, 0, 0] for vector in complete),
        "receipt_sha256": sha256_bytes(canonical_json(vectors)),
    }


def task_compression_certificate(regime: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(regime)
    normalized["target_labels"] = tuple(normalized["target_labels"])
    normalized["diagnostic_pairs"] = [
        tuple(item) for item in normalized["diagnostic_pairs"]
    ]
    normalized["heldout_pairs"] = [tuple(item) for item in normalized["heldout_pairs"]]
    return calibrated.compression_certificate(normalized, receipt)


def structural_calibration(task: dict[str, Any]) -> dict[str, Any]:
    validate_task(task)
    references = [reference_partition(regime) for regime in task["world"]["regimes"]]
    regimes = []
    for index, (regime, reference) in enumerate(
        zip(task["world"]["regimes"], references, strict=True)
    ):
        receipt = complete_contact(
            regime["contact"], ["left"] * len(regime["contact"]["bundles"])
        )
        overlap = {tuple(item) for item in regime["diagnostic_pairs"]} & {
            tuple(item) for item in regime["heldout_pairs"]
        }
        result = {
            "index": regime["index"],
            "reference_errors": relational.partition_errors(
                reference, regime["heldout"], regime["symbols"]
            ),
            "stateless": relational.stateless_certificate(regime),
            "compression": task_compression_certificate(regime, receipt),
            "heldout_overlap_count": len(overlap),
            "membership_sha256": relational.membership_fingerprint(reference, regime["symbols"]),
            "output_only": (
                {"pass": True, "minimum_contact_errors": None}
                if index == 0
                else relational._output_only_certificate(references[index - 1], regime)
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
        relational.partition_errors(references[0], regime["heldout"], regime["symbols"])
        for regime in task["world"]["regimes"]
    ]
    frozen_second = [
        relational.partition_errors(references[1], regime["heldout"], regime["symbols"])
        for regime in task["world"]["regimes"]
    ]
    fixed = _fixed_controls(task["world"], references)
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
        and frozen_first == [0, 8, 4]
        and frozen_second == [3, 0, 8]
        and fixed["pass"]
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": PROMPT_PATH,
        "orientation_sha256": ORIENTATION_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0069.py"),
        "carrier_calibration_sha256": Path("src/open_trajectory_harness/ot0068.py"),
        "relational_core_sha256": Path("src/open_trajectory_harness/ot0067.py"),
        "hosted_core_sha256": Path("src/open_trajectory_harness/ot0066.py"),
        "preflight_calibration_sha256": Path("src/open_trajectory_harness/ot0061.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path("src/open_trajectory_harness/deployment_proxy.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0069_harness.py"),
        "test_sha256": Path("tests/test_ot0069.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "tool_receipt_patch_sha256": PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0068_manifest_sha256": OT68_MANIFEST_PATH,
        "ot0067_manifest_sha256": OT67_MANIFEST_PATH,
        "ot0066_manifest_sha256": OT66_MANIFEST_PATH,
    }


def require_task_derivation_identity(repo: Path, implementation_commit: str) -> None:
    expected_task_seed(implementation_commit)
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0069 task derivation requires a clean implementation")
    if git_output(repo, "rev-parse", "HEAD") != implementation_commit:
        raise RuntimeError("OT-0069 task derivation identity differs from clean HEAD")


def prepare_task_manifest(
    repo: Path, path: Path, implementation_commit: str
) -> dict[str, Any]:
    require_task_derivation_identity(repo, implementation_commit)
    task = build_task(expected_task_seed(implementation_commit))
    validate_task(task)
    structural = structural_calibration(task)
    if not structural["pass"]:
        raise RuntimeError("OT-0069 private world failed structural calibration")
    raw = canonical_json(task)
    write_sealed_json(path, task)
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
        raise RuntimeError("OT-0069 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0069 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0069 task seed is not mechanically derived")
    observed = {name: sha256_file(repo / path) for name, path in fixed_input_paths().items()}
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0069 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo, "diff", "--name-only", f"{implementation}..{execution}", "--", *protected
    )
    if changed:
        raise RuntimeError(f"OT-0069 implementation changed after lock: {changed}")
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
        raise RuntimeError("OT-0069 backend or TLS identity differs")
    return lock


def actor_view(
    contact: dict[str, Any],
    choices: list[str],
    receipt: dict[str, Any],
    current: relational.PartitionSnapshot,
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
            for presentation in bundle["presentations"]:
                presentation["events"].reverse()
    elif worker != "worker-1":
        raise ValueError("OT-0069 worker identity is unavailable")
    return transformed


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
        {"correct_side", "target_labels", "heldout", "heldout_pairs"}
        & _collect_keys(view)
    )
    surface = prompt + orientation + canonical_json(schema).decode()
    forbidden_terms = sorted(
        term
        for term in ("interleaved", "contiguous", "crossed", "group-0")
        if term in surface.lower()
    )
    body = {
        "prompt_sha256": sha256_bytes(prompt.encode()),
        "orientation_sha256": sha256_bytes(orientation.encode()),
        "schema_sha256": sha256_bytes(canonical_json(schema)),
        "concrete_symbol_hits": re.findall(r"symbol-[0-9a-f]{8,}", surface),
        "forbidden_terms": forbidden_terms,
        "serialized_forbidden_keys": forbidden_keys,
        "probe_sha256": sha256_bytes(canonical_json(view)),
    }
    return {
        **body,
        "pass": not body["concrete_symbol_hits"]
        and not forbidden_terms
        and not forbidden_keys,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def partition_novelty(
    repo: Path,
    partition: dict[str, Any],
    parent: relational.PartitionSnapshot,
    symbols: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    try:
        relational.validate_partition(partition, symbols)
        partition_sha256 = sha256_bytes(canonical_json(partition))
        membership_sha256 = relational.membership_fingerprint(partition, symbols)
        valid = True
    except ValueError:
        partition_sha256 = membership_sha256 = None
        valid = False
    serialized = canonical_json(partition).decode() if isinstance(partition, dict) else ""
    normalized = "".join(serialized.split())
    collision_paths = []
    for path in (PROMPT_PATH, ORIENTATION_PATH, SCHEMA_PATH):
        text = (repo / path).read_text(encoding="utf-8")
        if normalized and normalized in "".join(text.split()):
            collision_paths.append(str(path))
    parent_partition = parent.state.get("partition")
    body = {
        "partition_sha256": partition_sha256,
        "membership_sha256": membership_sha256,
        "parent_partition_sha256": (
            sha256_bytes(canonical_json(parent_partition))
            if parent_partition is not None
            else None
        ),
        "partition_differs_from_parent": canonical_json(parent_partition)
        != canonical_json(partition),
        "collision_paths": collision_paths,
        "valid": valid,
    }
    return {
        **body,
        "pass": valid
        and body["partition_differs_from_parent"]
        and not collision_paths,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run_actor_turn(
    *,
    client: hosted.AppServerClient,
    proxy: hosted.SanitizedResponsesProxy,
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
            "baseInstructions": "Author one bounded deterministic partition and return only schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0069",
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
        or set(output) != {"groups", "within_output", "across_output"}
        or not isinstance(output["groups"], list)
    ):
        parse_error = parse_error or "actor output failed its exact partition envelope"
        output = None
    partition = output if output is not None else {}
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
            "hidden_task_leakage": [marker for marker in hidden_markers if marker in prompt],
            "usage": _turn_usage(client.raw_events[event_before:], thread["id"]),
            "current_projection_bytes": len(canonical_json(view["current_snapshot"])),
            "turn": turn,
        },
        partition,
        inventory,
    )


def _overbudget_reference(reference: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(reference)
    for index, group in enumerate(candidate["groups"]):
        group["id"] = chr(97 + index) * 40
    return candidate


def _membership_deleted(partition: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(partition)
    candidate["groups"][0]["members"].pop()
    return candidate


def execute_worker(
    *,
    repo: Path,
    task: dict[str, Any],
    worker: str,
    client: hosted.AppServerClient,
    proxy: hosted.SanitizedResponsesProxy,
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
    references = [reference_partition(regime) for regime in world["regimes"]]
    fixed_controls = _fixed_controls(world, references)
    for regime in world["regimes"]:
        index = regime["index"]
        before = current
        contact = worker_contact(regime["contact"], worker)
        choices = snapshot_choices(before, contact)
        receipt = complete_contact(contact, choices)
        view = actor_view(contact, choices, receipt, before)
        hidden = [
            *[canonical_json(item["query_symbols"]).decode() for item in regime["heldout"]],
            canonical_json(regime["target_labels"]).decode(),
            '"correct_side"',
            '"target_labels"',
            '"heldout"',
            '"heldout_pairs"',
        ]
        turn, partition, inventory = run_actor_turn(
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
        after, update_reason = safe_attempt_update(before, partition, receipt, contact)
        snapshots[after.sha256] = after
        no_credit, no_credit_reason = safe_attempt_update(before, partition, None, contact)
        invalid, invalid_reason = safe_attempt_update(before, {"groups": []}, receipt, contact)
        duplicate = reference_partition(regime)
        duplicate["groups"][0]["members"].append(duplicate["groups"][1]["members"][0])
        duplicate_result, duplicate_reason = safe_attempt_update(before, duplicate, receipt, contact)
        missing_result, missing_reason = safe_attempt_update(
            before, _membership_deleted(reference_partition(regime)), receipt, contact
        )
        empty = reference_partition(regime)
        empty["groups"].append({"id": "empty", "members": []})
        empty_result, empty_reason = safe_attempt_update(before, empty, receipt, contact)
        unknown = reference_partition(regime)
        unknown["groups"][0]["members"][0] = "unknown"
        unknown_result, unknown_reason = safe_attempt_update(before, unknown, receipt, contact)
        oversized_result, oversized_reason = safe_attempt_update(
            before, _overbudget_reference(reference_partition(regime)), receipt, contact
        )
        all_one = {
            "groups": [{"id": "all", "members": list(regime["symbols"])}],
            "within_output": "left",
            "across_output": "right",
        }
        imperfect, imperfect_reason = safe_attempt_update(before, all_one, receipt, contact)
        parent = (
            restore_snapshot(project_snapshot(snapshots[after.parent_sha256]))
            if after.sha256 != before.sha256
            else before
        )
        if index == 1:
            first_learned = after
        elif index == 2:
            second_learned = after
        pre_errors = snapshot_errors(before, regime)
        candidate_errors = snapshot_errors(after, regime)
        novelty = partition_novelty(repo, partition, before, regime["symbols"])
        replay_errors = snapshot_errors(restore_snapshot(project_snapshot(after)), regime)
        compression = task_compression_certificate(regime, receipt)
        try:
            relational.validate_partition(partition, regime["symbols"])
            partition_bytes = len(canonical_json(partition))
            candidate_membership = relational.membership_fingerprint(partition, regime["symbols"])
            parent_partition = before.state.get("partition")
            membership_changed = (
                parent_partition is None
                or candidate_membership
                != relational.membership_fingerprint(parent_partition, regime["symbols"])
            )
            output_only = (
                {"pass": True, "minimum_contact_errors": None}
                if parent_partition is None
                else relational._output_only_certificate(parent_partition, regime)
            )
            collapsed_errors = relational.partition_errors(
                relational._one_group(partition, regime["symbols"]),
                regime["heldout"],
                regime["symbols"],
            )
            fixed_output_errors = []
            for side in SIDES:
                fixed = copy.deepcopy(partition)
                fixed["within_output"] = fixed["across_output"] = side
                fixed_output_errors.append(
                    relational.partition_errors(fixed, regime["heldout"], regime["symbols"])
                )
        except (KeyError, TypeError, ValueError):
            partition_bytes = len(canonical_json(partition)) if isinstance(partition, dict) else 0
            candidate_membership = None
            membership_changed = False
            output_only = {"pass": False, "minimum_contact_errors": None}
            collapsed_errors = None
            fixed_output_errors = []
        result = {
            "index": index,
            "pre_update_errors": pre_errors,
            "candidate_errors": candidate_errors,
            "update_reason": update_reason,
            "partition_sha256": sha256_bytes(canonical_json(partition)),
            "partition_bytes": partition_bytes,
            "membership_sha256": candidate_membership,
            "membership_changed": membership_changed,
            "output_only_correction": output_only,
            "committed_bytes": len(canonical_json(project_snapshot(after))),
            "no_credit_preserved_parent": no_credit.sha256 == before.sha256,
            "no_credit_reason": no_credit_reason,
            "unchanged_errors": pre_errors,
            "no_persistence_errors": snapshot_errors(initial, regime),
            "digest_errors": snapshot_errors(initial, regime),
            "verbatim_error_vector": compression["allowed_replay_errors"],
            "complete_deletion_errors": snapshot_errors(initial, regime),
            "one_group_ablation_errors": collapsed_errors,
            "membership_deletion_errors": snapshot_errors(missing_result, regime),
            "fixed_output_ablation_errors": fixed_output_errors,
            "frozen_first_errors": snapshot_errors(
                first_learned if first_learned is not None else after, regime
            ),
            "frozen_second_errors": snapshot_errors(
                second_learned if second_learned is not None else after, regime
            ),
            "stateless_certificate": relational.stateless_certificate(regime),
            "invalid_preserved_parent": invalid.sha256 == before.sha256,
            "invalid_reason": invalid_reason,
            "duplicate_preserved_parent": duplicate_result.sha256 == before.sha256,
            "duplicate_reason": duplicate_reason,
            "missing_preserved_parent": missing_result.sha256 == before.sha256,
            "missing_reason": missing_reason,
            "empty_preserved_parent": empty_result.sha256 == before.sha256,
            "empty_reason": empty_reason,
            "unknown_preserved_parent": unknown_result.sha256 == before.sha256,
            "unknown_reason": unknown_reason,
            "oversized_preserved_parent": oversized_result.sha256 == before.sha256,
            "oversized_reason": oversized_reason,
            "contact_imperfect_preserved_parent": imperfect.sha256 == before.sha256,
            "contact_imperfect_reason": imperfect_reason,
            "parent_exact": parent.sha256 == before.sha256,
            "successor_exact": restore_snapshot(project_snapshot(after)).sha256 == after.sha256,
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
        regimes.append(result)
        current = after
    body = {
        "worker": worker,
        "regimes": regimes,
        "candidate_errors": [item["candidate_errors"] for item in regimes],
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "frozen_first_errors": [
            snapshot_errors(first_learned, regime) for regime in world["regimes"]
        ],
        "frozen_second_errors": [
            snapshot_errors(second_learned, regime) for regime in world["regimes"]
        ],
        "fixed_controls": fixed_controls,
    }
    body["pass"] = (
        body["candidate_errors"] == [0, 0, 0]
        and body["pre_update_errors"] == [4, 8, 8]
        and body["frozen_first_errors"] == [0, 8, 4]
        and body["frozen_second_errors"] == [3, 0, 8]
        and fixed_controls["pass"]
        and all(
            item["update_reason"] == "committed"
            and item["partition_bytes"] <= INHERITANCE_LIMIT
            and item["committed_bytes"] <= INHERITANCE_LIMIT
            and item["no_credit_preserved_parent"]
            and item["no_credit_reason"] == "no-credit"
            and item["unchanged_errors"] >= 1
            and item["no_persistence_errors"] == 4
            and item["digest_errors"] == 4
            and all(value == 4 for value in item["verbatim_error_vector"])
            and item["complete_deletion_errors"] >= 1
            and item["one_group_ablation_errors"] >= 1
            and item["membership_deletion_errors"] >= 1
            and all(value >= 1 for value in item["fixed_output_ablation_errors"])
            and item["stateless_certificate"]["pass"]
            and item["membership_changed"]
            and item["output_only_correction"]["pass"]
            and item["invalid_preserved_parent"]
            and item["invalid_reason"] == "invalid"
            and item["duplicate_preserved_parent"]
            and item["duplicate_reason"] == "invalid"
            and item["missing_preserved_parent"]
            and item["missing_reason"] == "invalid"
            and item["empty_preserved_parent"]
            and item["empty_reason"] == "invalid"
            and item["unknown_preserved_parent"]
            and item["unknown_reason"] == "invalid"
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
        and sha256_bytes(canonical_json(inventories[0]))
        == inventory_expected["sha256"]
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
    validity_names = set(gates) - {"candidate_endpoint"}
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
        raise RuntimeError("OT-0069 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution, codex_bin)
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task, task_bytes = read_sealed_json(task_manifest)
    validate_task(task)
    structural = structural_calibration(task)
    if (
        sha256_bytes(task_bytes) != lock.get("task_sha256")
        or task["task_seed"] != lock.get("task_seed")
        or structural["receipt_sha256"]
        != lock.get("world_structural_receipt_sha256")
        or not structural["pass"]
    ):
        raise RuntimeError("OT-0069 private task or structural receipt differs")
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0069 output or workspace exists")
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    orientation = (repo / ORIENTATION_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    preflight = require_hosted_schema(schema)
    surface_preflight = actor_surface_authority(repo)
    if not surface_preflight["pass"]:
        raise RuntimeError("OT-0069 actor surface failed before hosted execution")
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
        raise RuntimeError("OT-0069 local preflight failed before hosted execution")
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
        with hosted.SanitizedResponsesProxy() as proxy:
            proxy_ref = proxy
            with hosted.AppServerClient(
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
                        raise RuntimeError("OT-0069 frozen model unavailable")
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
            kind="equivalence-partition-representation-escape-candidate",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Private task, actor-authored partitions, hosted outputs, and deployment receipts remain private.",
                "A pass is one bounded representation-escape foothold and not developmental transfer or widened OT-2 evidence.",
                "The generic equivalence interpreter remains a researcher-built causal exoskeleton.",
            ],
            input_manifests=[
                str(OT68_MANIFEST_PATH),
                str(OT67_MANIFEST_PATH),
                str(OT66_MANIFEST_PATH),
            ],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0069-harness")
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
                    repo,
                    args.prepare_task_manifest.resolve(),
                    args.implementation_commit,
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
    except (hosted.AppServerError, OSError, RuntimeError, ValueError) as error:
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
