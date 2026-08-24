from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0005_world import ProgramLedger
from .ot0016_credit import (
    CounterfactualSelectorLedger,
    DecisionRuleLedger,
    DecisionRuleSnapshot,
    validate_decision_expression,
)
from .ot0021_trace import consequence_ledger, seed_consequence_entry


EXPERIMENT_ID = "OT-0023"
PROMPT_PATH = Path("fixtures/ot-0023/portfolio-prompt.txt")
SEED_PATH = Path("fixtures/ot-0023/portfolio-seed.txt")
ALTERNATIVE_COUNT = 3
DECISION_NODE_LIMIT = 64
ACCEPTANCE_PATH = Path("spec/ot-0023-acceptance.json")


def parse_portfolio_output(value: Any) -> tuple[list[dict[str, str]], dict[str, str]]:
    expected = {
        "alternatives",
        "decision_expression",
        "decision_expected_effect",
        "decision_cheapest_falsifier",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("OT-0023 output failed exact portfolio authority")
    alternatives = value["alternatives"]
    if not isinstance(alternatives, list) or len(alternatives) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0023 requires exactly three actor-authored alternatives")
    proposals = []
    for alternative in alternatives:
        if not isinstance(alternative, dict) or set(alternative) != {
            "selector_expression",
            "expected_effect",
            "cheapest_falsifier",
        }:
            raise ValueError("OT-0023 alternative failed exact authority")
        if any(
            not isinstance(alternative[name], str) or not alternative[name].strip()
            for name in alternative
        ):
            raise ValueError("OT-0023 alternative contains an invalid field")
        proposals.append(
            {
                "expression": alternative["selector_expression"],
                "expected_effect": alternative["expected_effect"],
                "cheapest_falsifier": alternative["cheapest_falsifier"],
            }
        )
    if len({proposal["expression"] for proposal in proposals}) != ALTERNATIVE_COUNT:
        raise ValueError("OT-0023 alternatives are not expression-distinct")
    decision = {
        "expression": value["decision_expression"],
        "expected_effect": value["decision_expected_effect"],
        "cheapest_falsifier": value["decision_cheapest_falsifier"],
    }
    if any(not isinstance(child, str) or not child.strip() for child in decision.values()):
        raise ValueError("OT-0023 decision rule contains an invalid field")
    return proposals, decision


def _portfolio_comparison(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    current_errors = {receipt["current"]["errors"] for receipt in receipts}
    if len(current_errors) != 1:
        raise RuntimeError("OT-0023 alternatives do not share one current branch")
    comparison: dict[str, Any] = {"current_errors": current_errors.pop()}
    for index, receipt in enumerate(receipts):
        comparison.update(
            {
                f"alternative_{index}_errors": receipt["challenger"]["errors"],
                f"alternative_{index}_error_advantage": receipt[
                    "challenger_error_advantage"
                ],
                f"alternative_{index}_selection_changed": receipt[
                    "selection_changed"
                ],
                f"alternative_{index}_prediction_changed": receipt[
                    "prediction_changed"
                ],
            }
        )
    return comparison


def _execute_portfolio_rule(
    rule: DecisionRuleSnapshot,
    comparison: dict[str, Any],
    *,
    source_receipt_sha256: str,
    projection: str,
) -> dict[str, Any]:
    tree = validate_decision_expression(rule.expression, node_limit=DECISION_NODE_LIMIT)
    globals_value = {"__builtins__": {}, "comparison": comparison}
    first = eval(compile(tree, "<portfolio-decision>", "eval"), globals_value, {})
    second = eval(compile(tree, "<portfolio-decision>", "eval"), globals_value, {})
    choices = {"current", *(f"alternative-{index}" for index in range(ALTERNATIVE_COUNT))}
    if first not in choices:
        raise ValueError("OT-0023 decision rule returned an invalid portfolio choice")
    if first != second:
        raise RuntimeError("OT-0023 decision rule replay changed")
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


def evaluate_portfolio_output(task: dict[str, Any], value: Any) -> dict[str, Any]:
    proposals, decision_proposal = parse_portfolio_output(value)
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
            split_identity=f"public-portfolio-alternative-{index}",
        )
        for index, challenger in enumerate(challengers)
    ]
    receipt_identity = sha256_bytes(
        canonical_json([receipt["receipt_sha256"] for receipt in receipts])
    )
    comparison = _portfolio_comparison(receipts)
    decision_ledger = DecisionRuleLedger(node_limit=DECISION_NODE_LIMIT)
    rule = decision_ledger.commit(decision_proposal)
    true_application = _execute_portfolio_rule(
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
    neutralized_application = _execute_portfolio_rule(
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
            raise RuntimeError("OT-0023 committed portfolio identity changed")
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


def portfolio_mechanism_valid(
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


def rendered_portfolio_prompt(
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
    "evaluate_portfolio_output",
    "parse_portfolio_output",
    "portfolio_mechanism_valid",
    "rendered_portfolio_prompt",
]
