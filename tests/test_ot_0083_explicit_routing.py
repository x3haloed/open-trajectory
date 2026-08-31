from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0083", ROOT / "experiments/ot_0083_explicit_routing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0083Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = module.load_prior(ROOT)

    def test_actor_facing_contract_conforms(self):
        result = module.contract_conformance(self.prior)
        self.assertTrue(result["passed"])

    def test_parent_position(self):
        subject = module.load_parent(self.prior, ROOT, ROOT / ".evidence")
        self.assertEqual(subject["artifact_digest"], "1c04f340012e69dbd7a3783ab85d2d0e37667d5beb552f879b2ac20ab5dd7b73")
        self.assertEqual(subject["continuation"]["next_opening"], "inspect-and-select-environmental-intervention")

    def test_representative_route_preserves_selector_difference(self):
        subject = module.load_parent(self.prior, ROOT, ROOT / ".evidence")
        route = module.representative_route(self.prior)
        self.assertEqual(self.prior.active_select(subject, route, set()), "surface-42")
        self.assertEqual(self.prior.erased_select(route), "surface-17")


if __name__ == "__main__":
    unittest.main()
