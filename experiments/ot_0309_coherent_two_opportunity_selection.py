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
BASE_PATH = ROOT / "ot_0308_actor_facing_coherence_repair.py"
BASE_SHA256 = "018eb6d799ba67b6bd0673b5f195b9b2885c2c9da985cfd6e1bd4f632b184425"
PARENT_DIGEST = "e9e152b37b42c37aad682a07780c2edc10a34e7404f875547f89296e4a4c053f"
OT308_RECEIPT = "4defdcc7bd6f007476226c8be2e67a46b2096df33776287ec0a70b0e473dbda6"
AUTHORITY = "ot-0309-coherent-two-opportunity-selection"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0308 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0309_frozen_ot0308", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base308 = load_base()
base307 = base308.base307
base297 = base307.base303.base297
b = base308.b
b.AUTHORITY = AUTHORITY
b.base272.base252.AUTHORITY = AUTHORITY
b.base272.base245.AUTHORITY = AUTHORITY
b.base272.base270.AUTHORITY = AUTHORITY


def write_json(path, value):
    base308.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0309").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0308",
        "open-subject-after-actor-facing-coherence-repair.json",
    )
    result308 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0308",
        "actor-facing-coherence-repair-aggregate.json",
    )
    result305 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        "subject-priority-world-selection-aggregate.json",
    )
    selected_world = result305["selection"]["selected_world_id"]
    provider_index = next(
        index
        for index, provider in enumerate(result305["providers"], 1)
        if provider["package"]["world_id"] == selected_world
    )
    package = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        f"subject-blind-provider-{provider_index:02d}-world-package.json",
    )
    result280 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0280",
        "import-stable-world-evaluator-aggregate.json",
    )
    return (
        repo,
        run,
        p82,
        runtime,
        parent,
        result308,
        result305,
        package,
        result280,
        core,
        base130,
    )


def seed_for(root, parent):
    return b.base272.base252.selection_seed(
        root, parent, b.base272.base245.template()
    )


def inherited_protected(subject):
    value = base307.protected(subject)
    value.pop("subject_originated_world_stakes")
    return value


def selection_continuity(before, after):
    old_stakes = before.get("subject_originated_world_stakes", [])
    new_stakes = after.get("subject_originated_world_stakes", [])
    return bool(
        inherited_protected(after) == inherited_protected(before)
        and len(new_stakes) == len(old_stakes) + 1
        and new_stakes[:-1] == old_stakes
    )


def fixture_branch(root, parent, package, result280, target, p82, runtime):
    row = b.base272.selection_fixture(
        root, parent, package, result280, target, p82, runtime
    )
    return {
        "target": target,
        "path": row["path"],
        "checker": row["checker"],
        "semantic": row["semantic"],
        "public": row["public"],
        "prompt_neutral": row["prompt_neutral"],
        "world_matches": row["world"]["result"]["matches"],
        "world_outcome": row["world"]["outcome"],
        "routes_correction": b.base272.derive(row["final"], p82)
        == "outward-correct",
        "coherence_repair_preserved": row["final"].get(
            "actor_facing_coherence_repairs"
        )
        == parent.get("actor_facing_coherence_repairs"),
        "selection_continuity": selection_continuity(parent, row["final"]),
        "conformant": row["conformant"]
        and runtime.identity_conforms(row["final"]),
    }


def preflight(
    root, p82, runtime, parent, result308, result305, package, result280
):
    root.mkdir(parents=True, exist_ok=True)
    evaluation = b.base268.evaluate_package(package, p82.digest)
    opportunities = parent["active_opportunity_projection"]["opportunities"]
    targets = [row["target_symbol"] for row in opportunities]
    branches = [
        fixture_branch(
            root / f"selection-{index:02d}",
            parent,
            package,
            result280,
            target,
            p82,
            runtime,
        )
        for index, target in enumerate(targets, 1)
    ]
    seed = seed_for(root / "target-neutral-seed", parent)
    coherence = base308.selection_seed_check(root / "coherence-seed", parent)
    priority = parent["subject_priority_contact_receipts"][-1]
    route, identity = b.base272.base265.floors(parent)
    source = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "exact_ot0308_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result308["receipt_digest"] == OT308_RECEIPT
        and result308["observer_disposition"] == "promoted"
        and b.base272.derive(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "two_coherent_opportunities": len(opportunities) == 2
        and parent["active_opportunity_projection"]["opportunity_count"] == 2
        and all(coherence.values()),
        "selection_seed_public_only": b.base272.base270.seed_excludes_sealed(
            seed, package, result280
        )
        and b.base272.base270.seed_excludes_sealed
        is base297.consequence_earned_public_only,
        "both_selection_branches_pass": len(branches) == 2
        and all(
            row["checker"]
            and row["semantic"]
            and row["public"]
            and row["prompt_neutral"]
            and row["world_matches"] == 2
            and row["world_outcome"] == "unresolved"
            and row["routes_correction"]
            and row["coherence_repair_preserved"]
            and row["selection_continuity"]
            and row["conformant"]
            for row in branches
        ),
        "priority_negative_preserved": result305["observer_disposition"]
        == "rejected"
        and result305["e11"]["priority_bearing_contact"] is False
        and priority["selected_world_id"] == priority["blind_control_world_id"],
        "target_untold_harness": all(
            token not in source
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
        "source_ot0308_receipt_digest": result308["receipt_digest"],
        "opportunities": opportunities,
        "branches": branches,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo,
        run,
        p82,
        runtime,
        parent,
        result308,
        result305,
        package,
        result280,
        core,
        base130,
    ) = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight",
            p82,
            runtime,
            parent,
            result308,
            result305,
            package,
            result280,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0309 unavailable")
    run.mkdir(parents=True, exist_ok=True)
    root = run / "invocation-01"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": b.base272.derive(parent, p82),
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    context = b.base274.context_for(core, base130, runtime, root, repo)
    actor, world, final = b.base272.live_selection(
        context, p82, root, parent, package, result280
    )
    selected = (actor.get("decision") or {}).get("next_contact")
    seed = root / "actor" / "seed"
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "one_content_free_opening": pulse["content"] is None
        and pulse["derived_operation"] == "expanded-select",
        "one_fresh_actor_no_retry": True,
        "workspace_outside_repo": not (root / "actor").resolve().is_relative_to(
            repo
        ),
        "actor_accepted": actor["accepted"],
        "g10_accepted": actor["g10_disposition"],
        "selected_projected_target": bool(
            selected
            and {
                "target_path": selected["target_path"],
                "target_symbol": selected["target_symbol"],
            }
            in parent["active_opportunity_projection"]["opportunities"]
        ),
        "workspace_public_only": b.base272.base270.seed_excludes_sealed(
            seed, package, result280
        ),
        "independent_2_of_6_contradiction": bool(
            world
            and world["result"]["all_valid"]
            and world["result"]["matches"] == 2
            and world["outcome"] == "unresolved"
        ),
        "coherence_repair_preserved": final.get("actor_facing_coherence_repairs")
        == parent.get("actor_facing_coherence_repairs"),
        "priority_negative_preserved": selection_continuity(parent, final)
        and final["subject_originated_world_stakes"][-1]["binding_digest"]
        == actor["binding"]["binding_digest"]
        and result305["e11"]["priority_bearing_contact"] is False,
        "consequence_selects_correction": bool(
            world and b.base272.derive(final, p82) == "outward-correct"
        ),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0308_receipt_digest": result308["receipt_digest"],
        "pulse": pulse,
        "actor": copy.deepcopy(actor),
        "world": world,
        "checks": checks,
        "operational_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    if world:
        write_json(run / "world-receipt.json", world)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
