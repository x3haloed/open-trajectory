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


if __name__ == "__main__":
    unittest.main()
