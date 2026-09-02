from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0296_post_correction_renewed_selection.py"
BASE_SHA256 = "610d405ded0921bbcb060e3b817f61d3dd8f0baf7c67069706eea4066c0ec6d3"
OT296_REJECTED_RECEIPT = "75c145737f3c8c1d421ff9777063a9dcacaebd68593e4ec661a3098db39b3033"
AUTHORITY = "ot-0297-consequence-earned-isolation"
ACTIVE_REPO = REPO
ACTIVE_STORE = REPO / ".evidence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0296 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0297_frozen_ot0296", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base296 = load_base()
base295 = base296.base295
b = base296.b
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def earned_targets(subject, package):
    ledger = subject.get("local_frontier_ledger", {}).get("targets", {})
    return {
        target
        for target in package["sealed_cases"]
        if (row := ledger.get(target, {})).get("status") == "verified-local"
        and bool(row.get("correction_receipts"))
        and bool(row.get("independent_success_receipts"))
    }


def target_paths(package):
    pairs = {}
    for path, source in package["visible_sources"].items():
        callables = [
            node.name
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if len(callables) != 1:
            raise RuntimeError("package surface must expose one top-level callable")
        pairs[callables[0]] = path
    return pairs


def consequence_earned_public_only(seed, package, result280):
    del result280
    subject = json.loads((seed / "exact-subject.json").read_text())
    earned = earned_targets(subject, package)
    files = [path for path in seed.rglob("*") if path.is_file()]
    corpus = "\n".join(path.read_text(errors="replace") for path in files)
    unearned = set(package["sealed_cases"]) - earned
    paths = target_paths(package)
    forbidden = [
        *(package["sealed_reference_sources"][paths[target]] for target in unearned),
        *(
            json.dumps(row, sort_keys=True)
            for target in unearned
            for row in package["sealed_cases"][target][4:]
        ),
        json.dumps(package["sealed_cases"], sort_keys=True),
    ]
    return all(value not in corpus for value in forbidden) and not any(
        "sealed" in path.name.lower() for path in files
    )


b.base281.base270.seed_excludes_sealed = consequence_earned_public_only
original_preflight = base296.preflight


def developmental_preflight(root, p82, runtime, parent, result295, package, result280):
    result = original_preflight(root, p82, runtime, parent, result295, package, result280)
    lineage = b.authority_base.guide_base.load_base()
    rejected296 = lineage.selector_base.load_artifact(
        p82, ACTIVE_REPO, ACTIVE_STORE, "OT-0296", "rejected-post-correction-selection-preflight.json"
    )
    refreshed = b.base264.refresh_projection_only(parent, p82)
    opportunity = refreshed["active_opportunity_projection"]["opportunities"][0]
    fixture_root = root / "developmental-controls"
    b.base272.selection_fixture(fixture_root, refreshed, package, result280, opportunity["target_symbol"], p82, runtime)
    seed = fixture_root / "actor" / "seed"
    clean_subject = json.loads((seed / "exact-subject.json").read_text())
    earned = earned_targets(clean_subject, package)
    unearned = sorted(set(package["sealed_cases"]) - earned)
    paths = target_paths(package)
    corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
    controls = {}
    marker = seed / "content-control.txt"
    for target in unearned:
        for kind, value in (
            ("reference", package["sealed_reference_sources"][paths[target]]),
            ("hidden", json.dumps(package["sealed_cases"][target][4], sort_keys=True)),
        ):
            marker.write_text(value)
            controls[f"{kind}-{target}"] = not consequence_earned_public_only(seed, package, result280)
            marker.unlink()
    marker.write_text(json.dumps(package["sealed_cases"], sort_keys=True))
    controls["full-case-collection"] = not consequence_earned_public_only(seed, package, result280)
    marker.unlink()
    sealed_marker = seed / "sealed-control.txt"; sealed_marker.write_text("filename control")
    controls["sealed-filename"] = not consequence_earned_public_only(seed, package, result280); sealed_marker.unlink()
    counterfeit = copy.deepcopy(clean_subject)
    counterfeit["local_frontier_ledger"]["targets"][unearned[0]] = {
        "status": "verified-local", "correction_receipts": [], "independent_success_receipts": []
    }
    (seed / "exact-subject.json").write_text(json.dumps(counterfeit, indent=2, sort_keys=True) + "\n")
    marker.write_text(package["sealed_reference_sources"][paths[unearned[0]]])
    controls["status-only-counterfeit"] = not consequence_earned_public_only(seed, package, result280)
    marker.unlink(); (seed / "exact-subject.json").write_text(json.dumps(clean_subject, indent=2, sort_keys=True) + "\n")
    result["checks"]["base_hash_exact"] = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    result["checks"]["ot0296_rejection_preserved"] = rejected296["receipt_digest"] == OT296_REJECTED_RECEIPT and rejected296["checks"]["passed"] is False and rejected296["checks"]["both_selection_branches"] is False
    result["checks"]["one_earned_two_unearned"] = len(earned) == 1 and len(unearned) == 2
    result["checks"]["earned_source_present_and_permitted"] = all(package["sealed_reference_sources"][paths[target]] in corpus for target in earned) and consequence_earned_public_only(seed, package, result280)
    result["checks"]["unearned_controls_reject"] = all(controls.values())
    result["checks"]["shared_authority_installed"] = b.base281.base270.seed_excludes_sealed is consequence_earned_public_only
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected296["receipt_digest"]
    result["isolation_controls"] = controls
    result.pop("receipt_digest", None); result["receipt_digest"] = p82.digest(result)
    base296.write_json(root / "fixture-conformance.json", result)
    return result


base296.preflight = developmental_preflight


def main():
    global ACTIVE_REPO, ACTIVE_STORE
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path)
    known, _ = parser.parse_known_args(); ACTIVE_REPO = known.repo.resolve(); ACTIVE_STORE = (known.store or ACTIVE_REPO / ".evidence").resolve()
    added = known.evidence_root is None
    if added: sys.argv.extend(["--evidence-root", str(ACTIVE_STORE / "runs" / "OT-0297")])
    try: return base296.main()
    finally:
        if added: del sys.argv[-2:]


if __name__ == "__main__": raise SystemExit(main())
