from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from open_trajectory_harness.ot0048 import neutralize_receipt
from open_trajectory_harness.ot0049 import actor_surface_authority, fixed_input_paths
from open_trajectory_harness.ot0049_world import (
    build_task,
    commit_proposal,
    completed_contact_for_snapshot,
    counterbalanced_split,
    expected_task_seed,
    expression_value,
    initial_snapshot,
    project_snapshot,
    restore_snapshot,
    validate_counterbalance_config,
    validate_task,
)


class OT0049Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("7" * 40))

    def test_task_is_mechanical_and_old_carrier_parent_is_exact(self) -> None:
        validate_task(self.task)
        parent = initial_snapshot()
        self.assertEqual(restore_snapshot(project_snapshot(parent)), parent)
        self.assertLessEqual(
            len(json.dumps(project_snapshot(parent), separators=(",", ":")).encode()),
            512,
        )

    def test_generic_expression_is_bounded_and_deterministic(self) -> None:
        source = "x[0] * x[1] + x[2]"
        self.assertEqual(expression_value(source, [2, -3, 5, 7]), -1)
        with self.assertRaises(ValueError):
            expression_value("__import__('os')", [1, 1, 1, 1])
        with self.assertRaises(ValueError):
            expression_value("x[4]", [1, 1, 1, 1])

    def test_credit_controls_commit_and_parent_identity(self) -> None:
        parent = initial_snapshot()
        contact = counterbalanced_split(self.task["regimes"][0]["contact"], "worker-1")
        _, receipt = completed_contact_for_snapshot(parent, contact)
        output = {"state": "x[0] + x[1]"}
        child = commit_proposal(parent, receipt, output)
        self.assertEqual(child.parent_sha256, parent.sha256)
        self.assertNotEqual(child.sha256, parent.sha256)
        self.assertEqual(
            commit_proposal(parent, neutralize_receipt(receipt), output), parent
        )
        self.assertEqual(restore_snapshot(project_snapshot(child)), child)

    def test_worker_counterbalance_preserves_world_authority(self) -> None:
        validate_counterbalance_config(
            json.loads(Path("fixtures/ot-0049/counterbalance.json").read_text())
        )
        split = self.task["regimes"][0]["contact"]
        first = counterbalanced_split(split, "worker-1")
        second = counterbalanced_split(split, "worker-2")
        self.assertEqual(
            {pair["preferred_event_id"] for pair in first["pairs"]},
            {pair["preferred_event_id"] for pair in second["pairs"]},
        )
        self.assertNotEqual(
            [pair["pattern_id"] for pair in first["pairs"]],
            [pair["pattern_id"] for pair in second["pairs"]],
        )

    def test_actor_surface_has_no_witness_or_mode_menu(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])
        schema = json.loads(
            Path("fixtures/ot-0049/candidate-output.schema.json").read_text()
        )
        jsonschema.validate({"state": "x[0] - x[1]"}, schema)
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0048.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
