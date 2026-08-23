from __future__ import annotations

import argparse
import json
import sys
import unittest
from io import StringIO
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from open_trajectory_evidence.audit import audit_repository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    suite = unittest.defaultTestLoader.discover(str(REPO / "tests"))
    result = unittest.TextTestRunner(stream=StringIO(), verbosity=0).run(suite)
    audit_errors = audit_repository(REPO)
    receipt = {
        "schema_version": 1,
        "experiment_id": "OT-0001",
        "checks": {
            "unit_tests": {
                "run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "passed": result.wasSuccessful(),
            },
            "repository_audit": {
                "violations": len(audit_errors),
                "passed": not audit_errors,
            },
        },
        "passed": result.wasSuccessful() and not audit_errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
