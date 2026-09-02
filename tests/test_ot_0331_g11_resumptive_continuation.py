from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/ot_0331_g11_resumptive_continuation.py"
spec = importlib.util.spec_from_file_location("ot0331_test_module", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


class OT0331Tests(unittest.TestCase):
    def test_g11_source_and_frozen_anchors(self):
        self.assertEqual(module.g11.evaluate(module.g11.g11)["pass_count"], 15)
        self.assertEqual(module.MAX_OPERATIONS, 7)
        self.assertEqual(module.MAX_ACTORS, 3)

    def test_g11_workspace_annotation_is_separate_from_base_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "label/actor-workspace"
            (workspace / ".git").mkdir(parents=True)
            (root / "actor/seed").mkdir(parents=True)
            base_audit = {"conformant": True, "trace_regime": {"accepted": True}, "denial_classification_v2": {"accepted": True}}
            events = "{}\n"
            stderr = ""
            (root / "label/actor-audit.json").write_text(json.dumps(base_audit))
            (root / "label/events.jsonl").write_text(events)
            (root / "label/stderr.txt").write_text(stderr)
            certificate = {"authority": module.g11.AUTHORITY, "event_trace_sha256": hashlib.sha256(events.encode()).hexdigest(), "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(), "challenger_accepted": True, "recovery_applied": False}
            actor = {"audit": {**base_audit, "g11_attributed_command_audit": certificate}}
            self.assertTrue(module.direct_fresh_workspace(root, actor))
            actor["audit"]["truthful"] = True
            self.assertFalse(module.direct_fresh_workspace(root, actor))


if __name__ == "__main__":
    unittest.main()
