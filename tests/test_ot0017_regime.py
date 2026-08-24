from __future__ import annotations

import unittest
import random

from open_trajectory_harness.ot0004_world import validate_task_manifest
from open_trajectory_harness.ot0005_world import generate_task_manifest
from open_trajectory_harness.ot0016 import FIXED_CONDITIONS
from open_trajectory_harness.ot0017_regime import (
    CONSTRUCTION_PLAN,
    SCORING,
    _mutate_manifest,
    construction_penalty,
    find_exact_witness,
    summarize,
    summarize_construction,
)


def split(stage: int, condition: str, errors: int) -> dict:
    return {
        "selected_event_ids": [f"{stage}-{condition}-{index}" for index in range(6)],
        "errors": errors,
    }


def witness_tables() -> list[dict]:
    tables = []
    for stage in range(6):
        conditions = {
            condition: {
                "contact": split(stage, condition, 8),
                "heldout": split(stage, condition, 8),
            }
            for condition in FIXED_CONDITIONS
        }
        tables.append({"stage": stage, "conditions": conditions})
    recent, first, nearest, none = FIXED_CONDITIONS
    values = [
        (none, 3, 3),
        (first, 0, 0),
        (first, 3, 4),
        (nearest, 0, 1),
        (nearest, 3, 4),
        (recent, 0, 1),
        (recent, 0, 0),
        (nearest, 0, 0),
        (recent, 4, 4),
        (nearest, 8, 0),
        (none, 0, 0),
        (none, 4, 3),
        (recent, 0, 0),
    ]
    assignments = [
        (0, *values[0]),
        (0, *values[1]),
        (1, *values[2]),
        (1, *values[3]),
        (2, *values[4]),
        (2, *values[5]),
        (3, *values[6]),
        (3, *values[7]),
        (4, *values[8]),
        (4, *values[9]),
        (4, *values[10]),
        (5, *values[11]),
        (5, *values[12]),
    ]
    for stage, condition, contact, heldout in assignments:
        tables[stage]["conditions"][condition] = {
            "contact": split(stage, condition, contact),
            "heldout": split(stage, condition, heldout),
        }
    return tables


class OT0017RegimeTests(unittest.TestCase):
    def test_exact_witness_covers_complete_frozen_chain(self) -> None:
        witness = find_exact_witness(witness_tables())
        self.assertIsNotNone(witness)
        self.assertTrue(witness["passes"])
        self.assertTrue(all(witness["gates"].values()))
        self.assertGreaterEqual(
            len(witness["chains"][0]["useful_pre_harm_stages"]),
            SCORING["useful_pre_harm_commits_required"],
        )
        self.assertEqual(CONSTRUCTION_PLAN[3], CONSTRUCTION_PLAN[2])
        self.assertEqual(construction_penalty(witness_tables()), 0)

    def test_missing_canary_has_no_witness(self) -> None:
        tables = witness_tables()
        for stage in (4, 5):
            for condition in FIXED_CONDITIONS:
                tables[stage]["conditions"][condition]["contact"]["errors"] = 0
                tables[stage]["conditions"][condition]["heldout"]["errors"] = 0
        self.assertIsNone(find_exact_witness(tables))

    def test_lineage_gate_is_part_of_witness(self) -> None:
        scoring = dict(SCORING)
        scoring["committed_lineage_errors_allowed"] = 0
        self.assertIsNone(find_exact_witness(witness_tables(), scoring))

    def test_study_gate_requires_predeclared_sample_count_and_incidence(self) -> None:
        analyses = [{"exact_witness": True, "witness": {"passes": True}}] * 256
        result = summarize(analyses, unique_manifests=256)
        self.assertTrue(result["viable"])
        self.assertEqual(result["observations"]["exact_witness_fraction"], 1.0)

    def test_stage_mutation_preserves_inherited_world_contract(self) -> None:
        mutated = _mutate_manifest(generate_task_manifest(), random.Random(7))
        inherited = dict(mutated)
        inherited["experiment_id"] = "OT-0004"
        validate_task_manifest(inherited)

    def test_construction_failures_are_retained(self) -> None:
        receipts = [
            {
                "success": False,
                "evaluations": 20_000,
                "manifest": None,
                "exact_witness": None,
            }
            for _ in range(16)
        ]
        result = summarize_construction(receipts)
        self.assertFalse(result["viable"])
        self.assertEqual(result["observations"]["completed_witnesses"], 0)
        self.assertTrue(result["gates"]["trial_count"])


if __name__ == "__main__":
    unittest.main()
