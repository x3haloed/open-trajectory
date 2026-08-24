from __future__ import annotations

import json
import unittest
from pathlib import Path

from open_trajectory_harness.ot0020_live import fixed_input_paths


REPO = Path(__file__).resolve().parents[1]


class OT0020ProtocolTests(unittest.TestCase):
    def test_acceptance_preserves_e4_and_recursive_gates(self) -> None:
        acceptance = json.loads(
            (REPO / "spec" / "ot-0020-acceptance.json").read_text(encoding="utf-8")
        )
        self.assertEqual(acceptance["experiment_id"], "OT-0020")
        self.assertEqual(acceptance["evaluation_epoch"], "E4")
        self.assertTrue(acceptance["world"]["exact_opportunity_witness_required"])
        scoring = acceptance["scoring"]
        self.assertEqual(scoring["useful_pre_harm_commits_required"], 2)
        self.assertEqual(scoring["correction_error_recovery_required"], 3)
        self.assertEqual(scoring["post_correction_canary_advantage_required"], 2)
        self.assertEqual(acceptance["candidate"]["seed_selector_expression"], "[]")
        self.assertEqual(
            acceptance["candidate"]["seed_decision_expression"], '"current"'
        )

    def test_live_authority_set_binds_e4_inputs_and_shared_core(self) -> None:
        paths = set(fixed_input_paths().values())
        self.assertIn(Path("src/open_trajectory_harness/ot0020_world.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0020_live.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0017_regime.py"), paths)
        self.assertIn(Path("src/open_trajectory_harness/ot0016_live.py"), paths)
        self.assertIn(
            Path(
                "evidence/manifests/OT-0019/ot-0019-full-suffix-e4-calibration-001.json"
            ),
            paths,
        )

    def test_unchanged_actor_text_contains_no_evaluator_modes(self) -> None:
        actor_facing = "\n".join(
            (REPO / "fixtures" / "ot-0016" / name).read_text(encoding="utf-8").lower()
            for name in ("selector-seed.txt", "challenger-prompt.txt")
        )
        for forbidden in (
            "exact witness",
            "construction path",
            "nearest",
            "first-seen",
            "most-recent",
            "stage 4",
            "stage 5",
        ):
            self.assertNotIn(forbidden, actor_facing)


if __name__ == "__main__":
    unittest.main()
