from __future__ import annotations

import unittest
from pathlib import Path

from open_trajectory_harness.ot0065 import (
    actor_surface_authority,
    build_case,
    complete_contact,
    compression_certificate,
    exact_replay_errors,
    evaluate_case,
    machine_errors,
    reference_machine,
    run_calibration,
    stateless_certificate,
    topology_fingerprint,
    validate_machine,
)


class OT0065Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_case(0)

    def test_reference_machines_are_safe_and_exact(self) -> None:
        fingerprints = []
        for regime in self.task["regimes"]:
            machine = reference_machine(regime["target_rule"], regime["cues"])
            validate_machine(machine, regime["cues"])
            self.assertEqual(machine_errors(machine, regime["heldout"], regime["cues"]), 0)
            fingerprints.append(topology_fingerprint(machine, regime["cues"]))
        self.assertEqual(len(set(fingerprints)), 3)

    def test_stateless_and_compression_certificates_pass(self) -> None:
        for regime in self.task["regimes"]:
            receipt = complete_contact(regime["contact"], ["left"] * 15)
            self.assertTrue(stateless_certificate(regime)["pass"])
            certificate = compression_certificate(regime, receipt)
            self.assertTrue(certificate["pass"])
            self.assertEqual(certificate["maximum_allowed_rows"], 1)
            self.assertEqual(certificate["heldout_overlap_count"], 0)
            self.assertTrue(certificate["all_allowed_replay_errors_four"])
            self.assertEqual(exact_replay_errors([], regime["heldout"]), 4)

    def test_case_realizes_topology_correction(self) -> None:
        result = evaluate_case(0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["reference_errors"], [0, 0, 0])
        self.assertEqual(result["frozen_first_errors"][1], 8)
        self.assertGreaterEqual(result["frozen_second_errors"][2], 4)
        self.assertTrue(all(item["topology_changed"] for item in result["regimes"]))
        self.assertTrue(result["fixed_controls"]["pass"])
        for regime in result["regimes"]:
            self.assertTrue(regime["unreachable_preserved"])
            self.assertTrue(regime["overbudget_preserved"])
            self.assertTrue(regime["transition_deletion_preserved_parent"])
            self.assertTrue(regime["cue_edge_deletion_preserved_parent"])

    def test_complete_family_and_surface_pass(self) -> None:
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])
        result = run_calibration(Path.cwd())
        self.assertEqual(result["passing_case_count"], 16)
        self.assertTrue(result["reverse_order_placebo"])
        self.assertEqual(result["disposition"], "promoted")
        self.assertEqual(result["maximum_heldout_overlap"], 0)
        self.assertTrue(result["gates"]["exact_replay"])


if __name__ == "__main__":
    unittest.main()
