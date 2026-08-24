from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import (
    default_store,
    load_manifest,
    object_path,
    sha256_file as evidence_sha256_file,
)

from . import ot0028_correction as prior_correction
from .ot0002 import canonical_json, load_json, sha256_bytes
from .ot0004_world import selected_events
from .ot0005_world import deterministic_predictions
from .ot0027_casebook import CasebookSnapshot, execute_casebook, parse_casebook_output


EXPERIMENT_ID = "OT-0029"
ACCEPTANCE_PATH = Path("spec/ot-0029-acceptance.json")
PROMPT_PATH = Path("fixtures/ot-0029/reversal-prompt.txt")
SEED_PATH = Path("fixtures/ot-0029/reversal-seed.txt")
SOURCE_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0028/ot-0028-casebook-correction-pilot-001.json"
)
SOURCE_TASK_PATH = Path("fixtures/ot-0028/pilot-task.json")
SOURCE_ACTOR_INDEX = 0
REPO_ROOT = Path(".")


def _load_source_raw(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_manifest(repo / SOURCE_MANIFEST_PATH)
    source_path = object_path(default_store(repo), manifest["sha256"])
    if not source_path.is_file():
        raise RuntimeError("OT-0029 source evidence object is unavailable")
    digest, size = evidence_sha256_file(source_path)
    if digest != manifest["sha256"] or size != manifest["bytes"]:
        raise RuntimeError("OT-0029 source evidence identity differs")
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
    if raw.get("experiment_id") != "OT-0028":
        raise ValueError("OT-0029 source experiment identity differs")
    outputs = raw.get("actor_outputs")
    mechanisms = raw.get("summary", {}).get("mechanisms")
    if (
        not isinstance(outputs, list)
        or len(outputs) != 2
        or not isinstance(mechanisms, list)
        or len(mechanisms) != 2
    ):
        raise ValueError("OT-0029 source encounter evidence is incomplete")
    source_task = load_json(repo / SOURCE_TASK_PATH)
    prior_correction.REPO_ROOT = repo
    if prior_state is None:
        prior_state, _ = prior_correction.source_projection(repo, source_task)
    source_output = outputs[SOURCE_ACTOR_INDEX]
    replay = prior_correction.evaluate_correction_with_source(
        source_task, source_output, prior_state
    )
    if replay != mechanisms[SOURCE_ACTOR_INDEX]:
        raise ValueError("OT-0029 source correction does not replay")
    current, _, _ = parse_casebook_output(source_task, source_output)
    completed = task["prior_completed_encounter"]
    selected_ids = execute_casebook(
        current, completed["archive"], task["selection_limit"]
    )
    retained = selected_events(completed["archive"], selected_ids)
    predictions = deterministic_predictions(retained, completed["queries"])
    query_receipts = [
        {
            "query": list(query),
            "outcome": outcome,
            "prediction": prediction,
            "error": prediction != outcome,
        }
        for query, outcome, prediction in zip(
            completed["queries"], completed["outcomes"], predictions
        )
    ]
    body = {
        "schema_version": 1,
        "source_experiment_id": "OT-0028",
        "source_artifact_sha256": source_sha256,
        "source_actor_index": SOURCE_ACTOR_INDEX,
        "current_casebook": {
            "identity": current.public_identity(),
            "exemplars": source_output["exemplars"],
        },
        "completed_regime_shift_encounter": {
            "archive": completed["archive"],
            "queries": completed["queries"],
            "outcomes": completed["outcomes"],
        },
        "selection_consequences": {
            "selected_events": retained,
            "query_receipts": query_receipts,
            "errors": sum(item["error"] for item in query_receipts),
        },
    }
    projection = {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}
    return current, projection


def evaluate_reversal_with_source(
    task: dict[str, Any], value: Any, current: CasebookSnapshot
) -> dict[str, Any]:
    challenger, _, _ = parse_casebook_output(task, value)
    evaluation = task["sealed_pilot_evaluation"]
    current_ids = execute_casebook(
        current, evaluation["archive"], task["selection_limit"]
    )
    current_retained = selected_events(evaluation["archive"], current_ids)
    current_predictions = deterministic_predictions(
        current_retained, evaluation["queries"]
    )
    current_errors = sum(
        prediction != outcome
        for prediction, outcome in zip(current_predictions, evaluation["outcomes"])
    )
    challenger_ids = execute_casebook(
        challenger, evaluation["archive"], task["selection_limit"]
    )
    challenger_retained = selected_events(evaluation["archive"], challenger_ids)
    challenger_predictions = deterministic_predictions(
        challenger_retained, evaluation["queries"]
    )
    challenger_errors = sum(
        prediction != outcome
        for prediction, outcome in zip(
            challenger_predictions, evaluation["outcomes"]
        )
    )
    return {
        "contradicted_casebook": current.public_identity(),
        "revised_casebook": challenger.public_identity(),
        "exemplar_count": len(challenger.exemplars),
        "selected_event_count": len(challenger_ids),
        "selected_event_ids_sha256": sha256_bytes(canonical_json(challenger_ids)),
        "inherited_errors": current_errors,
        "revised_errors": challenger_errors,
        "revision_error_advantage": current_errors - challenger_errors,
        "selection_changed": challenger_ids != current_ids,
        "prediction_changed": challenger_predictions != current_predictions,
        "deterministic_replay": True,
        "commit_changed": challenger.sha256 != current.sha256,
    }


def evaluate_reversal_output(task: dict[str, Any], value: Any) -> dict[str, Any]:
    current, _ = source_projection(REPO_ROOT, task)
    return evaluate_reversal_with_source(task, value, current)


def reversal_mechanism_valid(
    mechanisms: list[dict[str, Any]], acceptance: dict[str, Any]
) -> bool:
    return len(mechanisms) == acceptance["fresh_actor_encounters"] and all(
        item["inherited_errors"] >= acceptance["minimum_inherited_errors_each"]
        and item["revised_errors"] <= acceptance["maximum_revised_errors_each"]
        and item["revision_error_advantage"]
        >= acceptance["minimum_error_advantage_each"]
        and item["selected_event_count"] == acceptance["selection_limit"]
        and item["selection_changed"]
        and item["prediction_changed"]
        and item["deterministic_replay"]
        and item["commit_changed"]
        for item in mechanisms
    )


def rendered_reversal_prompt(
    repo: Path, task: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    _, projection = source_projection(repo, task)
    template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    body = template.replace(
        "{{CONSEQUENCE_PROJECTION}}",
        json.dumps(projection, sort_keys=True, separators=(",", ":")),
    )
    seed = (repo / SEED_PATH).read_text(encoding="utf-8")
    return f"{seed}\n\n{body}", projection
