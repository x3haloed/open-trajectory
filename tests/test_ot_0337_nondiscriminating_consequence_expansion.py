from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0337_nondiscriminating_consequence_expansion.py"
spec = importlib.util.spec_from_file_location("ot0337_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0337Tests(unittest.TestCase):
    def test_equal_signatures_do_not_distinguish(self):
        rows = [{"outcome_signature": {"eligible_count": 2, "scores": [2, 2]}}] * 2
        self.assertFalse(module.directionally_distinguishes(rows))

    def test_different_signatures_distinguish(self):
        rows = [
            {"outcome_signature": {"eligible_count": 2, "scores": [2, 2]}},
            {"outcome_signature": {"eligible_count": 3, "scores": [2, 2, 2]}},
        ]
        self.assertTrue(module.directionally_distinguishes(rows))


if __name__ == "__main__":
    unittest.main()
