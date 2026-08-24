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
from .ot0003 import write_sealed_json
from .ot0014 import instrumented_command


EXPERIMENT_ID = "OT-0040"
ACCEPTANCE_PATH = Path("spec/ot-0040-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0040-run-lock.json")
FIXTURE_ROOT = Path("fixtures/ot-0040")
PROMPT_PATH = FIXTURE_ROOT / "schema-canary-prompt.txt"
POSITIVE_SCHEMA_PATH = FIXTURE_ROOT / "candidate-output.schema.json"
NEGATIVE_SCHEMA_PATH = Path("fixtures/ot-0039/actor-output.schema.json")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
TOOL_RECEIPT_PATCH_PATH = Path(
    "patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch"
)
OT39_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0039/ot-0039-e7-self-authored-goal-candidate-001.json"
)
E7_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0038/ot-0038-e7-ot2-evaluator-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0040-e8-hosted-schema-calibration-001"
CANARY_OUTPUT = {
    "goal_contract": None,
    "goal_id": None,
    "goal_status": "unknown",
    "plan_version": None,
    "experiment_id": None,
    "subtask_id": None,
    "action": "schema-canary",
    "completion_claim": False,
}
ALLOWED_SCHEMA_KEYWORDS = {
    "$schema",
    "type",
    "additionalProperties",
    "required",
    "properties",
    "anyOf",
    "items",
    "enum",
}


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "positive_schema_sha256": POSITIVE_SCHEMA_PATH,
        "negative_schema_sha256": NEGATIVE_SCHEMA_PATH,
        "prompt_sha256": PROMPT_PATH,
        "calibration_harness_sha256": Path(
            "src/open_trajectory_harness/ot0040.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0040_harness.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": PROXY_PATH,
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "ot0_hosted_core_sha256": Path("src/open_trajectory_harness/ot0014.py"),
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "invalidated_candidate_manifest_sha256": OT39_MANIFEST_PATH,
        "e7_manifest_sha256": E7_MANIFEST_PATH,
    }


def unsupported_keywords(schema: Any, *, property_map: bool = False) -> set[str]:
    unsupported: set[str] = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            if not property_map and key not in ALLOWED_SCHEMA_KEYWORDS:
                unsupported.add(key)
            unsupported.update(
                unsupported_keywords(value, property_map=key == "properties")
            )
    elif isinstance(schema, list):
        for value in schema:
            unsupported.update(unsupported_keywords(value))
    return unsupported


def safe_latest_inventory(
    inventories: list[list[dict[str, Any]]], before: int
) -> list[dict[str, Any]] | None:
    return inventories[-1] if len(inventories) > before else None


def turn_error_message(turn: dict[str, Any] | None, caught: str | None) -> str:
    if caught:
        return caught
    if not isinstance(turn, dict):
        return "missing turn"
    error = turn.get("error")
    if isinstance(error, dict):
        return str(error.get("message", ""))
    return str(error or "")


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0040 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0040 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0040 fixed input identity differs")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("pinned Codex executable or code-mode host is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from the OT-0040 lock")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the OT-0040 lock")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex version differs from the OT-0040 lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from the OT-0040 lock")
    return lock


def run_schema_turn(
    *,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace: Path,
    prompt: str,
    schema: dict[str, Any],
    worker: str,
    condition: str,
) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    workspace.mkdir(parents=True, exist_ok=False)
    thread = client.start_thread(
        {
            "model": model,
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "baseInstructions": "Return only the fixed schema canary JSON.",
            "developerInstructions": "Do not call tools or inspect files.",
            "config": {
                "features": {"apps": False, "plugins": False, "js_repl": False},
                "web_search": "disabled",
            },
            "serviceName": "open_trajectory_ot0040",
        }
    )
    deployment_before = len(proxy.collector.snapshot())
    errors_before = len(proxy.collector.errors())
    inventories_before = len(client.model_visible_tool_inventories())
    turn: dict[str, Any] | None = None
    caught: str | None = None
    try:
        turn = client.run_turn(
            thread_id=thread["id"],
            input_text=prompt,
            output_schema=schema,
            sandbox_policy={"type": "readOnly", "networkAccess": False},
            timeout=180,
        )
    except Exception as error:
        caught = f"{type(error).__name__}: {error}"
    inventories = client.model_visible_tool_inventories()
    inventory = safe_latest_inventory(inventories, inventories_before)
    output, parse_error = final_agent_json(turn) if turn is not None else (None, caught)
    deployment = proxy.collector.snapshot()[deployment_before:]
    response_ids = sorted(
        {item["value"] for item in deployment if item["kind"] == "response_id"}
    )
    effective_models = sorted(
        {item["value"] for item in deployment if item["kind"] == "effective_model"}
    )
    tool_calls = (
        client.completed_turn_tool_calls(thread_id=thread["id"], turn_id=turn["id"])
        if isinstance(turn, dict) and isinstance(turn.get("id"), str)
        else 0
    )
    return (
        {
            "worker": worker,
            "condition": condition,
            "workspace": str(workspace.resolve()),
            "thread_id": thread["id"],
            "turn_id": turn.get("id") if isinstance(turn, dict) else None,
            "turn_status": turn.get("status") if isinstance(turn, dict) else "exception",
            "output": output,
            "parse_error": parse_error,
            "error_message": turn_error_message(turn, caught),
            "tool_calls": tool_calls,
            "inventory_present": inventory is not None,
            "response_ids": response_ids,
            "effective_models": effective_models,
            "collector_errors": proxy.collector.errors()[errors_before:],
            "deployment_receipts": deployment,
        },
        inventory,
    )


def summarize(
    *,
    acceptance: dict[str, Any],
    turns: list[dict[str, Any]],
    inventories: list[list[dict[str, Any]] | None],
    catalog_payloads: list[list[dict[str, Any]]],
    proxy_receipts: list[dict[str, Any]],
    usage: dict[str, int],
    elapsed_seconds: float,
    verification: dict[str, int],
    failure_type: str | None,
    positive_schema: dict[str, Any],
) -> dict[str, Any]:
    positives = [turn for turn in turns if turn["condition"] == "positive"]
    negatives = [turn for turn in turns if turn["condition"] == "negative"]
    positive_inventories = [
        inventory
        for turn, inventory in zip(turns, inventories, strict=True)
        if turn["condition"] == "positive"
    ]
    negative_inventories = [
        inventory
        for turn, inventory in zip(turns, inventories, strict=True)
        if turn["condition"] == "negative"
    ]
    expected_inventory = acceptance["direct_inventory"]
    inventory_pass = bool(positive_inventories) and all(
        inventory is not None
        and sha256_bytes(canonical_json(inventory)) == expected_inventory["sha256"]
        and len(inventory) == expected_inventory["tool_count"]
        for inventory in positive_inventories
    )
    response_ids = [value for turn in positives for value in turn["response_ids"]]
    proxy_response_ids = {
        item["value"] for item in proxy_receipts if item["kind"] == "response_id"
    }
    effective_models = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "effective_model"}
    )
    etags = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "models_etag"}
    )
    observed_order = {
        worker: [turn["condition"] for turn in turns if turn["worker"] == worker]
        for worker in ("worker-1", "worker-2")
    }
    gates = {
        "complete": len(turns) == acceptance["hosted_turns"],
        "counterbalance": observed_order
        == {
            "worker-1": ["negative", "positive"],
            "worker-2": ["positive", "negative"],
        },
        "negative_schema": len(negatives) == acceptance["negative_turns"]
        and all(turn["turn_status"] == "failed" for turn in negatives)
        and all("uniqueItems" in turn["error_message"] for turn in negatives)
        and all("invalid_json_schema" in turn["error_message"] for turn in negatives),
        "failure_safe": all(inventory is None for inventory in negative_inventories)
        and all(turn["response_ids"] == [] for turn in negatives)
        and all(turn["collector_errors"] == ["upstream forwarding failed"] for turn in negatives),
        "positive_schema": len(positives) == acceptance["positive_turns"]
        and all(turn["turn_status"] == "completed" for turn in positives)
        and all(turn["output"] == CANARY_OUTPUT for turn in positives)
        and all(turn["parse_error"] is None for turn in positives),
        "schema_subset": unsupported_keywords(positive_schema) == set(),
        "inventory": inventory_pass
        and all(turn["inventory_present"] for turn in positives),
        "tools": all(turn["tool_calls"] == 0 for turn in turns),
        "fresh_threads": len({turn["thread_id"] for turn in turns}) == len(turns),
        "fresh_workspaces": len({turn["workspace"] for turn in turns}) == len(turns),
        "responses": len(response_ids) == acceptance["positive_turns"]
        and len(set(response_ids)) == len(response_ids)
        and set(response_ids) == proxy_response_ids,
        "model": effective_models
        == [acceptance["deployment_epoch"]["requested_model"]]
        and all(
            turn["effective_models"]
            == [acceptance["deployment_epoch"]["requested_model"]]
            for turn in positives
        ),
        "catalog": len(catalog_payloads) == 2
        and bool(catalog_payloads[0])
        and catalog_payloads[0] == catalog_payloads[1],
        "etag": len(etags) == 1,
        "input_budget": usage["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total"],
        "wall_budget": elapsed_seconds
        <= acceptance["resource_budget"]["wall_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "evaluation_transition": acceptance["evaluation_transition"],
        "claim_limit": acceptance["claim_limit"],
        "candidate_goal_outputs": False,
        "positive_turn_count": len(positives),
        "negative_turn_count": len(negatives),
        "response_count": len(response_ids),
        "effective_models": effective_models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed_seconds,
        "failure_type": failure_type,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "authorized_candidate_count": (
            acceptance["authorized_candidate_count"] if all(gates.values()) else 0
        ),
        "pilot_pass": all(gates.values()),
    }


def run(
    *,
    repo: Path,
    run_id: str,
    codex_bin: Path,
    output_path: Path,
    workspace_root: Path,
) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0040 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0040 output or workspace already exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    prompt = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    schemas = {
        "positive": load_json(repo / POSITIVE_SCHEMA_PATH),
        "negative": load_json(repo / NEGATIVE_SCHEMA_PATH),
    }
    workspace_root.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    turns: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]] | None] = []
    catalog_payloads: list[list[dict[str, Any]]] = []
    proxy_receipts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    stderr: list[str] = []
    failure_type: str | None = None
    failure: str | None = None
    started = time.monotonic()
    active_proxy: SanitizedResponsesProxy | None = None
    client: AppServerClient | None = None
    try:
        with SanitizedResponsesProxy() as proxy:
            active_proxy = proxy
            with AppServerClient(
                command=instrumented_command(codex_bin, proxy.base_url),
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as active_client:
                client = active_client
                model = acceptance["deployment_epoch"]["requested_model"]
                orders = {
                    "worker-1": ["negative", "positive"],
                    "worker-2": ["positive", "negative"],
                }
                for worker, order in orders.items():
                    catalog = client.request(
                        "model/list", {"includeHidden": False}
                    )["data"]
                    catalog_payloads.append(catalog)
                    if model not in {item.get("id") for item in catalog}:
                        raise RuntimeError("OT-0040 frozen hosted model is unavailable")
                    for position, condition in enumerate(order):
                        result, inventory = run_schema_turn(
                            client=client,
                            proxy=proxy,
                            model=model,
                            workspace=workspace_root
                            / worker
                            / f"{position}-{condition}",
                            prompt=prompt,
                            schema=schemas[condition],
                            worker=worker,
                            condition=condition,
                        )
                        turns.append(result)
                        inventories.append(inventory)
                events = client.raw_events
                stderr = client.stderr_lines
            proxy_receipts = proxy.collector.snapshot()
    except Exception as error:
        failure_type = type(error).__name__
        failure = str(error)
        if client is not None:
            events = client.raw_events
            stderr = client.stderr_lines
        if active_proxy is not None:
            proxy_receipts = active_proxy.collector.snapshot()
    elapsed_seconds = time.monotonic() - started
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
            acceptance=acceptance,
            turns=turns,
            inventories=inventories,
            catalog_payloads=catalog_payloads,
            proxy_receipts=proxy_receipts,
            usage=token_usage(events),
            elapsed_seconds=elapsed_seconds,
            verification=verification,
            failure_type=failure_type,
            positive_schema=schemas["positive"],
        )
    except Exception as summary_error:
        failure_type = failure_type or type(summary_error).__name__
        failure = failure or str(summary_error)
        summary = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "claim_limit": acceptance["claim_limit"],
            "failure_type": failure_type,
            "gates": {"summary": False},
            "disposition": "invalidated",
            "authorized_candidate_count": 0,
            "pilot_pass": False,
        }
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "summary": summary,
        "turns": turns,
        "catalog_payloads": catalog_payloads,
        "catalog_payloads_sha256": sha256_bytes(canonical_json(catalog_payloads)),
        "proxy_receipts": proxy_receipts,
        "events": events,
        "stderr": stderr,
        "failure": failure,
        "verification": verification,
    }
    write_sealed_json(output_path, raw)
    output_path.chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=output_path,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="e8-hosted-schema-and-failure-path-calibration",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "This is hosted protocol calibration, not OT-2 evidence.",
                "The canary emits no candidate goal or task output.",
                "A pass authorizes at most one fresh E8 candidate.",
                "The hosted deployment is time-bounded.",
            ],
            input_manifests=[str(OT39_MANIFEST_PATH), str(E7_MANIFEST_PATH)],
        )
    finally:
        output_path.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0040-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        manifest, summary = run(
            repo=repo,
            run_id=args.run_id,
            codex_bin=args.codex_bin.resolve(),
            output_path=args.output.resolve(),
            workspace_root=args.workspace_root.resolve(),
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
