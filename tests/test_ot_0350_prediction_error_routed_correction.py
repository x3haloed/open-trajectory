from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0350_prediction_error_routed_correction.py"
spec = importlib.util.spec_from_file_location("ot0350_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0350Tests(unittest.TestCase):
    def test_driver_routes_only_valid_prediction_error(self):
        error = {
            "status": "unresolved",
            "next_operation": "resolve-selection-prediction-error",
            "violation": True,
            "source_subject_digest": module.PARENT_DIGEST,
            "source_policy_binding_digest": "p",
            "source_consequence_receipt_digest": "c",
        }
        subject = {
            "active_selection_prediction_error": error,
            "active_world_consequence_policy": {"binding_digest": "p"},
            "delayed_continuation_consequences": [{"source_receipt_digest": "c"}],
        }
        self.assertEqual(module.next_operation(subject, None), "resolve-selection-prediction-error")
        self.assertIsNone(module.next_operation({**subject, "active_selection_prediction_error": {**error, "violation": False}}, None))

    def test_driver_reuses_policy_without_error(self):
        subject = {
            "active_selection_architecture": {"next_operation": "test-world-consequence-policy-reuse"},
            "continuation": {"next_opening": "Test on a fresh consequence catalog."},
        }
        self.assertEqual(module.next_operation(subject, None), "test-world-consequence-policy-reuse")


if __name__ == "__main__":
    unittest.main()
