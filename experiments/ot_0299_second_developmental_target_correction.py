from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0298_developmental_isolation_provenance.py"
BASE_SHA256 = "20c0604722ce2ef45a6235ab92f958310c54ec1d1d0ac22bec0b8f710cbb6807"
PARENT_DIGEST = "450c7a1cac703d2b7b4dc90b5847a45653ac0779cef7c2b72ffa4ba6a0d5437b"
OT298_RECEIPT = "e4fe5eeefdf9e186b97496e4b6b92a5b583519ce80b749eb0a9b3af3355cf472"
AUTHORITY = "ot-0299-second-developmental-target-correction"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0298 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0299_frozen_ot0298", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base298 = load_base()
base297 = base298.base297
base295 = base297.base296.base295
b = base295.b
base295.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0299").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(p82, repo, store, "OT-0298", "open-subject-after-developmental-selection.json")
    result298 = selector.load_artifact(p82, repo, store, "OT-0298", "developmental-isolation-selection-aggregate.json")
    package = selector.load_artifact(p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json")
    result280 = selector.load_artifact(p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json")
    return repo, run, p82, runtime, parent, result298, package, result280, core, base130


def preflight(root, p82, runtime, parent, result298, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    selected = b.base274.selected(parent)
    target = selected[4]
    disclosure = parent.get("active_correction_disclosure") or {}
    available = base295.undisclosed(parent, package, p82)
    earned_before = base297.earned_targets(parent, package)
    branches = []
    for depth in range(len(available) + 1):
        final, row = b.correction_variant(parent, depth, package, result280, p82, runtime)
        branches.append({
            **row,
            "lineage_exact": base295.lineage_projection(final) == base295.lineage_projection(parent),
            "earned_after_exact": len(base297.earned_targets(final, package)) == 2 and target in base297.earned_targets(final, package),
        })
    exhausted, _ = b.correction_variant(parent, len(available), package, result280, p82, runtime)
    exhausted_fails = False
    try:
        b.correction_variant(exhausted, 1, package, result280, p82, runtime)
    except (RuntimeError, TypeError, KeyError):
        exhausted_fails = True
    route, identity = b.base272.base265.floors(parent)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_second_correction": parent["artifact_digest"] == PARENT_DIGEST and b.base272.derive(parent, p82) == "outward-correct" and runtime.identity_conforms(parent),
        "ot0298_exact_promotion": result298["receipt_digest"] == OT298_RECEIPT and result298["observer_disposition"] == "promoted" and result298["final_subject_digest"] == PARENT_DIGEST,
        "one_earned_before": len(earned_before) == 1 and target not in earned_before,
        "stale_disclosure_scoped_away": disclosure.get("target_symbol") != target and disclosure.get("status") == "resolved-after-revision" and not b.base274.feedback_mode(parent),
        "two_undisclosed_classes": len(available) == 2,
        "zero_one_two_feedback_paths": len(branches) == 3 and all(row["feedback_passed"] and row["success_public"] and row["success_6_2"] and row["conformant"] and row["routes_refresh"] and row["lineage_exact"] and row["earned_after_exact"] for row in branches),
        "exhausted_fails_closed": exhausted_fails,
        "consequence_earned_authority_retained": b.base281.base270.seed_excludes_sealed is base297.consequence_earned_public_only,
        "dynamic_target_not_hardcoded": target not in script and selected[5] not in script and package["world_id"] not in script,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "feedback_capacity": len(available), "branch_count": len(branches), "checks": checks}
    result["receipt_digest"] = p82.digest(result)
    base295.write_json(root / "fixture-conformance.json", result)
    return result


base295.setup = setup
base295.preflight = preflight


if __name__ == "__main__":
    raise SystemExit(base295.main())
