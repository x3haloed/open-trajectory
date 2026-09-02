from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0270_standing_scanner_independent_package_contact.py"
BASE_SHA256 = "04cfafa453e3be47a3eb489b2d923b29d306c5962104335963a4da574d976b2e"
PARENT_DIGEST = "f1c8d8de2f627451f4faefd4a1c21addb0b2c32ccc4c20588da89b37e3a02899"
OT275_RECEIPT = "fdee3f2f1b3152bbafe25341317658d25ce5812d0d2bb6436d5e5170c1ede265"
AUTHORITY = "ot-0277-asterfall-subject-selection"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0270 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0277_frozen_ot0270", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
base265 = base.base265
base260 = base.base260
authority_base = base.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0277").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0276", "open-subject-at-asterfall-offer.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0275", "independent-asterfall-world-package.json"
    )
    result275 = selector.load_artifact(
        p82, repo, store, "OT-0275", "post-mechanism-independent-world-aggregate.json"
    )
    return repo, run, p82, runtime, parent, package, result275, core, base130


def preflight(root, p82, runtime, parent, package, result275):
    root.mkdir(parents=True, exist_ok=True)
    evaluation = base.base268.evaluate_package(package, p82.digest)
    paths = [
        base.prospective_path(
            root / target,
            parent,
            package,
            evaluation,
            result275,
            target,
            p82,
            runtime,
        )
        for target in sorted(evaluation["targets"])
    ]
    route, identity = base265.floors(parent)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_offer": parent["artifact_digest"] == PARENT_DIGEST
        and base.derive(parent, p82) == "expand-environment"
        and runtime.identity_conforms(parent),
        "ot0275_exact_package": result275["receipt_digest"] == OT275_RECEIPT
        and result275["observer_disposition"] == "promoted"
        and result275["full_package_digest"] == evaluation["full_package_digest"],
        "all_three_paths_pass": len(paths) == 3
        and all(
            row["checker"]
            and row["semantic"]
            and row["public"]
            and row["sealed_matches"] == 2
            and row["world_outcome"] == "unresolved"
            and row["intermediate_conformant"]
            and row["final_conformant"]
            and row["routes_correction"]
            for row in paths
        ),
        "dynamic_surfaces_not_hardcoded": all(
            token not in script
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "paths": paths,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result, route, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, package, result275, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    if retained.exists():
        fixtures = json.loads(retained.read_text())
        route, identity = base265.floors(parent)
    else:
        fixtures, route, identity = preflight(
            run / "preflight", p82, runtime, parent, package, result275
        )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists() and (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0277 evidence")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    run.mkdir(parents=True, exist_ok=True)
    write_json(run / "fixture-conformance.json", fixtures)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": base.derive(parent, p82),
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        core.typed.base.make_context(runtime, run / "runtime", repo)
    )
    actor = base.run_actor(context, p82, run / "actor", parent)
    intermediate = base.compile_intermediate(parent, actor, pulse, p82) if actor["accepted"] else parent
    world = base.sealed_world(intermediate, actor, package, result275, p82) if actor["accepted"] else None
    final = base.compile_world(intermediate, world, p82) if world else intermediate
    if world:
        write_json(run / "world-receipt.json", world)
    selected = actor["decision"]["next_contact"] if actor.get("decision") else None
    pair = (selected["target_path"], selected["target_symbol"]) if selected else None
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "content_free_expansion": pulse["content"] is None
        and pulse["derived_operation"] == "expand-environment",
        "actor_accepted": actor["accepted"],
        "selected_offered_surface": pair in base.offered_pairs(parent),
        "g10_accepted": actor["g10_disposition"],
        "public_four_cases": bool(
            actor["public"] and actor["public"]["all_valid"] and actor["public"]["case_count"] == 4
        ),
        "workspace_public_only": base.seed_excludes_sealed(
            run / "actor" / "seed", package, result275
        ),
        "retained_package_2_of_6": bool(
            world
            and world["result"]["matches"] == 2
            and world["ot0268_aggregate_receipt_digest"] == OT275_RECEIPT
        ),
        "offer_consumed_new_epoch": final.get("active_streamed_world_offer") is None
        and len(final["actor_authored_environment_epochs"])
        == len(parent["actor_authored_environment_epochs"]) + 1,
        "correction_before_refresh": base260.needs_refresh(final, p82)
        and base.derive(final, p82) == "outward-correct",
        "scanner_preserved": final["active_standing_world_provider"]
        == parent["active_standing_world_provider"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "actor": actor,
        "world": world,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
