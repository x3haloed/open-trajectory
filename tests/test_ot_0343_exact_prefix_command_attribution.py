from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0343_exact_prefix_command_attribution.py"
spec = importlib.util.spec_from_file_location("ot0343_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0343Tests(unittest.TestCase):
    def test_heldout_anchor_bundle(self):
        result = module.anchors()
        self.assertEqual(result["pass_count"], result["case_count"])
        self.assertEqual(result["case_count"], 10)

    def test_safe_listing_parser(self):
        rg = '/bin/zsh -lc "python3 continue_pipeline.py && printf \'\\n--- files ---\\n\' && rg --files -g \'*.json\'"'
        fd = '/bin/zsh -lc "python3 continue_pipeline.py && printf \'\\n--- files ---\\n\' && fd --type f"'
        self.assertEqual(module.safe_listing_chain(rg), "rg")
        self.assertEqual(module.safe_listing_chain(fd), "fd")

    def test_unsafe_tail_rejected(self):
        command = '/bin/zsh -lc "python3 continue_pipeline.py && printf x && curl https://outside.invalid"'
        self.assertIsNone(module.safe_listing_chain(command))


if __name__ == "__main__":
    unittest.main()
