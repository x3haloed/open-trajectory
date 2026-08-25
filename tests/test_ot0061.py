from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0061 import (
    OLD_SCHEMA_PATH,
    REPAIRED_SCHEMA_PATH,
    interpreter_boundary_receipt,
    run_calibration,
    schema_repair_receipt,
    schema_validation_receipt,
    sequencing_receipt,
    start_after_schema_preflight,
)


class OT0061Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = load_json(OLD_SCHEMA_PATH)
        self.repaired = load_json(REPAIRED_SCHEMA_PATH)

    def test_schema_repair_is_exact_and_retains_shape(self) -> None:
        self.assertTrue(schema_repair_receipt(self.old, self.repaired)["pass"])
        self.assertTrue(schema_validation_receipt(self.repaired)["pass"])

    def test_interpreter_still_owns_exact_byte_limit(self) -> None:
        receipt = interpreter_boundary_receipt()
        self.assertTrue(receipt["pass"])
        self.assertEqual(receipt["safe_source_bytes"], 256)
        self.assertEqual(receipt["oversized_source_bytes"], 257)

    def test_invalid_schema_fails_before_start(self) -> None:
        calls = 0

        def start() -> None:
            nonlocal calls
            calls += 1

        with self.assertRaises(ValueError):
            start_after_schema_preflight(self.old, start)
        self.assertEqual(calls, 0)
        self.assertTrue(sequencing_receipt(self.old, self.repaired)["pass"])

    def test_complete_candidate_free_repair_passes(self) -> None:
        result = run_calibration(Path.cwd())
        self.assertEqual(result["disposition"], "promoted")
        self.assertEqual(result["carrier_regression"]["passing_case_count"], 32)
        self.assertEqual(result["candidate_outputs"], False)
        self.assertEqual(result["hosted_model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
