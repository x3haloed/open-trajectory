from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0086", ROOT / "experiments/ot_0086_behavior_discovery.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0086Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = module.load_prior(ROOT)
        cls.prior84 = cls.prior.load_prior(ROOT)
        cls.prior83 = cls.prior84.load_prior(ROOT)
        cls.prior82 = cls.prior83.load_prior(ROOT)

    def test_complete_environment_and_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module.write_environment(root)
            source = "\n".join(module.ENVIRONMENT_FILES.values())
            self.assertNotIn("NotImplementedError", source)
            self.assertTrue(module.target_has_symbol(root))
            self.assertTrue(module.floor_test(root)["passed"])
            self.assertEqual(len(module.observe(root)["rows"]), len(module.PUBLIC_CASES))
            representative = module.representative_frontier()
            self.assertTrue(module.valid_frontier(representative, root, self.prior82))
            duplicate = copy.deepcopy(representative)
            duplicate["candidates"][2]["implementation_opening"] = duplicate["candidates"][1]["implementation_opening"]
            self.assertFalse(module.valid_frontier(duplicate, root, self.prior82))

    def test_reference_crosses_frozen_world_and_ablation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.fixture_conformance(self.prior82, Path(directory))
        self.assertTrue(result["passed"], result)
        hidden = result["reference_receipts"]["hidden"]
        ablated = result["reference_receipts"]["ablated"]
        self.assertGreaterEqual(hidden["gain"], module.MIN_HIDDEN_GAIN)
        self.assertGreaterEqual(hidden["oracle_improvement_fraction"], module.MIN_ORACLE_FRACTION)
        self.assertLess(ablated["gain"], module.MAX_ABLATED_GAIN)

    def test_parent_position(self):
        parent = module.load_parent(self.prior, self.prior82, ROOT, ROOT / ".evidence")
        self.assertEqual(parent["artifact_digest"], module.PARENT_DIGEST)
        self.assertEqual(parent["continuation"]["next_opening"], "inspect-and-select-environmental-intervention")


if __name__ == "__main__":
    unittest.main()
