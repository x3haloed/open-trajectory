from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0351_corrected_policy_frontier_recurrence.py"
spec = importlib.util.spec_from_file_location("ot0351_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0351Tests(unittest.TestCase):
    def test_program_requires_frontier_binding(self):
        source = "x"
        old_digest = module.POLICY_SOURCE_DIGEST
        try:
            module.POLICY_SOURCE_DIGEST = module.hashlib.sha256(source.encode()).hexdigest()
            subject = {
                "active_world_contact_frontier": {"policy_binding_digest": "binding"},
                "active_world_consequence_policy_program": {
                    "binding_digest": "binding",
                    "policy_source": source,
                    "policy_source_digest": module.POLICY_SOURCE_DIGEST,
                },
            }
            self.assertTrue(module.valid_program(subject))
            subject["active_world_consequence_policy_program"]["binding_digest"] = "other"
            self.assertFalse(module.valid_program(subject))
        finally:
            module.POLICY_SOURCE_DIGEST = old_digest

    def test_choice_requires_remaining_contact(self):
        choice = {"opening_id": "continue-next", "next_operation": "continue-world-contact", "contact_id": "c2", "rationale": "Continue."}
        self.assertTrue(module.valid_choice(choice, ["c2", "c3"]))
        self.assertFalse(module.valid_choice({**choice, "contact_id": "c4"}, ["c2", "c3"]))
        self.assertFalse(module.valid_choice({**choice, "next_operation": "test-world-consequence-policy-reuse", "contact_id": None}, ["c2"]))

    def test_choice_routes_policy_only_at_exhaustion(self):
        choice = {"opening_id": "reuse-policy", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "Exhausted."}
        self.assertTrue(module.valid_choice(choice, []))
        self.assertFalse(module.valid_choice({**choice, "next_operation": "continue-world-contact", "contact_id": "c1"}, []))

    def test_checker_compiles(self):
        compile(module.CHECK, "check_contact.py", "exec")


if __name__ == "__main__":
    unittest.main()
