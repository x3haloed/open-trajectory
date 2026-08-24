from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import (
    default_store,
    load_manifest,
    object_path,
    record_artifact,
    sha256_file as evidence_sha256_file,
)

from . import ot0021_pilot as pilot
from . import ot0030_further as prior_further
from .app_server import AppServerClient, AppServerError
from .deployment_proxy import SanitizedResponsesProxy
from .ot0002 import (
    canonical_json,
    child_environment,
    load_json,
    sha256_bytes,
    sha256_file,
    token_usage,
)
from .ot0003 import write_sealed_json
from .ot0004_world import selected_events
from .ot0005 import instrumented_command, run_actor_turn
from .ot0005_world import deterministic_predictions
from .ot0021_trace import validate_public_task
from .ot0027_casebook import CasebookSnapshot, execute_casebook, parse_casebook_output


EXPERIMENT_ID = "OT-0031"
ACCEPTANCE_PATH = Path("spec/ot-0031-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0031-run-lock.json")
TASK_PATH = Path("fixtures/ot-0031/pilot-task.json")
SCHEMA_PATH = Path("fixtures/ot-0031/casebook-output.schema.json")
SEED_PATH = Path("fixtures/ot-0031/loop-seed.txt")
PROPOSAL_PROMPT_PATH = Path("fixtures/ot-0031/proposal-prompt.txt")
REVISION_PROMPT_PATH = Path("fixtures/ot-0031/revision-prompt.txt")
SOURCE_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0030/ot-0030-further-correction-pilot-001.json"
)
SOURCE_TASK_PATH = Path("fixtures/ot-0030/pilot-task.json")
SOURCE_ACTOR_INDEX = 1
PROGRAM_NAME = "ot-0031-harness"
DEFAULT_RUN_ID = "ot-0031-propose-score-revise-pilot-001"
ARTIFACT_KIND = "casebook-propose-score-revise-pilot"


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "public_task_sha256": TASK_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "loop_seed_sha256": SEED_PATH,
        "proposal_prompt_sha256": PROPOSAL_PROMPT_PATH,
        "revision_prompt_sha256": REVISION_PROMPT_PATH,
        "source_task_sha256": SOURCE_TASK_PATH,
        "source_manifest_sha256": SOURCE_MANIFEST_PATH,
        "ot0029_task_sha256": Path("fixtures/ot-0029/pilot-task.json"),
        "ot0029_manifest_sha256": Path(
            "evidence/manifests/OT-0029/ot-0029-casebook-reversal-pilot-001.json"
        ),
        "ot0028_task_sha256": Path("fixtures/ot-0028/pilot-task.json"),
        "ot0028_manifest_sha256": Path(
            "evidence/manifests/OT-0028/ot-0028-casebook-correction-pilot-001.json"
        ),
        "ot0027_task_sha256": Path("fixtures/ot-0027/pilot-task.json"),
        "ot0027_manifest_sha256": Path(
            "evidence/manifests/OT-0027/ot-0027-casebook-pilot-001.json"
        ),
        "hosted_pilot_core_sha256": Path(
            "src/open_trajectory_harness/ot0021_pilot.py"
        ),
        "casebook_core_sha256": Path(
            "src/open_trajectory_harness/ot0027_casebook.py"
        ),
        "ot0028_correction_core_sha256": Path(
            "src/open_trajectory_harness/ot0028_correction.py"
        ),
        "ot0029_reversal_core_sha256": Path(
            "src/open_trajectory_harness/ot0029_reversal.py"
        ),
        "ot0030_further_core_sha256": Path(
            "src/open_trajectory_harness/ot0030_further.py"
        ),
        "loop_harness_sha256": Path(
            "src/open_trajectory_harness/ot0031_loop.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0031_harness.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path(
            "src/open_trajectory_harness/ot0003.py"
        ),
        "hosted_command_sha256": Path("src/open_trajectory_harness/ot0005.py"),
        "expression_world_sha256": Path(
            "src/open_trajectory_harness/ot0005_world.py"
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
        "dependency_lock_sha256": pilot.LOCK_PATH,
        "tool_receipt_patch_sha256": pilot.PATCH_PATH,
        "deployment_pilot_manifest_sha256": pilot.PILOT_MANIFEST_PATH,
        "predecessor_manifest_sha256": SOURCE_MANIFEST_PATH,
    }


def configure_protocol() -> None:
    pilot.EXPERIMENT_ID = EXPERIMENT_ID
    pilot.ACCEPTANCE_PATH = ACCEPTANCE_PATH
    pilot.RUN_LOCK_PATH = RUN_LOCK_PATH
    pilot.fixed_input_paths = fixed_input_paths
    pilot.MECHANISM_VALIDATOR = loop_mechanism_valid


def _load_source_raw(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_manifest(repo / SOURCE_MANIFEST_PATH)
    source_path = object_path(default_store(repo), manifest["sha256"])
    if not source_path.is_file():
        raise RuntimeError("OT-0031 source evidence object is unavailable")
    digest, size = evidence_sha256_file(source_path)
    if digest != manifest["sha256"] or size != manifest["bytes"]:
        raise RuntimeError("OT-0031 source evidence identity differs")
    return manifest, load_json(source_path)


def source_projection(
    repo: Path,
    task: dict[str, Any],
    raw: dict[str, Any] | None = None,
    prior_state: CasebookSnapshot | None = None,
) -> tuple[CasebookSnapshot, dict[str, Any]]:
    if raw is None:
        manifest, raw = _load_source_raw(repo)
        source_sha256 = manifest["sha256"]
    else:
        source_sha256 = sha256_bytes(canonical_json(raw))
    if raw.get("experiment_id") != "OT-0030":
        raise ValueError("OT-0031 source experiment identity differs")
    outputs = raw.get("actor_outputs")
    mechanisms = raw.get("summary", {}).get("mechanisms")
    if (
        not isinstance(outputs, list)
        or len(outputs) != 2
        or not isinstance(mechanisms, list)
        or len(mechanisms) != 2
    ):
        raise ValueError("OT-0031 source encounter evidence is incomplete")
    source_task = load_json(repo / SOURCE_TASK_PATH)
    if prior_state is None:
        prior_state, _ = prior_further.source_projection(repo, source_task)
    source_output = outputs[SOURCE_ACTOR_INDEX]
    replay = prior_further.evaluate_further_with_source(
        source_task, source_output, prior_state
    )
    if replay != mechanisms[SOURCE_ACTOR_INDEX]:
        raise ValueError("OT-0031 source further revision does not replay")
    current, _, _ = parse_casebook_output(source_task, source_output)
    completed = task["prior_completed_encounter"]
    if completed != source_task["sealed_pilot_evaluation"]:
        raise ValueError("OT-0031 completed canary projection differs")
    consequence = score_casebook(current, completed, task["selection_limit"])
    body = {
        "schema_version": 1,
        "source_experiment_id": "OT-0030",
        "source_artifact_sha256": source_sha256,
        "source_actor_index": SOURCE_ACTOR_INDEX,
        "current_casebook": {
            "identity": current.public_identity(),
            "exemplars": source_output["exemplars"],
        },
        "completed_encounter": completed,
        "selection_consequences": consequence,
    }
    projection = {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}
    return current, projection


def score_casebook(
    snapshot: CasebookSnapshot, split: dict[str, Any], limit: int
) -> dict[str, Any]:
    selected_ids = execute_casebook(snapshot, split["archive"], limit)
    retained = selected_events(split["archive"], selected_ids)
    predictions = deterministic_predictions(retained, split["queries"])
    query_receipts = [
        {
            "query": list(query),
            "outcome": outcome,
            "prediction": prediction,
            "error": prediction != outcome,
        }
        for query, outcome, prediction in zip(
            split["queries"], split["outcomes"], predictions
        )
    ]
    body = {
        "casebook_sha256": snapshot.sha256,
        "selected_events": retained,
        "query_receipts": query_receipts,
        "errors": sum(item["error"] for item in query_receipts),
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def proposal_prompt(repo: Path, projection: dict[str, Any]) -> str:
    seed = (repo / SEED_PATH).read_text(encoding="utf-8")
    template = (repo / PROPOSAL_PROMPT_PATH).read_text(encoding="utf-8")
    body = template.replace(
        "{{SOURCE_PROJECTION}}",
        json.dumps(projection, sort_keys=True, separators=(",", ":")),
    )
    return f"{seed}\n\n{body}"


def revision_prompt(
    repo: Path,
    projection: dict[str, Any],
    candidate_output: dict[str, Any],
    candidate_receipt: dict[str, Any],
) -> str:
    seed = (repo / SEED_PATH).read_text(encoding="utf-8")
    template = (repo / REVISION_PROMPT_PATH).read_text(encoding="utf-8")
    replacements = {
        "{{SOURCE_PROJECTION}}": json.dumps(
            projection, sort_keys=True, separators=(",", ":")
        ),
        "{{CANDIDATE_CASEBOOK}}": json.dumps(
            candidate_output, sort_keys=True, separators=(",", ":")
        ),
        "{{CANDIDATE_RECEIPT}}": json.dumps(
            candidate_receipt, sort_keys=True, separators=(",", ":")
        ),
    }
    body = template
    for marker, replacement in replacements.items():
        body = body.replace(marker, replacement)
    return f"{seed}\n\n{body}"


def evaluate_loop_branch(
    task: dict[str, Any],
    source: CasebookSnapshot,
    candidate_output: dict[str, Any],
    final_output: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate, _, _ = parse_casebook_output(task, candidate_output)
    final, _, _ = parse_casebook_output(task, final_output)
    completed = task["prior_completed_encounter"]
    future = task["sealed_pilot_evaluation"]
    candidate_completed = score_casebook(
        candidate, completed, task["selection_limit"]
    )
    final_completed = score_casebook(final, completed, task["selection_limit"])
    source_future = score_casebook(source, future, task["selection_limit"])
    final_future = score_casebook(final, future, task["selection_limit"])
    candidate_already_valid = candidate_completed["errors"] <= 2
    feedback_improved = (
        final.sha256 != candidate.sha256
        and final_completed["errors"] < candidate_completed["errors"]
    )
    mechanism = {
        "source_casebook": source.public_identity(),
        "candidate_casebook": candidate.public_identity(),
        "final_casebook": final.public_identity(),
        "candidate_completed_errors": candidate_completed["errors"],
        "final_completed_errors": final_completed["errors"],
        "source_future_errors": source_future["errors"],
        "final_future_errors": final_future["errors"],
        "future_error_advantage": source_future["errors"] - final_future["errors"],
        "candidate_already_valid": candidate_already_valid,
        "feedback_improved": feedback_improved,
        "feedback_resolved": candidate_already_valid or feedback_improved,
        "selection_changed": final_future["selected_events"]
        != source_future["selected_events"],
        "prediction_changed": [
            item["prediction"] for item in final_future["query_receipts"]
        ]
        != [item["prediction"] for item in source_future["query_receipts"]],
        "commit_changed": final.sha256 != source.sha256,
        "deterministic_replay": True,
    }
    return candidate_completed, mechanism


def loop_mechanism_valid(
    mechanisms: list[dict[str, Any]], acceptance: dict[str, Any]
) -> bool:
    return len(mechanisms) == acceptance["branch_count"] and all(
        item["source_future_errors"] >= acceptance["minimum_source_errors_each"]
        and item["final_future_errors"] <= acceptance["maximum_final_errors_each"]
        and item["future_error_advantage"]
        >= acceptance["minimum_future_advantage_each"]
        and item["feedback_resolved"]
        and item["selection_changed"]
        and item["prediction_changed"]
        and item["commit_changed"]
        and item["deterministic_replay"]
        for item in mechanisms
    )


def run(
    *, repo: Path, run_id: str, codex_bin: Path, output_path: Path, workspace_root: Path
) -> tuple[Path, dict[str, Any]]:
    configure_protocol()
    execution_commit = pilot.require_clean_commit(repo)
    lock = pilot.validate_run_lock(repo, execution_commit, codex_bin)
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    task = load_json(repo / TASK_PATH)
    validate_public_task(task, experiment_id=EXPERIMENT_ID)
    source, projection = source_projection(repo, task)
    first_prompt = proposal_prompt(repo, projection)
    if "sealed11-event-" in first_prompt:
        raise RuntimeError("OT-0031 proposal prompt leaks the sealed canary")
    if output_path.exists() or workspace_root.exists():
        raise RuntimeError("OT-0031 run output or workspace already exists")
    workspace_root.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_results: list[dict[str, Any]] = []
    branch_outputs: list[dict[str, Any]] = []
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
                    raise RuntimeError("OT-0031 actor model is unavailable")
                schema = load_json(repo / SCHEMA_PATH)
                for branch in range(acceptance["branch_count"]):
                    proposal_result, proposal_output = run_actor_turn(
                        client=client,
                        proxy=proxy,
                        model=acceptance["actor_model"],
                        workspace=workspace_root / f"branch-{branch + 1}-proposal",
                        role=f"casebook-loop-{branch + 1}-proposal",
                        prompt=first_prompt,
                        output_schema=schema,
                    )
                    actor_results.append(proposal_result)
                    direct_inventories.append(
                        client.model_visible_tool_inventories()[-1]
                    )
                    if proposal_result["parse_error"] or proposal_output is None:
                        raise ValueError("OT-0031 proposal failed exact parsing")
                    candidate, _, _ = parse_casebook_output(task, proposal_output)
                    candidate_receipt = score_casebook(
                        candidate,
                        task["prior_completed_encounter"],
                        task["selection_limit"],
                    )
                    second_prompt = revision_prompt(
                        repo, projection, proposal_output, candidate_receipt
                    )
                    if "sealed11-event-" in second_prompt:
                        raise RuntimeError("OT-0031 revision prompt leaks sealed canary")
                    revision_result, revision_output = run_actor_turn(
                        client=client,
                        proxy=proxy,
                        model=acceptance["actor_model"],
                        workspace=workspace_root / f"branch-{branch + 1}-revision",
                        role=f"casebook-loop-{branch + 1}-revision",
                        prompt=second_prompt,
                        output_schema=schema,
                    )
                    actor_results.append(revision_result)
                    direct_inventories.append(
                        client.model_visible_tool_inventories()[-1]
                    )
                    if revision_result["parse_error"] or revision_output is None:
                        raise ValueError("OT-0031 revision failed exact parsing")
                    scored_candidate, mechanism = evaluate_loop_branch(
                        task, source, proposal_output, revision_output
                    )
                    if scored_candidate != candidate_receipt:
                        raise RuntimeError("OT-0031 candidate receipt changed")
                    branch_outputs.append(
                        {
                            "branch": branch + 1,
                            "candidate": proposal_output,
                            "candidate_receipt": candidate_receipt,
                            "revision": revision_output,
                        }
                    )
                    mechanisms.append(mechanism)
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
    summary = pilot._summary(
        acceptance=acceptance,
        actor_results=actor_results,
        mechanisms=mechanisms,
        direct_inventories=direct_inventories,
        proxy_receipts=proxy_receipts,
        collector_errors=collector_errors,
        usage=token_usage(events),
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
        "source_projection": projection,
        "summary": summary,
        "actor_results": actor_results,
        "branch_outputs": branch_outputs,
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
                "This is a public non-candidate learning-loop pilot, not OT-1 evidence.",
                "Hosted outputs, deployment events, identities, and workspaces remain private.",
                "A pass does not authorize E4 or a private candidate run.",
            ],
            input_manifests=[
                str(SOURCE_MANIFEST_PATH),
                str(pilot.PILOT_MANIFEST_PATH),
            ],
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
