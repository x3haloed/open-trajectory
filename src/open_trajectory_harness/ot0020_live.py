from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import ot0016_live as live
from .app_server import AppServerError
from .ot0002 import canonical_json, load_json
from .ot0016 import combined_summary
from .ot0020_world import EXPERIMENT_ID, generate_task_manifest, validate_task_manifest


FIXTURE_ROOT = Path("fixtures/ot-0016")
ACCEPTANCE_PATH = Path("spec/ot-0020-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0020-run-lock.json")
WORKER_MODULE = "open_trajectory_harness.ot0020_live"


def fixed_input_paths() -> dict[str, Path]:
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "task_order_sha256": FIXTURE_ROOT / "task-order.json",
        "dependency_lock_sha256": live.LOCK_PATH,
        "tool_receipt_patch_sha256": live.TOOL_RECEIPT_PATCH_PATH,
        "deployment_proxy_sha256": live.PROXY_PATH,
        "app_server_sha256": Path("src/open_trajectory_harness/app_server.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "inherited_world_sha256": Path("src/open_trajectory_harness/ot0004_world.py"),
        "hosted_command_sha256": Path("src/open_trajectory_harness/ot0005.py"),
        "expression_world_sha256": Path("src/open_trajectory_harness/ot0005_world.py"),
        "e4_constructor_sha256": Path("src/open_trajectory_harness/ot0017_regime.py"),
        "world_sha256": Path("src/open_trajectory_harness/ot0020_world.py"),
        "credit_sha256": Path("src/open_trajectory_harness/ot0016_credit.py"),
        "evaluator_sha256": Path("src/open_trajectory_harness/ot0016.py"),
        "harness_core_sha256": Path("src/open_trajectory_harness/ot0016_live.py"),
        "harness_sha256": Path("src/open_trajectory_harness/ot0020_live.py"),
        "entrypoint_sha256": Path("experiments/ot_0020_harness.py"),
        "e4_promotion_manifest_sha256": Path(
            "evidence/manifests/OT-0019/ot-0019-full-suffix-e4-calibration-001.json"
        ),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
    }
    for name in (
        "selector-seed.txt",
        "challenger-prompt.txt",
        "challenger-output.schema.json",
        "novelty-rubric.txt",
        "novelty-output.schema.json",
    ):
        key = f"fixture_{name.replace('.', '_').replace('-', '_')}_sha256"
        paths[key] = FIXTURE_ROOT / name
    return paths


def configure_live_protocol() -> None:
    live.EXPERIMENT_ID = EXPERIMENT_ID
    live.FIXTURE_ROOT = FIXTURE_ROOT
    live.ACCEPTANCE_PATH = ACCEPTANCE_PATH
    live.RUN_LOCK_PATH = RUN_LOCK_PATH
    live.WORKER_MODULE = WORKER_MODULE
    live.SERVICE_NAME = "open_trajectory_ot0020"
    live.ARTIFACT_KIND = "e4-counterfactual-challenger-hosted-epoch-run"
    live.EVIDENCE_LIMITATIONS = [
        "The E4 task, expressions, selections, actor events, reviews, ETag, and Response IDs remain private.",
        "The result is limited to one direct E4 family and a time-bounded hosted epoch.",
    ]
    live.generate_task_manifest = generate_task_manifest
    live.validate_task_manifest = validate_task_manifest
    live.fixed_input_paths = fixed_input_paths
    live.combined_summary = combined_summary


def main(argv: list[str] | None = None) -> int:
    configure_live_protocol()
    parser = argparse.ArgumentParser(prog="ot-0020-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="ot-0020-hosted-epoch-001")
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--prepare-task-manifest", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--worker-id", choices=("worker-1", "worker-2"))
    parser.add_argument("--reconstruct", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.prepare_task_manifest:
        result: dict[str, Any] = live.prepare_task_manifest(
            args.prepare_task_manifest.resolve()
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.reconstruct:
        sys.stdout.buffer.write(
            canonical_json(combined_summary(load_json(args.reconstruct)))
        )
        return 0
    if args.codex_bin is None or args.task_manifest is None:
        parser.error("--codex-bin and --task-manifest are required")
    try:
        if args.worker:
            if (
                args.worker_output is None
                or args.workspace_root is None
                or not args.worker_id
            ):
                parser.error(
                    "worker output, workspace root, and worker id are required"
                )
            live.execute_worker(
                repo=repo,
                task_manifest_path=args.task_manifest.resolve(),
                output_path=args.worker_output.resolve(),
                workspace_root=args.workspace_root.resolve(),
                codex_bin=args.codex_bin.resolve(),
                worker_id=args.worker_id,
            )
            return 0
        manifest, summary = live.run(
            repo, args.run_id, args.codex_bin.resolve(), args.task_manifest.resolve()
        )
    except (AppServerError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(repo)), "summary": summary}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
