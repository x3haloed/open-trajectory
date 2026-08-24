from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0005_world import ProgramLedger
from .ot0016_credit import CounterfactualSelectorLedger
from .ot0021_trace import consequence_ledger, seed_consequence_entry
from .ot0023_portfolio import ALTERNATIVE_COUNT, _portfolio_comparison


EXPERIMENT_ID = "OT-0025"
ACCEPTANCE_PATH = Path("spec/ot-0025-acceptance.json")
PROMPT_PATH = Path("fixtures/ot-0025/structured-prompt.txt")
SEED_PATH = Path("fixtures/ot-0025/structured-seed.txt")


@dataclass(frozen=True)
class StructuredDecisionSnapshot:
    revision: int
    parent_sha256: str | None
    proposal_sha256: str
    sha256: str
    clauses: tuple[dict[str, Any], ...]

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


def parse_structured_output(
    value: Any,
) -> tuple[list[dict[str, str]], StructuredDecisionSnapshot]:
    expected = {
        "alternatives",
        "decision_clauses",
        "decision_expected_effect",
        "decision_cheapest_falsifier",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("OT-0025 output failed exact structured authority")
    alternatives = value["alternatives"]
    if not isinstance(alternatives, list) or len(alternatives) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0025 requires exactly three selector alternatives")
    proposals: list[dict[str, str]] = []
    for alternative in alternatives:
        if not isinstance(alternative, dict) or set(alternative) != {
            "selector_expression",
            "expected_effect",
            "cheapest_falsifier",
        }:
            raise ValueError("OT-0025 alternative failed exact authority")
        if any(
            not isinstance(alternative[name], str) or not alternative[name].strip()
            for name in alternative
        ):
            raise ValueError("OT-0025 alternative contains an invalid field")
        proposals.append(
            {
                "expression": alternative["selector_expression"],
                "expected_effect": alternative["expected_effect"],
                "cheapest_falsifier": alternative["cheapest_falsifier"],
            }
        )
    if len({proposal["expression"] for proposal in proposals}) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0025 selector alternatives are not expression-distinct")

    clauses = value["decision_clauses"]
    if not isinstance(clauses, list) or len(clauses) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0025 requires exactly three decision clauses")
    expected_clause_keys = {
        "choice",
        "minimum_error_advantage",
        "require_selection_changed",
        "require_prediction_changed",
    }
    allowed_choices = {f"alternative-{index}" for index in range(ALTERNATIVE_COUNT)}
    normalized = []
    for clause in clauses:
        if not isinstance(clause, dict) or set(clause) != expected_clause_keys:
            raise ValueError("OT-0025 decision clause failed exact authority")
        if clause["choice"] not in allowed_choices:
            raise ValueError("OT-0025 decision clause has an invalid choice")
        threshold = clause["minimum_error_advantage"]
        if type(threshold) is not int or not -16 <= threshold <= 16:
            raise ValueError("OT-0025 decision threshold is outside its bound")
        if type(clause["require_selection_changed"]) is not bool or type(
            clause["require_prediction_changed"]
        ) is not bool:
            raise ValueError("OT-0025 decision clause has an invalid Boolean")
        normalized.append(dict(clause))
    if {clause["choice"] for clause in normalized} != allowed_choices:
        raise ValueError("OT-0025 decision clauses are not a choice permutation")
    for name in ("decision_expected_effect", "decision_cheapest_falsifier"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise ValueError(f"OT-0025 {name} is invalid")
    proposal = {
        "clauses": normalized,
        "expected_effect": value["decision_expected_effect"],
        "cheapest_falsifier": value["decision_cheapest_falsifier"],
    }
    proposal_sha256 = sha256_bytes(canonical_json(proposal))
    identity = {
        "revision": 1,
        "parent_sha256": sha256_bytes(
            canonical_json({"revision": 0, "clauses": [], "parent_sha256": None})
        ),
        "proposal_sha256": proposal_sha256,
        "clauses": normalized,
    }
    snapshot = StructuredDecisionSnapshot(
        revision=1,
        parent_sha256=identity["parent_sha256"],
        proposal_sha256=proposal_sha256,
        sha256=sha256_bytes(canonical_json(identity)),
        clauses=tuple(normalized),
    )
    return proposals, snapshot


def execute_structured_rule(
    rule: StructuredDecisionSnapshot,
    comparison: dict[str, Any],
    *,
    source_receipt_sha256: str,
    projection: str,
) -> dict[str, Any]:
    def choose() -> str:
        for clause in rule.clauses:
            index = int(clause["choice"].rsplit("-", 1)[1])
            if comparison[f"alternative_{index}_error_advantage"] < clause[
                "minimum_error_advantage"
            ]:
                continue
            if clause["require_selection_changed"] and not comparison[
                f"alternative_{index}_selection_changed"
            ]:
                continue
            if clause["require_prediction_changed"] and not comparison[
                f"alternative_{index}_prediction_changed"
            ]:
                continue
            return clause["choice"]
        return "current"

    first = choose()
    second = choose()
    if first != second:
        raise RuntimeError("OT-0025 structured decision replay changed")
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "decision_rule_sha256": rule.sha256,
        "portfolio_receipt_sha256": source_receipt_sha256,
        "projection": projection,
        "comparison_sha256": sha256_bytes(canonical_json(comparison)),
        "choice": first,
        "deterministic_replay": True,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def evaluate_structured_output(task: dict[str, Any], value: Any) -> dict[str, Any]:
    proposals, rule = parse_structured_output(value)
    selector_ledger = CounterfactualSelectorLedger(iteration_depth_limit=8)
    challengers = [selector_ledger.propose(proposal) for proposal in proposals]
    evaluation = task["sealed_pilot_evaluation"]
    receipts = [
        selector_ledger.compare(
            challenger,
            archive=evaluation["archive"],
            queries=evaluation["queries"],
            outcomes=evaluation["outcomes"],
            limit=task["selection_limit"],
            stage=1,
            split_identity=f"public-structured-alternative-{index}",
        )
        for index, challenger in enumerate(challengers)
    ]
    receipt_identity = sha256_bytes(
        canonical_json([receipt["receipt_sha256"] for receipt in receipts])
    )
    comparison = _portfolio_comparison(receipts)
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
    current = selector_ledger.current
    choice = true_application["choice"]
    committed = current
    if choice != "current":
        index = int(choice.rsplit("-", 1)[1])
        programs = ProgramLedger("[]", iteration_depth_limit=8)
        committed = programs.commit(proposals[index])
        if committed.sha256 != challengers[index].sha256:
            raise RuntimeError("OT-0025 committed portfolio identity changed")
    alternatives = [
        {
            "choice": f"alternative-{index}",
            "program": challenger.public_identity(),
            "errors": receipt["challenger"]["errors"],
            "advantage": receipt["challenger_error_advantage"],
            "selection_changed": receipt["selection_changed"],
            "prediction_changed": receipt["prediction_changed"],
            "selected_event_ids_sha256": receipt["challenger"][
                "selected_event_ids_sha256"
            ],
        }
        for index, (challenger, receipt) in enumerate(zip(challengers, receipts))
    ]
    chosen = next(
        (alternative for alternative in alternatives if alternative["choice"] == choice),
        None,
    )
    return {
        "portfolio_receipt_sha256": receipt_identity,
        "decision_rule": rule.public_identity(),
        "alternatives": alternatives,
        "program_identity_count": len(
            {alternative["program"]["sha256"] for alternative in alternatives}
        ),
        "selection_identity_count": len(
            {
                alternative["selected_event_ids_sha256"]
                for alternative in alternatives
            }
        ),
        "true_choice": choice,
        "neutralized_choice": neutralized_application["choice"],
        "chosen_advantage": chosen["advantage"] if chosen else 0,
        "chosen_selection_changed": chosen["selection_changed"] if chosen else False,
        "decision_replay": true_application["deterministic_replay"]
        and neutralized_application["deterministic_replay"],
        "commit_changed": committed.sha256 != current.sha256,
    }


def structured_mechanism_valid(
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


def rendered_structured_prompt(
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


__all__ = [
    "evaluate_structured_output",
    "execute_structured_rule",
    "parse_structured_output",
    "rendered_structured_prompt",
    "structured_mechanism_valid",
]
