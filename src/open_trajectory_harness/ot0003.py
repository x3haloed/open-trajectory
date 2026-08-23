from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .app_server import AppServerClient, AppServerError
from .ot0002 import (
    base_app_server_command,
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
from .ot0003_world import (
    DiscrepancyGatedVersionLedger,
    Observation,
    generate_task_manifest,
    manifest_batch,
    substrate_conditions,
    validate_task_manifest,
)


EXPERIMENT_ID = "OT-0003"
FIXTURE_ROOT = Path("fixtures/ot-0003")
ACCEPTANCE_PATH = Path("spec/ot-0003-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0003-run-lock.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
LOCK_PATH = Path("requirements-test.lock")


def require_clean_commit(repo: Path) -> str:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0003 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def validate_run_lock(repo: Path, execution_commit: str, codex_bin: Path) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    protocol = lock.get("protocol_origin_git_commit", "")
    for name, commit in (("implementation", implementation), ("protocol", protocol)):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise RuntimeError(f"run lock omits a full {name} commit")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, execution_commit], cwd=repo
        )
        if ancestor.returncode != 0:
            raise RuntimeError(f"frozen {name} commit is not an ancestor of execution HEAD")

    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": FIXTURE_ROOT / "actor-prompt.txt",
        "output_schema_sha256": FIXTURE_ROOT / "actor-output.schema.json",
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "substrates_sha256": FIXTURE_ROOT / "substrates.json",
        "dependency_lock_sha256": LOCK_PATH,
        "receipt_patch_sha256": PATCH_PATH,
    }
    observed = {name: sha256_file(repo / path) for name, path in paths.items()}
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("frozen input identity differs from the OT-0003 run lock")
    protected = [
        "src/open_trajectory_harness",
        "experiments/ot_0003_harness.py",
        "fixtures/ot-0003",
        "spec/ot-0003-acceptance.json",
        str(PATCH_PATH),
        "requirements-test.lock",
    ]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution_commit}",
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
    return lock


def write_sealed_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"sealed output already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))
    path.chmod(0)


def read_sealed_json(path: Path) -> tuple[dict[str, Any], bytes]:
    path.chmod(0o600)
    try:
        encoded = path.read_bytes()
    finally:
        path.chmod(0)
    value = json.loads(encoded)
    if not isinstance(value, dict):
        raise RuntimeError("sealed JSON root is not an object")
    return value, encoded


def prepare_task_manifest(path: Path) -> dict[str, Any]:
    manifest = generate_task_manifest()
    validate_task_manifest(manifest)
    write_sealed_json(path, manifest)
    encoded = canonical_json(manifest)
    return {"sha256": sha256_bytes(encoded), "bytes": len(encoded)}


def instrumented_command(codex_bin: Path) -> list[str]:
    command = base_app_server_command()
    command[0] = str(codex_bin)
    return command


def render_inputs(batch: tuple[tuple[int, int, int, int], ...]) -> str:
    names = ("a", "b", "c", "d")
    return json.dumps([dict(zip(names, item)) for item in batch], separators=(",", ":"))


def run_actor_turn(
    *,
    client: AppServerClient,
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
            "serviceName": "open_trajectory_ot0003",
        }
    )
    prompt = prompt_template.replace("{{PROJECTION}}", projection).replace(
        "{{INPUTS}}", render_inputs(batch)
    )
    receipts_before = len(client.model_visible_tool_inventories())
    turn = client.run_turn(
        thread_id=thread["id"],
        input_text=prompt,
        output_schema=output_schema,
        sandbox_policy={"type": "readOnly", "networkAccess": False},
        timeout=180,
    )
    time.sleep(0.05)
    receipt_count = len(client.model_visible_tool_inventories()) - receipts_before
    output, parse_error = final_agent_json(turn)
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
        "inventory_receipts": receipt_count,
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
    command = instrumented_command(codex_bin)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    client: AppServerClient | None = None
    try:
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
                    phase_results[condition][
                        "substrate_observe_operations"
                    ] = substrate.last_observe_operations

            for ablation in task_order["ablations"]:
                batch, outcomes = manifest_batch(manifest, "regime-b", ablation["batch"])
                result = run_actor_turn(
                    client=client,
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
            "elapsed_seconds": time.monotonic() - started,
        }
        write_sealed_json(output_path, failure)
        raise
    elapsed = time.monotonic() - started
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
        "usage": usage,
        "elapsed_seconds": elapsed,
        "events": events,
        "stderr": stderr,
    }
    write_sealed_json(output_path, worker)


def worker_summary(worker: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    results = worker["results"]
    conditions = ("candidate", "no-persistence", "verbatim-events", "nearest-events")
    heldout_errors = {
        condition: sum(
            item["errors"]
            for item in results
            if item["condition"] == condition and item["score_kind"] == "heldout"
        )
        for condition in conditions
    }
    heldout_predictions = {
        condition: sum(
            len(item["outcomes"])
            for item in results
            if item["condition"] == condition and item["score_kind"] == "heldout"
        )
        for condition in conditions
    }
    post_shift_errors = sum(
        item["errors"]
        for item in results
        if item["condition"] == "candidate" and item["phase"].startswith("regime-b-holdout")
    )
    ablation_errors = sum(
        item["errors"] for item in results if item["condition"] == "candidate-ablation"
    )
    ablation_predictions = sum(
        len(item["outcomes"])
        for item in results
        if item["condition"] == "candidate-ablation"
    )
    parse_failures = sum(bool(item["parse_error"]) for item in results)
    tool_calls = sum(item["tool_calls"] for item in results)
    thread_ids = [item["thread_id"] for item in results]
    workspaces = [item["workspace"] for item in results]
    budget = acceptance["resource_budget"]
    scoring = acceptance["scoring"]
    advantages = {
        condition: heldout_errors[condition] - heldout_errors["candidate"]
        for condition in conditions
        if condition != "candidate"
    }
    inventory = worker["direct_inventory"]
    expected_inventory = acceptance["direct_inventory"]
    gates = {
        "worker_completed": worker.get("status") == "completed",
        "heldout_shape": all(
            count == scoring["heldout_predictions_per_condition"]
            for count in heldout_predictions.values()
        ),
        "candidate_absolute": heldout_errors["candidate"]
        <= scoring["candidate_heldout_errors_allowed"],
        "candidate_post_shift": post_shift_errors
        <= scoring["candidate_post_shift_errors_allowed"],
        "control_advantages": all(
            advantage >= scoring["candidate_error_advantage_over_each_control_required"]
            for advantage in advantages.values()
        ),
        "ablation": ablation_errors >= scoring["candidate_ablation_errors_required"],
        "ablation_shape": ablation_predictions == 8,
        "parse_integrity": parse_failures <= scoring["actor_parse_failures_allowed"],
        "no_actor_tools": tool_calls <= scoring["actor_tool_calls_allowed"],
        "fresh_threads": len(thread_ids) == len(set(thread_ids)) == budget["actor_turns_per_run"],
        "fresh_workspaces": len(workspaces) == len(set(workspaces)) == budget["actor_turns_per_run"],
        "projection_budget": all(
            item["projection_bytes"] <= budget["projection_bytes_per_encounter"]
            for item in results
        ),
        "substrate_compute_budget": all(
            item["substrate_project_operations"] <= budget["substrate_operations_per_transition"]
            and item["substrate_observe_operations"]
            <= budget["substrate_operations_per_transition"]
            for item in results
        ),
        "inventory": inventory["stable"]
        and inventory["sha256"] == expected_inventory["sha256"]
        and inventory["tool_count"] == expected_inventory["tool_count"]
        and all(item["inventory_receipts"] >= 1 for item in results),
        "candidate_state": worker["candidate_state"]["regime"] == 1
        and worker["candidate_state"]["matches_hidden_regime_b"],
        "resource_budget": worker["usage"]["input_tokens"]
        <= budget["actor_input_tokens_total"]
        and worker["usage"]["output_tokens"] <= budget["actor_output_tokens_total"]
        and worker["elapsed_seconds"] <= budget["wall_seconds"],
    }
    return {
        "worker_id": worker["worker_id"],
        "heldout_errors": heldout_errors,
        "heldout_predictions": heldout_predictions,
        "post_shift_candidate_errors": post_shift_errors,
        "ablation_errors": ablation_errors,
        "ablation_predictions": ablation_predictions,
        "control_error_advantages": advantages,
        "parse_failures": parse_failures,
        "tool_calls": tool_calls,
        "direct_inventory": inventory,
        "observed_budget": {
            "actor_turns": len(results),
            **worker["usage"],
            "wall_seconds": worker["elapsed_seconds"],
        },
        "gates": gates,
        "scientific_pass": all(gates.values()),
    }


def combined_summary(raw: dict[str, Any]) -> dict[str, Any]:
    acceptance = raw["acceptance"]
    workers = [worker_summary(worker, acceptance) for worker in raw["workers"]]
    reproduction_pass = (
        len(workers) >= 2
        and all(worker["scientific_pass"] for worker in workers)
        and raw.get("same_task_manifest", False)
    )
    immutable_model = acceptance["resource_budget"]["model_stability"] == "immutable-revision"
    promotion = {
        "clean_predating_implementation": raw.get("implementation_clean", False),
        "original_scientific_gates": bool(workers and workers[0]["scientific_pass"]),
        "clean_reproduction": reproduction_pass,
        "audit_and_tests": raw.get("audit_and_tests", False),
        "immutable_model_revision": immutable_model,
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
        "evidence_horizon": "private two-process behavioral evidence; no promoted OT-1 claim",
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
    for index, (output, workspace) in enumerate(zip(worker_outputs, worker_roots), start=1):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "open_trajectory_harness.ot0003",
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
            {"worker_id": f"worker-{index}", "returncode": process.returncode, "stderr": process.stderr}
        )
        if process.returncode != 0:
            raise RuntimeError(f"worker-{index} failed before producing sealed evidence")

    workers: list[dict[str, Any]] = []
    for output in worker_outputs:
        worker, _ = read_sealed_json(output)
        workers.append(worker)
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
        "workers": workers,
        "worker_receipts": worker_receipts,
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
        evidence_class="exploratory-only",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0003 "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The actor model uses a drifting alias, so this result cannot promote OT-1.",
            "The salted task manifest, outcomes, actor events, and complete tool schemas remain private.",
        ],
        input_manifests=[],
    )
    return manifest, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0003-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0003-appserver-001")
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--prepare-task-manifest", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--worker-id")
    parser.add_argument("--reconstruct", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.prepare_task_manifest:
        print(json.dumps(prepare_task_manifest(args.prepare_task_manifest.resolve()), sort_keys=True))
        return 0
    if args.reconstruct:
        raw = load_json(args.reconstruct)
        sys.stdout.buffer.write(canonical_json(combined_summary(raw)))
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
