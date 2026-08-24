from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0025_pilot import configure_protocol, fixed_input_paths
from open_trajectory_harness.ot0025_structured import (
    evaluate_structured_output,
    parse_structured_output,
    rendered_structured_prompt,
    structured_mechanism_valid,
)


REPO = Path(__file__).resolve().parents[1]
VALID_OUTPUT = {
    "alternatives": [
        {
            "selector_expression": '[e["event_id"] for e in events[:limit]]',
            "expected_effect": "retain the earliest half relation",
            "cheapest_falsifier": "later examples reverse it",
        },
        {
            "selector_expression": '[e["event_id"] for e in events[-limit:]]',
            "expected_effect": "retain the latest half relation",
            "cheapest_falsifier": "earlier examples reverse it",
        },
        {
            "selector_expression": (
                '[e["event_id"] for e in '
                '(events[:limit//2] + events[-(limit-limit//2):])]'
            ),
            "expected_effect": "retain cross-half XOR contrast",
            "cheapest_falsifier": "paired errors do not fall",
        },
    ],
    "decision_clauses": [
        {
            "choice": "alternative-2",
            "minimum_error_advantage": 1,
            "require_selection_changed": True,
            "require_prediction_changed": True,
        },
        {
            "choice": "alternative-0",
            "minimum_error_advantage": 1,
            "require_selection_changed": True,
            "require_prediction_changed": True,
        },
        {
            "choice": "alternative-1",
            "minimum_error_advantage": 1,
            "require_selection_changed": True,
            "require_prediction_changed": True,
        },
    ],
    "decision_expected_effect": "commit the first useful contrast",
    "decision_cheapest_falsifier": "no clause has positive paired advantage",
}


class OT0025StructuredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0025/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0025-acceptance.json")

    def test_known_structured_portfolio_realizes_causal_choice(self) -> None:
        result = evaluate_structured_output(self.task, VALID_OUTPUT)
        self.assertEqual(result["program_identity_count"], 3)
        self.assertGreaterEqual(result["selection_identity_count"], 2)
        self.assertEqual(result["true_choice"], "alternative-2")
        self.assertEqual(result["neutralized_choice"], "current")
        self.assertEqual(result["chosen_advantage"], 8)
        self.assertTrue(
            structured_mechanism_valid([result, result], self.acceptance)
        )

    def test_clause_choice_must_be_an_exact_permutation(self) -> None:
        duplicate = deepcopy(VALID_OUTPUT)
        duplicate["decision_clauses"][1]["choice"] = "alternative-2"
        with self.assertRaisesRegex(ValueError, "choice permutation"):
            parse_structured_output(duplicate)

    def test_negative_threshold_is_allowed_but_fails_neutralization_gate(self) -> None:
        noncausal = deepcopy(VALID_OUTPUT)
        noncausal["decision_clauses"][0]["minimum_error_advantage"] = 0
        result = evaluate_structured_output(self.task, noncausal)
        self.assertEqual(result["neutralized_choice"], "alternative-2")
        self.assertFalse(
            structured_mechanism_valid([result, result], self.acceptance)
        )

    def test_prompt_excludes_fresh_sealed_split(self) -> None:
        prompt, ledger = rendered_structured_prompt(REPO, self.task)
        self.assertNotIn("sealed5-event-", prompt)
        self.assertIn("prior5-event-", prompt)
        self.assertEqual(len(ledger["entries"]), 1)

    def test_run_lock_covers_structured_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0025_structured.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0025_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0025/structured-output.schema.json"), paths)
        self.assertIn(Path("fixtures/ot-0025/pilot-task.json"), paths)
        self.assertIn(
            Path("evidence/manifests/OT-0024/ot-0024-portfolio-pilot-001.json"),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
