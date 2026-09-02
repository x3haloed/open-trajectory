from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0338_exact_comparison_response_reconstruction.py"
spec = importlib.util.spec_from_file_location("ot0338_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0338Tests(unittest.TestCase):
    def test_certificate_helper_depth_is_localized(self):
        self.assertFalse(hasattr(module.base.p35.base, "certify_g11"))
        self.assertTrue(hasattr(module.base.p35.base.base, "certify_g11"))


if __name__ == "__main__":
    unittest.main()
