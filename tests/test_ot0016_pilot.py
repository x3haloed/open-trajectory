from __future__ import annotations

import unittest

from open_trajectory_harness.ot0016_pilot import evaluate_pilot_output


VALID_OUTPUT = {
    "selector_expression": '[e["event_id"] for e in events[:limit]]',
    "decision_expression": (
        '"challenger" if comparison["challenger_errors"] '
        '< comparison["current_errors"] else "current"'
    ),
    "expected_effect": "Use the released comparison to determine the prospective commit.",
    "cheapest_falsifier": "The selector or decision rule has no deterministic effect.",
}


class OT0016PilotTests(unittest.TestCase):
    def test_valid_output_completes_public_causal_slice(self) -> None:
        result = evaluate_pilot_output(VALID_OUTPUT)
        self.assertTrue(result["selection_changed"])
        self.assertTrue(result["prediction_changed"])
        self.assertEqual(result["decision_choice"], "challenger")
        self.assertTrue(result["commit_changed"])
        self.assertTrue(result["deterministic_replay"])

    def test_extra_authority_or_invalid_expression_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_pilot_output({**VALID_OUTPUT, "claim": "success"})
        invalid = {**VALID_OUTPUT, "decision_expression": '__import__("os")'}
        with self.assertRaises(ValueError):
            evaluate_pilot_output(invalid)


if __name__ == "__main__":
    unittest.main()
