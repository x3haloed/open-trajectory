from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .app_server import AppServerClient
from .deployment_proxy import SanitizedResponsesProxy
from .ot0002 import canonical_json, child_environment, sha256_bytes
from .ot0005 import instrumented_command
from .ot0016_live import _actor_turn


MODELS = ("gpt-5.6-luna", "gpt-5.6-terra")
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean", "const": True}},
    "required": ["ok"],
    "additionalProperties": False,
}


def run_probe(repo: Path, codex_bin: Path, workspace_root: Path) -> dict:
    environment = child_environment(repo)
    environment["OT_TOOL_INVENTORY_RECEIPT"] = "1"
    turns = []
    inventories = {}
    with SanitizedResponsesProxy() as proxy:
        with AppServerClient(
            command=instrumented_command(codex_bin, proxy.base_url),
            cwd=repo,
            env=environment,
            request_timeout=180,
        ) as client:
            catalog = client.request("model/list", {"includeHidden": False})["data"]
            available = {item.get("id") for item in catalog}
            if not set(MODELS) <= available:
                raise RuntimeError("inventory probe models are unavailable")
            for index, model in enumerate(MODELS):
                result, output = _actor_turn(
                    client=client,
                    proxy=proxy,
                    model=model,
                    workspace=workspace_root / f"encounter-{index}-{model}",
                    role="non-candidate-inventory-probe",
                    prompt='Return exactly {"ok":true}.',
                    output_schema=OUTPUT_SCHEMA,
                    timeout=180,
                )
                if (
                    result["parse_error"]
                    or output != {"ok": True}
                    or result["tool_calls"]
                ):
                    raise RuntimeError("inventory probe actor contract failed")
                if result["inventory_receipts"] != 1:
                    inventories[model] = {
                        "sha256": None,
                        "tool_count": None,
                        "missing_receipt": True,
                    }
                    turns.append(result)
                    break
                inventory = client.model_visible_tool_inventories()[-1]
                inventories[model] = {
                    "sha256": sha256_bytes(canonical_json(inventory)),
                    "tool_count": len(inventory),
                    "missing_receipt": False,
                }
                turns.append(result)
            time.sleep(1)
            receipts = proxy.collector.snapshot()
            errors = proxy.collector.errors()
    return {
        "schema_version": 1,
        "experiment_id": "OT-0020",
        "purpose": "non-candidate deployment inventory pilot",
        "candidate_outputs_present": False,
        "catalog_payload_sha256": sha256_bytes(canonical_json(catalog)),
        "inventories": inventories,
        "turns": turns,
        "deployment_receipts": receipts,
        "deployment_errors": errors,
        "valid": not errors
        and len(turns) == len(MODELS)
        and all(turn["inventory_receipts"] == 1 for turn in turns)
        and all(
            turn["deployment_effective_models"] == [turn["model"]]
            and len(turn["deployment_response_ids"]) == 1
            for turn in turns
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_probe(
        args.repo.resolve(), args.codex_bin.resolve(), args.workspace_root.resolve()
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"inventories": result["inventories"], "valid": result["valid"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
