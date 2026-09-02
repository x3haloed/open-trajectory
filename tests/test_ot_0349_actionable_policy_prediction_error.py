from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0349_actionable_policy_prediction_error.py"
spec = importlib.util.spec_from_file_location("ot0349_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0349Tests(unittest.TestCase):
    def test_prediction_error_compiler_finds_proxy_inversion(self):
        worlds = module.base.derive_worlds(hashlib.sha256(b"prediction-error").digest(), heldout=False)
        rows = module.base.public_rows(worlds)
        incumbent = module.base.choose(module.base.INCUMBENT_SOURCE, rows)
        training = {"worlds": rows, "incumbent_selected_world_id": incumbent, "receipt_digest": "a" * 64}
        parent = {"artifact_digest": "b" * 64, "active_world_consequence_policy": {"binding_digest": "c" * 64, "policy": {"rationale": "Maximize continuation through immediate viable contact count."}}}
        discrepancy = module.compile_prediction_error(parent, training, type("D", (), {"digest": staticmethod(lambda value: "d" * 64)})())
        self.assertTrue(discrepancy["violation"])
        self.assertGreater(discrepancy["selected_observation"]["proxy_value"], discrepancy["admissible_counterexample"]["proxy_value"])
        self.assertLess(discrepancy["selected_observation"]["verified_reopened_contact_count"], discrepancy["admissible_counterexample"]["verified_reopened_contact_count"])

    def test_equivalence_detects_incumbent_vs_reference(self):
        self.assertFalse(module.source_equivalent(module.base.INCUMBENT_SOURCE, module.base.reference_source()))
        self.assertTrue(module.source_equivalent(module.base.INCUMBENT_SOURCE, module.base.INCUMBENT_SOURCE))


if __name__ == "__main__":
    unittest.main()
