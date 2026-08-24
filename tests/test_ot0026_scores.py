from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0026_pilot import configure_protocol, fixed_input_paths
from open_trajectory_harness.ot0026_scores import (
    evaluate_score_output,
    rendered_score_prompt,
    score_mechanism_valid,
    validate_score_program,
)


REPO = Path(__file__).resolve().parents[1]


def token(op: str, *, value: int = 0, index: int = 0) -> dict[str, int | str]:
    return {"op": op, "value": value, "index": index}


VALID_OUTPUT = {
    "alternatives": [
        {
            "selector_program": {
                "tokens": [token("sequence")],
                "descending": True,
            },
            "expected_effect": "retain the latest relation",
            "cheapest_falsifier": "the latest events do not reduce error",
        },
        {
            "selector_program": {
                "tokens": [token("sequence")],
                "descending": False,
            },
            "expected_effect": "retain the earliest relation",
            "cheapest_falsifier": "the earliest events do not reduce error",
        },
        {
            "selector_program": {
                "tokens": [
                    token("sequence"),
                    token("constant", value=7),
                    token("subtract"),
                    token("abs"),
                ],
                "descending": True,
            },
            "expected_effect": "retain both temporal extremes",
            "cheapest_falsifier": "the extremes do not preserve the relation",
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
    "decision_expected_effect": "commit the first useful score program",
    "decision_cheapest_falsifier": "no alternative has positive advantage",
}


class OT0026ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_protocol()

    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0026/pilot-task.json")
        self.acceptance = load_json(REPO / "spec/ot-0026-acceptance.json")

    def test_known_score_portfolio_realizes_causal_choice(self) -> None:
        result = evaluate_score_output(self.task, VALID_OUTPUT)
        self.assertEqual(result["program_identity_count"], 3)
        self.assertGreaterEqual(result["selection_identity_count"], 2)
        self.assertEqual(result["true_choice"], "alternative-2")
        self.assertEqual(result["neutralized_choice"], "current")
        self.assertEqual(result["chosen_advantage"], 8)
        self.assertTrue(score_mechanism_valid([result, result], self.acceptance))

    def test_program_rejects_underflow_and_unused_operands(self) -> None:
        with self.assertRaisesRegex(ValueError, "underflows"):
            validate_score_program(
                {"tokens": [token("add")], "descending": True}
            )
        with self.assertRaisesRegex(ValueError, "unused token operands"):
            validate_score_program(
                {"tokens": [token("sequence", value=1)], "descending": True}
            )

    def test_programs_must_be_identity_distinct(self) -> None:
        duplicate = deepcopy(VALID_OUTPUT)
        duplicate["alternatives"][1]["selector_program"] = deepcopy(
            duplicate["alternatives"][0]["selector_program"]
        )
        with self.assertRaisesRegex(ValueError, "not distinct"):
            evaluate_score_output(self.task, duplicate)

    def test_zero_threshold_fails_credit_neutralization(self) -> None:
        noncausal = deepcopy(VALID_OUTPUT)
        noncausal["decision_clauses"][0]["minimum_error_advantage"] = 0
        result = evaluate_score_output(self.task, noncausal)
        self.assertEqual(result["neutralized_choice"], "alternative-2")
        self.assertFalse(
            score_mechanism_valid([result, result], self.acceptance)
        )

    def test_prompt_excludes_fresh_sealed_split(self) -> None:
        prompt, ledger = rendered_score_prompt(REPO, self.task)
        self.assertNotIn("sealed6-event-", prompt)
        self.assertIn("prior6-event-", prompt)
        self.assertEqual(len(ledger["entries"]), 1)

    def test_run_lock_covers_score_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0026_scores.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0026_pilot.py"), paths)
        self.assertIn(Path("fixtures/ot-0026/score-output.schema.json"), paths)
        self.assertIn(Path("fixtures/ot-0026/pilot-task.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0025/"
                "ot-0025-structured-pilot-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
