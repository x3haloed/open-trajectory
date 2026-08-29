import unittest

from open_trajectory_harness import ot0079
from open_trajectory_harness import ot0079_protocol as protocol


CORRECTED = '''def select(candidates, budget):
    chosen = []
    used = set()
    remaining = budget
    while True:
        fitting = [item for item in candidates if item["id"] not in chosen and item["effort"] <= remaining]
        if not fitting:
            break
        ranked = sorted(fitting, key=lambda item: (-len(set(item["signals"]) - used), item["effort"], item["id"]))
        item = ranked[0]
        gain = len(set(item["signals"]) - used)
        if gain == 0:
            break
        chosen.append(item["id"])
        used = used | set(item["signals"])
        remaining = remaining - item["effort"]
    return chosen
'''

FIRST_CHILD = '''def select(candidates, budget):
    ranked = sorted(candidates, key=lambda item: (-item["certainty"], item["effort"], item["id"]))
    chosen = []
    remaining = budget
    for item in ranked:
        if item["effort"] <= remaining and len(chosen) < 2:
            chosen.append(item["id"])
            remaining = remaining - item["effort"]
    return chosen
'''


class OT0079HarnessTests(unittest.TestCase):
    def test_seed_receipts_match_frozen_opportunity(self) -> None:
        receipt = ot0079.evaluate(protocol.SEED_SELECTOR, "a_test")
        self.assertEqual(receipt["selected"], ["bastion", "monitor"])
        self.assertTrue(receipt["security_pass"])
        self.assertFalse(receipt["motion_pass"])

    def test_composition_program_completes_b_siblings(self) -> None:
        for world in ("b_train", "b_test"):
            receipt = ot0079.evaluate(CORRECTED, world)
            self.assertTrue(receipt["completed"])
            self.assertEqual(receipt["total_effort"], 3)

    def test_validator_rejects_external_authority(self) -> None:
        with self.assertRaises(ot0079.SelectorError):
            ot0079.validate_selector("import os\ndef select(candidates, budget):\n return []\n")

    def test_complete_evaluation_realizes_frozen_causal_comparison(self) -> None:
        first = ot0079.complete_evaluation(FIRST_CHILD, CORRECTED)
        second = ot0079.complete_evaluation(FIRST_CHILD, CORRECTED)
        self.assertTrue(first["passed"])
        self.assertEqual(ot0079.canonical_json(first), ot0079.canonical_json(second))
        self.assertTrue(all(first["gates"].values()))

    def test_prompt_contains_no_hidden_required_signals(self) -> None:
        receipt = ot0079.evaluate(protocol.SEED_SELECTOR, "a_train")
        prompt = ot0079.contact_prompt(protocol.SEED_SELECTOR, receipt, second=False)
        self.assertNotIn('"required"', prompt)


if __name__ == "__main__":
    unittest.main()
