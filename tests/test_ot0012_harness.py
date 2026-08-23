from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0012 import (
    combined_summary,
    decode_actor_output,
    generate_task_manifest,
    validate_task_manifest,
    worker_summary,
)


REPO = Path(__file__).resolve().parents[1]
EMPTY_INVENTORY_SHA256 = "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570"


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
        for condition in ("candidate", "no-persistence", "verbatim-events", "nearest-events"):
            score = 0 if condition == "candidate" else (2 if score_kind == "heldout" else 0)
            results.append(
                {
                    "condition": condition,
                    "phase": phase,
                    "score_kind": score_kind,
                    "errors": score,
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
        "model_identity_verified": True,
        "results": results,
        "candidate_state": {"regime": 1, "matches_hidden_regime_b": True},
        "direct_inventory": {
            "sha256": EMPTY_INVENTORY_SHA256,
            "tool_count": 0,
            "receipt_count": 26,
            "stable": True,
        },
        "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "elapsed_seconds": 10,
    }


class OT0012HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0012-acceptance.json")

    def test_decoder_accepts_only_direct_or_frozen_harmony_json(self) -> None:
        body = '{"predictions":[0,1,1,0]}'
        self.assertEqual(decode_actor_output(body, 4), ([0, 1, 1, 0], None))
        for case in ("json", "JSON"):
            framed = f"<|channel|>final <|constrain|>{case}<|message|>{body}"
            self.assertEqual(decode_actor_output(framed, 4), ([0, 1, 1, 0], None))

    def test_decoder_rejects_unknown_framing_and_invalid_shape(self) -> None:
        predictions, error = decode_actor_output(f"final: {{\"predictions\":[0,1,1,0]}}", 4)
        self.assertEqual(predictions, [])
        self.assertIsNotNone(error)
        for body in ('{"labels":[0,1,1,0]}', '{"predictions":[0,1]}'):
            self.assertNotEqual(decode_actor_output(body, 4)[1], None)

    def test_manifest_wrapper_preserves_world_validation(self) -> None:
        manifest = generate_task_manifest()
        validate_task_manifest(manifest)
        manifest["outcomes"]["regime-a"]["basis"][0] ^= 1
        with self.assertRaises(ValueError):
            validate_task_manifest(manifest)

    def test_two_passing_workers_promote_content_addressed_result(self) -> None:
        workers = [passing_worker("one"), passing_worker("two")]
        self.assertTrue(worker_summary(workers[0], self.acceptance)["scientific_pass"])
        raw = {
            "run_id": "test-run",
            "implementation_git_commit": "a" * 40,
            "task_manifest_sha256": "b" * 64,
            "same_task_manifest": True,
            "implementation_clean": True,
            "model_identity_verified": True,
            "audit_and_tests": True,
            "acceptance": self.acceptance,
            "workers": workers,
        }
        self.assertEqual(combined_summary(raw)["disposition"], "promoted")

    def test_model_identity_is_a_worker_gate(self) -> None:
        worker = passing_worker("failed")
        worker["model_identity_verified"] = False
        summary = worker_summary(worker, self.acceptance)
        self.assertFalse(summary["gates"]["content_addressed_model"])
        self.assertFalse(summary["scientific_pass"])


if __name__ == "__main__":
    unittest.main()
