from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0348_delayed_continuation_policy_correction.py"
spec = importlib.util.spec_from_file_location("ot0348_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0348Tests(unittest.TestCase):
    def test_incumbent_and_reference_separate_delayed_yield(self):
        worlds = module.derive_worlds(hashlib.sha256(b"unit-world").digest(), heldout=False)
        rows = module.public_rows(worlds)
        incumbent = module.choose(module.INCUMBENT_SOURCE, rows)
        corrected = module.choose(module.reference_source(), rows)
        roles = {world["world_id"]: world["role"] for world in worlds}
        self.assertEqual(roles[incumbent], "immediate")
        self.assertEqual(roles[corrected], "continuation")
        self.assertEqual(next(module.continuation_yield(row) for row in rows if row["world_id"] == incumbent), 0)

    def test_reference_is_permutation_invariant(self):
        rows = module.public_rows(module.derive_worlds(hashlib.sha256(b"unit-permutation").digest(), heldout=True))
        self.assertEqual(module.choose(module.reference_source(), rows), module.choose(module.reference_source(), list(reversed(rows))))

    def test_outcome_erasure_removes_delayed_signal(self):
        worlds = module.derive_worlds(hashlib.sha256(b"unit-erasure").digest(), heldout=True)
        self.assertTrue(all(module.continuation_yield(row) == 0 for row in module.public_rows(worlds, erase_outcomes=True)))

    def test_checkers_compile(self):
        compile(module.POLICY_CHECKER, "check_policy.py", "exec")
        compile(module.SELECTION_CHECKER, "check_selection.py", "exec")
        compile(module.CONTACT_CHECKER, "check_contact.py", "exec")

    def test_transport_schema_uses_supported_subset(self):
        schema = json.loads(module.CORRECTION_SCHEMA.read_text())
        self.assertNotIn("uniqueItems", schema["properties"]["files_changed"])
        self.assertFalse(module.correction_output_valid(
            {"action": "revise-continuation-policy", "files_changed": ["policy.py", "policy.py"], "note": "duplicate"},
            "revise",
            True,
        ))


if __name__ == "__main__":
    unittest.main()
