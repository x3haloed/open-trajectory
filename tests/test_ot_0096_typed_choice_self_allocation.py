from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0096", ROOT / "experiments/ot_0096_typed_choice_self_allocation.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0096TypedChoiceTests(unittest.TestCase):
    def setUp(self):
        self.contacts = module.allocation.live_reference_frontier()
        chosen = self.contacts[1]
        self.choice = {"contact_id": chosen["id"], "current_opening_disposition": "retire",
                       "intended_consequence": "enact contact", "observed_saturation": True,
                       "predicted_expansion": chosen["predicted_expansion"], "surrender_condition": "surrender on contradiction"}

    def test_reference_choice_passes(self):
        self.assertTrue(module.valid_typed_choice(self.choice, self.contacts))

    def test_stringified_facts_reject(self):
        self.choice["observed_saturation"] = "true"
        self.assertFalse(module.valid_typed_choice(self.choice, self.contacts))
        self.choice["observed_saturation"] = True; self.choice["predicted_expansion"] = "80.0"
        self.assertFalse(module.valid_typed_choice(self.choice, self.contacts))

    def test_wrong_expansion_rejects(self):
        self.choice["predicted_expansion"] = 81.0
        self.assertFalse(module.valid_typed_choice(self.choice, self.contacts))


if __name__ == "__main__":
    unittest.main()
