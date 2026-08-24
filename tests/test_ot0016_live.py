from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0005_world import ProgramLedger
from open_trajectory_harness.ot0016_live import (
    _invalidated_summary,
    _decision_identity_placebo,
    _program_identity_placebo,
    _proposal,
    deterministic_branch,
    fixed_input_paths,
    proposal_prompt,
)
from open_trajectory_harness.ot0016_credit import (
    CounterfactualSelectorLedger,
    DecisionRuleLedger,
)


REPO = Path(__file__).resolve().parents[1]


class OT0016LiveHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = [
            {
                "event_id": f"event-{index}",
                "sequence": index,
                "features": [index & 1, (index >> 1) & 1, 0, 0],
                "label": index & 1,
            }
            for index in range(8)
        ]
        self.queries = [event["features"] for event in self.archive[:6]]
        self.outcomes = [event["label"] for event in self.archive[:6]]

    def test_prompt_contains_only_supplied_prior_receipt(self) -> None:
        prompt = proposal_prompt(
            "carrier",
            "{{SELECTOR_EXPRESSION}}|{{DECISION_EXPRESSION}}|{{PRIOR_RECEIPT}}",
            "[]",
            '"current"',
            {"status": "seed", "candidate_task_outcomes": False},
        )
        self.assertIn('[]|"current"', prompt)
        self.assertIn('"candidate_task_outcomes":false', prompt)
        self.assertNotIn("future", prompt)

    def test_proposal_splits_selector_and_prospective_rule(self) -> None:
        selector, decision = _proposal(
            {
                "selector_expression": '[e["event_id"] for e in events[:limit]]',
                "decision_expression": (
                    '"challenger" if comparison["challenger_error_advantage"] > 0 '
                    'else "current"'
                ),
                "expected_effect": "lower contact error",
                "cheapest_falsifier": "no paired advantage",
            }
        )
        self.assertIn("events", selector["expression"])
        self.assertIn("comparison", decision["expression"])
        self.assertEqual(selector["expected_effect"], decision["expected_effect"])

    def test_deterministic_branch_supports_null_seed_and_depth_eight(self) -> None:
        seed = ProgramLedger("[]", iteration_depth_limit=8).current
        branch = deterministic_branch(
            condition="seed",
            snapshot=seed,
            archive=self.archive,
            queries=self.queries,
            outcomes=self.outcomes,
            limit=6,
            iteration_depth_limit=8,
        )
        self.assertEqual(branch["selected_event_ids"], [])
        self.assertTrue(branch["deterministic_replay"])

    def test_distinct_identity_placebos_preserve_behavior(self) -> None:
        expression = '[e["event_id"] for e in events[:limit]]'
        snapshot = ProgramLedger(expression, iteration_depth_limit=8).current
        self.assertTrue(
            _program_identity_placebo(
                snapshot,
                self.archive,
                self.queries,
                self.outcomes,
                6,
                8,
            )
        )
        selectors = CounterfactualSelectorLedger()
        challenger = selectors.propose(
            {
                "expression": expression,
                "expected_effect": "use contacts",
                "cheapest_falsifier": "no advantage",
            }
        )
        receipt = selectors.compare(
            challenger,
            archive=self.archive,
            queries=self.queries,
            outcomes=self.outcomes,
            limit=6,
            stage=0,
            split_identity="test-contact",
        )
        rule = DecisionRuleLedger().commit(
            {
                "expression": (
                    '"challenger" if comparison["challenger_error_advantage"] > 0 '
                    'else "current"'
                ),
                "expected_effect": "retain lower error",
                "cheapest_falsifier": "choice differs",
            }
        )
        self.assertTrue(_decision_identity_placebo(rule, receipt))

    def test_run_lock_covers_every_live_authority_file(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0016_credit.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0016_world.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0016_live.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0002.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0003.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0005.py"), paths)
        self.assertIn(Path("src/open_trajectory_evidence/audit.py"), paths)
        self.assertIn(Path("experiments/ot_0016_harness.py"), paths)

    def test_worker_failure_produces_safe_invalidated_summary(self) -> None:
        raw = {
            "experiment_id": "OT-TEST",
            "run_id": "failed-run",
            "implementation_git_commit": "a" * 40,
            "task_manifest_sha256": "b" * 64,
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "failed",
                    "error_type": "TimeoutError",
                },
                {"worker_id": "worker-2", "status": "completed"},
            ],
            "worker_receipts": [
                {"worker_id": "worker-1", "returncode": 2},
                {"worker_id": "worker-2", "returncode": 0},
            ],
            "same_task_manifest": True,
            "two_worker_window_seconds": 100,
            "implementation_clean": True,
            "audit_and_tests": True,
            "acceptance": {
                "evaluation_epoch": "E4",
                "target_scope": "test scope",
                "deployment_epoch": {"maximum_two_worker_window_seconds": 420},
            },
        }
        summary = _invalidated_summary(raw)
        self.assertEqual(summary["disposition"], "invalidated")
        self.assertFalse(
            summary["validity_gates"]["complete_worker_processes"]
        )
        self.assertTrue(summary["validity_gates"]["complete_sealed_outputs"])
        self.assertEqual(
            summary["worker_statuses"][0]["error_type"], "TimeoutError"
        )
        self.assertNotIn("error", summary["worker_statuses"][0])


if __name__ == "__main__":
    unittest.main()
