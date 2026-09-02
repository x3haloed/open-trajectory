from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0332_counterexample_driven_completion.py"
spec = importlib.util.spec_from_file_location("ot0332_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0332Tests(unittest.TestCase):
    def test_frozen_budgets_and_g11(self):
        self.assertEqual(module.MAX_OPERATIONS, 5)
        self.assertEqual(module.MAX_ACTORS, 3)
        self.assertEqual(module.g11.evaluate(module.g11.g11)["pass_count"], 15)


if __name__ == "__main__":
    unittest.main()
