from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from open_trajectory_harness.ot0036_e6_calibration import criteria, rule_pairs
from open_trajectory_harness.ot0038_e7_ot2_calibration import build_task, oracle_contract
from open_trajectory_harness.ot0043 import (
    safe_identifier,
    score_contract_e9,
    sentinel_projections,
    unsupported_keywords,
)


class OT0043Tests(unittest.TestCase):
    def test_safe_identity_is_format_neutral_but_bounded(self) -> None:
        task = build_task(0, criteria()[0], 0, rule_pairs()[0])
        packet = task["raw_packet"]
        for value in (
            "g:alpha",
            "goal-longer_identifier.27",
            "A-123",
            "identity.0123456789abcdef0123456789abcdef0123456789abcdef0",
        ):
            self.assertTrue(safe_identifier(value, packet))
        for value in ("", "x" * 65, "bad\nvalue", "/path", "a@b.invalid", "../x", task["assets"][0]["asset_id"]):
            self.assertFalse(safe_identifier(value, packet))

    def test_e9_changes_only_identifier_gate(self) -> None:
        task = build_task(127, criteria()[127], 2, rule_pairs()[2])
        contract = oracle_contract(task)
        contract["goal_id"] = "goal:nonhex-identity"
        result = score_contract_e9(task, contract, "actor-output")
        self.assertTrue(result["ot2_admissible"])
        self.assertTrue(all(result["checks"].values()))

    def test_pursuit_schema_forbids_contract_reauthoring(self) -> None:
        schema = json.loads(Path("fixtures/ot-0043/pursuit-output.schema.json").read_text())
        self.assertEqual(unsupported_keywords(schema), set())
        for item in sentinel_projections():
            jsonschema.validate(item["expected"], schema)
            self.assertIsNone(item["expected"]["goal_contract"])


if __name__ == "__main__":
    unittest.main()
