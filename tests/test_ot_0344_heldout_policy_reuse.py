from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0344_heldout_policy_reuse.py"
spec = importlib.util.spec_from_file_location("ot0344_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0344Tests(unittest.TestCase):
    def test_derivation_is_deterministic_and_opaque(self):
        seed = hashlib.sha256(b"deterministic").digest()
        first = module.derive_worlds(seed)
        self.assertEqual(first, module.derive_worlds(seed))
        self.assertEqual(sorted(len(row["contacts"]) for row in first), [2, 3, 4])
        self.assertTrue(all(row["role"] not in row["world_id"] for row in first))

    def test_public_projection_removes_hidden_cases_and_roles(self):
        rows = module.public_worlds(module.derive_worlds(hashlib.sha256(b"projection").digest()))
        self.assertTrue(all("role" not in row and "hidden_cases" not in str(row) for row in rows))

    def test_descriptor_template_is_distinct_from_expansion(self):
        self.assertEqual(module.ROLE_TEMPLATES["descriptor"]["contact_count"], 2)
        self.assertEqual(module.ROLE_TEMPLATES["expansion"]["contact_count"], 4)
        self.assertNotEqual(module.ROLE_TEMPLATES["descriptor"]["features"], module.ROLE_TEMPLATES["expansion"]["features"])

    def test_seed_size_is_enforced(self):
        with self.assertRaises(ValueError):
            module.derive_worlds(b"short")

    def test_actor_programs_compile(self):
        compile(module.PIPELINE, "continue_pipeline.py", "exec")
        compile(module.CHECK_SELECTION, "check_selection.py", "exec")
        compile(module.CHECK_CONTACT, "check_contact.py", "exec")


if __name__ == "__main__":
    unittest.main()
