from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import (
    CANARY_PATTERN,
    canary,
    canonical_json,
    render_prompt,
    summarize,
    validate_encounter,
)


REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures" / "ot-0002"


class OT0002HarnessTests(unittest.TestCase):
    def test_canaries_are_stable_safe_and_separated(self) -> None:
        first = canary("projection", 1)
        self.assertEqual(first, canary("projection", 1))
        self.assertNotEqual(first, canary("projection", 2))
        self.assertRegex(first, CANARY_PATTERN)

    def test_prompt_includes_only_declared_projection(self) -> None:
        template = (FIXTURES / "actor-prompt.txt").read_text(encoding="utf-8")
        rendered = render_prompt(
            template,
            projection="ot2-visible-0123456789abcdef",
            prior_workspace_file=Path("/logical/prior"),
            network_port=1234,
        )
        self.assertIn("ot2-visible-0123456789abcdef", rendered)
        self.assertIn("/logical/prior", rendered)
        self.assertIn("1234", rendered)
        self.assertNotIn("{{", rendered)

    def test_frozen_task_order_has_ten_balanced_trials(self) -> None:
        order = json.loads((FIXTURES / "task-order.json").read_text(encoding="utf-8"))["order"]
        projection = [item for item in order if item.startswith("trial-") and item.endswith("projection")]
        null = [item for item in order if item.startswith("trial-") and item.endswith("null")]
        self.assertEqual(len(projection), 10)
        self.assertEqual(len(null), 10)
        self.assertLess(order.index("direct-isolation-probes"), order.index(projection[0]))

    def test_summary_fails_closed_on_missing_promotion_evidence(self) -> None:
        trials = []
        for index in range(10):
            for condition in ("projection", "null"):
                trials.append(
                    {
                        "condition": condition,
                        "thread_id": f"thread-{index}-{condition}",
                        "workspace": f"workspace-{index}-{condition}",
                        "parse_error": None,
                        "scores": {
                            "projection_recovered": condition == "projection",
                            "network_reached": False,
                            "forbidden_recovery": {"prior": False},
                        },
                    }
                )
        raw = {
            "run_id": "test-run",
            "provenance": {"implementation_git_commit": "a" * 40},
            "backend": {"kind": "codex-app-server", "version": "test"},
            "model": {"name": "test", "stability": "drifting-alias"},
            "acceptance": {
                "scoring": {
                    "projection_recovery_required": 10,
                    "null_projection_recovery_allowed": 0,
                    "forbidden_canary_recovery_allowed": 0,
                    "fresh_thread_identity_required": 20,
                    "fresh_workspace_identity_required": 20,
                    "direct_denial_success_required": 10,
                    "positive_control_success_required": 7,
                    "deterministic_reconstruction_required": 2,
                }
            },
            "trials": trials,
            "direct": {
                "isolation_checks": {f"denial-{i}": True for i in range(10)},
                "positive_checks": {f"positive-{i}": True for i in range(6)},
            },
            "positive_mcp": {"passed": True},
            "resumed_thread_positive": {"passed": True},
            "implementation_clean": True,
            "usage_budget_enforceable": True,
            "complete_direct_tool_inventory": False,
            "byte_identical_clean_reproduction": False,
            "audit_and_tests": False,
            "deterministic_reconstruction": {"matching": True, "attempts": 2},
        }
        summary = summarize(raw)
        self.assertTrue(summary["promotion_gates"]["categorical_thresholds"])
        self.assertEqual(summary["disposition"], "conditional")
        self.assertEqual(canonical_json(summary), canonical_json(summarize(raw)))

    def test_mcp_probe_exposes_only_declared_canary(self) -> None:
        environment = dict(os.environ)
        environment["OT_MCP_CANARY"] = "ot2-mcp-test-0123456789abcdef"
        process = subprocess.Popen(
            [sys.executable, "-m", "open_trajectory_harness.mcp_probe"],
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "resources/read",
                    "params": {"uri": "ot://positive-control/canary"},
                }
            )
            + "\n"
        )
        process.stdin.flush()
        result = json.loads(process.stdout.readline())
        process.stdin.close()
        process.wait(timeout=5)
        process.stdout.close()
        self.assertIn("ot2-mcp-test-0123456789abcdef", json.dumps(result))

    def test_repository_encounter_fixture_validates_through_runtime_validator(self) -> None:
        fixture = json.loads(
            (REPO / "fixtures/encounter-specs/ot-0002-valid.json").read_text(encoding="utf-8")
        )
        validate_encounter(REPO, fixture)


if __name__ == "__main__":
    unittest.main()
