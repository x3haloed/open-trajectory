from __future__ import annotations

import ast
import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0016_credit import validate_decision_expression
from open_trajectory_harness.ot0023_portfolio import (
    evaluate_portfolio_output,
    portfolio_mechanism_valid,
    rendered_portfolio_prompt,
)
from open_trajectory_harness.ot0024_pilot import configure_protocol, fixed_input_paths


REPO = Path(__file__).resolve().parents[1]
DECISION = (
    '"alternative-2" if comparison["alternative_2_error_advantage"] > 0 and '
    'comparison["alternative_2_error_advantage"] >= '
    'comparison["alternative_0_error_advantage"] and '
    'comparison["alternative_2_error_advantage"] >= '
    'comparison["alternative_1_error_advantage"] and '
    'comparison["current_errors"] >= 0 else '
    '("alternative-0" if comparison["alternative_0_error_advantage"] > 0 '
    'else ("alternative-1" if '
    'comparison["alternative_1_error_advantage"] > 0 else "current"))'
)
VALID_OUTPUT = {
    "alternatives": [
        {
            "selector_expression": '[e["event_id"] for e in events[:limit]]',
            "expected_effect": "retain the earliest observations",
            "cheapest_falsifier": "later outcomes require missing contrast",
        },
        {
            "selector_expression": '[e["event_id"] for e in events[-limit:]]',
            "expected_effect": "retain the latest observations",
            "cheapest_falsifier": "earlier outcomes provide missing contrast",
        },
        {
            "selector_expression": (
                '[e["event_id"] for e in '
                '(events[:limit//2] + events[-(limit-limit//2):])]'
            ),
            "expected_effect": "retain contrast from both sequence halves",
            "cheapest_falsifier": "cross-half sample does not reduce error",
        },
    ],
    "decision_expression": DECISION,
    "decision_expected_effect": "prefer the strongest changed improvement",
    "decision_cheapest_falsifier": "no alternative improves paired error",
}


class OT0024PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0024/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0024-acceptance.json")

    def test_expanded_decision_carrier_is_specific_and_bounded(self) -> None:
        node_count = len(list(ast.walk(ast.parse(DECISION, mode="eval"))))
        self.assertGreater(node_count, 64)
        self.assertLessEqual(node_count, 128)
        with self.assertRaisesRegex(ValueError, "AST-node budget"):
            validate_decision_expression(DECISION, node_limit=64)
        validate_decision_expression(DECISION, node_limit=128)

    def test_known_portfolio_selects_cross_half_contrast(self) -> None:
        result = evaluate_portfolio_output(self.task, VALID_OUTPUT)
        self.assertEqual(result["program_identity_count"], 3)
        self.assertGreaterEqual(result["selection_identity_count"], 2)
        self.assertEqual(result["true_choice"], "alternative-2")
        self.assertEqual(result["neutralized_choice"], "current")
        self.assertEqual(result["chosen_advantage"], 8)
        self.assertTrue(
            portfolio_mechanism_valid([result, result], self.acceptance)
        )

    def test_prompt_excludes_fresh_sealed_split(self) -> None:
        prompt, _ = rendered_portfolio_prompt(REPO, self.task)
        self.assertNotIn("sealed4-event-", prompt)
        self.assertIn("prior4-event-", prompt)

    def test_run_lock_covers_expanded_carrier_and_fresh_task(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0016_credit.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0023_portfolio.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0024_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0024/pilot-task.json"), paths)
        self.assertIn(
            Path("evidence/manifests/OT-0023/ot-0023-portfolio-pilot-001.json"),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
