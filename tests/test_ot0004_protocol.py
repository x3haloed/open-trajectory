from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "fixtures" / "ot-0004"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object in {path.name}")
    return value


class OT0004ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec" / "ot-0004-acceptance.json")
        self.task_order = load_json(ROOT / "task-order.json")

    def test_actor_facing_seed_does_not_name_hidden_strategy_families(self) -> None:
        actor_facing = "\n".join(
            (ROOT / name).read_text(encoding="utf-8").lower()
            for name in (
                "selector-seed.txt",
                "selector-update-prompt.txt",
                "selector-apply-prompt.txt",
                "predictor-prompt.txt",
            )
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
            self.assertEqual(set(phase["condition_order"]), {"worker-1", "worker-2"})
            for order in phase["condition_order"].values():
                self.assertEqual(len(order), len(conditions))
                self.assertEqual(set(order), set(conditions))
                for position, condition in enumerate(order):
                    counts[condition][position] += 1
        expected = Counter({position: 2 for position in range(6)})
        self.assertTrue(all(value == expected for value in counts.values()))

    def test_output_schemas_are_valid_and_match_frozen_budgets(self) -> None:
        update = load_json(ROOT / "selector-update-output.schema.json")
        apply = load_json(ROOT / "selector-apply-output.schema.json")
        predictor = load_json(ROOT / "predictor-output.schema.json")
        novelty = load_json(ROOT / "novelty-output.schema.json")
        for schema in (update, apply, predictor, novelty):
            Draft202012Validator.check_schema(schema)
        self.assertEqual(
            update["properties"]["policy"]["maxLength"],
            self.acceptance["candidate"]["policy_bytes"],
        )
        self.assertEqual(
            apply["properties"]["selected_event_ids"]["minItems"],
            self.acceptance["candidate"]["selected_events_per_prediction"],
        )
        self.assertNotIn("uniqueItems", apply["properties"]["selected_event_ids"])
        self.assertEqual(
            predictor["properties"]["predictions"]["minItems"],
            self.acceptance["world"]["heldout_queries_per_stage"],
        )

    def test_prompts_keep_policy_update_selection_and_prediction_separate(self) -> None:
        update = (ROOT / "selector-update-prompt.txt").read_text(encoding="utf-8")
        apply = (ROOT / "selector-apply-prompt.txt").read_text(encoding="utf-8")
        predictor = (ROOT / "predictor-prompt.txt").read_text(encoding="utf-8")
        self.assertIn("{{RECEIPT}}", update)
        self.assertNotIn("{{EVENTS}}", update)
        self.assertIn("{{POLICY}}", apply)
        self.assertIn("{{EVENTS}}", apply)
        self.assertIn("{{QUERIES}}", apply)
        self.assertNotIn("{{POLICY}}", predictor)
        self.assertIn("{{SELECTED_EVENTS}}", predictor)

    def test_protocol_cannot_promote_from_policy_prose_alone(self) -> None:
        required = set(self.acceptance["required_receipts"])
        self.assertTrue(any("changed and frozen" in item for item in required))
        self.assertTrue(any("independent world outcomes" in item for item in required))
        self.assertTrue(self.acceptance["scoring"]["selected_identity_change_required"])
        self.assertTrue(self.acceptance["scoring"]["selector_change_ablation_required"])

    def test_frozen_turn_budget_matches_the_realized_schedule(self) -> None:
        budget = self.acceptance["resource_budget"]
        observed = sum(
            budget[key]
            for key in (
                "selector_apply_turns_per_worker",
                "predictor_turns_per_worker",
                "selector_update_turns_per_worker",
                "novelty_review_turns_per_worker",
            )
        )
        self.assertEqual(observed, budget["actor_turns_total_per_worker"])
        stages = self.acceptance["world"]["stages"]
        conditions = len(self.task_order["conditions"])
        self.assertEqual(budget["selector_apply_turns_per_worker"], stages * 3)
        self.assertEqual(budget["predictor_turns_per_worker"], stages * (conditions + 1))
        self.assertEqual(budget["selector_update_turns_per_worker"], stages)

    def test_stage_causal_order_separates_contact_learning_from_heldout_evaluation(self) -> None:
        self.assertEqual(
            self.task_order["stage_causal_order"],
            [
                "contact-probe",
                "counterbalanced-heldout-branches",
                "stage-seal",
                "proposal-and-commit-for-next-stage",
            ],
        )
        joined = " ".join(self.acceptance["stage_causal_order"])
        self.assertLess(joined.index("heldout branch"), joined.index("selector-update"))
        self.assertIn("without consulting heldout outcomes", joined)


if __name__ == "__main__":
    unittest.main()
