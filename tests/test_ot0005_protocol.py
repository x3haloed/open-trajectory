from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "fixtures" / "ot-0005"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object in {path.name}")
    return value


class OT0005ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec" / "ot-0005-acceptance.json")
        self.task_order = load_json(ROOT / "task-order.json")

    def test_actor_prompts_do_not_name_hidden_strategy_families(self) -> None:
        actor_facing = "\n".join(
            (ROOT / name).read_text(encoding="utf-8").lower()
            for name in ("selector-seed.txt", "selector-update-prompt.txt")
        )
        for forbidden in (
            "abstraction",
            "exception",
            "recency",
            "drift",
            "noise",
            "corroborat",
            "confidence",
        ):
            self.assertNotIn(forbidden, actor_facing)

    def test_condition_positions_are_exactly_counterbalanced(self) -> None:
        conditions = self.task_order["conditions"]
        counts = {condition: Counter() for condition in conditions}
        for phase in self.task_order["phases"]:
            for order in phase["condition_order"].values():
                self.assertEqual(set(order), set(conditions))
                for position, condition in enumerate(order):
                    counts[condition][position] += 1
        expected = Counter({position: 2 for position in range(6)})
        self.assertTrue(all(value == expected for value in counts.values()))

    def test_output_schemas_and_budgets_are_frozen(self) -> None:
        update = load_json(ROOT / "selector-update-output.schema.json")
        novelty = load_json(ROOT / "novelty-output.schema.json")
        Draft202012Validator.check_schema(update)
        Draft202012Validator.check_schema(novelty)
        self.assertEqual(
            update["properties"]["expression"]["maxLength"],
            self.acceptance["candidate"]["expression_bytes"],
        )

    def test_turn_budget_contains_only_updates_and_semantic_reviews(self) -> None:
        budget = self.acceptance["resource_budget"]
        self.assertEqual(
            budget["actor_turns_total_per_worker"],
            budget["selector_update_turns_per_worker"]
            + budget["novelty_review_turns_per_worker"],
        )
        self.assertEqual(budget["selector_update_turns_per_worker"], self.acceptance["world"]["stages"])

    def test_identity_placebo_and_deterministic_replay_are_promotion_gates(self) -> None:
        controls = " ".join(self.acceptance["controls"])
        promotion = " ".join(self.acceptance["promotion_gate"])
        self.assertIn("identity-program", controls)
        self.assertIn("stage-zero identical-program placebo", promotion)
        self.assertTrue(
            self.acceptance["deterministic_instrument"]["candidate_program_application_replayed_twice"]
        )

    def test_inventory_identity_is_frozen_per_model_role(self) -> None:
        inventories = self.acceptance["direct_inventory_by_model"]
        self.assertEqual(set(inventories), {"gpt-5.6-luna", "gpt-5.6-terra"})
        self.assertNotEqual(
            inventories["gpt-5.6-luna"]["sha256"],
            inventories["gpt-5.6-terra"]["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
