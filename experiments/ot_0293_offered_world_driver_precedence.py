from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0292_recovered_package_content_isolation.py"
BASE_SHA256 = "1cc1d4784bf0e5802c268aa8fb6f7afb153b445cc6b370f43a5bdd90adb119f0"
OT292_REJECTED_RECEIPT = "96727a85a6eb700e2403fba4d69867f22012be9e2a71406f784e15e845a93590"
POST_WAKE_DIGEST = "3fcb9e3993789dec8032fb25ad1fd68c005a7e181edc46cec6d9aca24ac609d1"
AUTHORITY = "ot-0293-offered-world-driver-precedence"
ACTIVE_REPO = REPO
ACTIVE_STORE = REPO / ".evidence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0292 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0293_frozen_ot0292", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base292 = load_base()
base291 = base292.base291
b = base292.b
base291.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


inherited_derive = b.base272.derive


def offered_world_derive(subject, p82):
    if subject.get("active_streamed_world_offer"):
        return "expanded-select"
    return inherited_derive(subject, p82)


b.base272.derive = offered_world_derive
original_preflight = base291.preflight


def precedence_preflight(root, p82, runtime, parent, package, result290, result280):
    result = original_preflight(
        root, p82, runtime, parent, package, result290, result280
    )
    lineage = b.authority_base.guide_base.load_base()
    selector = lineage.selector_base
    rejected292 = selector.load_artifact(
        p82,
        ACTIVE_REPO,
        ACTIVE_STORE,
        "OT-0292",
        "rejected-post-wake-live-routing-invocation.json",
    )
    retained_wake = selector.load_artifact(
        p82,
        ACTIVE_REPO,
        ACTIVE_STORE,
        "OT-0292",
        "open-subject-after-recovered-world-wake.json",
    )
    _, observation, offered, reused = base291.wake(parent, package, p82)
    result["checks"]["base_hash_exact"] = (
        hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    )
    result["checks"]["ot0292_rejection_preserved"] = (
        rejected292["receipt_digest"] == OT292_REJECTED_RECEIPT
        and rejected292["checks"]["passed"] is False
        and rejected292["fresh_actor_count"] == 0
        and rejected292["pulse"]["derived_operation"] == "expand-environment"
    )
    result["checks"]["exact_post_wake_reconstruction"] = (
        observation["status"] == "world-available"
        and not reused
        and retained_wake["artifact_digest"] == POST_WAKE_DIGEST
        and offered["artifact_digest"] == POST_WAKE_DIGEST
    )
    result["checks"]["actual_driver_sequence"] = [
        "wake-world",
        offered_world_derive(offered, p82),
    ] == ["wake-world", "expanded-select"]
    result["checks"]["rejected_route_localized"] = (
        inherited_derive(offered, p82) == "expand-environment"
        and offered_world_derive(parent, p82) == inherited_derive(parent, p82)
        and offered_world_derive(parent, p82) == "wait-provider"
    )
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected292["receipt_digest"]
    result.pop("receipt_digest", None)
    result["receipt_digest"] = p82.digest(result)
    base291.write_json(root / "fixture-conformance.json", result)
    return result


base291.preflight = precedence_preflight


def main():
    global ACTIVE_REPO, ACTIVE_STORE
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    known, _ = parser.parse_known_args()
    ACTIVE_REPO = known.repo.resolve()
    ACTIVE_STORE = (known.store or ACTIVE_REPO / ".evidence").resolve()
    base292.ACTIVE_REPO = ACTIVE_REPO
    base292.ACTIVE_STORE = ACTIVE_STORE
    added_root = known.evidence_root is None
    if added_root:
        sys.argv.extend(["--evidence-root", str(ACTIVE_STORE / "runs" / "OT-0293")])
    try:
        return base291.main()
    finally:
        if added_root:
            del sys.argv[-2:]


if __name__ == "__main__":
    raise SystemExit(main())
