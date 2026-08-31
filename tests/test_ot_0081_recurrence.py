from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0081", ROOT / "experiments/ot_0081_recurrence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OT0081Tests(unittest.TestCase):
    def test_metadata_envelope(self):
        valid = {"challenge_id": "x", "rationale": "r", "if_contradicted_opens": "o", "notes": ["bounded"]}
        self.assertTrue(module.valid_metadata(valid))
        self.assertFalse(module.valid_metadata({"challenge_id": "x"}))
        self.assertFalse(module.valid_metadata({**valid, "deep": [[[[["too deep"]]]]]}))

    def test_subject_digest_and_versions(self):
        store = ROOT / ".evidence"
        subject = module.load_subject(ROOT, store)
        self.assertEqual(module.seal(subject)["artifact_digest"], subject["artifact_digest"])
        self.assertEqual(subject["challenge_machinery"][-1].get("version"), 2)
        self.assertEqual(subject["executable_capabilities"][-1]["version"], 4)
        self.assertEqual(subject["continuation"]["next_opening"], "execute-subject-owned-challenge-machinery")

    def test_frozen_case_counts(self):
        self.assertEqual(3 + 4 + len(module.OLD_CASES) + len(module.CURRENT_CASES), 19)
        self.assertEqual(19 + len(module.REVISION_CASES) + len(module.WITHHELD_CASES), 25)


if __name__ == "__main__":
    unittest.main()
