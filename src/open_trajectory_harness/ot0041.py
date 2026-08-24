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
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import write_sealed_json
from .ot0014 import instrumented_command
from .ot0040 import (
    CANARY_OUTPUT,
    NEGATIVE_SCHEMA_PATH,
    POSITIVE_SCHEMA_PATH,
    PROMPT_PATH,
    run_schema_turn,
    unsupported_keywords,
)


EXPERIMENT_ID = "OT-0041"
ACCEPTANCE_PATH = Path("spec/ot-0041-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0041-run-lock.json")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
TOOL_RECEIPT_PATCH_PATH = Path(
    "patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch"
)
OT40_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0040/ot-0040-e8-hosted-schema-calibration-001.json"
)
OT39_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0039/ot-0039-e7-self-authored-goal-candidate-001.json"
)
DEFAULT_RUN_ID = "ot-0041-e8b-patched-backend-calibration-001"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "positive_schema_sha256": POSITIVE_SCHEMA_PATH,
        "negative_schema_sha256": NEGATIVE_SCHEMA_PATH,
        "prompt_sha256": PROMPT_PATH,
        "calibration_harness_sha256": Path(
            "src/open_trajectory_harness/ot0041.py"
        ),
        "paired_turn_core_sha256": Path("src/open_trajectory_harness/ot0040.py"),
        "entrypoint_sha256": Path("experiments/ot_0041_harness.py"),
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
        "rejected_calibration_manifest_sha256": OT40_MANIFEST_PATH,
        "invalidated_candidate_manifest_sha256": OT39_MANIFEST_PATH,
    }


def negative_turn_safe(
    turn: dict[str, Any], inventory: list[dict[str, Any]] | None
) -> bool:
    return (
        turn.get("turn_status") == "failed"
        and "uniqueItems" in turn.get("error_message", "")
        and "invalid_json_schema" in turn.get("error_message", "")
        and turn.get("response_ids") == []
        and turn.get("collector_errors") == []
        and turn.get("turn_status") != "exception"
        and (inventory is None or isinstance(inventory, list))
    )


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0041 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0041 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0041 fixed input identity differs")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("patched Codex executable or code-mode host is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from the OT-0041 lock")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the OT-0041 lock")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex version differs from the OT-0041 lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from the OT-0041 lock")
    return lock


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
    positives = [
        (turn, inventory)
        for turn, inventory in zip(turns, inventories, strict=True)
        if turn["condition"] == "positive"
    ]
    negatives = [
        (turn, inventory)
        for turn, inventory in zip(turns, inventories, strict=True)
        if turn["condition"] == "negative"
    ]
    expected_inventory = acceptance["direct_inventory"]
    positive_inventory = all(
        inventory is not None
        and sha256_bytes(canonical_json(inventory)) == expected_inventory["sha256"]
        and len(inventory) == expected_inventory["tool_count"]
        for _, inventory in positives
    )
    response_ids = [value for turn, _ in positives for value in turn["response_ids"]]
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
        "negative_failure_path": len(negatives) == acceptance["negative_turns"]
        and all(negative_turn_safe(*pair) for pair in negatives),
        "positive_schema": len(positives) == acceptance["positive_turns"]
        and all(turn["turn_status"] == "completed" for turn, _ in positives)
        and all(turn["output"] == CANARY_OUTPUT for turn, _ in positives)
        and all(turn["parse_error"] is None for turn, _ in positives),
        "schema_subset": unsupported_keywords(positive_schema) == set(),
        "positive_inventory": positive_inventory,
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
            for turn, _ in positives
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
        "negative_inventory_states": [
            "present" if inventory is not None else "absent"
            for _, inventory in negatives
        ],
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
        raise RuntimeError("OT-0041 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0041 output or workspace already exists")
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
                        raise RuntimeError("OT-0041 frozen hosted model is unavailable")
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
            kind="e8b-patched-backend-protocol-calibration",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "This is hosted protocol calibration, not OT-2 evidence.",
                "The canary emits no candidate goal or task output.",
                "A pass authorizes at most one fresh E8B candidate.",
                "The hosted deployment is time-bounded.",
            ],
            input_manifests=[str(OT40_MANIFEST_PATH), str(OT39_MANIFEST_PATH)],
        )
    finally:
        output_path.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0041-harness")
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
