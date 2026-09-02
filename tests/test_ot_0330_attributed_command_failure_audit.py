from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0330_attributed_command_failure_audit.py"
spec = importlib.util.spec_from_file_location("ot0330_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0330Tests(unittest.TestCase):
    def test_frozen_anchor_comparison(self):
        self.assertEqual(module.evaluate(module.incumbent)["pass_count"], 14)
        self.assertEqual(module.evaluate(module.g11)["pass_count"], 15)

    def test_recovery_is_narrow(self):
        cases = {case_id: (expected, value) for case_id, expected, value in module.heldout_anchors()}
        self.assertTrue(module.g11(cases["recoverable-local-control-error"][1]))
        for case_id in (
            "missing-successful-recheck",
            "actor-visible-permission-denial",
            "unsafe-failed-command",
            "failed-first-checker",
        ):
            self.assertFalse(module.g11(cases[case_id][1]), case_id)


if __name__ == "__main__":
    unittest.main()
