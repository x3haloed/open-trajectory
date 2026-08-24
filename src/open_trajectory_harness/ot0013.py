from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import canonical_json, child_environment, git_output, load_json, sha256_bytes, sha256_file
from .ot0003 import read_sealed_json, render_inputs, write_sealed_json
from .ot0003 import worker_summary as comparative_worker_summary
from .ot0003_world import (
    DiscrepancyGatedVersionLedger,
    Observation,
    manifest_batch,
    substrate_conditions,
)
from .ot0012 import (
    generate_task_manifest as generate_ot0012_task_manifest,
    local_model_identity,
    validate_task_manifest as validate_ot0012_task_manifest,
)


EXPERIMENT_ID = "OT-0013"
FIXTURE_ROOT = Path("fixtures/ot-0013")
ACCEPTANCE_PATH = Path("spec/ot-0013-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0013-run-lock.json")
LOCK_PATH = Path("requirements-test.lock")


def generate_task_manifest() -> dict[str, Any]:
    manifest = generate_ot0012_task_manifest()
    manifest["experiment_id"] = EXPERIMENT_ID
    return manifest


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0013 task-manifest identity")
    inherited = dict(manifest)
    inherited["experiment_id"] = "OT-0012"
    validate_ot0012_task_manifest(inherited)


def prepare_task_manifest(path: Path) -> dict[str, Any]:
    manifest = generate_task_manifest()
    validate_task_manifest(manifest)
    write_sealed_json(path, manifest)
    encoded = canonical_json(manifest)
    return {"sha256": sha256_bytes(encoded), "bytes": len(encoded)}


def require_clean_commit(repo: Path) -> str:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0013 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def validate_run_lock(
    repo: Path, execution_commit: str, model_identity: dict[str, Any]
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
        "request_sha256": FIXTURE_ROOT / "request.json",
        "dependency_lock_sha256": LOCK_PATH,
        "identity_harness_sha256": Path("src/open_trajectory_harness/ot0012.py"),
    }
    observed = {name: sha256_file(repo / path) for name, path in paths.items()}
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("frozen input identity differs from the OT-0013 run lock")
    protected = [
        "src/open_trajectory_harness/ot0013.py",
        "src/open_trajectory_harness/ot0012.py",
        "experiments/ot_0013_harness.py",
        "tests/test_ot0013_harness.py",
        "fixtures/ot-0013",
        str(ACCEPTANCE_PATH),
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
    if model_identity != lock.get("local_model_identity"):
        raise RuntimeError("local model or inference stack differs from the run lock")
    return lock


def response_schema(frozen: dict[str, Any], expected: int) -> dict[str, Any]:
    schema = json.loads(json.dumps(frozen))
    predictions = schema["properties"]["predictions"]
    predictions["minItems"] = expected
    predictions["maxItems"] = expected
    return schema


def decode_response(value: dict[str, Any], expected: int) -> tuple[list[int], str | None]:
    messages = [item for item in value.get("output", []) if item.get("type") == "message"]
    texts = [
        part.get("text", "")
        for item in messages
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    ]
    if len(texts) != 1:
        return [], "response did not contain exactly one final output_text"
    try:
        output = json.loads(texts[0])
    except json.JSONDecodeError:
        return [], "final output_text was not direct JSON"
    if not isinstance(output, dict) or set(output) != {"predictions"}:
        return [], "actor JSON must contain exactly the predictions key"
    predictions = output["predictions"]
    if (
        not isinstance(predictions, list)
        or len(predictions) != expected
        or any(type(item) is not int or item not in (0, 1) for item in predictions)
    ):
        return [], "prediction vector failed exact shape or binary validation"
    return predictions, None


def post_response(endpoint: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=canonical_json(body),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"LM Studio Responses request failed with HTTP {error.code}: {detail}")
    if not isinstance(value, dict):
        raise RuntimeError("LM Studio Responses result is not an object")
    return value


def run_actor_request(
    *,
    model: str,
    workspace: Path,
    prompt_template: str,
    frozen_schema: dict[str, Any],
    request_spec: dict[str, Any],
    projection: str,
    batch: tuple[tuple[int, int, int, int], ...],
    outcomes: tuple[int, ...],
    condition: str,
    phase: str,
    score_kind: str,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=False)
    prompt = prompt_template.replace("{{PROJECTION}}", projection).replace(
        "{{INPUTS}}", render_inputs(batch)
    )
    body = {
        "model": model,
        "instructions": request_spec["instructions"],
        "input": prompt,
        "reasoning": request_spec["reasoning"],
        "max_output_tokens": request_spec["max_output_tokens"],
        "tools": request_spec["tools"],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ot_binary_predictions",
                "schema": response_schema(frozen_schema, len(outcomes)),
                "strict": True,
            }
        },
    }
    if "previous_response_id" in body or body["tools"] != []:
        raise RuntimeError("actor request is not stateless or has a nonempty tool inventory")
    started = time.monotonic()
    response = post_response(request_spec["endpoint"], body, request_spec["timeout_seconds"])
    elapsed = time.monotonic() - started
    predictions, parse_error = decode_response(response, len(outcomes))
    if response.get("status") != "completed":
        parse_error = parse_error or f"response status was {response.get('status')!r}"
    errors = len(outcomes) if parse_error else sum(
        prediction != outcome for prediction, outcome in zip(predictions, outcomes)
    )
    output = response.get("output", [])
    tool_calls = sum(
        isinstance(item, dict) and item.get("type") in {"function_call", "computer_call"}
        for item in output
    )
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return {
        "condition": condition,
        "phase": phase,
        "score_kind": score_kind,
        "workspace": str(workspace.resolve()),
        "thread_id": response.get("id"),
        "projection": projection,
        "projection_bytes": len(projection.encode()),
        "batch": batch,
        "outcomes": outcomes,
        "predictions": predictions,
        "parse_error": parse_error,
        "errors": errors,
        "tool_calls": tool_calls,
        "inventory_receipts": 1,
        "request_has_no_prior_context": "previous_response_id" not in body,
        "request_sha256": sha256_bytes(canonical_json(body)),
        "request": body,
        "response": response,
        "response_status": response.get("status"),
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "elapsed_seconds": elapsed,
    }


def execute_worker(
    *,
    repo: Path,
    task_manifest_path: Path,
    output_path: Path,
    workspace_root: Path,
    worker_id: str,
) -> None:
    execution_commit = require_clean_commit(repo)
    identity = local_model_identity()
    lock = validate_run_lock(repo, execution_commit, identity)
    manifest, task_bytes = read_sealed_json(task_manifest_path)
    validate_task_manifest(manifest)
    if sha256_bytes(task_bytes) != lock.get("task_manifest_sha256"):
        raise RuntimeError("private task manifest differs from the frozen digest")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")
    frozen_schema = load_json(repo / FIXTURE_ROOT / "actor-output.schema.json")
    request_spec = load_json(repo / FIXTURE_ROOT / "request.json")
    prompt_template = (repo / FIXTURE_ROOT / "actor-prompt.txt").read_text(encoding="utf-8")
    projection_limit = acceptance["resource_budget"]["projection_bytes_per_encounter"]
    model = acceptance["resource_budget"]["model"]
    substrates = substrate_conditions()
    workspace_root.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    started_at = time.monotonic()
    try:
        for phase_spec in task_order["phases"]:
            phase = phase_spec["phase"]
            regime = "regime-a" if phase.startswith("regime-a") else "regime-b"
            batch, outcomes = manifest_batch(manifest, regime, phase_spec["batch"])
            observations = [
                Observation(features, outcome) for features, outcome in zip(batch, outcomes)
            ]
            requests: list[dict[str, Any]] = []
            for condition in task_order["conditions"]:
                substrate = substrates[condition]
                projection = substrate.project(batch, projection_limit)
                requests.append(
                    {
                        "model": model,
                        "workspace": workspace_root / f"{phase}-{condition}",
                        "prompt_template": prompt_template,
                        "frozen_schema": frozen_schema,
                        "request_spec": request_spec,
                        "projection": projection,
                        "batch": batch,
                        "outcomes": outcomes,
                        "condition": condition,
                        "phase": phase,
                        "score_kind": phase_spec["score"],
                        "substrate_project_operations": substrate.last_project_operations,
                    }
                )
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = [
                    pool.submit(
                        run_actor_request,
                        **{key: value for key, value in item.items() if key != "substrate_project_operations"},
                    )
                    for item in requests
                ]
                phase_results = [future.result() for future in futures]
            by_condition = {item["condition"]: item for item in phase_results}
            for item, request_item in zip(phase_results, requests):
                item["substrate_project_operations"] = request_item[
                    "substrate_project_operations"
                ]
                results.append(item)
            for condition, substrate in substrates.items():
                substrate.observe(observations)
                by_condition[condition]["substrate_observe_operations"] = (
                    substrate.last_observe_operations
                )
        ablation_requests: list[dict[str, Any]] = []
        for ablation in task_order["ablations"]:
            batch, outcomes = manifest_batch(manifest, "regime-b", ablation["batch"])
            ablation_requests.append(
                {
                    "model": model,
                    "workspace": workspace_root / ablation["phase"],
                    "prompt_template": prompt_template,
                    "frozen_schema": frozen_schema,
                    "request_spec": request_spec,
                    "projection": "[candidate projection ablated]",
                    "batch": batch,
                    "outcomes": outcomes,
                    "condition": "candidate-ablation",
                    "phase": ablation["phase"],
                    "score_kind": "ablation",
                }
            )
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_actor_request, **item) for item in ablation_requests]
            ablation_results = [future.result() for future in futures]
        for item in ablation_results:
            item["substrate_project_operations"] = 0
            item["substrate_observe_operations"] = 0
            results.append(item)
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
            "elapsed_seconds": time.monotonic() - started_at,
        }
        write_sealed_json(output_path, failure)
        raise
    candidate = substrates["candidate"]
    assert isinstance(candidate, DiscrepancyGatedVersionLedger)
    inventory_bytes = canonical_json(request_spec["tools"])
    usage = {
        key: sum(item["usage"][key] for item in results)
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }
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
            "sha256": sha256_bytes(inventory_bytes),
            "tool_count": len(request_spec["tools"]),
            "receipt_count": len(results),
            "stable": all(item["request"]["tools"] == request_spec["tools"] for item in results),
        },
        "usage": usage,
        "elapsed_seconds": time.monotonic() - started_at,
    }
    write_sealed_json(output_path, worker)


def worker_summary(worker: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    summary = comparative_worker_summary(worker, acceptance)
    budget = acceptance["resource_budget"]
    summary["gates"]["content_addressed_model"] = worker.get("model_identity_verified") is True
    summary["gates"]["stateless_requests"] = all(
        item.get("request_has_no_prior_context") is True for item in worker["results"]
    )
    summary["gates"]["output_cap"] = all(
        item["usage"]["output_tokens"] <= budget["actor_max_output_tokens_per_turn"]
        for item in worker["results"]
    )
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


def run(repo: Path, run_id: str, task_manifest_path: Path) -> tuple[Path, dict[str, Any]]:
    execution_commit = require_clean_commit(repo)
    identity = local_model_identity()
    lock = validate_run_lock(repo, execution_commit, identity)
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
    receipts: list[dict[str, Any]] = []
    for index, (output, workspace) in enumerate(zip(outputs, worker_roots), start=1):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "open_trajectory_harness.ot0013",
                "--worker",
                "--repo",
                str(repo),
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
            "PYTHONPATH=src python -m open_trajectory_harness.ot0013 "
            f"--reconstruct $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The salted task manifest, outcomes, actor requests, responses, and reasoning remain private.",
            "Model weights are content-addressed local artifacts and are not committed to this repository.",
        ],
        input_manifests=[],
    )
    return manifest, combined_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0013-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0013-direct-001")
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
        sys.stdout.buffer.write(canonical_json(combined_summary(load_json(args.reconstruct))))
        return 0
    if args.task_manifest is None:
        parser.error("--task-manifest is required")
    try:
        if args.worker:
            if args.worker_output is None or args.workspace_root is None or not args.worker_id:
                parser.error("worker output, workspace root, and worker id are required")
            execute_worker(
                repo=repo,
                task_manifest_path=args.task_manifest.resolve(),
                output_path=args.worker_output.resolve(),
                workspace_root=args.workspace_root.resolve(),
                worker_id=args.worker_id,
            )
            return 0
        manifest, summary = run(repo, args.run_id, args.task_manifest.resolve())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
