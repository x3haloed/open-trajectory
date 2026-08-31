from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0085", ROOT / "experiments/ot_0085_explicit_contact_abi.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0085Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = module.load_prior(ROOT)
        cls.prior83 = cls.prior.load_prior(ROOT)
        cls.prior82 = cls.prior83.load_prior(ROOT)

    def test_only_report_docstring_changes(self):
        self.assertTrue(module.source_delta_conforms(self.prior))
        self.assertTrue(module.abi_conformance(self.prior)["passed"])

    def test_contract_and_world_conform(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / "environment"
            module.write_environment(self.prior, environment)
            self.assertTrue(self.prior.contract_conformance(environment)["passed"])
            self.assertTrue(module.fixture_conformance(self.prior, self.prior82, root / "fixtures")["passed"])

    def test_parent_position(self):
        parent = module.load_parent(self.prior, self.prior83, self.prior82, ROOT, ROOT / ".evidence")
        self.assertEqual(parent["artifact_digest"], "8ba78ade10b5f19f56a079c0de195a83c1309506e852ddff76659d284ec83896")
        self.assertEqual(parent["continuation"]["next_opening"], "inspect-and-select-environmental-intervention")


if __name__ == "__main__":
    unittest.main()
