from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0336_consequence_before_revision_recovery.py"
spec = importlib.util.spec_from_file_location("ot0336_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0336Tests(unittest.TestCase):
    def test_response_schema_uses_scalar_item_const(self):
        schema = module.json.loads(module.SCHEMA.read_text())
        files = schema["properties"]["files_changed"]
        self.assertEqual(files["items"]["const"], "decision.json")
        self.assertEqual((files["minItems"], files["maxItems"]), (1, 1))
        self.assertNotIn("const", files)


if __name__ == "__main__":
    unittest.main()
