from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0334_scoped_provider_collision_recovery.py"
spec = importlib.util.spec_from_file_location("ot0334_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0334Tests(unittest.TestCase):
    def test_frozen_continuation_bounds(self):
        self.assertEqual(module.RETAINED_PROVIDER_COUNT, 1)
        self.assertEqual(module.MAX_NEW_PROVIDERS, 2)
        self.assertEqual(module.MINIMUM_ELIGIBLE_SURFACES, 2)


if __name__ == "__main__":
    unittest.main()
