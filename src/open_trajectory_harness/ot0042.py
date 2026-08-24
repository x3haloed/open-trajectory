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
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import read_sealed_json, write_sealed_json
from .ot0014 import instrumented_command
from .ot0039 import (
    run_actor_turn,
    summarize as predecessor_summary,
    validate_counterbalance,
)
from .ot0039_world import (
    GoalObservation,
    GoalWorld,
    admission_score,
    hierarchy_correct,
    selector_route_lineage,
    substrate_conditions,
)
from .ot0042_world import (
    EXPERIMENT_ID,
    build_task,
    expected_task_seed,
    validate_task,
)


FIXTURE_ROOT = Path("fixtures/ot-0039")
ACCEPTANCE_PATH = Path("spec/ot-0042-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0042-run-lock.json")
TASK_ORDER_PATH = FIXTURE_ROOT / "task-order.json"
PROMPT_PATH = FIXTURE_ROOT / "actor-prompt.txt"
OUTPUT_SCHEMA_PATH = Path("fixtures/ot-0040/candidate-output.schema.json")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
TOOL_RECEIPT_PATCH_PATH = Path(
    "patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch"
)
E8B_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0041/ot-0041-e8b-patched-backend-calibration-001.json"
)
E7_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0038/ot-0038-e7-ot2-evaluator-calibration-001.json"
)
OT1_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0037/ot-0037-e6-deterministic-ot1-candidate-001.json"
)
OT0_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0014/ot-0014-hosted-epoch-001.json"
)
OT6_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0006/ot-0006-hosted-epoch-001.json"
)
DEFAULT_RUN_ID = "ot-0042-e8b-self-authored-goal-candidate-001"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": TASK_ORDER_PATH,
        "prompt_sha256": PROMPT_PATH,
        "output_schema_sha256": OUTPUT_SCHEMA_PATH,
        "candidate_harness_sha256": Path("src/open_trajectory_harness/ot0042.py"),
        "candidate_world_sha256": Path(
            "src/open_trajectory_harness/ot0042_world.py"
        ),
        "goal_world_core_sha256": Path(
            "src/open_trajectory_harness/ot0039_world.py"
        ),
        "hosted_candidate_core_sha256": Path(
            "src/open_trajectory_harness/ot0039.py"
        ),
        "patched_protocol_core_sha256": Path(
            "src/open_trajectory_harness/ot0041.py"
        ),
        "e7_evaluator_sha256": Path(
            "src/open_trajectory_harness/ot0038_e7_ot2_calibration.py"
        ),
        "ot1_candidate_core_sha256": Path(
            "src/open_trajectory_harness/ot0037_deterministic_candidate.py"
        ),
        "selector_carrier_sha256": Path(
            "src/open_trajectory_harness/ot0033_weighted_selector.py"
        ),
        "integration_adapter_sha256": Path(
            "src/open_trajectory_harness/ot0035_integration.py"
        ),
        "ot0_ledger_core_sha256": Path(
            "src/open_trajectory_harness/ot0003_world.py"
        ),
        "ot0_hosted_core_sha256": Path("src/open_trajectory_harness/ot0014.py"),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": PROXY_PATH,
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "entrypoint_sha256": Path("experiments/ot_0042_harness.py"),
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": TOOL_RECEIPT_PATCH_PATH,
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "e8b_manifest_sha256": E8B_MANIFEST_PATH,
        "e7_manifest_sha256": E7_MANIFEST_PATH,
        "ot1_manifest_sha256": OT1_MANIFEST_PATH,
        "ot0_manifest_sha256": OT0_MANIFEST_PATH,
        "ot2_infrastructure_manifest_sha256": OT6_MANIFEST_PATH,
    }


def prepare_task_manifest(path: Path, implementation_commit: str) -> dict[str, Any]:
    task = build_task(expected_task_seed(implementation_commit))
    validate_task(task)
    write_sealed_json(path, task)
    raw = canonical_json(task)
    return {
        "task_seed": task["task_seed"],
        "task_sha256": sha256_bytes(raw),
        "bytes": len(raw),
    }


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0042 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0042 implementation is not an execution ancestor")
    if lock.get("task_seed") != expected_task_seed(implementation):
        raise RuntimeError("OT-0042 task seed is not mechanically derived")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0042 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution_commit}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"OT-0042 implementation changed after lock: {changed}")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("patched Codex executable or code-mode host is absent")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from the OT-0042 lock")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the OT-0042 lock")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex version differs from the OT-0042 lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from the OT-0042 lock")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    validate_counterbalance(
        load_json(repo / TASK_ORDER_PATH),
        acceptance["deployment_epoch"]["condition_position_count_across_workers"],
    )
    return lock


def execute_worker_safe(
    *,
    task: dict[str, Any],
    task_order: dict[str, Any],
    worker_id: str,
    client: AppServerClient,
    proxy: SanitizedResponsesProxy,
    model: str,
    workspace_root: Path,
    prompt_template: str,
    output_schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[list[dict[str, Any]]]]:
    lineage = selector_route_lineage(task)
    worlds = {
        condition: GoalWorld(task, lineage) for condition in task_order["conditions"]
    }
    substrates = substrate_conditions(task, lineage)
    controllers: dict[str, dict[str, Any] | None] = {
        condition: None for condition in task_order["conditions"]
    }
    results: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    for encounter_index, phase in enumerate(task_order["phases"]):
        pending: dict[str, GoalObservation] = {}
        for condition in phase[worker_id]:
            world = worlds[condition]
            substrate = substrates[condition]
            before_step = world.step
            packet = world.packet(encounter_index)
            projection = substrate.project(512)
            inventories_before = len(client.model_visible_tool_inventories())
            result, output = run_actor_turn(
                client=client,
                proxy=proxy,
                model=model,
                workspace=workspace_root / worker_id / phase["phase"] / condition,
                prompt_template=prompt_template,
                output_schema=output_schema,
                projection=projection,
                packet=packet,
                condition=condition,
                phase=phase["phase"],
                encounter_index=encounter_index,
                task=task,
            )
            observed_inventories = client.model_visible_tool_inventories()
            inventory = (
                observed_inventories[-1]
                if len(observed_inventories) > inventories_before
                else []
            )
            inventories.append(inventory)
            if before_step == 0:
                admission = admission_score(task, output)
                admission_valid = bool(admission["ot2_admissible"])
                if admission_valid and controllers[condition] is None:
                    assert output is not None
                    controllers[condition] = {
                        "contract": copy.deepcopy(output["goal_contract"]),
                        "initial_experiment_id": output["experiment_id"],
                        "initial_subtask_id": output["subtask_id"],
                    }
            else:
                admission = None
                admission_valid = False
            controller = controllers[condition]
            hierarchy_match = hierarchy_correct(
                controller["contract"] if controller else None,
                controller["initial_experiment_id"] if controller else None,
                controller["initial_subtask_id"] if controller else None,
                before_step,
                output,
            )
            receipt = world.apply(output, admission_valid)
            result.update(
                {
                    "worker": worker_id,
                    "world_step_before": before_step,
                    "world_step_after": world.step,
                    "world_receipt": receipt,
                    "admission_score": admission,
                    "hierarchy_correct": hierarchy_match,
                    "inventory_explicit": bool(inventory),
                }
            )
            pending[condition] = GoalObservation(
                packet=packet,
                actor_output=output,
                receipt=receipt,
                admission_valid=admission_valid,
            )
            results.append(result)
        for condition, observation in pending.items():
            substrates[condition].observe(observation)
    mechanism = {
        "worker": worker_id,
        "lineage_receipt_sha256": lineage["receipt_sha256"],
        "candidate_route_errors": lineage["candidate_route_errors"],
        "unchanged_route_errors": lineage["unchanged_route_errors"],
        "regimes": lineage["regimes"],
        "pass": lineage["pass"],
    }
    return results, mechanism, inventories


def goal_novelty(repo: Path, actor_results: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
    sources = "".join(
        (repo / path).read_text(encoding="utf-8")
        for path in (
            Path("src/open_trajectory_harness/ot0042.py"),
            Path("src/open_trajectory_harness/ot0042_world.py"),
            Path("src/open_trajectory_harness/ot0039_world.py"),
            PROMPT_PATH,
        )
    )
    goal_ids = {
        item["actor_output"]["goal_id"]
        for item in actor_results
        if item["encounter_index"] == 0
        and isinstance(item.get("actor_output"), dict)
        and isinstance(item["actor_output"].get("goal_id"), str)
    }
    body = {
        "goal_id_count": len(goal_ids),
        "literal_collision_count": sum(goal_id in sources for goal_id in goal_ids),
        "task_sha256": task["task_sha256"],
    }
    return {
        **body,
        "pass": bool(goal_ids) and body["literal_collision_count"] == 0,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def run(
    *,
    repo: Path,
    run_id: str,
    codex_bin: Path,
    task_manifest_path: Path,
    output_path: Path,
    workspace_root: Path,
) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0042 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    task, task_bytes = read_sealed_json(task_manifest_path)
    validate_task(task)
    if sha256_bytes(task_bytes) != lock.get("task_sha256"):
        raise RuntimeError("OT-0042 private task differs from the run lock")
    if task["task_seed"] != lock.get("task_seed"):
        raise RuntimeError("OT-0042 private task seed differs from the run lock")
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0042 output or workspace already exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task_order = load_json(repo / TASK_ORDER_PATH)
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    output_schema = load_json(repo / OUTPUT_SCHEMA_PATH)
    workspace_root.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]]] = []
    proxy_receipts: list[dict[str, Any]] = []
    collector_errors: list[str] = []
    catalog_payloads: list[list[dict[str, Any]]] = []
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
                for worker_id in ("worker-1", "worker-2"):
                    catalog = client.request(
                        "model/list", {"includeHidden": False}
                    )["data"]
                    catalog_payloads.append(catalog)
                    if model not in {item.get("id") for item in catalog}:
                        raise RuntimeError("OT-0042 frozen hosted model is unavailable")
                    worker_results, mechanism, worker_inventories = execute_worker_safe(
                        task=task,
                        task_order=task_order,
                        worker_id=worker_id,
                        client=client,
                        proxy=proxy,
                        model=model,
                        workspace_root=workspace_root,
                        prompt_template=prompt_template,
                        output_schema=output_schema,
                    )
                    actor_results.extend(worker_results)
                    mechanisms.append(mechanism)
                    inventories.extend(worker_inventories)
                events = client.raw_events
                stderr = client.stderr_lines
            proxy_receipts = proxy.collector.snapshot()
            collector_errors = proxy.collector.errors()
    except Exception as error:
        failure_type = type(error).__name__
        failure = str(error)
        if client is not None:
            events = client.raw_events
            stderr = client.stderr_lines
        if active_proxy is not None:
            proxy_receipts = active_proxy.collector.snapshot()
            collector_errors = active_proxy.collector.errors()
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
        summary = predecessor_summary(
            repo=repo,
            acceptance=acceptance,
            task_order=task_order,
            task=task,
            actor_results=actor_results,
            mechanisms=mechanisms,
            inventories=inventories,
            proxy_receipts=proxy_receipts,
            collector_errors=collector_errors,
            catalog_payloads=catalog_payloads,
            usage=token_usage(events),
            elapsed_seconds=elapsed_seconds,
            verification=verification,
            failure_type=failure_type,
        )
        novelty = goal_novelty(repo, actor_results, task)
        summary["experiment_id"] = EXPERIMENT_ID
        summary["novelty"] = novelty
        summary["gates"]["goal_novelty"] = novelty["pass"]
        summary["disposition"] = (
            "promoted" if all(summary["gates"].values()) else "rejected"
        )
        summary["pilot_pass"] = all(summary["gates"].values())
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
            "pilot_pass": False,
        }
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "task_sha256": task["task_sha256"],
        "summary": summary,
        "mechanisms": mechanisms,
        "actor_results": actor_results,
        "catalog_payloads": catalog_payloads,
        "catalog_payloads_sha256": sha256_bytes(canonical_json(catalog_payloads)),
        "proxy_receipts": proxy_receipts,
        "collector_errors": collector_errors,
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
            kind="e8b-self-authored-durable-goal-hosted-epoch-run",
            evidence_class="private-reproducible",
            recipe=None,
            public_url=None,
            limitations=[
                "Hosted outputs, task identities, world states, and deployment receipts remain private.",
                "A pass is time-bounded single-domain OT-2 evidence, not immutable reproduction.",
                "This run consumes E8B's one-candidate authorization regardless of disposition.",
                "A pass does not establish OT-3 or cross-domain self-direction.",
            ],
            input_manifests=[
                str(E8B_MANIFEST_PATH),
                str(E7_MANIFEST_PATH),
                str(OT1_MANIFEST_PATH),
                str(OT0_MANIFEST_PATH),
                str(OT6_MANIFEST_PATH),
            ],
        )
    finally:
        output_path.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0042-harness")
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
            parser.error("--implementation-commit is required for task preparation")
        print(
            json.dumps(
                prepare_task_manifest(
                    args.prepare_task_manifest.resolve(), args.implementation_commit
                ),
                sort_keys=True,
            )
        )
        return 0
    if (
        args.codex_bin is None
        or args.task_manifest is None
        or args.output is None
        or args.workspace_root is None
    ):
        parser.error(
            "--codex-bin, --task-manifest, --output, and --workspace-root are required"
        )
    try:
        manifest, summary = run(
            repo=repo,
            run_id=args.run_id,
            codex_bin=args.codex_bin.resolve(),
            task_manifest_path=args.task_manifest.resolve(),
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
