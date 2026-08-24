from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0013 import (
    combined_summary,
    decode_response,
    generate_task_manifest,
    response_schema,
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
                    "thread_id": f"response-{worker_id}-{index}",
                    "workspace": f"workspace-{worker_id}-{index}",
                    "projection_bytes": 80,
                    "inventory_receipts": 1,
                    "substrate_project_operations": 30,
                    "substrate_observe_operations": 150,
                    "request_has_no_prior_context": True,
                    "usage": {"input_tokens": 200, "output_tokens": 150, "total_tokens": 350},
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
                "thread_id": f"response-{worker_id}-{index}",
                "workspace": f"workspace-{worker_id}-{index}",
                "projection_bytes": 30,
                "inventory_receipts": 1,
                "substrate_project_operations": 0,
                "substrate_observe_operations": 0,
                "request_has_no_prior_context": True,
                "usage": {"input_tokens": 200, "output_tokens": 150, "total_tokens": 350},
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
        "usage": {"input_tokens": 5200, "output_tokens": 3900, "total_tokens": 9100},
        "elapsed_seconds": 1000,
    }


class OT0013HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acceptance = load_json(REPO / "spec/ot-0013-acceptance.json")

    def test_response_schema_binds_exact_batch_length(self) -> None:
        frozen = load_json(REPO / "fixtures/ot-0013/actor-output.schema.json")
        exact = response_schema(frozen, 5)
        self.assertEqual(exact["properties"]["predictions"]["minItems"], 5)
        self.assertEqual(exact["properties"]["predictions"]["maxItems"], 5)
        self.assertEqual(frozen["properties"]["predictions"]["minItems"], 4)

    def test_decoder_accepts_one_strict_final_message(self) -> None:
        response = {
            "output": [
                {"type": "reasoning", "content": []},
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '{"predictions":[0,1,1,0]}'}
                    ],
                },
            ]
        }
        self.assertEqual(decode_response(response, 4), ([0, 1, 1, 0], None))

    def test_decoder_rejects_reasoning_only_or_wrong_key(self) -> None:
        self.assertIsNotNone(decode_response({"output": [{"type": "reasoning"}]}, 4)[1])
        wrong = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"labels":[0,1,1,0]}'}],
                }
            ]
        }
        self.assertIsNotNone(decode_response(wrong, 4)[1])

    def test_manifest_wrapper_preserves_world_validation(self) -> None:
        manifest = generate_task_manifest()
        validate_task_manifest(manifest)
        manifest["outcomes"]["regime-a"]["basis"][0] ^= 1
        with self.assertRaises(ValueError):
            validate_task_manifest(manifest)

    def test_two_passing_workers_promote(self) -> None:
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

    def test_stateless_request_and_output_cap_are_gates(self) -> None:
        worker = passing_worker("failed")
        worker["results"][0]["request_has_no_prior_context"] = False
        worker["results"][1]["usage"]["output_tokens"] = 257
        summary = worker_summary(worker, self.acceptance)
        self.assertFalse(summary["gates"]["stateless_requests"])
        self.assertFalse(summary["gates"]["output_cap"])
        self.assertFalse(summary["scientific_pass"])


if __name__ == "__main__":
    unittest.main()
