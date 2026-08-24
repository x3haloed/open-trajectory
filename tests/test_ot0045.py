from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from open_trajectory_harness.ot0038_e7_ot2_calibration import oracle_contract
from open_trajectory_harness.ot0039_world import expected_hierarchy, public_evaluator_task, selector_route_lineage
from open_trajectory_harness.ot0040 import unsupported_keywords
from open_trajectory_harness.ot0045 import (
    admission_score_e10,
    fixed_input_paths,
    hierarchy_correct,
    valid_admission_hierarchy,
)
from open_trajectory_harness.ot0045_world import build_task, expected_task_seed, validate_task


class OT0045Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("5" * 40))

    def admission_output(self) -> dict[str, object]:
        contract = oracle_contract(public_evaluator_task(self.task))
        contract["goal_id"] = "goal:bounded-nonhex"
        return {"goal_contract": contract, "goal_id": contract["goal_id"], "goal_status": "active", "plan_version": 1, "experiment_id": "experiment:alpha", "subtask_id": "subtask:first", "action": "admit-contract", "completion_claim": False}

    def test_fresh_task_and_selector_path(self) -> None:
        validate_task(self.task)
        self.assertEqual(self.task["experiment_id"], "OT-0045")
        lineage = selector_route_lineage(self.task)
        self.assertTrue(lineage["pass"])
        self.assertEqual(lineage["candidate_route_errors"], [0, 0, 0])
        self.assertEqual(lineage["unchanged_route_errors"], [3, 3, 3])

    def test_format_neutral_admission(self) -> None:
        output = self.admission_output()
        self.assertTrue(admission_score_e10(self.task, output)["ot2_admissible"])
        self.assertTrue(valid_admission_hierarchy(self.task, output))
        schema = json.loads(Path("fixtures/ot-0045/admission-output.schema.json").read_text())
        self.assertEqual(unsupported_keywords(schema), set())
        jsonschema.validate(output, schema)

    def test_pursuit_is_null_and_exact(self) -> None:
        admission = self.admission_output()
        controller = {"contract": admission["goal_contract"], "initial_experiment_id": admission["experiment_id"], "initial_subtask_id": admission["subtask_id"]}
        expected = expected_hierarchy(controller["contract"], controller["initial_experiment_id"], controller["initial_subtask_id"], 3)
        output = {"goal_contract": None, **expected, "action": "action:opaque"}
        jsonschema.validate(output, json.loads(Path("fixtures/ot-0043/pursuit-output.schema.json").read_text()))
        self.assertTrue(hierarchy_correct(self.task, controller, 3, output))
        self.assertFalse(hierarchy_correct(self.task, controller, 3, {**output, "goal_contract": controller["contract"]}))

    def test_inputs_bind_e10_and_split_interface(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("fixtures/ot-0045/admission-prompt.txt"), paths)
        self.assertIn(Path("fixtures/ot-0043/pursuit-prompt.txt"), paths)
        self.assertIn(Path("evidence/manifests/OT-0044/ot-0044-e10-causal-advantage-calibration-001.json"), paths)


if __name__ == "__main__":
    unittest.main()
