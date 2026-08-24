from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from open_trajectory_harness.ot0040 import (
    CANARY_OUTPUT,
    fixed_input_paths,
    safe_latest_inventory,
    turn_error_message,
    unsupported_keywords,
)


class OT0040Tests(unittest.TestCase):
    def test_revised_schema_uses_only_frozen_hosted_subset(self) -> None:
        schema = json.loads(
            Path("fixtures/ot-0040/candidate-output.schema.json").read_text()
        )
        self.assertEqual(unsupported_keywords(schema), set())
        jsonschema.validate(CANARY_OUTPUT, schema)

    def test_frozen_negative_schema_retains_known_unsupported_keyword(self) -> None:
        schema = json.loads(
            Path("fixtures/ot-0039/actor-output.schema.json").read_text()
        )
        self.assertIn("uniqueItems", unsupported_keywords(schema))
        jsonschema.validate(CANARY_OUTPUT, schema)

    def test_failed_turn_inventory_is_explicitly_absent(self) -> None:
        self.assertIsNone(safe_latest_inventory([], 0))
        inventory = [{"name": "tool"}]
        self.assertEqual(safe_latest_inventory([inventory], 0), inventory)

    def test_failed_turn_diagnostic_is_preserved(self) -> None:
        turn = {
            "status": "failed",
            "error": {
                "message": "invalid_json_schema: uniqueItems is not permitted"
            },
        }
        message = turn_error_message(turn, None)
        self.assertIn("invalid_json_schema", message)
        self.assertIn("uniqueItems", message)

    def test_run_lock_will_bind_both_schemas_and_predecessors(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("fixtures/ot-0040/candidate-output.schema.json"), paths)
        self.assertIn(Path("fixtures/ot-0039/actor-output.schema.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0039/"
                "ot-0039-e7-self-authored-goal-candidate-001.json"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
