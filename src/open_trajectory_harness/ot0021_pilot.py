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
from .ot0005 import instrumented_command, run_actor_turn
from .ot0016_credit import (
    CounterfactualSelectorLedger,
    DecisionRuleLedger,
    execute_credit_neutralized_rule,
    execute_decision_rule,
)
from .ot0016_live import _proposal
from .ot0021_trace import (
    EXPERIMENT_ID,
    consequence_ledger,
    seed_consequence_entry,
    validate_public_task,
)


ACCEPTANCE_PATH = Path("spec/ot-0021-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0021-run-lock.json")
TASK_PATH = Path("fixtures/ot-0021/pilot-task.json")
PROMPT_PATH = Path("fixtures/ot-0021/trace-prompt.txt")
SEED_PATH = Path("fixtures/ot-0016/selector-seed.txt")
SCHEMA_PATH = Path("fixtures/ot-0016/challenger-output.schema.json")
LOCK_PATH = Path("requirements-test.lock")
PATCH_PATH = Path("patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch")
PILOT_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0020/ot-0020-inventory-pilot-002.json"
)
PREDECESSOR_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0020/ot-0020-hosted-epoch-001-invalidated.json"
)
TASK_VALIDATOR = validate_public_task
PROGRAM_NAME = "ot-0021-harness"
DEFAULT_RUN_ID = "ot-0021-trace-pilot-001"
SEALED_EVENT_PREFIX = "sealed-event-"
ARTIFACT_KIND = "public-consequence-ledger-feasibility-pilot"
INPUT_MANIFESTS = [str(PREDECESSOR_MANIFEST_PATH), str(PILOT_MANIFEST_PATH)]
PROMPT_RENDERER: Any = None
OUTPUT_EVALUATOR: Any = None
MECHANISM_VALIDATOR: Any = None


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "public_task_sha256": TASK_PATH,
        "trace_prompt_sha256": PROMPT_PATH,
        "selector_seed_sha256": SEED_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "trace_projector_sha256": Path(
            "src/open_trajectory_harness/ot0021_trace.py"
        ),
        "pilot_harness_sha256": Path(
            "src/open_trajectory_harness/ot0021_pilot.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0021_harness.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path(
            "src/open_trajectory_harness/ot0003.py"
        ),
        "hosted_command_sha256": Path("src/open_trajectory_harness/ot0005.py"),
        "expression_world_sha256": Path(
            "src/open_trajectory_harness/ot0005_world.py"
        ),
        "credit_sha256": Path("src/open_trajectory_harness/ot0016_credit.py"),
        "proposal_parser_sha256": Path(
            "src/open_trajectory_harness/ot0016_live.py"
        ),
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "deployment_proxy_sha256": Path(
            "src/open_trajectory_harness/deployment_proxy.py"
        ),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "dependency_lock_sha256": LOCK_PATH,
        "tool_receipt_patch_sha256": PATCH_PATH,
        "deployment_pilot_manifest_sha256": PILOT_MANIFEST_PATH,
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_PATH,
    }


def require_clean_commit(repo: Path) -> str:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0021 execution requires a clean commit")
    commit = git_output(repo, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("OT-0021 execution commit is not a full object id")
    return commit


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    for name in ("implementation_git_commit", "protocol_origin_git_commit"):
        commit = lock.get(name, "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise RuntimeError(f"OT-0021 run lock omits a full {name}")
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, execution_commit],
            cwd=repo,
        ).returncode:
            raise RuntimeError(f"OT-0021 frozen {name} is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if lock.get("fixed_inputs") != observed:
        raise RuntimeError("OT-0021 fixed input identity differs from the run lock")
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{lock['implementation_git_commit']}..{execution_commit}",
        "--",
        *(str(path) for path in fixed_input_paths().values()),
    )
    if changed:
        raise RuntimeError(f"OT-0021 implementation changed after freeze: {changed}")
    binary = lock["backend_binary"]
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if not codex_bin.is_file() or not sidecar.is_file():
        raise RuntimeError("OT-0021 pinned backend pair is absent")
    if sha256_file(codex_bin) != binary["codex_sha256"]:
        raise RuntimeError("OT-0021 Codex binary identity differs")
    if sha256_file(sidecar) != binary["code_mode_host_sha256"]:
        raise RuntimeError("OT-0021 code-mode host identity differs")
    if app_server_version(str(codex_bin)) != binary["version"]:
        raise RuntimeError("OT-0021 backend version differs")
    if sha256_file(Path(certifi.where())) != lock["tls_ca_bundle_sha256"]:
        raise RuntimeError("OT-0021 TLS identity differs")
    return lock


def rendered_prompt(repo: Path, task: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    ledger = consequence_ledger(
        [seed_consequence_entry(task)],
        max_entries=acceptance["ledger_entry_limit"],
        max_bytes=acceptance["ledger_byte_limit"],
    )
    template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    body = (
        template.replace("{{SELECTOR_EXPRESSION}}", "[]")
        .replace("{{DECISION_EXPRESSION}}", '"current"')
        .replace(
            "{{CONSEQUENCE_LEDGER}}",
            json.dumps(ledger, sort_keys=True, separators=(",", ":")),
        )
    )
    seed = (repo / SEED_PATH).read_text(encoding="utf-8")
    return f"{seed}\n\n{body}", ledger


def evaluate_actor_output(task: dict[str, Any], output: Any) -> dict[str, Any]:
    selector_proposal, decision_proposal = _proposal(output)
    selectors = CounterfactualSelectorLedger(iteration_depth_limit=8)
    challenger = selectors.propose(selector_proposal)
    decisions = DecisionRuleLedger()
    rule = decisions.commit(decision_proposal)
    evaluation = task["sealed_pilot_evaluation"]
    receipt = selectors.compare(
        challenger,
        archive=evaluation["archive"],
        queries=evaluation["queries"],
        outcomes=evaluation["outcomes"],
        limit=task["selection_limit"],
        stage=1,
        split_identity="public-noncandidate-trace-pilot",
    )
    true_application = execute_decision_rule(rule, receipt)
    neutralized_application = execute_credit_neutralized_rule(rule, receipt)
    before = selectors.current
    after = selectors.decide_with_rule(challenger, receipt, rule)
    return {
        "selector_challenger": challenger.public_identity(),
        "decision_rule": rule.public_identity(),
        "comparison_receipt_sha256": receipt["receipt_sha256"],
        "selection_changed": receipt["selection_changed"],
        "prediction_changed": receipt["prediction_changed"],
        "challenger_error_advantage": receipt["challenger_error_advantage"],
        "true_choice": true_application["choice"],
        "neutralized_choice": neutralized_application["choice"],
        "decision_replay": true_application["deterministic_replay"]
        and neutralized_application["deterministic_replay"],
        "commit_changed": before.sha256 != after.sha256,
    }


def _summary(
    *,
    acceptance: dict[str, Any],
    actor_results: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    direct_inventories: list[list[dict[str, Any]]],
    proxy_receipts: list[dict[str, Any]],
    collector_errors: list[str],
    usage: dict[str, int],
    elapsed_seconds: float,
    failure_type: str | None,
    verification: dict[str, int],
) -> dict[str, Any]:
    proxy_response_ids = [
        item["value"] for item in proxy_receipts if item["kind"] == "response_id"
    ]
    per_turn_response_ids = [
        item.get("deployment_response_ids", []) for item in actor_results
    ]
    distinct_response_ids = {
        response_id for values in per_turn_response_ids for response_id in values
    }
    effective_models = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "effective_model"}
    )
    etags = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "models_etag"}
    )
    expected_inventory = acceptance["direct_inventory"]
    inventory_valid = len(direct_inventories) == acceptance["fresh_actor_encounters"]
    if inventory_valid:
        first = direct_inventories[0]
        inventory_valid = (
            all(value == first for value in direct_inventories)
            and sha256_bytes(canonical_json(first)) == expected_inventory["sha256"]
            and len(first) == expected_inventory["tool_count"]
        )
    default_mechanism_valid = len(mechanisms) == acceptance[
        "fresh_actor_encounters"
    ] and all(
        item["selection_changed"]
        and item["prediction_changed"]
        and item["challenger_error_advantage"]
        >= acceptance["minimum_error_advantage_each"]
        and item["true_choice"] == "challenger"
        and item["neutralized_choice"] == "current"
        and item["decision_replay"]
        and item["commit_changed"]
        for item in mechanisms
    )
    mechanism_valid = (
        MECHANISM_VALIDATOR(mechanisms, acceptance)
        if MECHANISM_VALIDATOR is not None
        else default_mechanism_valid
    )
    gates = {
        "complete_encounters": len(actor_results)
        == acceptance["fresh_actor_encounters"],
        "parse": all(item["parse_error"] is None for item in actor_results),
        "tools": all(
            item["tool_calls"] <= acceptance["actor_tool_calls_allowed"]
            for item in actor_results
        ),
        "fresh_threads": len({item["thread_id"] for item in actor_results})
        == acceptance["fresh_actor_encounters"],
        "fresh_workspaces": len({item["workspace"] for item in actor_results})
        == acceptance["fresh_actor_encounters"],
        "mechanism": mechanism_valid,
        "effective_model": effective_models == [acceptance["actor_model"]],
        "response_receipts": len(per_turn_response_ids)
        == acceptance["fresh_actor_encounters"]
        and all(len(values) == 1 for values in per_turn_response_ids)
        and len(distinct_response_ids) == acceptance["fresh_actor_encounters"]
        and distinct_response_ids == set(proxy_response_ids),
        "inventory_receipts": all(
            item["inventory_receipts"] == 1 for item in actor_results
        ),
        "direct_inventory": inventory_valid,
        "catalog_etag": len(etags) == 1,
        "collector_integrity": collector_errors == [],
        "input_budget": usage["input_tokens"]
        <= acceptance["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["actor_output_tokens_total"],
        "wall_budget": elapsed_seconds <= acceptance["maximum_run_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": acceptance["purpose"],
        "encounter_count": len(actor_results),
        "mechanisms": mechanisms,
        "effective_models": effective_models,
        "response_count": len(distinct_response_ids),
        "response_receipt_event_count": len(proxy_response_ids),
        "catalog_etag_count": len(etags),
        "collector_error_count": len(collector_errors),
        "usage": usage,
        "elapsed_seconds": elapsed_seconds,
        "failure_type": failure_type,
        "gates": gates,
        "pilot_pass": all(gates.values()),
        "claim_limit": acceptance["claim_limit"],
    }


def run(
    *, repo: Path, run_id: str, codex_bin: Path, output_path: Path, workspace_root: Path
) -> tuple[Path, dict[str, Any]]:
    execution_commit = require_clean_commit(repo)
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task = load_json(repo / TASK_PATH)
    TASK_VALIDATOR(task)
    prompt, ledger = (
        PROMPT_RENDERER(repo, task)
        if PROMPT_RENDERER is not None
        else rendered_prompt(repo, task)
    )
    if SEALED_EVENT_PREFIX in prompt:
        raise RuntimeError("OT-0021 rendered prompt leaks sealed pilot evaluation")
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0021 run output or workspace already exists")
    workspace_root.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    actor_outputs: list[dict[str, Any] | None] = []
    mechanisms: list[dict[str, Any]] = []
    direct_inventories: list[list[dict[str, Any]]] = []
    catalog_payload: list[dict[str, Any]] | None = None
    proxy_receipts: list[dict[str, Any]] = []
    collector_errors: list[str] = []
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
                catalog_payload = client.request(
                    "model/list", {"includeHidden": False}
                )["data"]
                if acceptance["actor_model"] not in {
                    item.get("id") for item in catalog_payload
                }:
                    raise RuntimeError("OT-0021 actor model is unavailable")
                for index in range(acceptance["fresh_actor_encounters"]):
                    result, output = run_actor_turn(
                        client=client,
                        proxy=proxy,
                        model=acceptance["actor_model"],
                        workspace=workspace_root / f"encounter-{index + 1}",
                        role=f"public-trace-pilot-{index + 1}",
                        prompt=prompt,
                        output_schema=load_json(repo / SCHEMA_PATH),
                    )
                    actor_results.append(result)
                    actor_outputs.append(output)
                    direct_inventories.append(
                        client.model_visible_tool_inventories()[-1]
                    )
                    if result["parse_error"] or output is None:
                        raise ValueError("OT-0021 actor output failed exact parsing")
                    mechanisms.append(
                        OUTPUT_EVALUATOR(task, output)
                        if OUTPUT_EVALUATOR is not None
                        else evaluate_actor_output(task, output)
                    )
                time.sleep(1)
                events = client.raw_events
                stderr = client.stderr_lines
    except Exception as error:
        failure_type = type(error).__name__
        failure = str(error)
        if client is not None:
            events = client.raw_events
            stderr = client.stderr_lines
    finally:
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
        [sys.executable, "-m", "open_trajectory_evidence.cli", "audit"],
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
    usage = token_usage(events)
    summary = _summary(
        acceptance=acceptance,
        actor_results=actor_results,
        mechanisms=mechanisms,
        direct_inventories=direct_inventories,
        proxy_receipts=proxy_receipts,
        collector_errors=collector_errors,
        usage=usage,
        elapsed_seconds=elapsed_seconds,
        failure_type=failure_type,
        verification=verification,
    )
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
        "task_sha256": sha256_file(repo / TASK_PATH),
        "ledger": ledger,
        "summary": summary,
        "actor_results": actor_results,
        "actor_outputs": actor_outputs,
        "catalog_payload": catalog_payload,
        "catalog_payload_sha256": sha256_bytes(canonical_json(catalog_payload)),
        "direct_inventories": direct_inventories,
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
            kind=ARTIFACT_KIND,
            evidence_class="exploratory-only",
            recipe=None,
            public_url=None,
            limitations=[
                "This is a public non-candidate carrier pilot, not OT-1 evidence.",
                "The hosted outputs, deployment events, identities, and workspaces remain private.",
                "A pass does not authorize E4 or a private candidate run.",
            ],
            input_manifests=INPUT_MANIFESTS,
        )
    finally:
        output_path.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, summary = run(
            repo=args.repo.resolve(),
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
            {"manifest": str(manifest.relative_to(args.repo.resolve())), "summary": summary},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
