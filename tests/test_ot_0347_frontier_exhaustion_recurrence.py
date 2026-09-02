from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0347_frontier_exhaustion_recurrence.py"
spec = importlib.util.spec_from_file_location("ot0347_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0347Tests(unittest.TestCase):
    def test_choice_contract_with_remaining(self):
        self.assertTrue(module.valid_choice({"opening_id": "continue-one", "next_operation": "continue-world-contact", "contact_id": "c2", "rationale": "Continue."}, ["c2"]))
        self.assertFalse(module.valid_choice({"opening_id": "premature-expand", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "Expand."}, ["c2"]))

    def test_choice_contract_at_exhaustion(self):
        self.assertTrue(module.valid_choice({"opening_id": "expand-now", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "The local frontier is exhausted."}, []))
        self.assertFalse(module.valid_choice({"opening_id": "continue-none", "next_operation": "continue-world-contact", "contact_id": "c2", "rationale": "Continue."}, []))

    def test_checker_compiles(self):
        compile(module.CHECK, "check_contact.py", "exec")


if __name__ == "__main__":
    unittest.main()
