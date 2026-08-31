from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0084", ROOT / "experiments/ot_0084_discovered_contact.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0084Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior83 = module.load_prior(ROOT)
        cls.prior82 = cls.prior83.load_prior(ROOT)

    def test_frontier_contract_conforms(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory)
            module.write_environment(environment)
            result = module.contract_conformance(environment)
        self.assertTrue(result["passed"])

    def test_world_fixtures_conform(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior82, Path(directory))
        self.assertTrue(result["passed"])

    def test_discovered_frontier_preserves_selector_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory)
            module.write_environment(environment)
            frontier = module.representative_frontier()
            self.assertTrue(module.valid_frontier(frontier, environment))
        parent = module.load_parent(self.prior83, self.prior82, ROOT, ROOT / ".evidence")
        audit = {"patch_digest": "fixture"}
        binding = module.bind_frontier(self.prior82, parent, frontier, audit, set())
        self.assertEqual(module.active_select(parent, binding, set())["target_path"], "workbench/report.py")
        self.assertEqual(module.erased_select(binding)["target_path"], "workbench/cadence.py")

    def test_parent_position(self):
        parent = module.load_parent(self.prior83, self.prior82, ROOT, ROOT / ".evidence")
        self.assertEqual(parent["artifact_digest"], "8ba78ade10b5f19f56a079c0de195a83c1309506e852ddff76659d284ec83896")
        self.assertEqual(parent["continuation"]["next_opening"], "inspect-and-select-environmental-intervention")


if __name__ == "__main__":
    unittest.main()
