from __future__ import annotations

from pathlib import Path
from typing import Any

from . import ot0021_pilot as pilot
from .ot0021_trace import validate_public_task


EXPERIMENT_ID = "OT-0022"
ACCEPTANCE_PATH = Path("spec/ot-0022-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0022-run-lock.json")
TASK_PATH = Path("fixtures/ot-0022/pilot-task.json")
PREDECESSOR_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0021/ot-0021-trace-pilot-001.json"
)


def fixed_input_paths() -> dict[str, Path]:
    paths = {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "public_task_sha256": TASK_PATH,
        "trace_prompt_sha256": pilot.PROMPT_PATH,
        "selector_seed_sha256": pilot.SEED_PATH,
        "output_schema_sha256": pilot.SCHEMA_PATH,
        "trace_projector_sha256": Path(
            "src/open_trajectory_harness/ot0021_trace.py"
        ),
        "pilot_core_sha256": Path("src/open_trajectory_harness/ot0021_pilot.py"),
        "pilot_harness_sha256": Path(
            "src/open_trajectory_harness/ot0022_pilot.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0022_harness.py"),
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
        "dependency_lock_sha256": pilot.LOCK_PATH,
        "tool_receipt_patch_sha256": pilot.PATCH_PATH,
        "deployment_pilot_manifest_sha256": pilot.PILOT_MANIFEST_PATH,
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_PATH,
    }
    return paths


def _validate_task(task: dict[str, Any]) -> None:
    validate_public_task(task, experiment_id=EXPERIMENT_ID)


def configure_protocol() -> None:
    pilot.EXPERIMENT_ID = EXPERIMENT_ID
    pilot.ACCEPTANCE_PATH = ACCEPTANCE_PATH
    pilot.RUN_LOCK_PATH = RUN_LOCK_PATH
    pilot.TASK_PATH = TASK_PATH
    pilot.PREDECESSOR_MANIFEST_PATH = PREDECESSOR_MANIFEST_PATH
    pilot.TASK_VALIDATOR = _validate_task
    pilot.PROGRAM_NAME = "ot-0022-harness"
    pilot.DEFAULT_RUN_ID = "ot-0022-trace-pilot-001"
    pilot.SEALED_EVENT_PREFIX = "sealed2-event-"
    pilot.ARTIFACT_KIND = "response-corrected-consequence-ledger-pilot"
    pilot.INPUT_MANIFESTS = [
        str(PREDECESSOR_MANIFEST_PATH),
        str(pilot.PILOT_MANIFEST_PATH),
    ]
    pilot.fixed_input_paths = fixed_input_paths


def main(argv: list[str] | None = None) -> int:
    configure_protocol()
    return pilot.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
