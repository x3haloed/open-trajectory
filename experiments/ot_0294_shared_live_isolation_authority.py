from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0293_offered_world_driver_precedence.py"
BASE_SHA256 = "f7660cde074e11255f77eb83ce9cb035a5b0f6225b93e2ad3f10cd536b9cbd68"
OT293_REJECTED_RECEIPT = "39ab37a29e7b6c4dfdefd2dbf62d9ae5d24c747ec3ca6234c343345da73a62b8"
AUTHORITY = "ot-0294-shared-live-isolation-authority"
ACTIVE_REPO = REPO
ACTIVE_STORE = REPO / ".evidence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0293 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0294_frozen_ot0293", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base293 = load_base()
base292 = base293.base292
base291 = base293.base291
b = base293.b
base270 = b.base281.base270
base291.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def shared_current_package_public_only(seed, package, result280):
    del result280
    return base292.current_package_public_only(seed, package)


base270.seed_excludes_sealed = shared_current_package_public_only
base291.selected_fixture = base292.original_selected_fixture
original_preflight = base291.preflight


def shared_authority_preflight(
    root, p82, runtime, parent, package, result290, result280
):
    result = original_preflight(
        root, p82, runtime, parent, package, result290, result280
    )
    lineage = b.authority_base.guide_base.load_base()
    rejected293 = lineage.selector_base.load_artifact(
        p82,
        ACTIVE_REPO,
        ACTIVE_STORE,
        "OT-0293",
        "rejected-live-isolation-authority-invocation.json",
    )
    evaluation, _, offered, _ = base291.wake(parent, package, p82)
    target = sorted(evaluation["targets"])[0]
    fixture_root = root / "shared-authority-control"
    branch = base291.selected_fixture(
        fixture_root,
        offered,
        target,
        package,
        evaluation,
        result280,
        p82,
        runtime,
    )
    clean_seed = fixture_root / "actor" / "seed"
    result["checks"]["base_hash_exact"] = (
        hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    )
    result["checks"]["ot0293_rejection_preserved"] = (
        rejected293["receipt_digest"] == OT293_REJECTED_RECEIPT
        and rejected293["checks"]["passed"] is False
        and rejected293["checks"]["public_seed_only"] is False
        and rejected293["checks"]["actor_accepted"]
        and rejected293["checks"]["g10_accepted"]
        and rejected293["checks"]["retained_package_2_of_6"]
        and rejected293["checks"]["next_is_correction"]
    )
    result["checks"]["single_shared_isolation_authority"] = (
        base270.seed_excludes_sealed is shared_current_package_public_only
        and base291.selected_fixture is base292.original_selected_fixture
    )
    result["checks"]["clean_live_helper_passes"] = (
        shared_current_package_public_only(clean_seed, package, result280)
        and branch["public_only"]
    )
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected293["receipt_digest"]
    result.pop("receipt_digest", None)
    result["receipt_digest"] = p82.digest(result)
    base291.write_json(root / "fixture-conformance.json", result)
    return result


base291.preflight = shared_authority_preflight


def main():
    global ACTIVE_REPO, ACTIVE_STORE
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    known, _ = parser.parse_known_args()
    ACTIVE_REPO = known.repo.resolve()
    ACTIVE_STORE = (known.store or ACTIVE_REPO / ".evidence").resolve()
    base293.ACTIVE_REPO = ACTIVE_REPO
    base293.ACTIVE_STORE = ACTIVE_STORE
    base292.ACTIVE_REPO = ACTIVE_REPO
    base292.ACTIVE_STORE = ACTIVE_STORE
    added_root = known.evidence_root is None
    if added_root:
        sys.argv.extend(["--evidence-root", str(ACTIVE_STORE / "runs" / "OT-0294")])
    try:
        return base291.main()
    finally:
        if added_root:
            del sys.argv[-2:]


if __name__ == "__main__":
    raise SystemExit(main())
