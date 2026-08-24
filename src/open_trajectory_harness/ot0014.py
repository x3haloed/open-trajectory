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
from .ot0003 import (
    read_sealed_json,
    render_inputs,
    worker_summary as behavioral_worker_summary,
    write_sealed_json,
)
from .ot0003_world import (
    DiscrepancyGatedVersionLedger,
    Observation,
    generate_task_manifest as generate_ot0003_task_manifest,
    manifest_batch,
    substrate_conditions,
    validate_task_manifest as validate_ot0003_task_manifest,
)


EXPERIMENT_ID = "OT-0014"
FIXTURE_ROOT = Path("fixtures/ot-0014")
ACCEPTANCE_PATH = Path("spec/ot-0014-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0014-run-lock.json")
TOOL_RECEIPT_PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")


def generate_task_manifest() -> dict[str, Any]:
    manifest = generate_ot0003_task_manifest()
    manifest["experiment_id"] = EXPERIMENT_ID
    return manifest


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0014 task-manifest identity")
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
        raise RuntimeError("OT-0014 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def validate_counterbalance(task_order: dict[str, Any], expected_count: int) -> None:
    conditions = task_order.get("conditions")
    phases = task_order.get("phases")
    if not isinstance(conditions, list) or len(conditions) != 4 or len(set(conditions)) != 4:
        raise ValueError("counterbalance requires four distinct conditions")
    if not isinstance(phases, list) or not phases:
        raise ValueError("counterbalance requires phases")
    position_counts = {condition: Counter() for condition in conditions}
    for phase in phases:
        orders = phase.get("condition_order") if isinstance(phase, dict) else None
        if not isinstance(orders, dict) or set(orders) != {"worker-1", "worker-2"}:
            raise ValueError("each phase requires two worker-specific condition orders")
        for order in orders.values():
            if not isinstance(order, list) or set(order) != set(conditions) or len(order) != 4:
                raise ValueError("condition order is not an exact permutation")
            for position, condition in enumerate(order):
                position_counts[condition][position] += 1
    expected = Counter({position: expected_count for position in range(4)})
    if any(counts != expected for counts in position_counts.values()):
        raise ValueError("condition positions are not exactly counterbalanced")


def validate_run_lock(repo: Path, execution_commit: str, codex_bin: Path) -> dict[str, Any]:
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
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "deployment_proxy_sha256": PROXY_PATH,
        "harness_sha256": Path("src/open_trajectory_harness/ot0014.py"),
    }
    observed = {name: sha256_file(repo / path) for name, path in paths.items()}
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("frozen input identity differs from the OT-0014 run lock")
    protected = [
        "src/open_trajectory_harness/app_server.py",
        "src/open_trajectory_harness/deployment_proxy.py",
        "src/open_trajectory_harness/ot0002.py",
        "src/open_trajectory_harness/ot0003.py",
        "src/open_trajectory_harness/ot0003_world.py",
        "src/open_trajectory_harness/ot0014.py",
        "experiments/ot_0014_harness.py",
        "fixtures/ot-0014",
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
        raise RuntimeError("Codex executable differs from the frozen byte identity")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the frozen byte identity")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex executable version differs from the run lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from the frozen byte identity")

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
        "{name=\"OpenAI\","
        f"base_url=\"{proxy_base_url}codex\","
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
    prompt_template: str,
    output_schema: dict[str, Any],
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
            "baseInstructions": "Predict the requested binary labels and return only schema-conforming JSON.",
            "developerInstructions": "Do not call tools or inspect files. Use only the current prompt.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0014",
        }
    )
    prompt = prompt_template.replace("{{PROJECTION}}", projection).replace(
        "{{INPUTS}}", render_inputs(batch)
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
    deployment_receipts = proxy.collector.snapshot()[deployment_before:]
    inventory_count = len(client.model_visible_tool_inventories()) - inventories_before
    output, parse_error = final_agent_json(turn)
    if turn.get("status") != "completed":
        parse_error = parse_error or "actor turn did not complete"
    predictions = output.get("predictions") if output else None
    valid_predictions = (
        isinstance(predictions, list)
        and len(predictions) == len(outcomes)
        and all(type(value) is int and value in (0, 1) for value in predictions)
    )
    if not valid_predictions:
        parse_error = parse_error or "prediction vector failed exact shape or binary validation"
        predictions = []
        errors = len(outcomes)
    else:
        errors = sum(prediction != outcome for prediction, outcome in zip(predictions, outcomes))
    response_ids = sorted(
        {item["value"] for item in deployment_receipts if item["kind"] == "response_id"}
    )
    effective_models = sorted(
        {item["value"] for item in deployment_receipts if item["kind"] == "effective_model"}
    )
    return {
        "condition": condition,
        "phase": phase,
        "score_kind": score_kind,
        "workspace": str(workspace.resolve()),
        "thread_id": thread["id"],
        "thread_session_id": thread.get("sessionId"),
        "projection": projection,
        "projection_bytes": len(projection.encode()),
        "batch": batch,
        "outcomes": outcomes,
        "predictions": predictions,
        "errors": errors,
        "parse_error": parse_error,
        "tool_calls": client.completed_turn_tool_calls(
            thread_id=thread["id"], turn_id=turn["id"]
        ),
        "inventory_receipts": inventory_count,
        "deployment_receipts": deployment_receipts,
        "deployment_effective_models": effective_models,
        "deployment_response_ids": response_ids,
        "turn": turn,
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
        raise RuntimeError("private task manifest differs from the frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    output_schema = load_json(repo / FIXTURE_ROOT / "actor-output.schema.json")
    prompt_template = (repo / FIXTURE_ROOT / "actor-prompt.txt").read_text(encoding="utf-8")
    projection_limit = acceptance["resource_budget"]["projection_bytes_per_encounter"]
    model = acceptance["resource_budget"]["model"]
    substrates = substrate_conditions()
    workspace_root.mkdir(parents=True, exist_ok=False)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    client: AppServerClient | None = None
    proxy: SanitizedResponsesProxy | None = None
    try:
        with SanitizedResponsesProxy() as active_proxy:
            proxy = active_proxy
            command = instrumented_command(codex_bin, proxy.base_url)
            with AppServerClient(
                command=command,
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as active_client:
                client = active_client
                models = client.request("model/list", {"includeHidden": False})["data"]
                if model not in {item.get("id") for item in models}:
                    raise RuntimeError(f"frozen model is unavailable: {model}")
                catalog_payload_sha256 = sha256_bytes(canonical_json(models))
                for phase_spec in task_order["phases"]:
                    phase = phase_spec["phase"]
                    regime = "regime-a" if phase.startswith("regime-a") else "regime-b"
                    batch, outcomes = manifest_batch(manifest, regime, phase_spec["batch"])
                    observations = [
                        Observation(features, outcome)
                        for features, outcome in zip(batch, outcomes)
                    ]
                    phase_results: dict[str, dict[str, Any]] = {}
                    for condition in phase_spec["condition_order"][worker_id]:
                        substrate = substrates[condition]
                        projection = substrate.project(batch, projection_limit)
                        result = run_actor_turn(
                            client=client,
                            proxy=proxy,
                            model=model,
                            workspace=workspace_root / f"{phase}-{condition}",
                            prompt_template=prompt_template,
                            output_schema=output_schema,
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
                        proxy=proxy,
                        model=model,
                        workspace=workspace_root / ablation["phase"],
                        prompt_template=prompt_template,
                        output_schema=output_schema,
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
                deployment_receipts = proxy.collector.snapshot()
                deployment_errors = proxy.collector.errors()
                deployment_diagnostics = proxy.collector.diagnostics()
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
            "results": results,
            "events": client.raw_events if client is not None else [],
            "stderr": client.stderr_lines if client is not None else [],
            "deployment_receipts": proxy.collector.snapshot() if proxy is not None else [],
            "deployment_errors": proxy.collector.errors() if proxy is not None else [],
            "elapsed_seconds": time.monotonic() - started,
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


def expected_learning_order(task_order: dict[str, Any], worker_id: str) -> list[str]:
    return [
        condition
        for phase in task_order["phases"]
        for condition in phase["condition_order"][worker_id]
    ]


def deployment_worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    model = acceptance["deployment_epoch"]["requested_model"]
    deployment = worker["deployment"]
    results = worker["results"]
    learning_results = [item for item in results if item["condition"] != "candidate-ablation"]
    observed_order = [item["condition"] for item in learning_results]
    per_turn_valid = all(
        item.get("deployment_effective_models") == [model]
        and len(item.get("deployment_response_ids", [])) == 1
        for item in results
    )
    response_ids = [item["deployment_response_ids"][0] for item in results if item.get("deployment_response_ids")]
    hashed_response_ids = [sha256_bytes(value.encode()) for value in response_ids]
    receipts = deployment["receipts"]
    effective_models = sorted(
        {item["value"] for item in receipts if item["kind"] == "effective_model"}
    )
    model_etags = sorted({item["value"] for item in receipts if item["kind"] == "models_etag"})
    catalog_payload_sha256 = deployment["catalog_payload_sha256"]
    model_etag_sha256 = sha256_bytes(canonical_json(model_etags)) if model_etags else None
    epoch_fields = {
        "requested_model": model,
        "effective_models": effective_models,
        "catalog_payload_sha256": catalog_payload_sha256,
        "models_etag_sha256": model_etag_sha256,
    }
    epoch_identity_sha256 = sha256_bytes(canonical_json(epoch_fields))
    gates = {
        "collector_integrity": deployment.get("collector_errors") == [],
        "effective_model": effective_models == [model],
        "catalog_payload": isinstance(catalog_payload_sha256, str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", catalog_payload_sha256)),
        "catalog_etag": len(model_etags) == 1,
        "per_turn_receipts": per_turn_valid,
        "distinct_response_ids": len(response_ids)
        == len(set(response_ids))
        == acceptance["resource_budget"]["actor_turns_per_run"],
        "counterbalanced_order": observed_order
        == expected_learning_order(task_order, worker["worker_id"]),
    }
    return {
        "effective_models": effective_models,
        "catalog_payload_sha256": catalog_payload_sha256,
        "models_etag_sha256": model_etag_sha256,
        "response_receipts_sha256": sha256_bytes(canonical_json(hashed_response_ids)),
        "response_count": len(response_ids),
        "epoch_identity_sha256": epoch_identity_sha256,
        "gates": gates,
        "valid": all(gates.values()),
    }


def worker_summary(
    worker: dict[str, Any], acceptance: dict[str, Any], task_order: dict[str, Any]
) -> dict[str, Any]:
    summary = behavioral_worker_summary(worker, acceptance)
    behavioral_pass = summary["scientific_pass"]
    deployment = deployment_worker_summary(worker, acceptance, task_order)
    summary["behavioral_pass"] = behavioral_pass
    summary["deployment_epoch"] = deployment
    summary["scientific_pass"] = behavioral_pass and deployment["valid"]
    return summary


def combined_summary(raw: dict[str, Any]) -> dict[str, Any]:
    acceptance = raw["acceptance"]
    task_order = raw["task_order"]
    workers = [worker_summary(worker, acceptance, task_order) for worker in raw["workers"]]
    same_epoch = (
        len(workers) == 2
        and len({worker["deployment_epoch"]["epoch_identity_sha256"] for worker in workers}) == 1
    )
    window_ok = raw["two_worker_window_seconds"] <= acceptance["deployment_epoch"][
        "maximum_two_worker_window_seconds"
    ]
    validity = {
        "worker_deployment_receipts": len(workers) == 2
        and all(worker["deployment_epoch"]["valid"] for worker in workers),
        "same_deployment_epoch": same_epoch,
        "same_task_manifest": raw.get("same_task_manifest", False),
        "two_worker_window": window_ok,
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
    elif workers and not all(worker["behavioral_pass"] for worker in workers):
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
        "model": acceptance["resource_budget"]["model"],
        "model_stability": acceptance["resource_budget"]["model_stability"],
        "task_manifest_sha256": raw["task_manifest_sha256"],
        "two_worker_window_seconds": raw["two_worker_window_seconds"],
        "workers": workers,
        "validity_gates": validity,
        "promotion_gates": promotion,
        "disposition": disposition,
        "evidence_horizon": (
            "private two-process behavioral evidence within one receipted, time-bounded "
            "hosted deployment epoch; no immutable-checkpoint or exact-weight claim"
        ),
    }


def run(
    repo: Path,
    run_id: str,
    codex_bin: Path,
    task_manifest_path: Path,
) -> tuple[Path, dict[str, Any]]:
    execution_commit = require_clean_commit(repo)
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    task_manifest, task_bytes = read_sealed_json(task_manifest_path)
    validate_task_manifest(task_manifest)
    task_digest = sha256_bytes(task_bytes)
    if task_digest != lock.get("task_manifest_sha256"):
        raise RuntimeError("private task manifest differs from the frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    run_root = repo / ".evidence" / "runs" / EXPERIMENT_ID / run_id
    if run_root.exists():
        raise RuntimeError(f"run id already exists: {run_id}")
    run_root.mkdir(parents=True)
    worker_outputs = [run_root / "original.json", run_root / "reproduction.json"]
    worker_roots = [
        repo / ".evidence" / "sandboxes" / f"{run_id}-original",
        repo / ".evidence" / "sandboxes" / f"{run_id}-reproduction",
    ]
    worker_receipts: list[dict[str, Any]] = []
    two_worker_started = time.monotonic()
    for index, (output, workspace) in enumerate(zip(worker_outputs, worker_roots), start=1):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "open_trajectory_harness.ot0014",
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
            capture_output=True,
            text=True,
        )
        worker_receipts.append(
            {
                "worker_id": f"worker-{index}",
                "returncode": process.returncode,
                "stderr_sha256": sha256_bytes(process.stderr.encode()),
                "stderr_lines": len(process.stderr.splitlines()),
            }
        )
        if process.returncode != 0:
            raise RuntimeError(f"worker-{index} failed before producing sealed evidence")
    two_worker_window_seconds = time.monotonic() - two_worker_started

    workers = [read_sealed_json(path)[0] for path in worker_outputs]
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
        "two_worker_window_seconds": two_worker_window_seconds,
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
        kind="predictive-inheritance-hosted-epoch-run",
        evidence_class="private-reproducible",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0014 "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The salted task manifest, outcomes, actor events, complete tool schemas, catalog ETag, and Response IDs remain private.",
            "The hosted deployment is identified only within the observed time-bounded epoch; this is not an immutable-checkpoint or exact-weight claim.",
        ],
        input_manifests=[],
    )
    return manifest, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0014-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0014-hosted-epoch-001")
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
            repo,
            args.run_id,
            args.codex_bin.resolve(),
            args.task_manifest.resolve(),
        )
    except (AppServerError, OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
