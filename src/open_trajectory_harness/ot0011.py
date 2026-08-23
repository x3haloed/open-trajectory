from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .app_server import AppServerClient, AppServerError
from .ot0002 import (
    LoopbackListener,
    actor_trial,
    app_server_version,
    base_app_server_command,
    canary,
    canonical_json,
    child_environment,
    direct_boundary_probes,
    git_output,
    load_json,
    positive_mcp_probe,
    resumed_thread_positive_control,
    sha256_bytes,
    sha256_file,
    summarize,
    token_usage,
)


EXPERIMENT_ID = "OT-0011"
FIXTURE_ROOT = Path("fixtures/ot-0002")
ACCEPTANCE_PATH = Path("spec/ot-0011-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0011-run-lock.json")
ENCOUNTER_SCHEMA_PATH = Path("spec/ot-0011-run.schema.json")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
LOCK_PATH = Path("requirements-test.lock")


def require_clean_commit(repo: Path) -> str:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0011 execution requires a clean implementation commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("execution commit is not a full Git object id")
    return commit


def validate_run_lock(
    repo: Path,
    execution_commit: str,
    codex_bin: Path,
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation_commit = lock.get("implementation_git_commit", "")
    protocol_origin = lock.get("protocol_origin_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise RuntimeError("run lock omits a full implementation commit")
    if not re.fullmatch(r"[0-9a-f]{40}", protocol_origin):
        raise RuntimeError("run lock omits a full protocol-origin commit")
    for commit in (implementation_commit, protocol_origin):
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, execution_commit],
            cwd=repo,
        )
        if ancestor.returncode != 0:
            raise RuntimeError("frozen commit is not an ancestor of execution HEAD")

    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "prompt_sha256": FIXTURE_ROOT / "actor-prompt.txt",
        "tool_inventory_sha256": FIXTURE_ROOT / "tool-inventory.json",
        "sandbox_policy_sha256": FIXTURE_ROOT / "sandbox-policy.json",
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "dependency_lock_sha256": LOCK_PATH,
        "evaluator_sha256": FIXTURE_ROOT / "evaluator.json",
        "output_schema_sha256": FIXTURE_ROOT / "actor-output.schema.json",
        "receipt_patch_sha256": PATCH_PATH,
        "encounter_schema_sha256": ENCOUNTER_SCHEMA_PATH,
    }
    observed = {name: sha256_file(repo / path) for name, path in paths.items()}
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("frozen input identity differs from the OT-0011 run lock")

    protected = [
        "src/open_trajectory_harness",
        "experiments/ot_0011_harness.py",
        "fixtures/ot-0002",
        "spec/ot-0011-acceptance.json",
        "spec/ot-0011-run.schema.json",
        str(PATCH_PATH),
        "requirements-test.lock",
    ]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation_commit}..{execution_commit}",
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


def boundary_summary(raw: dict[str, Any]) -> dict[str, Any]:
    base = summarize(raw)
    categorical = base["categorical_gates"]
    promotion = {
        "categorical_thresholds": all(categorical.values()),
        "clean_predating_implementation": raw.get("implementation_clean", False),
        "complete_direct_tool_inventory": raw.get("complete_direct_tool_inventory", False),
        "usage_budget_enforceable": raw.get("usage_budget_enforceable", False),
        "independent_summary_reconstruction": raw.get(
            "independent_summary_reconstruction", False
        ),
        "audit_and_tests": raw.get("audit_and_tests", False),
    }
    if not promotion["categorical_thresholds"]:
        disposition = "rejected"
    elif all(promotion.values()):
        disposition = "promoted"
    else:
        disposition = "conditional"
    return {
        **base,
        "experiment_id": EXPERIMENT_ID,
        "promotion_gates": promotion,
        "disposition": disposition,
        "direct_inventory": raw.get("direct_inventory", {}),
    }


def evaluator_projection(raw: dict[str, Any]) -> dict[str, Any]:
    summary = boundary_summary(raw)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "counts": summary["counts"],
        "categorical_gates": summary["categorical_gates"],
        "direct_inventory": raw.get("direct_inventory", {}),
        "observed_budget": raw.get("observed_budget", {}),
    }


def instrumented_command(codex_bin: Path) -> list[str]:
    command = base_app_server_command()
    command[0] = str(codex_bin)
    return command


def run(repo: Path, run_id: str, codex_bin: Path) -> tuple[Path, dict[str, Any]]:
    execution_commit = require_clean_commit(repo)
    run_lock = validate_run_lock(repo, execution_commit, codex_bin)
    implementation_commit = run_lock["implementation_git_commit"]
    protocol_origin = run_lock["protocol_origin_git_commit"]
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / FIXTURE_ROOT / "task-order.json")["order"]
    output_schema = load_json(repo / FIXTURE_ROOT / "actor-output.schema.json")
    prompt_template = (repo / FIXTURE_ROOT / "actor-prompt.txt").read_text(encoding="utf-8")
    evidence_root = repo / ".evidence"
    run_root = evidence_root / "runs" / EXPERIMENT_ID / run_id
    if run_root.exists():
        raise RuntimeError(f"run id already exists: {run_id}")
    run_root.mkdir(parents=True)
    workspace_root = evidence_root / "sandboxes" / run_id
    if workspace_root.exists():
        raise RuntimeError(f"workspace root already exists: {run_id}")
    workspace_root.mkdir(parents=True)

    fixed_inputs = run_lock["fixed_inputs"]
    model = acceptance["resource_budget"]["model"]
    command = instrumented_command(codex_bin)
    os.environ["OT_CONTROLLER_HANDLE_CANARY"] = canary("controller-parent")
    os.environ["OT_PROCESS_INPUT_CANARY"] = canary("process-parent")
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    raw: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": EXPERIMENT_ID,
        "provenance": {
            "protocol_origin_git_commit": protocol_origin,
            "implementation_git_commit": implementation_commit,
            "execution_git_commit": execution_commit,
            "implementation_dirty": False,
            **fixed_inputs,
            **run_lock["backend_binary"],
        },
        "implementation_clean": True,
        "backend": {"kind": "codex-app-server", "version": app_server_version(str(codex_bin))},
        "model": {
            "provider": "openai",
            "name": model,
            "revision": model,
            "stability": acceptance["resource_budget"]["model_stability"],
        },
        "acceptance": acceptance,
        "task_order": task_order,
        "trials": [],
        "complete_direct_tool_inventory": False,
        "independent_summary_reconstruction": False,
        "audit_and_tests": False,
    }
    started = time.monotonic()
    with LoopbackListener() as listener:
        with AppServerClient(
            command=command,
            cwd=repo,
            env=environment,
            request_timeout=180,
            event_log=run_root / "app-server-events.jsonl",
        ) as client:
            models = client.request("model/list", {"includeHidden": False})["data"]
            if model not in {item.get("id") for item in models}:
                raise RuntimeError(f"frozen model is unavailable: {model}")
            raw["direct"] = direct_boundary_probes(
                client=client, workspace_root=workspace_root, listener=listener
            )
            for position in task_order:
                match = re.fullmatch(r"trial-(\d\d)-(projection|null)", position)
                if not match:
                    continue
                index = int(match.group(1))
                raw["trials"].append(
                    actor_trial(
                        client=client,
                        model=model,
                        label=position,
                        condition=match.group(2),
                        index=index,
                        workspace_root=workspace_root,
                        listener=listener,
                        prompt_template=prompt_template,
                        output_schema=output_schema,
                        encounter_context={
                            "repo": repo,
                            "run_id": run_id,
                            "experiment_id": EXPERIMENT_ID,
                            "encounter_schema_path": ENCOUNTER_SCHEMA_PATH,
                            "provenance": {
                                "protocol_origin_git_commit": protocol_origin,
                                "implementation_git_commit": implementation_commit,
                                "implementation_dirty": False,
                                **{
                                    key: fixed_inputs[key]
                                    for key in (
                                        "acceptance_spec_sha256",
                                        "prompt_sha256",
                                        "tool_inventory_sha256",
                                        "sandbox_policy_sha256",
                                        "task_order_sha256",
                                        "dependency_lock_sha256",
                                    )
                                },
                            },
                            "backend": raw["backend"],
                            "model": raw["model"],
                            "budget": acceptance["resource_budget"],
                            "evaluator_sha256": fixed_inputs["evaluator_sha256"],
                        },
                    )
                )
            raw["resumed_thread_positive"] = resumed_thread_positive_control(
                client=client, model=model, workspace_root=workspace_root
            )
            inventories = client.model_visible_tool_inventories()
            raw["app_server_events"] = client.raw_events
            raw["app_server_stderr"] = client.stderr_lines
            raw["usage"] = token_usage(client.raw_events)
        raw["positive_mcp"] = positive_mcp_probe(
            repo,
            workspace_root,
            run_root / "mcp-positive-events.jsonl",
            base_command=command,
            environment=environment,
        )
    raw["elapsed_seconds"] = time.monotonic() - started

    inventory_bytes = canonical_json(inventories[0]) if inventories else b""
    inventory_digest = sha256_bytes(inventory_bytes) if inventories else None
    inventory_stable = bool(inventories) and all(item == inventories[0] for item in inventories)
    actor_turns = len(raw["trials"]) + 2
    per_turn_inventory_receipts = [trial["inventory_receipts"] for trial in raw["trials"]]
    per_turn_inventory_receipts.extend(
        [
            raw["resumed_thread_positive"]["first_inventory_receipts"],
            raw["resumed_thread_positive"]["second_inventory_receipts"],
        ]
    )
    inventory_covers_every_turn = all(count >= 1 for count in per_turn_inventory_receipts)
    raw["direct_inventory"] = {
        "sha256": inventory_digest,
        "tool_count": len(inventories[0]) if inventories else 0,
        "receipt_count": len(inventories),
        "stable": inventory_stable,
        "covers_every_actor_turn": inventory_covers_every_turn,
    }
    expected_inventory = acceptance["direct_inventory"]
    raw["complete_direct_tool_inventory"] = (
        inventory_stable
        and inventory_digest == expected_inventory["sha256"]
        and len(inventories[0]) == expected_inventory["tool_count"]
        and inventory_covers_every_turn
    )

    budget = acceptance["resource_budget"]
    per_turn_tool_calls = [trial["tool_calls"] for trial in raw["trials"]]
    per_turn_tool_calls.extend(
        [
            raw["resumed_thread_positive"]["first_tool_calls"],
            raw["resumed_thread_positive"]["second_tool_calls"],
        ]
    )
    raw["usage_budget_enforceable"] = (
        actor_turns <= budget["actor_turns"]
        and all(count <= budget["actor_tool_calls_per_turn"] for count in per_turn_tool_calls)
        and raw["usage"]["input_tokens"] <= budget["actor_input_tokens_total"]
        and raw["usage"]["output_tokens"] <= budget["actor_output_tokens_total"]
        and raw["elapsed_seconds"] <= budget["wall_seconds"]
    )
    raw["observed_budget"] = {
        "actor_turns": actor_turns,
        "max_tool_calls_per_turn": max(per_turn_tool_calls, default=0),
        **raw["usage"],
        "wall_seconds": raw["elapsed_seconds"],
    }
    first_bytes = canonical_json(summarize(raw))
    second_bytes = canonical_json(summarize(json.loads(json.dumps(raw))))
    raw["deterministic_reconstruction"] = {
        "attempts": 2,
        "matching": first_bytes == second_bytes,
        "sha256": sha256_bytes(first_bytes),
    }

    raw_path = run_root / "run.json"
    raw_path.write_bytes(canonical_json(raw))
    expected_projection = canonical_json(evaluator_projection(raw))
    reconstruction = subprocess.run(
        [
            sys.executable,
            "-m",
            "open_trajectory_harness.ot0011",
            "--reconstruct-evaluator",
            str(raw_path),
        ],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
    )
    raw["independent_summary_reconstruction"] = (
        reconstruction.returncode == 0 and reconstruction.stdout == expected_projection
    )
    raw["independent_reconstruction_receipt"] = {
        "returncode": reconstruction.returncode,
        "expected_sha256": sha256_bytes(expected_projection),
        "observed_sha256": sha256_bytes(reconstruction.stdout),
        "stderr": reconstruction.stderr.decode(errors="replace"),
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
    raw_path.write_bytes(canonical_json(raw))
    manifest = record_artifact(
        repo=repo,
        input_path=raw_path,
        experiment_id=EXPERIMENT_ID,
        artifact_id=run_id,
        kind="harness-run",
        evidence_class="private-reproducible",
        recipe=(
            "PYTHONPATH=src python -m open_trajectory_harness.ot0011 "
            f"--reconstruct-evaluator $EVIDENCE/runs/{EXPERIMENT_ID}/{run_id}/run.json"
        ),
        public_url=None,
        limitations=[
            "The actor model uses a drifting alias; this run makes no learning claim.",
            "Raw model events and complete tool schemas remain in the private evidence store.",
        ],
        input_manifests=[],
    )
    return manifest, boundary_summary(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0011-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0011-appserver-001")
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--reconstruct-evaluator", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.reconstruct_evaluator:
        raw = load_json(args.reconstruct_evaluator)
        sys.stdout.buffer.write(canonical_json(evaluator_projection(raw)))
        return 0
    if args.codex_bin is None:
        parser.error("--codex-bin is required for execution")
    try:
        manifest, summary = run(repo, args.run_id, args.codex_bin.resolve())
    except (AppServerError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
