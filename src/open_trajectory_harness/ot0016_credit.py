from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0005_world import (
    ProgramLedger,
    ProgramSnapshot,
    deterministic_predictions,
    deterministic_selection,
    selected_events,
    validate_selector_expression,
)


EXPERIMENT_ID = "OT-0016"
DECISION_ALLOWED_NODES = {
    ast.Expression,
    ast.IfExp,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Name,
    ast.Load,
    ast.Subscript,
    ast.Constant,
}


@dataclass(frozen=True)
class Challenger:
    revision: int
    expression: str
    parent_sha256: str
    proposal_sha256: str
    sha256: str
    proposal: dict[str, str]

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DecisionRuleSnapshot:
    revision: int
    expression: str
    parent_sha256: str | None
    proposal_sha256: str | None
    sha256: str

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


def validate_decision_expression(expression: Any, byte_limit: int = 512) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("decision expression must be non-empty text")
    if len(expression.encode()) > byte_limit:
        raise ValueError("decision expression exceeds its byte budget")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError("decision expression is not valid expression syntax") from error
    nodes = list(ast.walk(tree))
    if len(nodes) > 64:
        raise ValueError("decision expression exceeds its AST-node budget")
    for node in nodes:
        if type(node) not in DECISION_ALLOWED_NODES:
            raise ValueError(f"decision expression uses forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id != "comparison":
            raise ValueError("decision expression uses an unknown name")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and len(node.value) > 64:
                raise ValueError("decision expression string literal is too long")
            if type(node.value) is int and abs(node.value) > 10000:
                raise ValueError("decision expression integer literal is too large")
    return tree


class DecisionRuleLedger:
    def __init__(self, seed_expression: str = '"current"', byte_limit: int = 512):
        self.byte_limit = byte_limit
        self._snapshots: list[DecisionRuleSnapshot] = []
        self._append(seed_expression, proposal=None)

    @property
    def current(self) -> DecisionRuleSnapshot:
        return self._snapshots[-1]

    @property
    def snapshots(self) -> tuple[DecisionRuleSnapshot, ...]:
        return tuple(self._snapshots)

    def _append(
        self, expression: str, proposal: dict[str, str] | None
    ) -> DecisionRuleSnapshot:
        validate_decision_expression(expression, self.byte_limit)
        parent = self._snapshots[-1].sha256 if self._snapshots else None
        proposal_sha256 = sha256_bytes(canonical_json(proposal)) if proposal else None
        identity = {
            "revision": len(self._snapshots),
            "expression": expression,
            "parent_sha256": parent,
            "proposal_sha256": proposal_sha256,
        }
        snapshot = DecisionRuleSnapshot(
            revision=identity["revision"],
            expression=expression,
            parent_sha256=parent,
            proposal_sha256=proposal_sha256,
            sha256=sha256_bytes(canonical_json(identity)),
        )
        self._snapshots.append(snapshot)
        return snapshot

    def commit(self, proposal: dict[str, str]) -> DecisionRuleSnapshot:
        _validate_proposal(proposal)
        return self._append(proposal["expression"], proposal)


def decision_comparison(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_errors": receipt["current"]["errors"],
        "challenger_errors": receipt["challenger"]["errors"],
        "challenger_error_advantage": receipt["challenger_error_advantage"],
        "selection_changed": receipt["selection_changed"],
        "prediction_changed": receipt["prediction_changed"],
    }


def execute_decision_rule(
    rule: DecisionRuleSnapshot, receipt: dict[str, Any]
) -> dict[str, Any]:
    comparison = decision_comparison(receipt)
    return execute_decision_rule_on_comparison(
        rule,
        comparison,
        source_receipt_sha256=receipt["receipt_sha256"],
        projection="true-credit",
    )


def execute_decision_rule_on_comparison(
    rule: DecisionRuleSnapshot,
    comparison: dict[str, Any],
    *,
    source_receipt_sha256: str,
    projection: str,
) -> dict[str, Any]:
    tree = validate_decision_expression(rule.expression)
    globals_value = {"__builtins__": {}, "comparison": comparison}
    first = eval(compile(tree, "<decision-expression>", "eval"), globals_value, {})
    second = eval(compile(tree, "<decision-expression>", "eval"), globals_value, {})
    if first not in {"current", "challenger"}:
        raise ValueError("decision expression did not return a valid choice")
    if first != second:
        raise RuntimeError("decision expression replay changed")
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "decision_rule_sha256": rule.sha256,
        "counterfactual_receipt_sha256": source_receipt_sha256,
        "projection": projection,
        "comparison_sha256": sha256_bytes(canonical_json(comparison)),
        "choice": first,
        "deterministic_replay": True,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def execute_credit_neutralized_rule(
    rule: DecisionRuleSnapshot, receipt: dict[str, Any]
) -> dict[str, Any]:
    comparison = decision_comparison(receipt)
    comparison.update(
        {
            "current_errors": 0,
            "challenger_errors": 0,
            "challenger_error_advantage": 0,
        }
    )
    return execute_decision_rule_on_comparison(
        rule,
        comparison,
        source_receipt_sha256=receipt["receipt_sha256"],
        projection="credit-neutralized-v1",
    )


def _validate_proposal(proposal: Any) -> dict[str, str]:
    expected = {"expression", "expected_effect", "cheapest_falsifier"}
    if not isinstance(proposal, dict) or set(proposal) != expected:
        raise ValueError("challenger proposal failed exact authority check")
    for name in expected:
        if not isinstance(proposal[name], str) or not proposal[name].strip():
            raise ValueError(f"challenger proposal has invalid {name}")
    return proposal


def _prospective_snapshot(
    current: ProgramSnapshot,
    proposal: dict[str, str],
    *,
    byte_limit: int,
    iteration_depth_limit: int,
) -> Challenger:
    _validate_proposal(proposal)
    validate_selector_expression(
        proposal["expression"],
        byte_limit=byte_limit,
        iteration_depth_limit=iteration_depth_limit,
    )
    proposal_sha256 = sha256_bytes(canonical_json(proposal))
    identity = {
        "revision": current.revision + 1,
        "expression": proposal["expression"],
        "parent_sha256": current.sha256,
        "proposal_sha256": proposal_sha256,
    }
    return Challenger(
        revision=identity["revision"],
        expression=proposal["expression"],
        parent_sha256=current.sha256,
        proposal_sha256=proposal_sha256,
        sha256=sha256_bytes(canonical_json(identity)),
        proposal=dict(proposal),
    )


def _branch_result(
    *,
    expression: str,
    program_sha256: str,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
    timeout_seconds: float,
    iteration_depth_limit: int,
) -> dict[str, Any]:
    selected_ids = deterministic_selection(
        expression,
        archive,
        queries,
        limit,
        allow_empty=expression == "[]",
        timeout_seconds=timeout_seconds,
        iteration_depth_limit=iteration_depth_limit,
    )
    predictions = deterministic_predictions(selected_events(archive, selected_ids), queries)
    replay = deterministic_predictions(selected_events(archive, list(selected_ids)), queries)
    if replay != predictions:
        raise RuntimeError("counterfactual branch replay changed")
    error_vector = [int(prediction != outcome) for prediction, outcome in zip(predictions, outcomes)]
    return {
        "program_sha256": program_sha256,
        "selected_event_ids": selected_ids,
        "selected_event_ids_sha256": sha256_bytes(canonical_json(selected_ids)),
        "predictions": predictions,
        "predictions_sha256": sha256_bytes(canonical_json(predictions)),
        "outcomes": list(outcomes),
        "error_vector": error_vector,
        "errors": sum(error_vector),
        "deterministic_replay": True,
    }


def counterfactual_receipt(
    *,
    current: ProgramSnapshot,
    challenger: Challenger,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    outcomes: list[int],
    limit: int,
    stage: int,
    split_identity: str,
    timeout_seconds: float = 0.5,
    iteration_depth_limit: int = 8,
) -> dict[str, Any]:
    if challenger.parent_sha256 != current.sha256:
        raise ValueError("challenger does not descend from the current snapshot")
    if not isinstance(split_identity, str) or not split_identity:
        raise ValueError("counterfactual split identity is required")
    if len(queries) != len(outcomes) or not queries:
        raise ValueError("counterfactual queries and outcomes must be non-empty and paired")
    current_branch = _branch_result(
        expression=current.expression,
        program_sha256=current.sha256,
        archive=archive,
        queries=queries,
        outcomes=outcomes,
        limit=limit,
        timeout_seconds=timeout_seconds,
        iteration_depth_limit=iteration_depth_limit,
    )
    challenger_branch = _branch_result(
        expression=challenger.expression,
        program_sha256=challenger.sha256,
        archive=archive,
        queries=queries,
        outcomes=outcomes,
        limit=limit,
        timeout_seconds=timeout_seconds,
        iteration_depth_limit=iteration_depth_limit,
    )
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "stage": stage,
        "split_identity": split_identity,
        "current": current_branch,
        "challenger": challenger_branch,
        "challenger_error_advantage": current_branch["errors"]
        - challenger_branch["errors"],
        "selection_changed": current_branch["selected_event_ids"]
        != challenger_branch["selected_event_ids"],
        "prediction_changed": current_branch["predictions"]
        != challenger_branch["predictions"],
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


class CounterfactualSelectorLedger:
    """Controller authority for propose -> compare -> decide -> commit.

    Candidate actors may author proposals and prospective decision rules, but
    cannot mutate the committed program chain or manufacture the consequence
    receipt that binds a decision to a specific parent and challenger.
    """

    def __init__(
        self,
        seed_expression: str = "[]",
        byte_limit: int = 2048,
        iteration_depth_limit: int = 8,
    ):
        self.byte_limit = byte_limit
        self.iteration_depth_limit = iteration_depth_limit
        self._programs = ProgramLedger(
            seed_expression,
            byte_limit,
            iteration_depth_limit,
        )
        self._issued_receipts: dict[str, bytes] = {}
        self._used_receipts: set[str] = set()
        self._decision_receipts: list[dict[str, Any]] = []

    @property
    def current(self) -> ProgramSnapshot:
        return self._programs.current

    @property
    def snapshots(self) -> tuple[ProgramSnapshot, ...]:
        return self._programs.snapshots

    @property
    def decisions(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._decision_receipts)

    def propose(self, proposal: dict[str, str]) -> Challenger:
        return _prospective_snapshot(
            self.current,
            proposal,
            byte_limit=self.byte_limit,
            iteration_depth_limit=self.iteration_depth_limit,
        )

    def compare(
        self,
        challenger: Challenger,
        *,
        archive: list[dict[str, Any]],
        queries: list[list[int]],
        outcomes: list[int],
        limit: int,
        stage: int,
        split_identity: str,
    ) -> dict[str, Any]:
        receipt = counterfactual_receipt(
            current=self.current,
            challenger=challenger,
            archive=archive,
            queries=queries,
            outcomes=outcomes,
            limit=limit,
            stage=stage,
            split_identity=split_identity,
            timeout_seconds=0.5,
            iteration_depth_limit=self.iteration_depth_limit,
        )
        receipt_sha256 = receipt["receipt_sha256"]
        encoded = canonical_json(receipt)
        existing = self._issued_receipts.get(receipt_sha256)
        if existing is not None and existing != encoded:
            raise RuntimeError("issued receipt identity collision")
        self._issued_receipts[receipt_sha256] = encoded
        return receipt

    def decide(
        self,
        challenger: Challenger,
        receipt: dict[str, Any],
        decision: dict[str, str],
    ) -> ProgramSnapshot:
        expected = {"choice", "grounds", "expected_next_effect", "cheapest_falsifier"}
        if not isinstance(decision, dict) or set(decision) != expected:
            raise ValueError("commit decision failed exact authority check")
        for name in expected:
            if not isinstance(decision[name], str) or not decision[name].strip():
                raise ValueError(f"commit decision has invalid {name}")
        if decision["choice"] not in {"current", "challenger"}:
            raise ValueError("commit decision choice is invalid")
        return self._resolve(
            challenger,
            receipt,
            decision,
            decision_authority={"kind": "fresh-actor-choice"},
        )

    def decide_with_rule(
        self,
        challenger: Challenger,
        receipt: dict[str, Any],
        rule: DecisionRuleSnapshot,
    ) -> ProgramSnapshot:
        application = execute_decision_rule(rule, receipt)
        decision = {
            "choice": application["choice"],
            "grounds": "Controller replayed the actor-authored decision expression.",
            "expected_next_effect": "The committed choice changes later deterministic behavior.",
            "cheapest_falsifier": "The exact rule changes under replay or its choice has no later effect.",
        }
        return self._resolve(
            challenger,
            receipt,
            decision,
            decision_authority={
                "kind": "controller-executed-actor-authored-rule",
                "application": application,
            },
        )

    def _resolve(
        self,
        challenger: Challenger,
        receipt: dict[str, Any],
        decision: dict[str, str],
        *,
        decision_authority: dict[str, Any],
    ) -> ProgramSnapshot:
        if challenger.parent_sha256 != self.current.sha256:
            raise ValueError("challenger parent is no longer current")
        body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        receipt_sha256 = receipt.get("receipt_sha256")
        if receipt_sha256 != sha256_bytes(canonical_json(body)):
            raise ValueError("counterfactual receipt identity is invalid")
        if self._issued_receipts.get(receipt_sha256) != canonical_json(receipt):
            raise ValueError("counterfactual receipt was not issued by this controller")
        if receipt_sha256 in self._used_receipts:
            raise ValueError("counterfactual receipt has already been resolved")
        if receipt.get("current", {}).get("program_sha256") != self.current.sha256:
            raise ValueError("counterfactual receipt does not name the current snapshot")
        if receipt.get("challenger", {}).get("program_sha256") != challenger.sha256:
            raise ValueError("counterfactual receipt does not name the challenger")

        before = self.current
        if decision["choice"] == "challenger":
            after = self._programs.commit(challenger.proposal)
            if after.sha256 != challenger.sha256:
                raise RuntimeError("committed challenger identity changed")
        else:
            after = before
        decision_body = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "parent_sha256": before.sha256,
            "challenger_sha256": challenger.sha256,
            "counterfactual_receipt_sha256": receipt_sha256,
            "decision": dict(decision),
            "decision_authority": decision_authority,
            "committed_sha256": after.sha256,
            "changed": after.sha256 != before.sha256,
        }
        self._decision_receipts.append(
            {**decision_body, "receipt_sha256": sha256_bytes(canonical_json(decision_body))}
        )
        self._used_receipts.add(receipt_sha256)
        return after


__all__ = [
    "Challenger",
    "CounterfactualSelectorLedger",
    "DecisionRuleLedger",
    "DecisionRuleSnapshot",
    "counterfactual_receipt",
    "decision_comparison",
    "execute_credit_neutralized_rule",
    "execute_decision_rule",
    "execute_decision_rule_on_comparison",
    "validate_decision_expression",
]
