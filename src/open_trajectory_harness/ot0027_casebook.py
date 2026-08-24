from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0004_world import selected_events
from .ot0005_world import deterministic_predictions
from .ot0021_trace import consequence_ledger, seed_consequence_entry


EXPERIMENT_ID = "OT-0027"
ACCEPTANCE_PATH = Path("spec/ot-0027-acceptance.json")
PROMPT_PATH = Path("fixtures/ot-0027/casebook-prompt.txt")
SEED_PATH = Path("fixtures/ot-0027/casebook-seed.txt")
EXEMPLAR_LIMIT = 8


@dataclass(frozen=True)
class CasebookSnapshot:
    revision: int
    parent_sha256: str
    proposal_sha256: str
    sha256: str
    exemplars: tuple[dict[str, Any], ...]

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


def parse_casebook_output(
    task: dict[str, Any], value: Any
) -> tuple[CasebookSnapshot, str, str]:
    if not isinstance(value, dict) or set(value) != {
        "exemplars",
        "expected_effect",
        "cheapest_falsifier",
    }:
        raise ValueError("OT-0027 output failed exact authority")
    expected_effect = value["expected_effect"]
    cheapest_falsifier = value["cheapest_falsifier"]
    if any(
        not isinstance(text, str) or not text.strip()
        for text in (expected_effect, cheapest_falsifier)
    ):
        raise ValueError("OT-0027 explanation is invalid")
    raw_exemplars = value["exemplars"]
    if not isinstance(raw_exemplars, list) or not 1 <= len(raw_exemplars) <= 8:
        raise ValueError("OT-0027 exemplar count is outside its bound")
    prior_archive = task["prior_completed_encounter"]["archive"]
    prior_by_id = {event["event_id"]: event for event in prior_archive}
    normalized = []
    for exemplar in raw_exemplars:
        if not isinstance(exemplar, dict) or set(exemplar) != {
            "anchor_event_id",
            "mask",
            "radius",
            "priority",
        }:
            raise ValueError("OT-0027 exemplar failed exact authority")
        anchor_id = exemplar["anchor_event_id"]
        mask = exemplar["mask"]
        radius = exemplar["radius"]
        priority = exemplar["priority"]
        if anchor_id not in prior_by_id:
            raise ValueError("OT-0027 exemplar anchor is not in the prior encounter")
        if (
            not isinstance(mask, list)
            or len(mask) != 4
            or any(type(item) is not bool for item in mask)
        ):
            raise ValueError("OT-0027 exemplar mask is invalid")
        if type(radius) is not int or not 0 <= radius <= 4:
            raise ValueError("OT-0027 exemplar radius is outside its bound")
        if type(priority) is not int or not -16 <= priority <= 16:
            raise ValueError("OT-0027 exemplar priority is outside its bound")
        normalized.append(
            {
                "anchor_event_id": anchor_id,
                "anchor_features": list(prior_by_id[anchor_id]["features"]),
                "mask": list(mask),
                "radius": radius,
                "priority": priority,
            }
        )
    anchor_ids = [item["anchor_event_id"] for item in normalized]
    if len(anchor_ids) != len(set(anchor_ids)):
        raise ValueError("OT-0027 exemplar anchors are not distinct")
    proposal = {
        "exemplars": raw_exemplars,
        "expected_effect": expected_effect,
        "cheapest_falsifier": cheapest_falsifier,
    }
    proposal_sha256 = sha256_bytes(canonical_json(proposal))
    parent_sha256 = sha256_bytes(
        canonical_json({"revision": 0, "exemplars": [], "parent_sha256": None})
    )
    identity = {
        "revision": 1,
        "parent_sha256": parent_sha256,
        "proposal_sha256": proposal_sha256,
        "exemplars": normalized,
    }
    return (
        CasebookSnapshot(
            revision=1,
            parent_sha256=parent_sha256,
            proposal_sha256=proposal_sha256,
            sha256=sha256_bytes(canonical_json(identity)),
            exemplars=tuple(normalized),
        ),
        expected_effect,
        cheapest_falsifier,
    )


def execute_casebook(
    snapshot: CasebookSnapshot, archive: list[dict[str, Any]], limit: int
) -> list[str]:
    def score(event: dict[str, Any]) -> int:
        total = 0
        for exemplar in snapshot.exemplars:
            distance = sum(
                current != anchor
                for current, anchor, active in zip(
                    event["features"], exemplar["anchor_features"], exemplar["mask"]
                )
                if active
            )
            if distance <= exemplar["radius"]:
                total += exemplar["priority"]
        return total

    def select() -> list[str]:
        ranked = sorted(
            archive,
            key=lambda event: (-score(event), event["sequence"], event["event_id"]),
        )
        return [event["event_id"] for event in ranked[:limit]]

    first = select()
    second = select()
    if first != second or len(first) != limit or len(set(first)) != limit:
        raise RuntimeError("OT-0027 casebook selection replay changed")
    selected_events(archive, first)
    return first


def evaluate_casebook_output(task: dict[str, Any], value: Any) -> dict[str, Any]:
    snapshot, _, _ = parse_casebook_output(task, value)
    evaluation = task["sealed_pilot_evaluation"]
    current_predictions = deterministic_predictions([], evaluation["queries"])
    current_errors = sum(
        prediction != outcome
        for prediction, outcome in zip(current_predictions, evaluation["outcomes"])
    )
    selected_ids = execute_casebook(
        snapshot, evaluation["archive"], task["selection_limit"]
    )
    retained = selected_events(evaluation["archive"], selected_ids)
    predictions = deterministic_predictions(retained, evaluation["queries"])
    errors = sum(
        prediction != outcome
        for prediction, outcome in zip(predictions, evaluation["outcomes"])
    )
    selection_changed = bool(selected_ids)
    prediction_changed = predictions != current_predictions
    commit_changed = snapshot.sha256 != snapshot.parent_sha256
    return {
        "casebook": snapshot.public_identity(),
        "exemplar_count": len(snapshot.exemplars),
        "selected_event_ids_sha256": sha256_bytes(canonical_json(selected_ids)),
        "selected_event_count": len(selected_ids),
        "current_errors": current_errors,
        "casebook_errors": errors,
        "casebook_error_advantage": current_errors - errors,
        "selection_changed": selection_changed,
        "prediction_changed": prediction_changed,
        "deterministic_replay": True,
        "commit_changed": commit_changed,
    }


def casebook_mechanism_valid(
    mechanisms: list[dict[str, Any]], acceptance: dict[str, Any]
) -> bool:
    return len(mechanisms) == acceptance["fresh_actor_encounters"] and all(
        item["exemplar_count"] >= 1
        and item["selected_event_count"] == acceptance["selection_limit"]
        and item["casebook_error_advantage"]
        >= acceptance["minimum_error_advantage_each"]
        and item["selection_changed"]
        and item["prediction_changed"]
        and item["deterministic_replay"]
        and item["commit_changed"]
        for item in mechanisms
    )


def rendered_casebook_prompt(
    repo: Path, task: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    acceptance = json.loads(
        (repo / ACCEPTANCE_PATH).read_text(encoding="utf-8")
    )
    ledger = consequence_ledger(
        [seed_consequence_entry(task)],
        max_entries=acceptance["ledger_entry_limit"],
        max_bytes=acceptance["ledger_byte_limit"],
    )
    template = (repo / PROMPT_PATH).read_text(encoding="utf-8")
    body = template.replace(
        "{{CONSEQUENCE_LEDGER}}",
        json.dumps(ledger, sort_keys=True, separators=(",", ":")),
    )
    seed = (repo / SEED_PATH).read_text(encoding="utf-8")
    return f"{seed}\n\n{body}", ledger
