from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from open_trajectory_harness.ot0038_e7_ot2_calibration import oracle_contract
from open_trajectory_harness.ot0039_world import (
    public_evaluator_task,
    selector_route_lineage,
)
from open_trajectory_harness.ot0040 import unsupported_keywords
from open_trajectory_harness.ot0042 import fixed_input_paths
from open_trajectory_harness.ot0042_world import (
    build_task,
    expected_task_seed,
    validate_task,
)


class OT0042Tests(unittest.TestCase):
    def test_fresh_task_is_mechanical_and_selector_complete(self) -> None:
        task = build_task(expected_task_seed("2" * 40))
        validate_task(task)
        self.assertEqual(task["experiment_id"], "OT-0042")
        lineage = selector_route_lineage(task)
        self.assertTrue(lineage["pass"])
        self.assertEqual(lineage["candidate_route_errors"], [0, 0, 0])
        self.assertEqual(lineage["unchanged_route_errors"], [3, 3, 3])

    def test_oracle_admission_conforms_to_revised_transport_schema(self) -> None:
        task = build_task(expected_task_seed("2" * 40))
        contract = oracle_contract(public_evaluator_task(task))
        output = {
            "goal_contract": contract,
            "goal_id": contract["goal_id"],
            "goal_status": "active",
            "plan_version": 1,
            "experiment_id": "exp-123456789abc",
            "subtask_id": "sub-123456789abc",
            "action": "admit-contract",
            "completion_claim": False,
        }
        schema = json.loads(
            Path("fixtures/ot-0040/candidate-output.schema.json").read_text()
        )
        self.assertEqual(unsupported_keywords(schema), set())
        jsonschema.validate(output, schema)

    def test_run_lock_binds_revised_schema_patched_protocol_and_e8b(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("fixtures/ot-0040/candidate-output.schema.json"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0041.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0041/"
                "ot-0041-e8b-patched-backend-calibration-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
