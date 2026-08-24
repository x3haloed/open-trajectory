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
from .ot0003 import write_sealed_json
from .ot0014 import instrumented_command
from .ot0036_e6_calibration import criteria, rule_pairs
from .ot0038_e7_ot2_calibration import build_task, oracle_contract, score_contract
from .ot0040 import run_schema_turn, unsupported_keywords


EXPERIMENT_ID = "OT-0043"
ACCEPTANCE_PATH = Path("spec/ot-0043-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0043-run-lock.json")
PROMPT_PATH = Path("fixtures/ot-0043/pursuit-prompt.txt")
SCHEMA_PATH = Path("fixtures/ot-0043/pursuit-output.schema.json")
LOCK_PATH = Path("requirements-test.lock")
PROXY_PATH = Path("src/open_trajectory_harness/deployment_proxy.py")
TOOL_RECEIPT_PATCH_PATH = Path(
    "patches/codex-rust-v0.149.0-model-visible-tool-receipt.patch"
)
OT42_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0042/ot-0042-e8b-self-authored-goal-candidate-001.json"
)
E8B_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0041/ot-0041-e8b-patched-backend-calibration-001.json"
)
E7_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0038/ot-0038-e7-ot2-evaluator-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0043-e9-split-interface-calibration-001"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,63}")


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "pursuit_prompt_sha256": PROMPT_PATH,
        "pursuit_schema_sha256": SCHEMA_PATH,
        "calibration_harness_sha256": Path(
            "src/open_trajectory_harness/ot0043.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0043_harness.py"),
        "e7_evaluator_sha256": Path(
            "src/open_trajectory_harness/ot0038_e7_ot2_calibration.py"
        ),
        "paired_turn_core_sha256": Path("src/open_trajectory_harness/ot0040.py"),
        "patched_protocol_core_sha256": Path(
            "src/open_trajectory_harness/ot0041.py"
        ),
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
        "rejected_candidate_manifest_sha256": OT42_MANIFEST_PATH,
        "e8b_manifest_sha256": E8B_MANIFEST_PATH,
        "e7_manifest_sha256": E7_MANIFEST_PATH,
    }


def safe_identifier(value: Any, packet: dict[str, Any]) -> bool:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        return False
    if ".." in value or "/" in value or "\\" in value or "@" in value:
        return False
    return value.encode() not in canonical_json(packet)


def score_contract_e9(
    task: dict[str, Any], contract: dict[str, Any], origin: str
) -> dict[str, Any]:
    prior = score_contract(task, contract, origin)
    checks = dict(prior["checks"])
    checks["novel_identifier"] = safe_identifier(
        contract.get("goal_id"), task["raw_packet"]
    )
    quality = all(checks.values())
    body = {
        "checks": checks,
        "quality_pass": quality,
        "origin": origin,
        "ot2_admissible": quality and origin == "actor-output",
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def run_identity_calibration() -> dict[str, Any]:
    cases = [
        (criterion_index, criterion, pair_index, pair)
        for criterion_index, criterion in enumerate(criteria())
        for pair_index, pair in enumerate(rule_pairs())
    ]
    receipts = []
    valid = 0
    invalid = 0
    for criterion_index, criterion, pair_index, pair in cases:
        task = build_task(criterion_index, criterion, pair_index, pair)
        contract = oracle_contract(task)
        digest = sha256_bytes(canonical_json((criterion_index, pair_index)))
        identity_variants = (
            f"g:{digest[:8]}",
            f"goal_{digest[:17]}",
            f"A-{digest[:31]}",
            f"identity.{digest[:49]}",
        )
        contract["goal_id"] = identity_variants[len(receipts) % len(identity_variants)]
        score = score_contract_e9(task, contract, "actor-output")
        valid += score["ot2_admissible"]
        bad_values = (
            "",
            "x" * 65,
            "bad\nidentity",
            "/local/path",
            "name@example.invalid",
            "../escape",
            task["assets"][0]["asset_id"],
        )
        rejected = []
        for value in bad_values:
            mutant = copy.deepcopy(contract)
            mutant["goal_id"] = value
            result = score_contract_e9(task, mutant, "actor-output")
            rejected.append(not result["quality_pass"])
        invalid += all(rejected)
        receipts.append(
            sha256_bytes(
                canonical_json(
                    {
                        "task": task["task_receipt"],
                        "valid": score["receipt_sha256"],
                        "invalid": rejected,
                    }
                )
            )
        )
    body = {
        "case_count": len(cases),
        "valid_case_count": valid,
        "invalid_family_case_count": invalid,
        "receipts_sha256": sha256_bytes(canonical_json(receipts)),
    }
    return {
        **body,
        "pass": valid == len(cases) and invalid == len(cases),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def sentinel_projections() -> list[dict[str, Any]]:
    plans = (1, 2, 2, 3, 3, 3, 3)
    values = []
    for index, plan in enumerate(plans, start=1):
        completed = index == len(plans)
        projection = {
            "goal_id": "goal:sentinel-alpha",
            "goal_status": "completed" if completed else "active",
            "plan_version": plan,
            "experiment_id": f"experiment:sentinel-{plan}",
            "subtask_id": f"subtask:sentinel-{index}",
            "completion_claim": completed,
            "targets": ["service:red", "service:blue", "service:green"],
            "threshold": 21,
            "required_action": f"action:{sha256_bytes(str(index).encode())[:16]}",
        }
        expected = {
            "goal_contract": None,
            "goal_id": projection["goal_id"],
            "goal_status": projection["goal_status"],
            "plan_version": projection["plan_version"],
            "experiment_id": projection["experiment_id"],
            "subtask_id": projection["subtask_id"],
            "action": projection["required_action"],
            "completion_claim": projection["completion_claim"],
        }
        values.append({"projection": projection, "expected": expected})
    return values


def validate_run_lock(
    repo: Path, execution_commit: str, codex_bin: Path
) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0043 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0043 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0043 fixed input identity differs")
    binary = lock.get("backend_binary", {})
    sidecar = codex_bin.with_name("codex-code-mode-host")
    if sha256_file(codex_bin) != binary.get("codex_sha256"):
        raise RuntimeError("Codex executable differs from the OT-0043 lock")
    if sha256_file(sidecar) != binary.get("code_mode_host_sha256"):
        raise RuntimeError("code-mode host differs from the OT-0043 lock")
    if app_server_version(str(codex_bin)) != binary.get("version"):
        raise RuntimeError("Codex version differs from the OT-0043 lock")
    if sha256_file(Path(certifi.where())) != lock.get("tls_ca_bundle_sha256"):
        raise RuntimeError("TLS CA bundle differs from the OT-0043 lock")
    return lock


def summarize(
    acceptance: dict[str, Any],
    identity: dict[str, Any],
    turns: list[dict[str, Any]],
    inventories: list[list[dict[str, Any]] | None],
    catalogs: list[list[dict[str, Any]]],
    proxy_receipts: list[dict[str, Any]],
    usage: dict[str, int],
    elapsed: float,
    verification: dict[str, int],
    failure_type: str | None,
    schema: dict[str, Any],
) -> dict[str, Any]:
    expected_inventory = acceptance["direct_inventory"]
    outputs = sentinel_projections()
    exact = all(
        turn["output"] == outputs[turn["position"]]["expected"]
        for turn in turns
    )
    inventory = all(
        item is not None
        and len(item) == expected_inventory["tool_count"]
        and sha256_bytes(canonical_json(item)) == expected_inventory["sha256"]
        for item in inventories
    )
    response_ids = [value for turn in turns for value in turn["response_ids"]]
    proxy_ids = {
        item["value"] for item in proxy_receipts if item["kind"] == "response_id"
    }
    models = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "effective_model"}
    )
    etags = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "models_etag"}
    )
    gates = {
        "identity_calibration": identity["pass"]
        and identity["case_count"] == acceptance["identity_case_count"],
        "complete": len(turns) == acceptance["hosted_pursuit_turns"],
        "exact_pursuit_copy": exact
        and all(turn["turn_status"] == "completed" for turn in turns)
        and all(turn["parse_error"] is None for turn in turns),
        "schema_subset": unsupported_keywords(schema) == set(),
        "inventory": inventory,
        "tools": all(turn["tool_calls"] == 0 for turn in turns),
        "fresh_threads": len({turn["thread_id"] for turn in turns}) == len(turns),
        "fresh_workspaces": len({turn["workspace"] for turn in turns}) == len(turns),
        "responses": len(response_ids) == len(turns)
        and len(set(response_ids)) == len(turns)
        and set(response_ids) == proxy_ids,
        "model": models == [acceptance["deployment_epoch"]["requested_model"]]
        and all(
            turn["effective_models"]
            == [acceptance["deployment_epoch"]["requested_model"]]
            for turn in turns
        ),
        "catalog": len(catalogs) == 2
        and bool(catalogs[0])
        and catalogs[0] == catalogs[1],
        "etag": len(etags) == 1,
        "input_budget": usage["input_tokens"]
        <= acceptance["resource_budget"]["actor_input_tokens_total"],
        "output_budget": usage["output_tokens"]
        <= acceptance["resource_budget"]["actor_output_tokens_total"],
        "wall_budget": elapsed <= acceptance["resource_budget"]["wall_seconds"],
        "tests": verification["tests_returncode"] == 0,
        "audit": verification["audit_returncode"] == 0,
        "no_runtime_failure": failure_type is None,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "candidate_goal_outputs": False,
        "identity_calibration": identity,
        "hosted_turn_count": len(turns),
        "response_count": len(response_ids),
        "effective_models": models,
        "etag_count": len(etags),
        "usage": usage,
        "elapsed_seconds": elapsed,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "authorized_candidate_count": (
            acceptance["authorized_candidate_count"] if all(gates.values()) else 0
        ),
        "pilot_pass": all(gates.values()),
    }


def run(repo: Path, run_id: str, codex_bin: Path, output: Path, workspace: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0043 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit, codex_bin)
    if output.exists() or workspace.exists():
        raise RuntimeError("OT-0043 output or workspace already exists")
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    prompt_template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    schema = load_json(repo / SCHEMA_PATH)
    identity = run_identity_calibration()
    workspace.mkdir(parents=True)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    turns: list[dict[str, Any]] = []
    inventories: list[list[dict[str, Any]] | None] = []
    catalogs: list[list[dict[str, Any]]] = []
    receipts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    stderr: list[str] = []
    failure_type = None
    failure = None
    started = time.monotonic()
    proxy_ref = None
    client = None
    try:
        with SanitizedResponsesProxy() as proxy:
            proxy_ref = proxy
            with AppServerClient(
                command=instrumented_command(codex_bin, proxy.base_url),
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as active:
                client = active
                model = acceptance["deployment_epoch"]["requested_model"]
                projections = sentinel_projections()
                orders = {
                    "worker-1": list(range(7)),
                    "worker-2": list(reversed(range(7))),
                }
                for worker, order in orders.items():
                    catalog = active.request("model/list", {"includeHidden": False})["data"]
                    catalogs.append(catalog)
                    for position in order:
                        item = projections[position]
                        prompt = prompt_template.replace(
                            "{{PROJECTION}}", canonical_json(item["projection"]).decode()
                        ).replace(
                            "{{PACKET}}",
                            canonical_json({"sealed": True, "phase": position + 1}).decode(),
                        )
                        turn, inventory = run_schema_turn(
                            client=active,
                            proxy=proxy,
                            model=model,
                            workspace=workspace / worker / f"phase-{position + 1}",
                            prompt=prompt,
                            schema=schema,
                            worker=worker,
                            condition="pursuit-copy",
                        )
                        turn["position"] = position
                        turns.append(turn)
                        inventories.append(inventory)
                events = active.raw_events
                stderr = active.stderr_lines
            receipts = proxy.collector.snapshot()
    except Exception as error:
        failure_type = type(error).__name__
        failure = str(error)
        if client is not None:
            events = client.raw_events
            stderr = client.stderr_lines
        if proxy_ref is not None:
            receipts = proxy_ref.collector.snapshot()
    elapsed = time.monotonic() - started
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=repo, env=child_environment(repo), capture_output=True, text=True)
    audit = subprocess.run([sys.executable, "-m", "open_trajectory_evidence", "audit"], cwd=repo, env=child_environment(repo), capture_output=True, text=True)
    verification = {
        "tests_returncode": tests.returncode,
        "tests_stdout_sha256": sha256_bytes(tests.stdout.encode()),
        "tests_stderr_sha256": sha256_bytes(tests.stderr.encode()),
        "audit_returncode": audit.returncode,
        "audit_stdout_sha256": sha256_bytes(audit.stdout.encode()),
        "audit_stderr_sha256": sha256_bytes(audit.stderr.encode()),
    }
    try:
        summary = summarize(acceptance, identity, turns, inventories, catalogs, receipts, token_usage(events), elapsed, verification, failure_type, schema)
    except Exception as error:
        failure_type = failure_type or type(error).__name__
        failure = failure or str(error)
        summary = {"schema_version": 1, "experiment_id": EXPERIMENT_ID, "claim_limit": acceptance["claim_limit"], "gates": {"summary": False}, "disposition": "invalidated", "authorized_candidate_count": 0, "pilot_pass": False}
    raw = {"schema_version": 1, "experiment_id": EXPERIMENT_ID, "run_id": run_id, "implementation_git_commit": lock["implementation_git_commit"], "execution_git_commit": execution_commit, "summary": summary, "turns": turns, "identity": identity, "catalogs": catalogs, "proxy_receipts": receipts, "events": events, "stderr": stderr, "failure": failure, "verification": verification}
    write_sealed_json(output, raw)
    output.chmod(0o600)
    try:
        manifest = record_artifact(repo=repo, input_path=output, experiment_id=EXPERIMENT_ID, artifact_id=run_id, kind="e9-split-interface-identity-calibration", evidence_class="private-reproducible", recipe=None, public_url=None, limitations=["This is evaluator calibration, not OT-2 evidence.", "No candidate goal or task output was generated.", "A pass authorizes at most one fresh E9 candidate.", "Hosted evidence is time-bounded."], input_manifests=[str(OT42_MANIFEST_PATH), str(E8B_MANIFEST_PATH), str(E7_MANIFEST_PATH)])
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0043-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        manifest, summary = run(repo, args.run_id, args.codex_bin.resolve(), args.output.resolve(), args.workspace_root.resolve())
    except (AppServerError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
