from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from open_trajectory_harness.ot0002 import load_json
from open_trajectory_harness.ot0021_pilot import rendered_prompt
from open_trajectory_harness.ot0021_trace import (
    consequence_ledger,
    seed_consequence_entry,
    validate_consequence_ledger,
    validate_public_task,
)


REPO = Path(__file__).resolve().parents[1]


class OT0021TraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = load_json(REPO / "fixtures/ot-0021/pilot-task.json")

    def test_public_task_projects_only_completed_prior_encounter(self) -> None:
        validate_public_task(self.task)
        prompt, ledger = rendered_prompt(REPO, self.task)
        self.assertNotIn("sealed-event-", prompt)
        self.assertNotIn("sealed_pilot_evaluation", prompt)
        self.assertIn("prior-event-", prompt)
        entry = ledger["entries"][0]
        self.assertTrue(entry["completed"])
        self.assertEqual(
            entry["selector_consequences"]["current"]["errors"], 4
        )

    def test_receipt_identity_and_append_only_order_are_enforced(self) -> None:
        ledger = consequence_ledger(
            [seed_consequence_entry(self.task)], max_entries=5, max_bytes=49152
        )
        tampered = deepcopy(ledger)
        tampered["entries"][0]["raw_encounter"]["outcomes"][0] = 1
        with self.assertRaisesRegex(ValueError, "receipt identity"):
            validate_consequence_ledger(tampered)
        reordered = deepcopy(ledger)
        reordered["entries"][0]["source_stage"] = 1
        with self.assertRaisesRegex(ValueError, "append-only"):
            validate_consequence_ledger(reordered)

    def test_ledger_budgets_are_enforced(self) -> None:
        entry = seed_consequence_entry(self.task)
        with self.assertRaisesRegex(ValueError, "entry budget"):
            consequence_ledger([entry], max_entries=0, max_bytes=49152)
        with self.assertRaisesRegex(ValueError, "byte budget"):
            consequence_ledger([entry], max_entries=5, max_bytes=100)


if __name__ == "__main__":
    unittest.main()
