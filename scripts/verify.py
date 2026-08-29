#!/usr/bin/env python3
"""Run fast active checks or the complete archival reconstruction suite."""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
existing_pythonpath = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = (
    str(SRC)
    if not existing_pythonpath
    else str(SRC) + os.pathsep + existing_pythonpath
)

from open_trajectory_evidence.audit import audit_repository  # noqa: E402


FAST_MODULES = (
    "tests.test_audit",
    "tests.test_evidence",
    "tests.test_trajectory",
    "tests.test_ot0079",
    "tests.test_ot0079_protocol",
)


def suite(mode: str) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    if mode == "archive":
        return loader.discover(str(REPO / "tests"))
    return loader.loadTestsFromNames(FAST_MODULES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("fast", "archive"), default="fast")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=1).run(suite(args.mode))
    if not result.wasSuccessful():
        return 1
    errors = audit_repository(REPO)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"{args.mode} verification and privacy audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
