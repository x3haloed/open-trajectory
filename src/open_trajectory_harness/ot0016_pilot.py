from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .app_server import AppServerClient
from .deployment_proxy import SanitizedResponsesProxy
from .ot0002 import canonical_json, child_environment, load_json, sha256_bytes, token_usage
from .ot0005 import instrumented_command, run_actor_turn
from .ot0016_credit import (
    CounterfactualSelectorLedger,
    DecisionRuleLedger,
    execute_decision_rule,
)


EXPERIMENT_ID = "OT-0016"
FIXTURE_ROOT = Path("fixtures/ot-0016")
ACTOR_MODEL = "gpt-5.6-luna"
PROXY_DRAIN_SECONDS = 1.0


def public_fixture() -> tuple[list[dict[str, Any]], list[list[int]], list[int]]:
    archive = [
        {
            "event_id": f"event-{index}",
            "sequence": index,
            "features": [index & 1, (index >> 1) & 1, (index >> 2) & 1, 0],
            "label": 1,
        }
        for index in range(6)
    ]
    return archive, [event["features"] for event in archive], [1] * len(archive)


def pilot_prompt(repo: Path) -> str:
    seed = (repo / FIXTURE_ROOT / "selector-seed.txt").read_text(encoding="utf-8")
    template = (repo / FIXTURE_ROOT / "challenger-prompt.txt").read_text(encoding="utf-8")
    rendered = (
        template.replace("{{SELECTOR_EXPRESSION}}", "[]")
        .replace("{{DECISION_EXPRESSION}}", '"current"')
        .replace(
            "{{PRIOR_RECEIPT}}",
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "seed",
                    "released_prior_contact": [],
                    "candidate_task_outcomes": False,
                },
                sort_keys=True,
            ),
        )
    )
    return f"{seed}\n\n{rendered}"


def evaluate_pilot_output(output: Any) -> dict[str, Any]:
    expected = {
        "selector_expression",
        "decision_expression",
        "expected_effect",
        "cheapest_falsifier",
    }
    if not isinstance(output, dict) or set(output) != expected:
        raise ValueError("pilot output failed exact schema authority check")
    for name in expected:
        if not isinstance(output[name], str) or not output[name].strip():
            raise ValueError(f"pilot output has invalid {name}")

    common = {
        "expected_effect": output["expected_effect"],
        "cheapest_falsifier": output["cheapest_falsifier"],
    }
    selector_ledger = CounterfactualSelectorLedger()
    challenger = selector_ledger.propose(
        {"expression": output["selector_expression"], **common}
    )
    decision_ledger = DecisionRuleLedger()
    decision_rule = decision_ledger.commit(
        {"expression": output["decision_expression"], **common}
    )
    archive, queries, outcomes = public_fixture()
    receipt = selector_ledger.compare(
        challenger,
        archive=archive,
        queries=queries,
        outcomes=outcomes,
        limit=len(archive),
        stage=0,
        split_identity="public-noncandidate-pilot",
    )
    application = execute_decision_rule(decision_rule, receipt)
    before = selector_ledger.current
    after = selector_ledger.decide_with_rule(challenger, receipt, decision_rule)
    return {
        "selector_challenger": challenger.public_identity(),
        "decision_rule": decision_rule.public_identity(),
        "comparison_receipt_sha256": receipt["receipt_sha256"],
        "selection_changed": receipt["selection_changed"],
        "prediction_changed": receipt["prediction_changed"],
        "challenger_error_advantage": receipt["challenger_error_advantage"],
        "decision_application_sha256": application["receipt_sha256"],
        "decision_choice": application["choice"],
        "commit_changed": before.sha256 != after.sha256,
        "committed_sha256": after.sha256,
        "deterministic_replay": application["deterministic_replay"],
    }


def run_pilot(
    *,
    repo: Path,
    output_path: Path,
    workspace_root: Path,
    codex_bin: Path,
    model: str = ACTOR_MODEL,
) -> None:
    started = time.monotonic()
    workspace_root.mkdir(parents=True, exist_ok=False)
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    actor_result: dict[str, Any] | None = None
    actor_output: dict[str, Any] | None = None
    mechanism: dict[str, Any] | None = None
    failure: str | None = None
    catalog_payload: list[dict[str, Any]] | None = None
    proxy_receipts: list[dict[str, Any]] = []
    collector_errors: list[str] = []
    active_proxy: SanitizedResponsesProxy | None = None
    try:
        with SanitizedResponsesProxy() as proxy:
            active_proxy = proxy
            with AppServerClient(
                command=instrumented_command(codex_bin, proxy.base_url),
                cwd=repo,
                env=environment,
                request_timeout=180,
            ) as client:
                catalog_payload = client.request("model/list", {"includeHidden": False})[
                    "data"
                ]
                if model not in {item.get("id") for item in catalog_payload}:
                    raise RuntimeError("pilot actor model is unavailable")
                actor_result, actor_output = run_actor_turn(
                    client=client,
                    proxy=proxy,
                    model=model,
                    workspace=workspace_root / "encounter-00-challenger",
                    role="noncandidate-challenger",
                    prompt=pilot_prompt(repo),
                    output_schema=load_json(repo / FIXTURE_ROOT / "challenger-output.schema.json"),
                )
                if actor_result["parse_error"]:
                    raise ValueError("pilot actor output did not parse")
                mechanism = evaluate_pilot_output(actor_output)
                # The one-turn pilot otherwise closes its app-server client as
                # soon as the terminal event arrives. Give the proxy thread a
                # bounded interval to forward trailing SSE bytes before the
                # downstream connection is closed.
                time.sleep(PROXY_DRAIN_SECONDS)
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    finally:
        if active_proxy is not None:
            proxy_receipts = active_proxy.collector.snapshot()
            collector_errors = active_proxy.collector.errors()

    response_ids = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "response_id"}
    )
    effective_models = sorted(
        {item["value"] for item in proxy_receipts if item["kind"] == "effective_model"}
    )
    summary = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "one-turn public non-candidate causal-slice pilot",
        "requested_model": model,
        "effective_models": effective_models,
        "response_receipt_count": len(response_ids),
        "actor_parse_valid": bool(actor_result and actor_result["parse_error"] is None),
        "actor_tool_calls": actor_result["tool_calls"] if actor_result else None,
        "inventory_receipts": actor_result["inventory_receipts"] if actor_result else None,
        "mechanism": mechanism,
        "collector_error_count": len(collector_errors),
        "failure": failure,
        "elapsed_seconds": time.monotonic() - started,
        "proxy_drain_seconds": PROXY_DRAIN_SECONDS,
    }
    summary["pilot_pass"] = all(
        (
            failure is None,
            summary["actor_parse_valid"],
            summary["actor_tool_calls"] == 0,
            summary["inventory_receipts"] == 1,
            effective_models == [model],
            len(response_ids) == 1,
            not collector_errors,
            mechanism is not None and mechanism["deterministic_replay"],
        )
    )
    raw = {
        "summary": summary,
        "actor_result": actor_result,
        "actor_output": actor_output,
        "catalog_payload": catalog_payload,
        "catalog_payload_sha256": sha256_bytes(canonical_json(catalog_payload)),
        "proxy_receipts": proxy_receipts,
        "collector_errors": collector_errors,
        "usage": token_usage([actor_result] if actor_result else []),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--model", default=ACTOR_MODEL)
    args = parser.parse_args(argv)
    run_pilot(
        repo=args.repo.resolve(),
        output_path=args.output,
        workspace_root=args.workspace_root,
        codex_bin=args.codex_bin,
        model=args.model,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
