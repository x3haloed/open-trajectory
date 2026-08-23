from __future__ import annotations

import unittest

from open_trajectory_harness.ot0003_world import (
    DiscrepancyGatedVersionLedger,
    NearestEvents,
    NoPersistence,
    Observation,
    RULES,
    VerbatimEvents,
    generate_manifest_for_rules,
    generate_task_manifest,
    manifest_batch,
    rule_contact_batch,
    structural_holdout_batch,
    validate_task_manifest,
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
            self.assertLessEqual(substrate.last_project_operations, 256)
            self.assertLessEqual(substrate.last_observe_operations, 256)

    def test_private_task_manifest_binds_distinct_balanced_rules_and_outcomes(self) -> None:
        manifest = generate_task_manifest()
        validate_task_manifest(manifest)
        self.assertNotEqual(manifest["rules"]["regime-a"], manifest["rules"]["regime-b"])
        _, outcomes = manifest_batch(manifest, "regime-b", "structural-1")
        self.assertEqual(len(outcomes), 4)
        changed = generate_manifest_for_rules(
            manifest["rules"]["regime-b"],
            manifest["rules"]["regime-a"],
            manifest["salt"],
        )
        self.assertNotEqual(changed, manifest)


if __name__ == "__main__":
    unittest.main()
