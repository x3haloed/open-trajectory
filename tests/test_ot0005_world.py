from __future__ import annotations

import unittest

from open_trajectory_harness.ot0005_world import (
    ProgramLedger,
    archive_through_stage,
    deterministic_predictions,
    deterministic_selection,
    execute_selector,
    generate_task_manifest,
    selected_events,
    validate_selector_expression,
    validate_task_manifest,
)


RECENT_EXPRESSION = (
    '[e["event_id"] for e in sorted(events, '
    'key=lambda e: e["sequence"], reverse=True)[:limit]]'
)
NEAREST_EXPRESSION = (
    '[e["event_id"] for e in sorted(events, key=lambda e: '
    'min(sum(a != b for a, b in zip(e["features"], q)) for q in queries))[:limit]]'
)


class OT0005WorldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = generate_task_manifest()
        validate_task_manifest(self.manifest)
        self.archive = archive_through_stage(self.manifest, 2)
        self.queries = self.manifest["stages"][2]["heldout"]["queries"]

    def test_generic_expression_executes_with_exact_deterministic_budget(self) -> None:
        selected = deterministic_selection(RECENT_EXPRESSION, self.archive, self.queries, 6)
        self.assertEqual(len(selected), 6)
        self.assertEqual(selected, deterministic_selection(RECENT_EXPRESSION, self.archive, self.queries, 6))
        self.assertEqual(
            selected,
            [event["event_id"] for event in sorted(self.archive, key=lambda event: event["sequence"], reverse=True)[:6]],
        )

    def test_expression_lambda_can_compare_events_with_queries(self) -> None:
        selected = deterministic_selection(NEAREST_EXPRESSION, self.archive, self.queries, 6)
        self.assertEqual(len(selected), 6)

    def test_null_seed_is_allowed_only_when_explicitly_requested(self) -> None:
        self.assertEqual(execute_selector("[]", self.archive, self.queries, 6, allow_empty=True), [])
        with self.assertRaises(ValueError):
            execute_selector("[]", self.archive, self.queries, 6)

    def test_runtime_rejects_imports_attributes_private_names_and_unlisted_calls(self) -> None:
        for expression in (
            '__import__("os")',
            "events.__class__",
            "open(\"private\")",
            "_hidden",
            "[e for e in events if (lambda: 1)()]",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                validate_selector_expression(expression)

    def test_runtime_rejects_excessive_iteration_depth(self) -> None:
        expression = (
            '[a["event_id"] for a in events for b in events for c in events '
            'for d in events for e in events][:limit]'
        )
        with self.assertRaises(ValueError):
            validate_selector_expression(expression)
        validate_selector_expression(expression, iteration_depth_limit=8)

    def test_deeper_version_remains_bounded_by_evaluation_timeout(self) -> None:
        expression = (
            '[a["event_id"] for a in events for b in events for c in events '
            'for d in events for e in events for f in events][:limit]'
        )
        with self.assertRaises(ValueError):
            execute_selector(
                expression,
                self.archive,
                self.queries,
                6,
                timeout_seconds=0.01,
                iteration_depth_limit=8,
            )

    def test_runtime_rejects_duplicate_unknown_and_under_budget_results(self) -> None:
        event_id = self.archive[0]["event_id"]
        for expression in (
            repr([event_id] * 6),
            repr(["event-unknown"] * 6),
            repr([event_id]),
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                execute_selector(expression, self.archive, self.queries, 6)

    def test_deterministic_predictor_uses_exact_majority_then_parity_fit(self) -> None:
        selected = [
            {"features": [0, 0, 0, 0], "label": 1},
            {"features": [0, 0, 0, 0], "label": 1},
            {"features": [1, 0, 0, 0], "label": 0},
            {"features": [0, 1, 0, 0], "label": 0},
        ]
        queries = [[0, 0, 0, 0], [1, 1, 0, 0]]
        first = deterministic_predictions(selected, queries)
        self.assertEqual(first[0], 1)
        self.assertEqual(first, deterministic_predictions(selected, queries))

    def test_program_ledger_commits_an_immutable_validated_chain(self) -> None:
        ledger = ProgramLedger()
        seed = ledger.current
        changed = ledger.commit(
            {
                "expression": RECENT_EXPRESSION,
                "expected_effect": "Use a different bounded subset.",
                "cheapest_falsifier": "The selected identity vector does not change.",
            }
        )
        self.assertEqual(changed.parent_sha256, seed.sha256)
        self.assertNotEqual(changed.sha256, seed.sha256)
        self.assertEqual(ledger.snapshots[0], seed)

    def test_selected_events_remain_controller_validated(self) -> None:
        ids = deterministic_selection(RECENT_EXPRESSION, self.archive, self.queries, 6)
        self.assertEqual(len(selected_events(self.archive, ids)), 6)


if __name__ == "__main__":
    unittest.main()
