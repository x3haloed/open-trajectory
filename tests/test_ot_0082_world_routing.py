from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0082", ROOT / "experiments/ot_0082_world_routing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0082Tests(unittest.TestCase):
    def test_fixture_conformance(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(Path(directory))
        self.assertTrue(result["passed"])
        self.assertEqual([row["surface_id"] for row in result["rows"]], list(module.SURFACE_ORDER))

    def test_selector_and_ablation(self):
        subject = module.load_parent(ROOT, ROOT / ".evidence")
        route = {"assessments": [
            self.assessment("surface-17", chord=1, held=True),
            self.assessment("surface-42", chord=4, lumen=4),
            self.assessment("surface-68", chord=2, lumen=3),
        ], "next_pursuit": "implement the selected surface"}
        self.assertTrue(module.valid_route(route))
        self.assertEqual(module.active_select(subject, route, set()), "surface-42")
        self.assertEqual(module.erased_select(route), "surface-17")

    def test_parent_position(self):
        subject = module.load_parent(ROOT, ROOT / ".evidence")
        self.assertEqual(subject["artifact_digest"], "c55166a1805e3ef96f059832d7199f39e53a778bad301a600d2df1c8927ec128")
        self.assertEqual(subject["challenge_machinery"][-1]["version"], 3)
        self.assertEqual(subject["executable_capabilities"][-1]["version"], 5)

    @staticmethod
    def assessment(surface_id, chord, held=False, lumen=2):
        return {"surface_id": surface_id, "axis_chord": chord, "reversibility": 4,
                "immediate_gain": 3, "axis_lumen": lumen, "collision": False,
                "held_repeat": held, "irreversible_closure": False,
                "world_invalid": False, "rationale": "bounded assessment",
                "implementation_opening": "implement and test"}


if __name__ == "__main__":
    unittest.main()
