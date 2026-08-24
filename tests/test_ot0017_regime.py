from __future__ import annotations

import unittest

from open_trajectory_harness.ot0016 import FIXED_CONDITIONS
from open_trajectory_harness.ot0017_regime import (
    SCORING,
    find_exact_witness,
    summarize,
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
        (recent, 0, 0),
        (recent, 3, 4),
        (first, 0, 1),
        (first, 3, 4),
        (nearest, 0, 1),
        (nearest, 4, 4),
        (first, 2, 0),
        (none, 0, 0),
        (none, 4, 3),
        (first, 0, 0),
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
        (5, *values[9]),
        (5, *values[10]),
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


if __name__ == "__main__":
    unittest.main()
