from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0023_pilot import configure_protocol, fixed_input_paths
from open_trajectory_harness.ot0023_portfolio import (
    evaluate_portfolio_output,
    parse_portfolio_output,
    portfolio_mechanism_valid,
    rendered_portfolio_prompt,
)


REPO = Path(__file__).resolve().parents[1]
VALID_OUTPUT = {
    "alternatives": [
        {
            "selector_expression": '[e["event_id"] for e in events[:limit]]',
            "expected_effect": "retain an early contrast sample",
            "cheapest_falsifier": "paired errors do not improve",
        },
        {
            "selector_expression": '[e["event_id"] for e in events[-limit:]]',
            "expected_effect": "retain a later contrast sample",
            "cheapest_falsifier": "paired errors do not improve",
        },
        {
            "selector_expression": (
                '[e["event_id"] for e in sorted(events, '
                'key=lambda e: (e["sequence"] % 2, e["sequence"]))[:limit]]'
            ),
            "expected_effect": "retain sequence-spread contrast",
            "cheapest_falsifier": "selection collapses to one outcome",
        },
    ],
    "decision_expression": (
        '"alternative-0" if comparison["alternative_0_error_advantage"] > 0 '
        'else ("alternative-1" if '
        'comparison["alternative_1_error_advantage"] > 0 else '
        '("alternative-2" if '
        'comparison["alternative_2_error_advantage"] > 0 else "current"))'
    ),
    "decision_expected_effect": "commit the first measured improvement",
    "decision_cheapest_falsifier": "no alternative has positive advantage",
}


class OT0023PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0023/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0023-acceptance.json")

    def test_known_portfolio_realizes_credit_dependent_choice(self) -> None:
        result = evaluate_portfolio_output(self.task, VALID_OUTPUT)
        self.assertEqual(result["program_identity_count"], 3)
        self.assertGreaterEqual(result["selection_identity_count"], 2)
        self.assertGreaterEqual(result["chosen_advantage"], 4)
        self.assertEqual(result["true_choice"], "alternative-0")
        self.assertEqual(result["neutralized_choice"], "current")
        self.assertTrue(result["commit_changed"])
        self.assertTrue(
            portfolio_mechanism_valid([result, result], self.acceptance)
        )

    def test_duplicate_alternatives_are_rejected(self) -> None:
        duplicate = deepcopy(VALID_OUTPUT)
        duplicate["alternatives"][1]["selector_expression"] = duplicate[
            "alternatives"
        ][0]["selector_expression"]
        with self.assertRaisesRegex(ValueError, "expression-distinct"):
            parse_portfolio_output(duplicate)

    def test_prompt_excludes_fresh_sealed_split(self) -> None:
        prompt, ledger = rendered_portfolio_prompt(REPO, self.task)
        self.assertNotIn("sealed3-event-", prompt)
        self.assertIn("prior3-event-", prompt)
        self.assertEqual(len(ledger["entries"]), 1)

    def test_run_lock_covers_portfolio_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0023_portfolio.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0023_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0023/portfolio-output.schema.json"), paths)
        self.assertIn(Path("fixtures/ot-0023/pilot-task.json"), paths)
        self.assertIn(
            Path("evidence/manifests/OT-0022/ot-0022-trace-pilot-001.json"),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
