from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0342_selector_scope_schema_recovery.py"
spec = importlib.util.spec_from_file_location("ot0342_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0342Tests(unittest.TestCase):
    def test_schema_delta_is_one_keyword(self):
        delta = module.schema_delta()
        self.assertTrue(delta["removed_value"])
        self.assertTrue(delta["otherwise_exact"])
        self.assertNotIn("uniqueItems", json.dumps(delta["new_schema"]))

    def test_recovery_uses_new_schema(self):
        self.assertEqual(module.base.SCHEMA, module.SCHEMA)


if __name__ == "__main__":
    unittest.main()
