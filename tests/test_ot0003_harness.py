from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0003 import (
    combined_summary,
    read_sealed_json,
    worker_summary,
    write_sealed_json,
)


REPO = Path(__file__).resolve().parents[1]


def passing_worker(worker_id: str) -> dict:
    results = []
    index = 0
    for phase, score_kind in (
        ("regime-a-contact", "contact"),
        ("regime-a-holdout-1", "heldout"),
        ("regime-a-holdout-2", "heldout"),
        ("regime-b-contact", "shift-contact"),
        ("regime-b-holdout-1", "heldout"),
        ("regime-b-holdout-2", "heldout"),
    ):
        for condition in (
            "candidate",
            "no-persistence",
            "verbatim-events",
            "nearest-events",
        ):
            error = 0 if condition == "candidate" else (2 if score_kind == "heldout" else 0)
            results.append(
                {
                    "condition": condition,
                    "phase": phase,
                    "score_kind": score_kind,
                    "errors": error,
                    "outcomes": [0, 1, 0, 1] if score_kind == "heldout" else [0] * 5,
                    "parse_error": None,
                    "tool_calls": 0,
                    "thread_id": f"thread-{worker_id}-{index}",
                    "workspace": f"workspace-{worker_id}-{index}",
                    "projection_bytes": 80,
                    "inventory_receipts": 1,
                    "substrate_project_operations": 30,
                    "substrate_observe_operations": 150,
                }
            )
            index += 1
    for phase in ("regime-b-ablation-1", "regime-b-ablation-2"):
        results.append(
            {
                "condition": "candidate-ablation",
                "phase": phase,
                "score_kind": "ablation",
                "errors": 2,
                "outcomes": [0, 1, 0, 1],
                "parse_error": None,
                "tool_calls": 0,
                "thread_id": f"thread-{worker_id}-{index}",
                "workspace": f"workspace-{worker_id}-{index}",
                "projection_bytes": 30,
                "inventory_receipts": 1,
                "substrate_project_operations": 0,
                "substrate_observe_operations": 0,
            }
        )
        index += 1
    return {
        "worker_id": worker_id,
        "status": "completed",
        "results": results,
        "candidate_state": {"regime": 1, "matches_hidden_regime_b": True},
        "direct_inventory": {
            "sha256": "b970b69dbf7459cc52d3aeca3d02ed9ece172abaa3378d3fbea5a9ca8bc50841",
            "tool_count": 3,
            "receipt_count": 26,
            "stable": True,
        },
        "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "elapsed_seconds": 10,
    }


class OT0003HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0003-acceptance.json")

    def test_comparative_evaluator_passes_science_but_not_drifting_model_promotion(self) -> None:
        workers = [passing_worker("one"), passing_worker("two")]
        for worker in workers:
            self.assertTrue(worker_summary(worker, self.acceptance)["scientific_pass"])
        raw = {
            "run_id": "test-run",
            "implementation_git_commit": "a" * 40,
            "task_manifest_sha256": "b" * 64,
            "same_task_manifest": True,
            "implementation_clean": True,
            "audit_and_tests": True,
            "acceptance": self.acceptance,
            "workers": workers,
        }
        summary = combined_summary(raw)
        self.assertTrue(summary["promotion_gates"]["clean_reproduction"])
        self.assertFalse(summary["promotion_gates"]["immutable_model_revision"])
        self.assertEqual(summary["disposition"], "conditional")

    def test_evaluator_rejects_a_control_margin_failure(self) -> None:
        worker = passing_worker("failed")
        for item in worker["results"]:
            if item["condition"] == "nearest-events" and item["score_kind"] == "heldout":
                item["errors"] = 0
        summary = worker_summary(worker, self.acceptance)
        self.assertFalse(summary["gates"]["control_advantages"])
        self.assertFalse(summary["scientific_pass"])

    def test_private_json_is_permission_sealed_between_workers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sealed.json"
            write_sealed_json(path, {"safe": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0)
            value, _ = read_sealed_json(path)
            self.assertEqual(value, {"safe": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0)


if __name__ == "__main__":
    unittest.main()
