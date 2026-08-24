from __future__ import annotations

import copy
import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0035_integration import (
    build_task,
    expected_task_seed,
    fixed_input_paths,
    fixed_snapshots,
    run_core,
    summarize,
    validate_task_order,
)


DEVELOPMENT_SEED = "0" * 64


class OT0035IntegrationTests(unittest.TestCase):
    def test_development_task_realizes_selector_to_ot0_ledger_path(self) -> None:
        result = run_core(DEVELOPMENT_SEED)
        self.assertEqual(
            [regime["contact_errors"] for regime in result["regimes"]],
            [40, 80, 80],
        )
        self.assertEqual(
            [regime["candidate_ledger_errors"] for regime in result["regimes"]],
            [0, 0, 0],
        )
        self.assertEqual(
            [regime["unchanged_ledger_errors"] for regime in result["regimes"]],
            [8, 8, 8],
        )
        self.assertEqual(result["candidate_aggregate_ledger_errors"], 0)
        self.assertEqual(result["best_fixed_aggregate_ledger_errors"], 8)
        self.assertTrue(
            all(not regime["neutralized_changed"] for regime in result["regimes"])
        )

    def test_candidate_projection_names_the_task_rule_after_each_update(self) -> None:
        result = run_core(DEVELOPMENT_SEED)
        for regime in result["regimes"]:
            self.assertIn("Inherited rule", regime["candidate_projection"])
            self.assertNotEqual(
                regime["candidate_projection"], regime["unchanged_projection"]
            )

    def test_task_is_post_implementation_and_seed_sensitive(self) -> None:
        first = expected_task_seed("1" * 40)
        second = expected_task_seed("2" * 40)
        self.assertNotEqual(first, second)
        self.assertNotEqual(build_task(first)["task_sha256"], build_task(second)["task_sha256"])

    def test_excluded_development_seed_family_preserves_all_core_gates(self) -> None:
        for index in range(32):
            with self.subTest(index=index):
                result = run_core(f"{index:064x}")
                self.assertEqual(result["candidate_aggregate_ledger_errors"], 0)
                self.assertEqual(result["best_fixed_aggregate_ledger_errors"], 8)

    def test_all_fixed_selectors_have_the_exact_active_budget(self) -> None:
        controls = fixed_snapshots()
        self.assertEqual(len(controls), 9)
        self.assertEqual(
            set(controls),
            {
                "fixed-zero",
                "fixed-axis-0-negative",
                "fixed-axis-0-positive",
                "fixed-axis-1-negative",
                "fixed-axis-1-positive",
                "fixed-axis-2-negative",
                "fixed-axis-2-positive",
                "fixed-axis-3-negative",
                "fixed-axis-3-positive",
            },
        )

    def test_task_order_is_reversed_and_time_balanced(self) -> None:
        acceptance = load_json(Path("spec/ot-0035-acceptance.json"))
        order = load_json(Path("fixtures/ot-0035/task-order.json"))
        validate_task_order(order, acceptance)

    def test_run_lock_will_bind_every_runtime_authority(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("spec/ot-0035-acceptance.json"), paths)
        self.assertIn(Path("fixtures/ot-0035/task-order.json"), paths)
        self.assertIn(
            Path("src/open_trajectory_harness/ot0035_integration.py"), paths
        )
        self.assertIn(Path("src/open_trajectory_harness/ot0003_world.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0014.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0034/"
                "ot-0034-e5-weighted-selector-calibration-001.json"
            ),
            paths,
        )

    def test_summary_dispatches_every_frozen_scientific_gate(self) -> None:
        acceptance = copy.deepcopy(load_json(Path("spec/ot-0035-acceptance.json")))
        order = load_json(Path("fixtures/ot-0035/task-order.json"))
        inventory = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        acceptance["direct_inventory"] = {
            "sha256": sha256_bytes(canonical_json(inventory)),
            "tool_count": 3,
        }
        actor_results = []
        proxy_receipts = [{"kind": "models_etag", "value": "etag"}]
        counter = 0
        outcomes = [0, 1, 0, 1, 0, 1, 0, 1]
        for worker in ("worker-1", "worker-2"):
            for phase in order["phases"]:
                index = int(phase["phase"][-1])
                for condition in phase[worker]:
                    if condition == "candidate":
                        predictions = list(outcomes)
                    elif condition == "unchanged-selector":
                        predictions = [1 - value for value in outcomes]
                        if index == 1:
                            predictions[3:] = outcomes[3:]
                    elif condition == "frozen-first-learned" and index in (1, 3):
                        predictions = list(outcomes)
                    else:
                        predictions = [1 - value for value in outcomes]
                    counter += 1
                    response_id = f"response-{counter}"
                    actor_results.append(
                        {
                            "worker": worker,
                            "phase": phase["phase"],
                            "condition": condition,
                            "predictions": predictions,
                            "errors": sum(a != b for a, b in zip(predictions, outcomes)),
                            "parse_error": None,
                            "tool_calls": 0,
                            "thread_id": f"thread-{counter}",
                            "workspace": f"workspace-{counter}",
                            "deployment_response_ids": [response_id],
                            "deployment_effective_models": ["gpt-5.6-luna"],
                            "inventory_receipts": 1,
                        }
                    )
                    proxy_receipts.extend(
                        [
                            {"kind": "response_id", "value": response_id},
                            {"kind": "effective_model", "value": "gpt-5.6-luna"},
                        ]
                    )
            counter += 1
            response_id = f"response-{counter}"
            predictions = list(outcomes)
            predictions[:3] = [1 - value for value in outcomes[:3]]
            actor_results.append(
                {
                    "worker": worker,
                    "phase": "regime-3",
                    "condition": "candidate-projection-ablation",
                    "predictions": predictions,
                    "errors": 3,
                    "parse_error": None,
                    "tool_calls": 0,
                    "thread_id": f"thread-{counter}",
                    "workspace": f"workspace-{counter}",
                    "deployment_response_ids": [response_id],
                    "deployment_effective_models": ["gpt-5.6-luna"],
                    "inventory_receipts": 1,
                }
            )
            proxy_receipts.extend(
                [
                    {"kind": "response_id", "value": response_id},
                    {"kind": "effective_model", "value": "gpt-5.6-luna"},
                ]
            )
        ablations = {
            item["worker"]: item
            for item in actor_results
            if item["condition"] == "candidate-projection-ablation"
        }
        actor_results = [
            item
            for item in actor_results
            if item["condition"] != "candidate-projection-ablation"
        ] + [ablations["worker-2"], ablations["worker-1"]]
        mechanisms = [
            {
                "worker": worker,
                "regime": index,
                "changed": True,
                "neutralized_changed": False,
                "contact_errors": 40 if index == 1 else 80,
            }
            for worker in ("worker-1", "worker-2")
            for index in (1, 2, 3)
        ]
        summary = summarize(
            acceptance=acceptance,
            actor_results=actor_results,
            mechanisms=mechanisms,
            inventories=[inventory] * len(actor_results),
            proxy_receipts=proxy_receipts,
            collector_errors=[],
            usage={"input_tokens": 0, "output_tokens": 0},
            elapsed_seconds=1,
            verification={"tests_returncode": 0, "audit_returncode": 0},
            failure_type=None,
            task_order=order,
            catalog_payloads=[
                [{"id": "gpt-5.6-luna"}],
                [{"id": "gpt-5.6-luna"}],
            ],
        )
        self.assertTrue(summary["pilot_pass"])
        self.assertTrue(all(summary["gates"].values()))


if __name__ == "__main__":
    unittest.main()
