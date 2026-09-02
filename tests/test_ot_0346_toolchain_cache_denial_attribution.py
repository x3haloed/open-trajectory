from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0346_toolchain_cache_denial_attribution.py"
spec = importlib.util.spec_from_file_location("ot0346_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0346Tests(unittest.TestCase):
    def test_heldout_anchors(self):
        result = module.anchors()
        self.assertEqual(result["pass_count"], result["case_count"])
        self.assertEqual(result["case_count"], 12)

    def test_cache_shape_is_narrow(self):
        self.assertIsNotNone(module.CACHE_DENIAL.fullmatch("git: error: couldn't create cache file '/var/folders/aa/bb/T/xcrun_db-Ab12' (errno=Operation not permitted)"))
        self.assertIsNone(module.CACHE_DENIAL.fullmatch("git: error: couldn't create cache file '/tmp/xcrun_db-Ab12' (errno=Operation not permitted)"))

    def test_clean_g11_case_remains_accepted(self):
        self.assertTrue(module.g13(module.g11.row()))


if __name__ == "__main__":
    unittest.main()
