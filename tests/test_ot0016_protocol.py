from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "fixtures" / "ot-0016"


class OT0016ProtocolTests(unittest.TestCase):
    def test_actor_facing_text_does_not_supply_hidden_selector_modes(self) -> None:
        actor_facing = "\n".join(
            (ROOT / name).read_text(encoding="utf-8").lower()
            for name in ("selector-seed.txt", "challenger-prompt.txt")
        )
        for forbidden in (
            "abstraction",
            "exception",
            "recency",
            "drift",
            "noise",
            "corroborat",
            "confidence",
            "nearest",
            "first-seen",
            "most-recent",
        ):
            self.assertNotIn(forbidden, actor_facing)

    def test_challenger_schema_freezes_both_expression_budgets(self) -> None:
        schema = json.loads(
            (ROOT / "challenger-output.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["properties"]["selector_expression"]["maxLength"], 2048)
        self.assertEqual(schema["properties"]["decision_expression"]["maxLength"], 512)
        self.assertFalse(schema["additionalProperties"])

    def test_decision_rule_is_prospective_and_controller_applied(self) -> None:
        seed = (ROOT / "selector-seed.txt").read_text(encoding="utf-8").lower()
        prompt = (ROOT / "challenger-prompt.txt").read_text(encoding="utf-8").lower()
        self.assertIn("authored before", seed)
        self.assertIn("python expression syntax", seed)
        self.assertIn("javascript syntax are invalid", seed)
        self.assertIn("will not see that future comparison", " ".join(prompt.split()))
        self.assertIn("controller owns", seed)

    def test_acceptance_freezes_recursive_causal_gates(self) -> None:
        acceptance = json.loads(
            (REPO / "spec" / "ot-0016-acceptance.json").read_text(encoding="utf-8")
        )
        scoring = acceptance["scoring"]
        self.assertEqual(scoring["useful_pre_harm_commits_required"], 2)
        self.assertEqual(
            scoring["learned_selector_harm_over_protected_parent_required"], 2
        )
        self.assertEqual(scoring["correction_error_recovery_required"], 3)
        self.assertEqual(scoring["post_correction_canary_advantage_required"], 2)
        controls = " ".join(acceptance["controls"])
        self.assertIn("outcome-credit-neutralization", controls)
        self.assertIn("protected-preupdate-parent", controls)
        self.assertEqual(acceptance["candidate"]["seed_selector_expression"], "[]")
        self.assertEqual(acceptance["candidate"]["seed_decision_expression"], '"current"')

    def test_task_order_separates_shaping_comparison_and_heldout_scoring(self) -> None:
        order = json.loads((ROOT / "task-order.json").read_text(encoding="utf-8"))
        causal = order["stage_causal_order"]
        self.assertLess(
            causal.index("fresh-proposal-from-prior-stage-receipt"),
            causal.index("reveal-contact-outcomes-and-issue-comparison-receipt"),
        )
        self.assertLess(
            causal.index("controller-commit-exact-true-choice"),
            causal.index("reveal-heldout-outcomes-and-issue-next-stage-receipt"),
        )
        self.assertNotIn("preupdate-parent", order["conditions"])


if __name__ == "__main__":
    unittest.main()
