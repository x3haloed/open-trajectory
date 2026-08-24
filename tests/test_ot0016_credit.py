from __future__ import annotations

import unittest

from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes
from open_trajectory_harness.ot0016_credit import (
    CounterfactualSelectorLedger,
    DecisionRuleLedger,
    execute_credit_neutralized_rule,
    execute_decision_rule,
    validate_decision_expression,
)


FIRST_EXPRESSION = '[e["event_id"] for e in events[:limit]]'
LOWER_ERROR_RULE = (
    '"challenger" if comparison["challenger_errors"] '
    '< comparison["current_errors"] else "current"'
)


def proposal(expression: str) -> dict[str, str]:
    return {
        "expression": expression,
        "expected_effect": "Change the bounded projection on the released comparison split.",
        "cheapest_falsifier": "The deterministic selection or predictions do not change.",
    }


def decision(choice: str) -> dict[str, str]:
    return {
        "choice": choice,
        "grounds": "Use the protected paired consequence receipt.",
        "expected_next_effect": "The committed choice changes later deterministic behavior.",
        "cheapest_falsifier": "The later changed and unchanged branches are identical.",
    }


class OT0016CreditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = [
            {
                "event_id": f"event-{index}",
                "sequence": index,
                "features": [index & 1, (index >> 1) & 1, (index >> 2) & 1, 0],
                "label": 1,
            }
            for index in range(6)
        ]
        self.queries = [event["features"] for event in self.archive]
        self.outcomes = [1] * len(self.queries)
        self.ledger = CounterfactualSelectorLedger()

    def compare(self, challenger):
        return self.ledger.compare(
            challenger,
            archive=self.archive,
            queries=self.queries,
            outcomes=self.outcomes,
            limit=len(self.archive),
            stage=0,
            split_identity="released-calibration-0",
        )

    def test_identical_program_placebo_has_identical_behavior(self) -> None:
        challenger = self.ledger.propose(proposal("[]"))
        receipt = self.compare(challenger)
        self.assertEqual(receipt["challenger_error_advantage"], 0)
        self.assertFalse(receipt["selection_changed"])
        self.assertFalse(receipt["prediction_changed"])
        self.assertEqual(
            receipt["current"]["selected_event_ids_sha256"],
            receipt["challenger"]["selected_event_ids_sha256"],
        )

    def test_paired_receipt_exposes_controller_owned_counterfactual_credit(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        first = self.compare(challenger)
        second = self.compare(challenger)
        self.assertEqual(first, second)
        self.assertEqual(first["current"]["errors"], 6)
        self.assertEqual(first["challenger"]["errors"], 0)
        self.assertEqual(first["challenger_error_advantage"], 6)
        self.assertTrue(first["selection_changed"])
        self.assertTrue(first["prediction_changed"])

    def test_controller_commits_only_the_receipted_challenger(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        before = self.ledger.current
        after = self.ledger.decide(challenger, receipt, decision("challenger"))
        self.assertNotEqual(after.sha256, before.sha256)
        self.assertEqual(after.sha256, challenger.sha256)
        self.assertTrue(self.ledger.decisions[-1]["changed"])

    def test_keep_current_preserves_snapshot_but_retains_decision_receipt(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        before = self.ledger.current
        after = self.ledger.decide(challenger, receipt, decision("current"))
        self.assertEqual(after, before)
        self.assertFalse(self.ledger.decisions[-1]["changed"])

    def test_tampered_or_replayed_receipt_cannot_authorize_commit(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        tampered = {**receipt, "challenger_error_advantage": 99}
        with self.assertRaises(ValueError):
            self.ledger.decide(challenger, tampered, decision("challenger"))
        self.ledger.decide(challenger, receipt, decision("challenger"))
        with self.assertRaises(ValueError):
            self.ledger.decide(challenger, receipt, decision("challenger"))

    def test_rehashed_forgery_cannot_substitute_for_controller_issuance(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        forged_body = {
            **{key: value for key, value in receipt.items() if key != "receipt_sha256"},
            "challenger_error_advantage": 99,
        }
        forged = {
            **forged_body,
            "receipt_sha256": sha256_bytes(canonical_json(forged_body)),
        }
        with self.assertRaises(ValueError):
            self.ledger.decide(challenger, forged, decision("challenger"))

    def test_stale_challenger_cannot_be_committed_after_parent_changes(self) -> None:
        first = self.ledger.propose(proposal(FIRST_EXPRESSION))
        first_receipt = self.compare(first)
        stale = self.ledger.propose(proposal("[]"))
        self.ledger.decide(first, first_receipt, decision("challenger"))
        with self.assertRaises(ValueError):
            self.compare(stale)

    def test_actor_authored_rule_makes_credit_application_deterministic(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        rules = DecisionRuleLedger()
        rule = rules.commit(proposal(LOWER_ERROR_RULE))
        first = execute_decision_rule(rule, receipt)
        second = execute_decision_rule(rule, receipt)
        self.assertEqual(first, second)
        self.assertEqual(first["choice"], "challenger")
        after = self.ledger.decide_with_rule(challenger, receipt, rule)
        self.assertEqual(after.sha256, challenger.sha256)
        self.assertEqual(
            self.ledger.decisions[-1]["decision_authority"]["kind"],
            "controller-executed-actor-authored-rule",
        )

    def test_same_rule_reverses_only_when_controller_outcomes_reverse(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        favorable = self.compare(challenger)
        adverse = self.ledger.compare(
            challenger,
            archive=self.archive,
            queries=self.queries,
            outcomes=[0] * len(self.queries),
            limit=len(self.archive),
            stage=0,
            split_identity="controller-credit-ablation-0",
        )
        rule = DecisionRuleLedger().commit(proposal(LOWER_ERROR_RULE))
        self.assertEqual(execute_decision_rule(rule, favorable)["choice"], "challenger")
        self.assertEqual(execute_decision_rule(rule, adverse)["choice"], "current")
        self.assertEqual(
            favorable["current"]["selected_event_ids"],
            adverse["current"]["selected_event_ids"],
        )
        self.assertEqual(
            favorable["challenger"]["selected_event_ids"],
            adverse["challenger"]["selected_event_ids"],
        )

    def test_credit_neutralization_changes_only_frozen_credit_scalars(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        rule = DecisionRuleLedger().commit(proposal(LOWER_ERROR_RULE))
        true = execute_decision_rule(rule, receipt)
        neutral = execute_credit_neutralized_rule(rule, receipt)
        self.assertEqual(true["decision_rule_sha256"], neutral["decision_rule_sha256"])
        self.assertEqual(
            true["counterfactual_receipt_sha256"],
            neutral["counterfactual_receipt_sha256"],
        )
        self.assertEqual(true["choice"], "challenger")
        self.assertEqual(neutral["choice"], "current")

    def test_identical_decision_rule_placebo_replays_identically(self) -> None:
        challenger = self.ledger.propose(proposal(FIRST_EXPRESSION))
        receipt = self.compare(challenger)
        rules = DecisionRuleLedger(LOWER_ERROR_RULE)
        seed = rules.current
        distinct_snapshot = rules.commit(proposal(LOWER_ERROR_RULE))
        self.assertNotEqual(seed.sha256, distinct_snapshot.sha256)
        self.assertEqual(
            execute_decision_rule(seed, receipt)["choice"],
            execute_decision_rule(distinct_snapshot, receipt)["choice"],
        )

    def test_decision_rule_rejects_code_execution_and_unknown_names(self) -> None:
        for expression in (
            '__import__("os")',
            'open("private")',
            'other["current_errors"]',
            '[value for value in comparison]',
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                validate_decision_expression(expression)


if __name__ == "__main__":
    unittest.main()
