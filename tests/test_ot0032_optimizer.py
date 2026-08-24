from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from open_trajectory_harness.ot0003 import write_sealed_json
from open_trajectory_harness.ot0032_optimizer import (
    _initial_snapshot,
    _project,
    _restore,
    build_split,
    fixed_input_paths,
    optimize,
    record_sealed_result,
    run_protocol,
    score_snapshot,
)


class OT0032OptimizerTests(unittest.TestCase):
    def test_complete_walking_skeleton_passes_frozen_gates(self) -> None:
        result = run_protocol()
        self.assertTrue(result["pilot_pass"])
        self.assertEqual(result["initial"]["score"]["errors"], 8)
        self.assertEqual(
            result["learned"]["snapshot"]["patterns"], [0, 1, 2, 3, 4, 8]
        )
        self.assertEqual(result["contradiction"]["errors"], 16)
        self.assertEqual(
            result["corrected"]["snapshot"]["patterns"], [5, 6, 7, 9, 10, 12]
        )
        self.assertEqual(result["candidate_aggregate_errors"], 0)
        self.assertEqual(result["best_fixed_aggregate_errors"], 8)

    def test_optimizer_scores_every_candidate_and_changes_state(self) -> None:
        initial = _initial_snapshot()
        learned, receipt = optimize(initial, build_split("completed"))
        self.assertEqual(receipt["candidate_count"], 8008)
        self.assertEqual(receipt["current_errors"], 8)
        self.assertEqual(receipt["best_errors"], 0)
        self.assertNotEqual(learned.sha256, initial.sha256)

    def test_restored_snapshot_is_the_only_causal_projection(self) -> None:
        initial = _initial_snapshot()
        learned, _ = optimize(initial, build_split("completed"))
        restored = _restore(_project(learned))
        self.assertEqual(restored, learned)
        self.assertEqual(
            score_snapshot(restored, build_split("canary"))["errors"], 0
        )

    def test_tampered_projection_is_rejected(self) -> None:
        projection = _project(_initial_snapshot())
        projection["patterns"][-1] = 15
        with self.assertRaisesRegex(ValueError, "identity differs"):
            _restore(projection)

    def test_run_lock_covers_optimizer_authorities(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(
            Path("src/open_trajectory_harness/ot0032_optimizer.py"), paths
        )
        self.assertIn(Path("experiments/ot_0032_harness.py"), paths)
        self.assertIn(Path("spec/ot-0032-acceptance.json"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0031/"
                "ot-0031-propose-score-revise-pilot-001.json"
            ),
            paths,
        )

    def test_sealed_result_is_readable_only_during_recording(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            write_sealed_json(output, {"pilot_pass": True})
            observed = {}

            def fake_record_artifact(**kwargs):
                observed["bytes"] = kwargs["input_path"].read_bytes()
                return Path(directory) / "manifest.json"

            with patch(
                "open_trajectory_harness.ot0032_optimizer.record_artifact",
                side_effect=fake_record_artifact,
            ):
                record_sealed_result(Path(directory), output, "test-result")
            self.assertIn(b"pilot_pass", observed["bytes"])
            self.assertEqual(output.stat().st_mode & 0o777, 0)


if __name__ == "__main__":
    unittest.main()
