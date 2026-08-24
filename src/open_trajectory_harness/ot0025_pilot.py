from __future__ import annotations

from pathlib import Path
from typing import Any

from . import ot0021_pilot as pilot
from . import ot0025_structured as structured
from .ot0021_trace import validate_public_task
from .ot0025_structured import (
    evaluate_structured_output,
    rendered_structured_prompt,
    structured_mechanism_valid,
)


EXPERIMENT_ID = "OT-0025"
ACCEPTANCE_PATH = Path("spec/ot-0025-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0025-run-lock.json")
TASK_PATH = Path("fixtures/ot-0025/pilot-task.json")
SCHEMA_PATH = Path("fixtures/ot-0025/structured-output.schema.json")
PREDECESSOR_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0024/ot-0024-portfolio-pilot-001.json"
)


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "public_task_sha256": TASK_PATH,
        "structured_prompt_sha256": structured.PROMPT_PATH,
        "structured_seed_sha256": structured.SEED_PATH,
        "output_schema_sha256": SCHEMA_PATH,
        "trace_projector_sha256": Path(
            "src/open_trajectory_harness/ot0021_trace.py"
        ),
        "hosted_pilot_core_sha256": Path(
            "src/open_trajectory_harness/ot0021_pilot.py"
        ),
        "credit_carrier_sha256": Path(
            "src/open_trajectory_harness/ot0016_credit.py"
        ),
        "portfolio_comparison_sha256": Path(
            "src/open_trajectory_harness/ot0023_portfolio.py"
        ),
        "structured_core_sha256": Path(
            "src/open_trajectory_harness/ot0025_structured.py"
        ),
        "pilot_harness_sha256": Path(
            "src/open_trajectory_harness/ot0025_pilot.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0025_harness.py"),
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
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_PATH,
    }


def _validate_task(task: dict[str, Any]) -> None:
    validate_public_task(task, experiment_id=EXPERIMENT_ID)


def configure_protocol() -> None:
    structured.EXPERIMENT_ID = EXPERIMENT_ID
    structured.ACCEPTANCE_PATH = ACCEPTANCE_PATH
    pilot.EXPERIMENT_ID = EXPERIMENT_ID
    pilot.ACCEPTANCE_PATH = ACCEPTANCE_PATH
    pilot.RUN_LOCK_PATH = RUN_LOCK_PATH
    pilot.TASK_PATH = TASK_PATH
    pilot.SCHEMA_PATH = SCHEMA_PATH
    pilot.PROMPT_PATH = structured.PROMPT_PATH
    pilot.SEED_PATH = structured.SEED_PATH
    pilot.PREDECESSOR_MANIFEST_PATH = PREDECESSOR_MANIFEST_PATH
    pilot.TASK_VALIDATOR = _validate_task
    pilot.PROGRAM_NAME = "ot-0025-harness"
    pilot.DEFAULT_RUN_ID = "ot-0025-structured-pilot-001"
    pilot.SEALED_EVENT_PREFIX = "sealed5-event-"
    pilot.ARTIFACT_KIND = "structured-decision-contrast-portfolio-pilot"
    pilot.INPUT_MANIFESTS = [
        str(PREDECESSOR_MANIFEST_PATH),
        str(pilot.PILOT_MANIFEST_PATH),
    ]
    pilot.PROMPT_RENDERER = rendered_structured_prompt
    pilot.OUTPUT_EVALUATOR = evaluate_structured_output
    pilot.MECHANISM_VALIDATOR = structured_mechanism_valid
    pilot.fixed_input_paths = fixed_input_paths


def main(argv: list[str] | None = None) -> int:
    configure_protocol()
    return pilot.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
