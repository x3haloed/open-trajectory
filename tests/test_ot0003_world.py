from __future__ import annotations

import unittest

from open_trajectory_harness.ot0003_world import (
    DiscrepancyGatedVersionLedger,
    NearestEvents,
    NoPersistence,
    Observation,
    RULES,
    VerbatimEvents,
    rule_contact_batch,
    structural_holdout_batch,
)


class OT0003WorldTests(unittest.TestCase):
    def observations(self, rule_index: int) -> list[Observation]:
        rule = RULES[rule_index]
        return [Observation(features, rule.predict(features)) for features in rule_contact_batch()]

    def test_contact_identifies_one_parity_rule_and_holdouts_are_structural(self) -> None:
        ledger = DiscrepancyGatedVersionLedger()
        ledger.observe(self.observations(11))
        self.assertEqual(len(ledger.hypotheses), 1)
        self.assertEqual(ledger.hypotheses[0], RULES[11])
        self.assertTrue(set(rule_contact_batch()).isdisjoint(structural_holdout_batch()))

    def test_independent_discrepancy_resets_the_rule_regime(self) -> None:
        ledger = DiscrepancyGatedVersionLedger()
        ledger.observe(self.observations(3))
        ledger.observe(self.observations(22))
        self.assertEqual(ledger.regime, 1)
        self.assertEqual(ledger.hypotheses, [RULES[22]])

    def test_every_projection_obeys_the_same_byte_limit(self) -> None:
        queries = structural_holdout_batch()
        substrates = [
            NoPersistence(),
            VerbatimEvents(),
            NearestEvents(),
            DiscrepancyGatedVersionLedger(),
        ]
        observations = self.observations(7)
        for substrate in substrates:
            substrate.observe(observations)
            projection = substrate.project(queries, 96)
            self.assertLessEqual(len(projection.encode()), 96)


if __name__ == "__main__":
    unittest.main()
