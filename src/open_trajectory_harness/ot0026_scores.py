from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0004_world import selected_events
from .ot0005_world import deterministic_predictions
from .ot0021_trace import consequence_ledger, seed_consequence_entry
from .ot0025_structured import StructuredDecisionSnapshot, execute_structured_rule


EXPERIMENT_ID = "OT-0026"
ACCEPTANCE_PATH = Path("spec/ot-0026-acceptance.json")
PROMPT_PATH = Path("fixtures/ot-0026/score-prompt.txt")
SEED_PATH = Path("fixtures/ot-0026/score-seed.txt")
ALTERNATIVE_COUNT = 3
TOKEN_LIMIT = 24
PUSH_OPS = {"sequence", "label", "feature", "constant"}
UNARY_OPS = {"abs", "negate"}
BINARY_OPS = {"add", "subtract", "multiply", "mod"}
ALL_OPS = PUSH_OPS | UNARY_OPS | BINARY_OPS


@dataclass(frozen=True)
class ScoreProgramSnapshot:
    revision: int
    parent_sha256: str
    proposal_sha256: str
    sha256: str
    tokens: tuple[dict[str, Any], ...]
    descending: bool

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


def validate_score_program(program: Any) -> tuple[tuple[dict[str, Any], ...], bool]:
    if not isinstance(program, dict) or set(program) != {"tokens", "descending"}:
        raise ValueError("OT-0026 score program failed exact authority")
    if type(program["descending"]) is not bool:
        raise ValueError("OT-0026 score direction is not Boolean")
    tokens = program["tokens"]
    if not isinstance(tokens, list) or not 1 <= len(tokens) <= TOKEN_LIMIT:
        raise ValueError("OT-0026 score token count is outside its bound")
    depth = 0
    normalized = []
    for token in tokens:
        if not isinstance(token, dict) or set(token) != {"op", "value", "index"}:
            raise ValueError("OT-0026 score token failed exact authority")
        op = token["op"]
        value = token["value"]
        index = token["index"]
        if op not in ALL_OPS or type(value) is not int or type(index) is not int:
            raise ValueError("OT-0026 score token has an invalid field")
        if op == "constant":
            if not -32 <= value <= 32 or index != 0:
                raise ValueError("OT-0026 constant token is outside its bound")
        elif op == "feature":
            if value != 0 or not 0 <= index <= 3:
                raise ValueError("OT-0026 feature token is outside its bound")
        elif value != 0 or index != 0:
            raise ValueError("OT-0026 unused token operands must be zero")
        if op in PUSH_OPS:
            depth += 1
        elif op in UNARY_OPS:
            if depth < 1:
                raise ValueError("OT-0026 unary token underflows its stack")
        else:
            if depth < 2:
                raise ValueError("OT-0026 binary token underflows its stack")
            depth -= 1
        normalized.append(dict(token))
    if depth != 1:
        raise ValueError("OT-0026 score program does not leave one value")
    return tuple(normalized), program["descending"]


def _score(tokens: tuple[dict[str, Any], ...], event: dict[str, Any]) -> int:
    stack: list[int] = []
    for token in tokens:
        op = token["op"]
        if op == "sequence":
            stack.append(event["sequence"])
        elif op == "label":
            stack.append(event["label"])
        elif op == "feature":
            stack.append(event["features"][token["index"]])
        elif op == "constant":
            stack.append(token["value"])
        elif op == "abs":
            stack[-1] = abs(stack[-1])
        elif op == "negate":
            stack[-1] = -stack[-1]
        else:
            right = stack.pop()
            left = stack.pop()
            if op == "add":
                stack.append(left + right)
            elif op == "subtract":
                stack.append(left - right)
            elif op == "multiply":
                stack.append(left * right)
            elif op == "mod":
                stack.append(left % right if right else 0)
    return stack[0]


def execute_score_program(
    program: ScoreProgramSnapshot, archive: list[dict[str, Any]], limit: int
) -> list[str]:
    def select() -> list[str]:
        ranked = sorted(
            archive,
            key=lambda event: (
                -_score(program.tokens, event)
                if program.descending
                else _score(program.tokens, event),
                event["sequence"],
                event["event_id"],
            ),
        )
        return [event["event_id"] for event in ranked[:limit]]

    first = select()
    second = select()
    if first != second or len(first) != limit or len(set(first)) != limit:
        raise RuntimeError("OT-0026 score selection replay changed")
    selected_events(archive, first)
    return first


def _program_snapshot(proposal: dict[str, Any]) -> ScoreProgramSnapshot:
    tokens, descending = validate_score_program(proposal["program"])
    proposal_sha256 = sha256_bytes(canonical_json(proposal))
    parent_sha256 = sha256_bytes(
        canonical_json({"revision": 0, "program": None, "parent_sha256": None})
    )
    program_identity = {
        "revision": 1,
        "parent_sha256": parent_sha256,
        "tokens": tokens,
        "descending": descending,
    }
    return ScoreProgramSnapshot(
        revision=1,
        parent_sha256=parent_sha256,
        proposal_sha256=proposal_sha256,
        sha256=sha256_bytes(canonical_json(program_identity)),
        tokens=tokens,
        descending=descending,
    )


def _decision_snapshot(value: dict[str, Any]) -> StructuredDecisionSnapshot:
    clauses = value["decision_clauses"]
    allowed = {f"alternative-{index}" for index in range(ALTERNATIVE_COUNT)}
    keys = {
        "choice",
        "minimum_error_advantage",
        "require_selection_changed",
        "require_prediction_changed",
    }
    if not isinstance(clauses, list) or len(clauses) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0026 requires exactly three decision clauses")
    normalized = []
    for clause in clauses:
        if not isinstance(clause, dict) or set(clause) != keys:
            raise ValueError("OT-0026 decision clause failed exact authority")
        threshold = clause["minimum_error_advantage"]
        if (
            clause["choice"] not in allowed
            or type(threshold) is not int
            or not -16 <= threshold <= 16
            or type(clause["require_selection_changed"]) is not bool
            or type(clause["require_prediction_changed"]) is not bool
        ):
            raise ValueError("OT-0026 decision clause has an invalid field")
        normalized.append(dict(clause))
    if {clause["choice"] for clause in normalized} != allowed:
        raise ValueError("OT-0026 clauses are not a choice permutation")
    proposal = {
        "clauses": normalized,
        "expected_effect": value["decision_expected_effect"],
        "cheapest_falsifier": value["decision_cheapest_falsifier"],
    }
    if any(
        not isinstance(proposal[name], str) or not proposal[name].strip()
        for name in ("expected_effect", "cheapest_falsifier")
    ):
        raise ValueError("OT-0026 decision explanation is invalid")
    proposal_sha256 = sha256_bytes(canonical_json(proposal))
    parent_sha256 = sha256_bytes(
        canonical_json({"revision": 0, "clauses": [], "parent_sha256": None})
    )
    identity = {
        "revision": 1,
        "parent_sha256": parent_sha256,
        "proposal_sha256": proposal_sha256,
        "clauses": normalized,
    }
    return StructuredDecisionSnapshot(
        revision=1,
        parent_sha256=parent_sha256,
        proposal_sha256=proposal_sha256,
        sha256=sha256_bytes(canonical_json(identity)),
        clauses=tuple(normalized),
    )


def evaluate_score_output(task: dict[str, Any], value: Any) -> dict[str, Any]:
    expected = {
        "alternatives",
        "decision_clauses",
        "decision_expected_effect",
        "decision_cheapest_falsifier",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("OT-0026 output failed exact authority")
    raw_alternatives = value["alternatives"]
    if not isinstance(raw_alternatives, list) or len(raw_alternatives) != 3:
        raise ValueError("OT-0026 requires exactly three alternatives")
    proposals = []
    programs = []
    for alternative in raw_alternatives:
        if not isinstance(alternative, dict) or set(alternative) != {
            "selector_program",
            "expected_effect",
            "cheapest_falsifier",
        }:
            raise ValueError("OT-0026 alternative failed exact authority")
        proposal = {
            "program": alternative["selector_program"],
            "expected_effect": alternative["expected_effect"],
            "cheapest_falsifier": alternative["cheapest_falsifier"],
        }
        if any(
            not isinstance(proposal[name], str) or not proposal[name].strip()
            for name in ("expected_effect", "cheapest_falsifier")
        ):
            raise ValueError("OT-0026 alternative explanation is invalid")
        proposals.append(proposal)
        programs.append(_program_snapshot(proposal))
    if len({program.sha256 for program in programs}) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0026 score programs are not distinct")
    rule = _decision_snapshot(value)
    evaluation = task["sealed_pilot_evaluation"]
    current_predictions = deterministic_predictions([], evaluation["queries"])
    current_errors = sum(
        prediction != outcome
        for prediction, outcome in zip(current_predictions, evaluation["outcomes"])
    )
    alternatives = []
    comparison: dict[str, Any] = {"current_errors": current_errors}
    receipt_bodies = []
    for index, program in enumerate(programs):
        selected_ids = execute_score_program(
            program, evaluation["archive"], task["selection_limit"]
        )
        selected = selected_events(evaluation["archive"], selected_ids)
        predictions = deterministic_predictions(selected, evaluation["queries"])
        errors = sum(
            prediction != outcome
            for prediction, outcome in zip(predictions, evaluation["outcomes"])
        )
        advantage = current_errors - errors
        selection_changed = bool(selected_ids)
        prediction_changed = predictions != current_predictions
        selected_sha = sha256_bytes(canonical_json(selected_ids))
        comparison.update(
            {
                f"alternative_{index}_errors": errors,
                f"alternative_{index}_error_advantage": advantage,
                f"alternative_{index}_selection_changed": selection_changed,
                f"alternative_{index}_prediction_changed": prediction_changed,
            }
        )
        body = {
            "choice": f"alternative-{index}",
            "program_sha256": program.sha256,
            "selected_event_ids_sha256": selected_sha,
            "predictions_sha256": sha256_bytes(canonical_json(predictions)),
            "errors": errors,
            "advantage": advantage,
        }
        receipt_bodies.append(body)
        alternatives.append(
            {
                **body,
                "program": program.public_identity(),
                "selection_changed": selection_changed,
                "prediction_changed": prediction_changed,
            }
        )
    receipt_identity = sha256_bytes(canonical_json(receipt_bodies))
    true_application = execute_structured_rule(
        rule,
        comparison,
        source_receipt_sha256=receipt_identity,
        projection="true-credit",
    )
    neutralized = dict(comparison)
    neutralized["current_errors"] = 0
    for index in range(ALTERNATIVE_COUNT):
        neutralized[f"alternative_{index}_errors"] = 0
        neutralized[f"alternative_{index}_error_advantage"] = 0
    neutralized_application = execute_structured_rule(
        rule,
        neutralized,
        source_receipt_sha256=receipt_identity,
        projection="credit-neutralized-v1",
    )
    choice = true_application["choice"]
    chosen = next(
        (alternative for alternative in alternatives if alternative["choice"] == choice),
        None,
    )
    return {
        "portfolio_receipt_sha256": receipt_identity,
        "decision_rule": rule.public_identity(),
        "alternatives": alternatives,
        "program_identity_count": len({program.sha256 for program in programs}),
        "selection_identity_count": len(
            {item["selected_event_ids_sha256"] for item in alternatives}
        ),
        "true_choice": choice,
        "neutralized_choice": neutralized_application["choice"],
        "chosen_advantage": chosen["advantage"] if chosen else 0,
        "chosen_selection_changed": chosen["selection_changed"] if chosen else False,
        "decision_replay": true_application["deterministic_replay"]
        and neutralized_application["deterministic_replay"],
        "commit_changed": choice != "current",
    }


def score_mechanism_valid(
    mechanisms: list[dict[str, Any]], acceptance: dict[str, Any]
) -> bool:
    return len(mechanisms) == acceptance["fresh_actor_encounters"] and all(
        item["program_identity_count"] == ALTERNATIVE_COUNT
        and item["selection_identity_count"]
        >= acceptance["minimum_distinct_selection_sets_each"]
        and item["true_choice"].startswith("alternative-")
        and item["neutralized_choice"] == "current"
        and item["chosen_advantage"] >= acceptance["minimum_error_advantage_each"]
        and item["chosen_selection_changed"]
        and item["decision_replay"]
        and item["commit_changed"]
        for item in mechanisms
    )


def rendered_score_prompt(
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
