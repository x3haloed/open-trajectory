from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0295_recovered_world_target_correction.py"
BASE_SHA256 = "de8dd0e926c309fa663f9c4901c0c2a462daa222ce6c443f7240d9520fc14b1a"
PARENT_DIGEST = "90b6999ce21650f13205c91f644ebeb43561413af7e836ee3ffadc18ebe8c61a"
OT295_RECEIPT = "f94d93cc7d5058e3192ea2dc14d6e38561033f9d8cc9818f91c18b08149ef854"
AUTHORITY = "ot-0296-post-correction-renewed-selection"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0295 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0296_frozen_ot0295", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base295 = load_base()
b = base295.b
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base295.write_json(path, value)


def lineage(subject):
    return {
        "scars": subject.get("invalid_encounter_scars"),
        "recoveries": subject.get("invalid_encounter_recovery_receipts"),
        "policy": subject.get("active_invalid_encounter_reopening_policy"),
    }


def setup(args):
    lineage_base = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage_base.selector_base, lineage_base.base, lineage_base.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0296").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(p82, repo, store, "OT-0295", "open-subject-after-recovered-world-correction.json")
    result295 = selector.load_artifact(p82, repo, store, "OT-0295", "recovered-world-target-correction-aggregate.json")
    package = selector.load_artifact(p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json")
    result280 = selector.load_artifact(p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json")
    return repo, run, p82, runtime, parent, result295, package, result280, core, base130


def preflight(root, p82, runtime, parent, result295, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    refreshed = b.base264.refresh_projection_only(parent, p82)
    opportunities = refreshed["active_opportunity_projection"]["opportunities"]
    branches = []
    for index, opportunity in enumerate(opportunities):
        row = b.base272.selection_fixture(root / f"selection-{index}", refreshed, package, result280, opportunity["target_symbol"], p82, runtime)
        seed = root / f"selection-{index}" / "actor" / "seed"
        row["shared_public_only"] = b.base281.base270.seed_excludes_sealed(seed, package, result280)
        row["lineage_exact"] = lineage(row["final"]) == lineage(parent)
        branches.append(row)
    route, identity = b.base272.base265.floors(parent)
    script = Path(__file__).read_text()
    evaluation = b.base268.evaluate_package(package, p82.digest)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_refresh": parent["artifact_digest"] == PARENT_DIGEST and b.base272.derive(parent, p82) == "refresh-opportunity-projection" and runtime.identity_conforms(parent),
        "ot0295_exact_promotion": result295["receipt_digest"] == OT295_RECEIPT and result295["observer_disposition"] == "promoted" and result295["final_subject_digest"] == PARENT_DIGEST,
        "refresh_actor_free_exact": not b.base260.needs_refresh(refreshed, p82) and b.base272.derive(refreshed, p82) == "expanded-select" and lineage(refreshed) == lineage(parent),
        "exactly_two_remaining": len(opportunities) == 2 and len(branches) == 2,
        "both_selection_branches": all(row["checker"] and row["semantic"] and row["public"] and row["prompt_neutral"] and row["shared_public_only"] and row["world"]["result"]["matches"] == 2 and row["routes_correction"] and row["conformant"] and row["lineage_exact"] for row in branches),
        "dynamic_targets_not_hardcoded": all(token not in script for row in opportunities for token in (row["target_symbol"], row["target_path"])) and package["world_id"] not in script and all(row["target_symbol"] in evaluation["targets"] for row in opportunities),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "choice_count": len(branches), "checks": checks}
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [json.loads(path.read_text()) for path in sorted(run.glob("invocation-*-result.json"))]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_content_free_openings": len(rows) == 2 and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "refresh_then_selection": [row["transition"] for row in rows] == ["refresh-opportunity-projection", "expanded-select"],
        "one_fresh_selector": sum(row["fresh_actor_count"] for row in rows) == 1,
        "lineage_exact": lineage(final) == lineage(parent),
        "correction_live": b.base272.derive(final, p82) == "outward-correct",
        "final_open_conformant": final["continuation"]["status"] == "open" and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "invocation_receipt_digests": [row["receipt_digest"] for row in rows], "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1}
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result295, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(run / "preflight", p82, runtime, parent, result295, package, result280)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists(): raise SystemExit("OT-0296 unavailable")
    results = sorted(run.glob("invocation-*-result.json")); checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists(): raise SystemExit("preserve failed OT-0296 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index not in {1, 2} or not runtime.identity_conforms(subject): raise SystemExit("invalid OT-0296 checkpoint")
    operation = b.base272.derive(subject, p82)
    root = run / f"invocation-{index:02d}"; root.mkdir(parents=True)
    pulse = {"authority": AUTHORITY + "-pulse", "content": None, "source_subject_digest": subject["artifact_digest"], "derived_operation": operation}; pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = None
    if operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82)
        checks = {"content_free": True, "zero_fresh_actors": True, "projection_fresh": not b.base260.needs_refresh(final, p82), "two_remaining": len(final["active_opportunity_projection"]["opportunities"]) == 2, "next_is_selection": b.base272.derive(final, p82) == "expanded-select", "lineage_exact": lineage(final) == lineage(parent)}
    elif operation == "expanded-select":
        context = b.base274.context_for(core, base130, runtime, root, repo)
        actor, world, final = b.base272.live_selection(context, p82, root, subject, package, result280)
        checks = {"content_free": True, "workspace_outside_repo": not (root / "actor").resolve().is_relative_to(repo), "actor_accepted": actor["accepted"], "g10_accepted": actor["g10_disposition"], "public_seed_only": b.base281.base270.seed_excludes_sealed(root / "actor" / "seed", package, result280), "retained_package_2_of_6": bool(world and world["result"]["matches"] == 2), "next_is_correction": b.base272.derive(final, p82) == "outward-correct", "lineage_exact": lineage(final) == lineage(parent)}
    else:
        final = subject; checks = {"known_operation": False}
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"; checks["identity_conformant"] = runtime.identity_conforms(final); checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + f"-invocation-{index:02d}", "invocation_index": index, "source_subject_digest": subject["artifact_digest"], "pulse": pulse, "transition": operation, "actor": copy.deepcopy(actor), "world": world, "checks": checks, "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1 if actor else 0}; result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result); write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]: print(json.dumps(result, indent=2, sort_keys=True)); return 2
    write_json(checkpoint, final)
    if index == 1: print(json.dumps(result, indent=2, sort_keys=True)); return 0
    return finalize(run, fixtures, p82, runtime, parent, final)


if __name__ == "__main__": raise SystemExit(main())
