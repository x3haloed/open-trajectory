from __future__ import annotations

import unittest

from open_trajectory_harness.ot0005_failure import reconstruct_failure


class OT0005FailureTests(unittest.TestCase):
    def test_reconstruction_returns_only_frozen_public_summary(self) -> None:
        summary = {"disposition": "rejected", "decisive_falsifier": "carrier"}
        raw = {
            "schema_version": 1,
            "experiment_id": "OT-0005",
            "run_id": "ot-0005-hosted-epoch-001",
            "public_summary": summary,
            "private": {"expression": "not published"},
        }
        self.assertEqual(reconstruct_failure(raw), summary)

    def test_reconstruction_rejects_wrong_identity(self) -> None:
        with self.assertRaises(ValueError):
            reconstruct_failure(
                {
                    "schema_version": 1,
                    "experiment_id": "OT-0004",
                    "run_id": "ot-0005-hosted-epoch-001",
                    "public_summary": {},
                }
            )


if __name__ == "__main__":
    unittest.main()
