from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .app_server import AppServerClient, AppServerError
from .ot0002 import (
    app_server_version,
    canonical_json,
    child_environment,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import read_sealed_json, render_inputs, write_sealed_json
from .ot0003 import worker_summary as comparative_worker_summary
from .ot0003_world import (
    DiscrepancyGatedVersionLedger,
    Observation,
    generate_task_manifest as generate_ot0003_task_manifest,
    manifest_batch,
    substrate_conditions,
    validate_task_manifest as validate_ot0003_task_manifest,
)


EXPERIMENT_ID = "OT-0012"
FIXTURE_ROOT = Path("fixtures/ot-0012")
ACCEPTANCE_PATH = Path("spec/ot-0012-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0012-run-lock.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
LOCK_PATH = Path("requirements-test.lock")
MODEL_RELATIVE_PATH = Path(
    "models/lmstudio-community/gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf"
)
RUNTIME_RELATIVE_PATH = Path(
    "extensions/backends/llama.cpp-mac-arm64-apple-metal-advsimd-2.13.0"
)
RUNTIME_ENGINE = "llama.cpp-mac-arm64-apple-metal-advsimd@2.13.0"
HARMONY_RELATIVE_PATH = Path("extensions/backends/vendor/_amphibian/app-harmony-mac-arm64@6")
LM_STUDIO_APP = Path("/Applications/LM Studio.app")
LM_STUDIO_SERVER = "http://127.0.0.1:1234"
HARMONY_PREFIXES = (
    "<|channel|>final <|constrain|>json<|message|>",
    "<|channel|>final <|constrain|>JSON<|message|>",
)


def generate_task_manifest() -> dict[str, Any]:
    manifest = generate_ot0003_task_manifest()
    manifest["experiment_id"] = EXPERIMENT_ID
    return manifest


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0012 task-manifest identity")
    inherited = dict(manifest)
    inherited["experiment_id"] = "OT-0003"
    validate_ot0003_task_manifest(inherited)


def prepare_task_manifest(path: Path) -> dict[str, Any]:
    manifest = generate_task_manifest()
    validate_task_manifest(manifest)
    write_sealed_json(path, manifest)
    encoded = canonical_json(manifest)
    return {"sha256": sha256_bytes(encoded), "bytes": len(encoded)}


def require_clean_commit(repo: Path) -> str:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0012 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise RuntimeError(f"required content-addressed directory is absent: {root.name}")
    rows: list[dict[str, Any]] = []
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        size = path.stat().st_size
        total += size
        rows.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": size,
                "sha256": sha256_file(path),
            }
        )
    return {"sha256": sha256_bytes(canonical_json(rows)), "files": len(rows), "bytes": total}


def _json_url(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise RuntimeError("LM Studio returned a non-object model catalog")
    return value


def local_model_identity() -> dict[str, Any]:
    cache = Path.home() / ".cache" / "lm-studio"
    model = cache / MODEL_RELATIVE_PATH
    runtime = cache / RUNTIME_RELATIVE_PATH
    harmony = cache / HARMONY_RELATIVE_PATH
    app_executable = LM_STUDIO_APP / "Contents" / "MacOS" / "LM Studio"
    app_main = (
        LM_STUDIO_APP / "Contents" / "Resources" / "app" / ".webpack" / "main" / "index.js"
    )
    info_path = LM_STUDIO_APP / "Contents" / "Info.plist"
    lms = shutil.which("lms")
    if not model.is_file() or not app_executable.is_file() or not info_path.is_file() or not lms:
        raise RuntimeError("frozen LM Studio model, app, or CLI is unavailable")
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)
    cli_version = subprocess.run(
        [lms, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    cli_commit_match = re.fullmatch(r"CLI commit: ([0-9a-f]+)", cli_version)
    if not cli_commit_match:
        raise RuntimeError("LM Studio CLI omitted its commit identity")
    runtime_listing = subprocess.run(
        [lms, "runtime", "ls"], capture_output=True, text=True, check=True
    ).stdout
    selected_runtime_pattern = re.compile(
        rf"^{re.escape(RUNTIME_ENGINE)}\s+✓\s+GGUF\s*$", re.MULTILINE
    )
    if not selected_runtime_pattern.search(runtime_listing):
        raise RuntimeError("frozen llama.cpp runtime is not the selected GGUF engine")
    process_listing = subprocess.run(
        [lms, "ps", "--json"], capture_output=True, text=True, check=True
    )
    processes = json.loads(process_listing.stdout)
    if not isinstance(processes, list):
        raise RuntimeError("LM Studio process catalog is not a list")
    selected_processes = [
        item for item in processes if item.get("identifier") == "openai/gpt-oss-20b"
    ]
    if len(selected_processes) != 1:
        raise RuntimeError("frozen GPT-OSS process is not uniquely loaded")
    selected_process = selected_processes[0]
    process_state = {
        "identifier": selected_process.get("identifier"),
        "format": selected_process.get("format"),
        "selected_variant": selected_process.get("selectedVariant"),
        "quantization": (selected_process.get("quantization") or {}).get("name"),
        "context_length": selected_process.get("contextLength"),
        "parallel": selected_process.get("parallel"),
    }
    expected_process = {
        "identifier": "openai/gpt-oss-20b",
        "format": "gguf",
        "selected_variant": "openai/gpt-oss-20b@mxfp4",
        "quantization": "MXFP4",
        "context_length": 8192,
        "parallel": 4,
    }
    if process_state != expected_process:
        raise RuntimeError("LM Studio loaded process differs from the frozen actor configuration")
    catalog = _json_url(f"{LM_STUDIO_SERVER}/api/v0/models")
    models = catalog.get("data")
    if not isinstance(models, list):
        raise RuntimeError("LM Studio model catalog omitted data")
    selected = [item for item in models if item.get("id") == "openai/gpt-oss-20b"]
    if len(selected) != 1:
        raise RuntimeError("frozen GPT-OSS model is not uniquely loaded")
    model_state = selected[0]
    live = {
        "id": model_state.get("id"),
        "state": model_state.get("state"),
        "compatibility_type": model_state.get("compatibility_type"),
        "quantization": model_state.get("quantization"),
        "loaded_context_length": model_state.get("loaded_context_length"),
    }
    expected_live = {
        "id": "openai/gpt-oss-20b",
        "state": "loaded",
        "compatibility_type": "gguf",
        "quantization": "MXFP4",
        "loaded_context_length": 8192,
    }
    if live != expected_live:
        raise RuntimeError("LM Studio live model state differs from the frozen actor configuration")
    return {
        "model_artifact": {"sha256": sha256_file(model), "bytes": model.stat().st_size},
        "lm_studio": {
            "version": info.get("CFBundleShortVersionString"),
            "build": info.get("CFBundleVersion"),
            "executable_sha256": sha256_file(app_executable),
            "executable_bytes": app_executable.stat().st_size,
            "server_bundle": {
                "sha256": sha256_file(app_main),
                "files": 1,
                "bytes": app_main.stat().st_size,
            },
        },
        "inference_runtime": {
            "cache_identifier": RUNTIME_RELATIVE_PATH.name,
            "engine_identifier": RUNTIME_ENGINE,
            **tree_identity(runtime),
        },
        "harmony_adapter": {"identifier": HARMONY_RELATIVE_PATH.name, **tree_identity(harmony)},
        "cli": {
            "commit": cli_commit_match.group(1),
            "sha256": sha256_file(Path(lms)),
            "bytes": Path(lms).stat().st_size,
        },
        "live_model": live,
        "loaded_process": process_state,
    }


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path, model_identity: dict[str, Any]
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    for name in ("implementation_git_commit", "protocol_origin_git_commit"):
        commit = lock.get(name, "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise RuntimeError(f"run lock omits a full {name}")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, execution_commit], cwd=repo
        )
        if ancestor.returncode != 0:
            raise RuntimeError(f"frozen {name} is not an ancestor of execution HEAD")
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": FIXTURE_ROOT / "actor-prompt.txt",
        "output_schema_sha256": FIXTURE_ROOT / "actor-output.schema.json",
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "substrates_sha256": FIXTURE_ROOT / "substrates.json",
        "model_catalog_sha256": FIXTURE_ROOT / "model-catalog.json",
        "dependency_lock_sha256": LOCK_PATH,
        "receipt_patch_sha256": PATCH_PATH,
    }
    observed = {name: sha256_file(repo / path) for name, path in paths.items()}
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("frozen input identity differs from the OT-0012 run lock")
    protected = [
        "src/open_trajectory_harness/ot0012.py",
        "experiments/ot_0012_harness.py",
        "tests/test_ot0012_harness.py",
        "fixtures/ot-0012",
        str(ACCEPTANCE_PATH),
        str(PATCH_PATH),
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
        raise RuntimeError("Codex executable differs from the frozen byte identity")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the frozen byte identity")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex executable version differs from the run lock")
    if model_identity != lock.get("local_model_identity"):
        raise RuntimeError("local model or inference stack differs from the run lock")
    return lock


def instrumented_command(repo: Path, codex_bin: Path) -> list[str]:
    catalog = str((repo / FIXTURE_ROOT / "model-catalog.json").resolve())
    return [
        str(codex_bin),
        "app-server",
        "--disable",
        "apps",
        "--disable",
        "plugins",
        "--disable",
        "js_repl",
        "--disable",
        "view_image",
        "--disable",
        "shell_tool",
        "--disable",
        "unified_exec",
        "-c",
        'web_search="disabled"',
        "-c",
        'model_provider="lmstudio"',
        "-c",
        "agents.enabled=false",
        "-c",
        "tools.update_plan.enabled=false",
        "-c",
        "tools.experimental_request_user_input.enabled=false",
        "-c",
        f"model_catalog_json={json.dumps(catalog)}",
    ]


def decode_actor_output(text: str, expected: int) -> tuple[list[int], str | None]:
    encoded = text.strip()
    for prefix in HARMONY_PREFIXES:
        if encoded.startswith(prefix):
            encoded = encoded[len(prefix) :].strip()
            break
    try:
        value = json.loads(encoded)
    except json.JSONDecodeError:
        return [], "actor output was neither direct JSON nor exact frozen Harmony framing"
    if not isinstance(value, dict) or set(value) != {"predictions"}:
        return [], "actor JSON must contain exactly the predictions key"
    predictions = value["predictions"]
    if (
        not isinstance(predictions, list)
        or len(predictions) != expected
        or any(type(item) is not int or item not in (0, 1) for item in predictions)
    ):
        return [], "prediction vector failed exact shape or binary validation"
    return predictions, None


def run_actor_turn(
    *,
    client: AppServerClient,
    model: str,
    workspace: Path,
    prompt_template: str,
    projection: str,
    batch: tuple[tuple[int, int, int, int], ...],
    outcomes: tuple[int, ...],
    condition: str,
    phase: str,
    score_kind: str,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Return only the exact JSON object requested by the user.",
            "developerInstructions": "Do not use tools or inspect files. Use only the current prompt.",
            "serviceName": "open_trajectory_ot0012",
        }
    )
    prompt = prompt_template.replace("{{PROJECTION}}", projection).replace(
        "{{INPUTS}}", render_inputs(batch)
    )
    before = len(client.model_visible_tool_inventories())
    after = client.notification_count()
    started = client.request(
        "turn/start",
        {
            "threadId": thread["id"],
            "input": [{"type": "text", "text": prompt}],
            "approvalPolicy": "never",
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "effort": "low",
        },
        timeout=180,
    )
    turn_id = started["turn"]["id"]
    completed = client.wait_notification(
        "turn/completed",
        after=after,
        predicate=lambda item: item.get("params", {}).get("threadId") == thread["id"]
        and item.get("params", {}).get("turn", {}).get("id") == turn_id,
        timeout=180,
    )["params"]["turn"]
    time.sleep(0.05)
    receipts = len(client.model_visible_tool_inventories()) - before
    messages = [item for item in completed.get("items", []) if item.get("type") == "agentMessage"]
    text = messages[-1].get("text", "") if messages else ""
    predictions, parse_error = decode_actor_output(text, len(outcomes))
    errors = len(outcomes) if parse_error else sum(
        prediction != outcome for prediction, outcome in zip(predictions, outcomes)
    )
    return {
        "condition": condition,
        "phase": phase,
        "score_kind": score_kind,
        "workspace": str(workspace.resolve()),
        "thread_id": thread["id"],
        "projection": projection,
        "projection_bytes": len(projection.encode()),
        "batch": batch,
        "outcomes": outcomes,
        "predictions": predictions,
        "parse_error": parse_error,
        "errors": errors,
        "tool_calls": client.completed_turn_tool_calls(thread_id=thread["id"], turn_id=turn_id),
        "inventory_receipts": receipts,
        "turn_status": completed.get("status"),
    }


def execute_worker(
    *,
    repo: Path,
    task_manifest_path: Path,
    output_path: Path,
    workspace_root: Path,
    codex_home: Path,
    codex_bin: Path,
    worker_id: str,
) -> None:
    execution_commit = require_clean_commit(repo)
    identity = local_model_identity()
    lock = validate_run_lock(repo, execution_commit, codex_bin, identity)
    manifest, task_bytes = read_sealed_json(task_manifest_path)
    validate_task_manifest(manifest)
    if sha256_bytes(task_bytes) != lock.get("task_manifest_sha256"):
        raise RuntimeError("private task manifest differs from the frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    prompt_template = (repo / FIXTURE_ROOT / "actor-prompt.txt").read_text(encoding="utf-8")
    projection_limit = acceptance["resource_budget"]["projection_bytes_per_encounter"]
    model = acceptance["resource_budget"]["model"]
    substrates = substrate_conditions()
    workspace_root.mkdir(parents=True, exist_ok=False)
    codex_home.mkdir(parents=True, exist_ok=False)
    environment = child_environment(repo)
    environment["CODEX_HOME"] = str(codex_home)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    environment["CODEX_INTERNAL_APP_SERVER_REMOTE_CONTROL_DISABLED"] = "1"
    results: list[dict[str, Any]] = []
    started_at = time.monotonic()
    client: AppServerClient | None = None
    try:
        with AppServerClient(
            command=instrumented_command(repo, codex_bin),
            cwd=repo,
            env=environment,
            request_timeout=180,
        ) as active_client:
            client = active_client
            models = client.request("model/list", {"includeHidden": False})["data"]
            if [item.get("id") for item in models] != [model]:
                raise RuntimeError("isolated Codex model catalog is not the one frozen actor model")
            for phase_spec in task_order["phases"]:
                phase = phase_spec["phase"]
                regime = "regime-a" if phase.startswith("regime-a") else "regime-b"
                batch, outcomes = manifest_batch(manifest, regime, phase_spec["batch"])
                observations = [
                    Observation(features, outcome) for features, outcome in zip(batch, outcomes)
                ]
                phase_results: dict[str, dict[str, Any]] = {}
                for condition in task_order["conditions"]:
                    substrate = substrates[condition]
                    projection = substrate.project(batch, projection_limit)
                    result = run_actor_turn(
                        client=client,
                        model=model,
                        workspace=workspace_root / f"{phase}-{condition}",
                        prompt_template=prompt_template,
                        projection=projection,
                        batch=batch,
                        outcomes=outcomes,
                        condition=condition,
                        phase=phase,
                        score_kind=phase_spec["score"],
                    )
                    result["substrate_project_operations"] = substrate.last_project_operations
                    phase_results[condition] = result
                    results.append(result)
                for condition, substrate in substrates.items():
                    substrate.observe(observations)
                    phase_results[condition]["substrate_observe_operations"] = (
                        substrate.last_observe_operations
                    )
            for ablation in task_order["ablations"]:
                batch, outcomes = manifest_batch(manifest, "regime-b", ablation["batch"])
                result = run_actor_turn(
                    client=client,
                    model=model,
                    workspace=workspace_root / ablation["phase"],
                    prompt_template=prompt_template,
                    projection="[candidate projection ablated]",
                    batch=batch,
                    outcomes=outcomes,
                    condition="candidate-ablation",
                    phase=ablation["phase"],
                    score_kind="ablation",
                )
                result["substrate_project_operations"] = 0
                result["substrate_observe_operations"] = 0
                results.append(result)
            inventories = client.model_visible_tool_inventories()
            events = client.raw_events
            stderr = client.stderr_lines
            usage = token_usage(events)
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
            "results": results,
            "events": client.raw_events if client else [],
            "stderr_sha256": sha256_bytes(canonical_json(client.stderr_lines if client else [])),
            "elapsed_seconds": time.monotonic() - started_at,
        }
        write_sealed_json(output_path, failure)
        raise
    candidate = substrates["candidate"]
    assert isinstance(candidate, DiscrepancyGatedVersionLedger)
    inventory_bytes = canonical_json(inventories[0]) if inventories else b""
    worker = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": "completed",
        "worker_id": worker_id,
        "execution_git_commit": execution_commit,
        "task_manifest_sha256": sha256_bytes(task_bytes),
        "model": model,
        "model_identity_verified": True,
        "results": results,
        "candidate_state": {
            "regime": candidate.regime,
            "hypotheses": [rule.rule_id for rule in candidate.hypotheses],
            "matches_hidden_regime_b": len(candidate.hypotheses) == 1
            and candidate.hypotheses[0].rule_id == manifest["rules"]["regime-b"],
        },
        "direct_inventory": {
            "sha256": sha256_bytes(inventory_bytes) if inventories else None,
            "tool_count": len(inventories[0]) if inventories else 0,
            "receipt_count": len(inventories),
            "stable": bool(inventories) and all(item == inventories[0] for item in inventories),
        },
        "usage": usage,
        "elapsed_seconds": time.monotonic() - started_at,
        "events": events,
        "stderr_sha256": sha256_bytes(canonical_json(stderr)),
        "stderr_lines": len(stderr),
    }
    write_sealed_json(output_path, worker)


def worker_summary(worker: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    summary = comparative_worker_summary(worker, acceptance)
    summary["gates"]["content_addressed_model"] = worker.get("model_identity_verified") is True
    summary["scientific_pass"] = all(summary["gates"].values())
    return summary


def combined_summary(raw: dict[str, Any]) -> dict[str, Any]:
    acceptance = raw["acceptance"]
    workers = [worker_summary(worker, acceptance) for worker in raw["workers"]]
    reproduction = (
        len(workers) >= 2
        and all(worker["scientific_pass"] for worker in workers)
        and raw.get("same_task_manifest", False)
    )
    promotion = {
        "clean_predating_implementation": raw.get("implementation_clean", False),
        "original_scientific_gates": bool(workers and workers[0]["scientific_pass"]),
        "clean_reproduction": reproduction,
        "audit_and_tests": raw.get("audit_and_tests", False),
        "content_addressed_model_stack": raw.get("model_identity_verified", False),
    }
    if workers and not all(worker["scientific_pass"] for worker in workers):
        disposition = "rejected"
    elif all(promotion.values()):
        disposition = "promoted"
    else:
        disposition = "conditional"
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": raw["run_id"],
        "implementation_git_commit": raw["implementation_git_commit"],
        "model": acceptance["resource_budget"]["model"],
        "model_stability": acceptance["resource_budget"]["model_stability"],
        "task_manifest_sha256": raw["task_manifest_sha256"],
        "workers": workers,
        "promotion_gates": promotion,
        "disposition": disposition,
        "evidence_horizon": "private two-process content-addressed behavioral evidence",
    }


def run(repo: Path, run_id: str, codex_bin: Path, task_manifest_path: Path) -> tuple[Path, dict[str, Any]]:
    execution_commit = require_clean_commit(repo)
    identity = local_model_identity()
    lock = validate_run_lock(repo, execution_commit, codex_bin, identity)
    task_manifest, task_bytes = read_sealed_json(task_manifest_path)
    validate_task_manifest(task_manifest)
    task_digest = sha256_bytes(task_bytes)
    if task_digest != lock.get("task_manifest_sha256"):
        raise RuntimeError("private task manifest differs from the frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    run_root = repo / ".evidence" / "runs" / EXPERIMENT_ID / run_id
    if run_root.exists():
        raise RuntimeError(f"run id already exists: {run_id}")
    run_root.mkdir(parents=True)
    outputs = [run_root / "original.json", run_root / "reproduction.json"]
    worker_roots = [
        repo / ".evidence" / "sandboxes" / f"{run_id}-original",
        repo / ".evidence" / "sandboxes" / f"{run_id}-reproduction",
    ]
    home_roots = [
        repo / ".evidence" / "codex-homes" / f"{run_id}-original",
        repo / ".evidence" / "codex-homes" / f"{run_id}-reproduction",
    ]
    receipts: list[dict[str, Any]] = []
    for index, (output, workspace, codex_home) in enumerate(
        zip(outputs, worker_roots, home_roots), start=1
    ):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "open_trajectory_harness.ot0012",
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
                "--codex-home",
                str(codex_home),
                "--worker-id",
                f"worker-{index}",
            ],
            cwd=repo,
            env=child_environment(repo),
            capture_output=True,
            text=True,
        )
        receipts.append(
            {
                "worker_id": f"worker-{index}",
                "returncode": process.returncode,
                "stderr_sha256": sha256_bytes(process.stderr.encode()),
                "stderr_lines": len(process.stderr.splitlines()),
            }
        )
        if process.returncode != 0:
            raise RuntimeError(f"worker-{index} failed before producing sealed evidence")
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
        "model_identity_verified": identity == lock["local_model_identity"],
        "local_model_identity": identity,
        "acceptance": acceptance,
        "workers": workers,
        "worker_receipts": receipts,
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
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
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
    manifest = record_artifact(
        repo=repo,
        input_path=raw_path,
        experiment_id=EXPERIMENT_ID,
        artifact_id=run_id,
        kind="predictive-inheritance-run",
        evidence_class="private-reproducible",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0012 "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The salted task manifest, outcomes, actor events, and complete prompts remain private.",
            "Model weights are content-addressed local artifacts and are not committed to this repository.",
        ],
        input_manifests=[],
    )
    return manifest, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0012-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0012-local-001")
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--prepare-task-manifest", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--worker-id")
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
            if (
                args.worker_output is None
                or args.workspace_root is None
                or args.codex_home is None
                or not args.worker_id
            ):
                parser.error("worker output, workspace root, Codex home, and worker id are required")
            execute_worker(
                repo=repo,
                task_manifest_path=args.task_manifest.resolve(),
                output_path=args.worker_output.resolve(),
                workspace_root=args.workspace_root.resolve(),
                codex_home=args.codex_home.resolve(),
                codex_bin=args.codex_bin.resolve(),
                worker_id=args.worker_id,
            )
            return 0
        manifest, summary = run(
            repo, args.run_id, args.codex_bin.resolve(), args.task_manifest.resolve()
        )
    except (AppServerError, OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
