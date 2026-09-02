from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0335_consequence_before_revision.py"
spec = importlib.util.spec_from_file_location("ot0335_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0335Tests(unittest.TestCase):
    def test_turnover_winners(self):
        history = [
            {"supported": False, "selected_world_id": None},
            {"supported": True, "selected_world_id": "a"},
            {"supported": True, "selected_world_id": "b"},
        ]
        self.assertEqual(module.turnover_winners(history), ["a", "b"])

    def test_revision_requires_authoritative_directional_error(self):
        self.assertFalse(module.revision_evidence([]))
        self.assertFalse(module.revision_evidence([{"outcome_authority": False, "directional_error": True}]))
        self.assertTrue(module.revision_evidence([{"outcome_authority": True, "directional_error": True}]))


if __name__ == "__main__":
    unittest.main()
