from __future__ import annotations

import unittest

from open_trajectory_harness.ot0019_regime import summarize_full_suffix


class OT0019RegimeTests(unittest.TestCase):
    def receipts(self) -> list[dict]:
        return [
            {
                "success": True,
                "evaluations": 10,
                "semantic_fingerprint": f"semantic-{index}",
                "rule_profile": f"rule-{index}",
                "excluded_semantic_collision": False,
                "excluded_rule_collision": False,
                "split_queries_separated": True,
                "schema_valid": True,
                "planned_witness": {"passes": True},
                "calibration_analysis": {
                    "base_exact_witness": True,
                    "placebos": {
                        name: {
                            "schema_valid": True,
                            "error_grid_invariant": True,
                            "witness_invariant": True,
                        }
                        for name in ("event_identity", "query_order")
                    },
                    "replicated_ablations": {
                        name: {"schema_valid": True, "exact_witness": False}
                        for name in (
                            "stage_2_pre_harm",
                            "stage_4_harm_correction",
                        )
                    },
                    "canary_deletion": {
                        "schema_valid": True,
                        "route_complete": True,
                        "planned_path_passes": False,
                        "exact_witness": False,
                    },
                    "canary_rescue": {
                        "schema_valid": True,
                        "error_grid_invariant": True,
                        "witness_invariant": True,
                    },
                },
            }
            for index in range(64)
        ]

    def test_complete_full_suffix_calibration_promotes_e4(self) -> None:
        result = summarize_full_suffix(self.receipts(), exclusion_artifact_count=3)
        self.assertTrue(result["promote_e4"])
        self.assertTrue(all(result["gates"].values()))
        self.assertIn("full_suffix_exact_witness_removed", result["gates"])
        self.assertNotIn("canary_exact_witness_removed", result["gates"])

    def test_surviving_suffix_witness_rejects_calibration(self) -> None:
        receipts = self.receipts()
        receipts[0]["calibration_analysis"]["canary_deletion"]["exact_witness"] = True
        result = summarize_full_suffix(receipts, exclusion_artifact_count=3)
        self.assertFalse(result["promote_e4"])
        self.assertFalse(result["gates"]["full_suffix_exact_witness_removed"])

    def test_missing_prior_exclusion_rejects_calibration(self) -> None:
        result = summarize_full_suffix(self.receipts(), exclusion_artifact_count=2)
        self.assertFalse(result["promote_e4"])
        self.assertFalse(result["gates"]["exclusion_artifact_count"])


if __name__ == "__main__":
    unittest.main()
