from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0345_actionable_opening_reconstruction.py"
spec = importlib.util.spec_from_file_location("ot0345_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0345Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p82 = module.base.setup(type("Args", (), {"repo": ROOT, "store": ROOT / ".evidence", "evidence_root": None})())[3]

    def test_materialization_anchors(self):
        result = module.anchors(self.p82)
        self.assertEqual(result["pass_count"], result["case_count"])
        self.assertEqual(result["case_count"], 8)

    def test_complete_fixture_materializes(self):
        self.assertTrue(module.can_materialize(module.fixture_subject(self.p82), self.p82))

    def test_id_only_fixture_rejects(self):
        subject = {"continuation": {"status": "open", "next_opening": "Continue through contact-1."}}
        self.assertFalse(module.can_materialize(subject, self.p82))


if __name__ == "__main__":
    unittest.main()
