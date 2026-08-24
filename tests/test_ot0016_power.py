from __future__ import annotations

import unittest

from open_trajectory_harness.ot0005_world import generate_task_manifest
from open_trajectory_harness.ot0016_power import (
    CONSTRAINED_SAMPLES,
    CONDITIONS,
    SAMPLES,
    analyze_manifest,
    constrained_manifest_gates,
    summarize,
    summarize_constrained,
)


class OT0016PowerTests(unittest.TestCase):
    def test_analysis_is_deterministic_for_one_sealed_manifest(self) -> None:
        manifest = generate_task_manifest()
        first = analyze_manifest(manifest)
        second = analyze_manifest(manifest)
        self.assertEqual(first, second)
        self.assertEqual(set(first["fixed_totals"]), set(CONDITIONS))
        self.assertEqual(len(first["stages"]), 6)

    def test_dynamic_oracle_cannot_be_worse_than_best_static(self) -> None:
        analysis = analyze_manifest(generate_task_manifest())
        self.assertGreaterEqual(analysis["dynamic_advantage"], 0)
        self.assertGreaterEqual(analysis["contact_choice_regret"], 0)

    def test_small_development_sample_cannot_pass_frozen_sample_gate(self) -> None:
        analyses = [analyze_manifest(generate_task_manifest()) for _ in range(2)]
        summary = summarize(analyses)
        self.assertEqual(summary["sample_count"], 2)
        self.assertFalse(summary["gates"]["sample_count"])
        self.assertFalse(summary["viable"])
        self.assertEqual(SAMPLES, 256)

    def test_constrained_manifest_gate_requires_all_causal_pressures(self) -> None:
        analysis = {
            "dynamic_advantage": 4,
            "contact_choice_regret": 2,
            "harm_and_contact_recovery_transitions": 1,
            "best_static_total": 10,
            "contact_selected_total": 8,
        }
        self.assertTrue(all(constrained_manifest_gates(analysis).values()))
        analysis["dynamic_advantage"] = 3
        self.assertFalse(constrained_manifest_gates(analysis)["dynamic_advantage"])

    def test_small_constrained_study_cannot_pass_sample_gate(self) -> None:
        analysis = {
            "task_manifest_sha256": "a" * 64,
            "dynamic_advantage": 4,
            "contact_choice_regret": 1,
            "harm_and_contact_recovery_transitions": 1,
            "best_static_total": 10,
            "contact_selected_total": 7,
        }
        receipt = {
            "attempts": 2,
            "analysis": analysis,
            "gates": constrained_manifest_gates(analysis),
            "rejected": [{}],
        }
        summary = summarize_constrained([receipt])
        self.assertFalse(summary["gates"]["sample_count"])
        self.assertEqual(CONSTRAINED_SAMPLES, 64)


if __name__ == "__main__":
    unittest.main()
