from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0331_g11_resumptive_continuation.py"
spec = importlib.util.spec_from_file_location("ot0331_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0331Tests(unittest.TestCase):
    def test_g11_source_and_frozen_anchors(self):
        self.assertEqual(module.g11.evaluate(module.g11.g11)["pass_count"], 15)
        self.assertEqual(module.MAX_OPERATIONS, 7)
        self.assertEqual(module.MAX_ACTORS, 3)


if __name__ == "__main__":
    unittest.main()
