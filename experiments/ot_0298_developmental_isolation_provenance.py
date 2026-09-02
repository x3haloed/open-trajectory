from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0297_consequence_earned_isolation.py"
BASE_SHA256 = "f73976fe56bfcc449a30a4cc3e40ce8ea4da2f81d0e41ac4ac4d2095bf3f7616"
OT297_REJECTED_RECEIPT = "33deecde784fee88be9ab8caf89582437a45f518ca68728822ee11dddbbfe35a"
AUTHORITY = "ot-0298-developmental-isolation-provenance"
ACTIVE_REPO = REPO
ACTIVE_STORE = REPO / ".evidence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0297 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0298_frozen_ot0297", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base297 = load_base()
base296 = base297.base296
b = base297.b
base296.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY
original_preflight = base296.preflight


def provenance_preflight(root, p82, runtime, parent, result295, package, result280):
    result = original_preflight(root, p82, runtime, parent, result295, package, result280)
    lineage = b.authority_base.guide_base.load_base()
    rejected297 = lineage.selector_base.load_artifact(
        p82, ACTIVE_REPO, ACTIVE_STORE, "OT-0297", "rejected-mislabeled-developmental-isolation-invocation.json"
    )
    expected = {
        "aggregate": AUTHORITY,
        "pulse": AUTHORITY + "-pulse",
        "invocation_01": AUTHORITY + "-invocation-01",
        "invocation_02": AUTHORITY + "-invocation-02",
    }
    result["checks"]["base_hash_exact"] = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    result["checks"]["ot0297_mislabel_rejection_preserved"] = rejected297["receipt_digest"] == OT297_REJECTED_RECEIPT and rejected297["fresh_actor_count"] == 0 and rejected297["authority"].startswith("ot-0296-") and rejected297["pulse"]["authority"].startswith("ot-0296-")
    result["checks"]["runner_authority_exact"] = base296.AUTHORITY == AUTHORITY
    result["checks"]["all_live_labels_exact"] = expected == {
        "aggregate": base296.AUTHORITY,
        "pulse": base296.AUTHORITY + "-pulse",
        "invocation_01": base296.AUTHORITY + "-invocation-01",
        "invocation_02": base296.AUTHORITY + "-invocation-02",
    }
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected297["receipt_digest"]
    result["expected_live_authorities"] = expected
    result.pop("receipt_digest", None); result["receipt_digest"] = p82.digest(result)
    base296.write_json(root / "fixture-conformance.json", result)
    return result


base296.preflight = provenance_preflight


def main():
    global ACTIVE_REPO, ACTIVE_STORE
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path)
    known, _ = parser.parse_known_args(); ACTIVE_REPO = known.repo.resolve(); ACTIVE_STORE = (known.store or ACTIVE_REPO / ".evidence").resolve()
    base297.ACTIVE_REPO = ACTIVE_REPO; base297.ACTIVE_STORE = ACTIVE_STORE
    added = known.evidence_root is None
    if added: sys.argv.extend(["--evidence-root", str(ACTIVE_STORE / "runs" / "OT-0298")])
    try: return base296.main()
    finally:
        if added: del sys.argv[-2:]


if __name__ == "__main__": raise SystemExit(main())
