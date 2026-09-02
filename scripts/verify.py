#!/usr/bin/env python3
"""Run fast active checks or the complete archival reconstruction suite."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
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
from open_trajectory_evidence.evidence import EvidenceError, load_manifest, object_path  # noqa: E402


CHECKOUT_MODULES = (
    "tests.test_audit",
    "tests.test_evidence",
    "tests.test_trajectory",
    "tests.test_ot0079",
    "tests.test_ot0079_protocol",
)

# These tests replay exact exploratory-only artifacts retained outside Git.
# They are valuable on a workstation carrying the complete evidence slice, but
# cannot be a clean-checkout publication gate: their manifests intentionally
# have no public reconstruction recipe.
LOCAL_EVIDENCE_MODULES = (
    "tests.test_ot_0081_recurrence",
    "tests.test_ot_0082_world_routing",
    "tests.test_ot_0083_explicit_routing",
    "tests.test_ot_0084_discovered_contact",
    "tests.test_ot_0085_explicit_contact_abi",
    "tests.test_ot_0086_behavior_discovery",
    "tests.test_ot_0087_actor_opening_handoff",
    "tests.test_ot_0088_unseen_pursuit_selection",
    "tests.test_ot_0089_derived_liveness",
    "tests.test_ot_0090_confirmation_renewal",
    "tests.test_ot_0091_post_consequence_assimilation",
    "tests.test_ot_0092_actor_contact_renewal",
    "tests.test_ot_0093_saturation_self_allocation",
    "tests.test_ot_0094_live_frontier_self_allocation",
    "tests.test_ot_0095_normalized_boundary_self_allocation",
    "tests.test_ot_0096_typed_choice_self_allocation",
    "tests.test_ot_0097_consequence_corrected_allocation",
    "tests.test_ot_0098_iterated_allocation_correction",
    "tests.test_ot_0099_third_consequence_allocation_correction",
    "tests.test_ot_0100_threshold_corrected_allocation",
    "tests.test_ot_0101_derived_retention_promotion",
)
LOCAL_EVIDENCE_EXPERIMENTS = tuple(f"OT-{number:04d}" for number in range(80, 102))

# Last commit in which the retired E14 evaluator lineage and its complete test
# surface were part of the active tree.  Archival verification reconstructs
# this commit instead of forcing historical machinery to remain live forever.
E14_ARCHIVE_COMMIT = "7b443429f8f6fdeb341227c0ef5582fc99d6cdc0"


def local_evidence_inventory(repo: Path) -> tuple[int, tuple[Path, ...]]:
    """Return the number of historical manifests and locally missing objects."""
    store = repo / ".evidence"
    manifests = tuple(
        path
        for experiment in LOCAL_EVIDENCE_EXPERIMENTS
        for path in sorted((repo / "evidence" / "manifests" / experiment).glob("*.json"))
    )
    missing: list[Path] = []
    for path in manifests:
        try:
            digest = load_manifest(path)["sha256"]
        except EvidenceError:
            missing.append(path)
            continue
        if not object_path(store, digest).is_file():
            missing.append(path)
    return len(manifests), tuple(missing)


def fast_suite(*, include_local_evidence: bool) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    modules = CHECKOUT_MODULES + (LOCAL_EVIDENCE_MODULES if include_local_evidence else ())
    return loader.loadTestsFromNames(modules)


def audit(repo: Path) -> bool:
    errors = audit_repository(repo)
    if not errors:
        return True
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return False


def verify_e14_archive() -> int:
    with tempfile.TemporaryDirectory(prefix="ot-e14-archive-") as temporary:
        checkout = Path(temporary) / "repo"
        add = subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(checkout),
                E14_ARCHIVE_COMMIT,
            ],
            cwd=REPO,
            check=False,
        )
        if add.returncode:
            return add.returncode
        try:
            # The historical lifecycle suite treated the ignored local evidence
            # root as a pre-existing harness fixture.
            (checkout / ".evidence").mkdir()
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(checkout / "src")
            tests = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=checkout,
                env=environment,
                check=False,
            )
            if tests.returncode:
                return tests.returncode
            archived_audit = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; "
                    "from open_trajectory_evidence.audit import audit_repository; "
                    "errors = audit_repository(Path('.')); "
                    "[print(f'ERROR: {error}', file=__import__('sys').stderr) "
                    "for error in errors]; raise SystemExit(bool(errors))",
                ],
                cwd=checkout,
                env=environment,
                check=False,
            )
            return archived_audit.returncode
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(checkout)],
                cwd=REPO,
                check=False,
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("fast", "archive"), default="fast")
    evidence_mode = parser.add_mutually_exclusive_group()
    evidence_mode.add_argument(
        "--require-local-evidence",
        action="store_true",
        help="fail unless the complete OT-0080 through OT-0101 external evidence slice is available",
    )
    evidence_mode.add_argument(
        "--checkout-only",
        action="store_true",
        help="run only checks reproducible from a clean repository checkout",
    )
    args = parser.parse_args()
    manifest_count, missing = local_evidence_inventory(REPO)
    include_local_evidence = (
        not args.checkout_only and manifest_count > 0 and not missing
    )
    if args.require_local_evidence and not include_local_evidence:
        print(
            "ERROR: local evidence suite required but "
            f"{len(missing)} of {manifest_count} external objects are unavailable",
            file=sys.stderr,
        )
        return 1
    if args.checkout_only:
        print("running checkout-only suite (external evidence disabled explicitly)")
    elif include_local_evidence:
        print(f"including local evidence suite ({manifest_count} external objects available)")
    else:
        print(
            "skipping local evidence suite "
            f"({len(missing)} of {manifest_count} external objects unavailable; "
            "use --require-local-evidence to make this fatal)"
        )
    result = unittest.TextTestRunner(verbosity=1).run(
        fast_suite(include_local_evidence=include_local_evidence)
    )
    if not result.wasSuccessful():
        return 1
    if not audit(REPO):
        return 1
    if args.mode == "archive" and verify_e14_archive():
        return 1
    print(f"{args.mode} verification and privacy audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
