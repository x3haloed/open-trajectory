from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from open_trajectory_harness import ot0069
from open_trajectory_harness.ot0002 import canonical_json, load_json
from open_trajectory_harness.ot0061 import require_hosted_schema
from open_trajectory_harness.ot0069 import (
    actor_surface_authority,
    build_task,
    execute_worker,
    expected_task_seed,
    partition_novelty,
    reference_partition,
    require_task_derivation_identity,
    structural_calibration,
    validate_task,
    worker_contact,
)


class OT0069Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("9" * 40))

    def test_private_task_and_actor_surface_are_mechanical(self) -> None:
        validate_task(self.task)
        structural = structural_calibration(self.task)
        self.assertTrue(structural["pass"])
        self.assertEqual(structural["reference_errors"], [0, 0, 0])
        self.assertEqual(structural["frozen_first_errors"], [0, 8, 4])
        self.assertEqual(structural["frozen_second_errors"], [3, 0, 8])
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])

    def test_serialized_private_task_revalidates_structurally(self) -> None:
        restored = json.loads(canonical_json(self.task))
        validate_task(restored)
        self.assertTrue(structural_calibration(restored)["pass"])

    def test_partition_schema_is_supported(self) -> None:
        schema = load_json(Path("fixtures/ot-0069/actor-output.schema.json"))
        self.assertTrue(require_hosted_schema(schema)["pass"])

    def test_preflight_precedes_workspace_and_backend(self) -> None:
        source = inspect.getsource(ot0069.run)
        self.assertLess(
            source.index("require_hosted_schema"), source.index("workspace.mkdir")
        )
        self.assertLess(
            source.index("workspace.mkdir"), source.index("SanitizedResponsesProxy")
        )

    def test_task_derivation_requires_exact_clean_head(self) -> None:
        commit = "a" * 40

        def clean_head(repo, *args):
            return "" if args[0] == "status" else commit

        with patch.object(ot0069, "git_output", side_effect=clean_head):
            require_task_derivation_identity(Path.cwd(), commit)
            with self.assertRaises(RuntimeError):
                require_task_derivation_identity(Path.cwd(), "b" * 40)

    def test_worker_counterbalance_changes_order_only(self) -> None:
        contact = self.task["world"]["regimes"][0]["contact"]
        first = worker_contact(contact, "worker-1")
        second = worker_contact(contact, "worker-2")
        self.assertNotEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(
            {item["bundle_id"] for item in first["bundles"]},
            {item["bundle_id"] for item in second["bundles"]},
        )

    def test_hidden_reference_synthetic_worker_realizes_frozen_gates(self) -> None:
        calls = iter(self.task["world"]["regimes"])

        def fake_turn(**kwargs):
            regime = next(calls)
            partition = reference_partition(regime)
            return ({"parse_error": None}, partition, [])

        with patch.object(ot0069, "run_actor_turn", side_effect=fake_turn):
            _, result, _ = execute_worker(
                repo=Path.cwd(),
                task=self.task,
                worker="worker-1",
                client=object(),
                proxy=object(),
                model="synthetic",
                workspace_root=Path("unused"),
                prompt_template="unused",
                orientation="unused",
                schema={},
            )
        self.assertTrue(result["pass"])
        self.assertEqual(result["candidate_errors"], [0, 0, 0])
        self.assertEqual(result["pre_update_errors"], [4, 8, 8])
        self.assertTrue(all(item["novelty"]["pass"] for item in result["regimes"]))
        self.assertTrue(all(item["membership_changed"] for item in result["regimes"]))

    def test_reference_partition_is_not_in_actor_surface(self) -> None:
        regime = self.task["world"]["regimes"][0]
        partition = reference_partition(regime)
        novelty = partition_novelty(
            Path.cwd(), partition, ot0069.initial_snapshot(), regime["symbols"]
        )
        self.assertTrue(novelty["pass"])


if __name__ == "__main__":
    unittest.main()
