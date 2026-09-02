from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0305_subject_priority_world_selection.py"
BASE_SHA256 = "f83490c90784634cbfc1b85076a319d3ec33d03404b14cd73ddc3448ee1219e0"
PARENT_DIGEST = "071bb37d271528138f156ce58775f41cea05ee2030fb61dd0db485eafa326579"
OT305_RECEIPT = "2941a2e3bc6410bf7a26adbfd7b320559ff3c8b25d947d53ce54842664efda43"
AUTHORITY = "ot-0306-priority-selected-world-contact"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0305 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0306_frozen_ot0305", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base305 = load_base()
b = base305.b
base270 = b.base281.base270


def write_json(path, value):
    base305.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0306").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        "open-subject-after-supported-stake-same-control.json",
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
    return repo, run, p82, runtime, parent, result305, package, result280, core, base130


def fixture_branch(root, parent, package, evaluation, result280, target, p82, runtime):
    decision = base270.fixture_decision(package, evaluation, target)
    seed = base270.seed_actor(root / "actor", parent, decision)
    checker = subprocess.run(
        ["python3", "check_expansion.py"], cwd=seed, capture_output=True
    )
    evaluated = base270.evaluate_workspace(seed, seed, parent)
    action = {
        "decision": decision,
        "binding": {
            "binding_digest": "a" * 64,
            "contact_identity": "b" * 64,
        },
    }
    pulse = {
        "authority": AUTHORITY + "-fixture-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": "expanded-select",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    intermediate = base270.compile_intermediate(parent, action, pulse, p82)
    world = base270.sealed_world(intermediate, action, package, result280, p82)
    final = base270.compile_world(intermediate, world, p82)
    return {
        "target": target,
        "path": evaluation["targets"][target],
        "checker": checker.returncode == 0,
        "semantic": evaluated["semantic"],
        "public": bool(evaluated["public"] and evaluated["public"]["all_valid"]),
        "public_only": base270.seed_excludes_sealed(seed, package, result280),
        "world_matches": world["result"]["matches"],
        "world_outcome": world["outcome"],
        "offer_consumed": intermediate.get("active_streamed_world_offer") is None,
        "new_epoch": len(intermediate["actor_authored_environment_epochs"])
        == len(parent["actor_authored_environment_epochs"]) + 1,
        "stake_exact": intermediate.get("active_world_seeking_stake")
        == parent.get("active_world_seeking_stake")
        and final.get("active_world_seeking_stake")
        == parent.get("active_world_seeking_stake"),
        "priority_receipts_exact": intermediate.get("subject_priority_contact_receipts")
        == parent.get("subject_priority_contact_receipts")
        and final.get("subject_priority_contact_receipts")
        == parent.get("subject_priority_contact_receipts"),
        "conformant": runtime.identity_conforms(intermediate)
        and runtime.identity_conforms(final),
        "routes_correction": b.base272.derive(final, p82) == "outward-correct",
    }


def preflight(root, p82, runtime, parent, result305, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    evaluation = base305.b.base281.with_evaluator(
        base305.b.base268.evaluate_package, package, p82.digest
    )
    branches = [
        fixture_branch(
            root / f"selection-{index:02d}",
            parent,
            package,
            evaluation,
            result280,
            target,
            p82,
            runtime,
        )
        for index, target in enumerate(sorted(evaluation["targets"]), 1)
    ]
    prompt_seed = base270.seed_actor(root / "prompt-neutrality", parent, base270.template())
    prompt = (prompt_seed / "README.md").read_text()
    priority = parent["subject_priority_contact_receipts"][-1]
    route, identity = b.base272.base265.floors(parent)
    source = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and b.base272.derive(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0305_split_verdict_preserved": result305["receipt_digest"]
        == OT305_RECEIPT
        and result305["operational_transition_passed"]
        and result305["observer_disposition"] == "rejected"
        and result305["e11"]
        == {
            "operational_contact": True,
            "subject_conditioned_choice": False,
            "priority_bearing_contact": False,
        },
        "same_world_control_preserved": priority["selected_world_id"]
        == priority["blind_control_world_id"]
        == package["world_id"],
        "active_offer_matches_exact_package": parent["active_streamed_world_offer"][
            "world_id"
        ]
        == package["world_id"]
        and parent["active_streamed_world_offer"]["public_package_digest"]
        == evaluation["public_package_digest"],
        "three_exact_2_of_6_surfaces": evaluation["valid"]
        and len(evaluation["targets"]) == 3
        and all(
            sum(row["matches"] for row in rows) == 2
            for rows in evaluation["rows"].values()
        ),
        "all_offer_consumption_branches_pass": len(branches) == 3
        and all(
            row["checker"]
            and row["semantic"]
            and row["public"]
            and row["public_only"]
            and row["world_matches"] == 2
            and row["world_outcome"] == "unresolved"
            and row["offer_consumed"]
            and row["new_epoch"]
            and row["stake_exact"]
            and row["priority_receipts_exact"]
            and row["conformant"]
            and row["routes_correction"]
            for row in branches
        ),
        "target_untold_prompt": not any(
            token in prompt
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "no_target_literal_in_harness": all(
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
        "source_ot0305_receipt_digest": result305["receipt_digest"],
        "world_full_package_digest": evaluation["full_package_digest"],
        "choice_count": len(branches),
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
            run / "preflight", p82, runtime, parent, result305, package, result280
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0306 unavailable")
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
    actor = base270.run_actor(context, p82, root / "actor", parent)
    intermediate = (
        base270.compile_intermediate(parent, actor, pulse, p82)
        if actor["accepted"]
        else parent
    )
    world = (
        base270.sealed_world(intermediate, actor, package, result280, p82)
        if actor["accepted"] and runtime.identity_conforms(intermediate)
        else None
    )
    final = base270.compile_world(intermediate, world, p82) if world else intermediate
    if world:
        write_json(root / "world-receipt.json", world)
    selected = actor.get("decision", {}).get("next_contact")
    stake_exact = final.get("active_world_seeking_stake") == parent.get(
        "active_world_seeking_stake"
    )
    priority_exact = final.get("subject_priority_contact_receipts") == parent.get(
        "subject_priority_contact_receipts"
    )
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "one_content_free_opening": pulse["content"] is None
        and pulse["derived_operation"] == "expanded-select",
        "one_fresh_actor_no_retry": True,
        "workspace_outside_repo": not (root / "actor").resolve().is_relative_to(repo),
        "actor_accepted": actor["accepted"],
        "g10_accepted": actor["g10_disposition"],
        "public_executable": bool(actor["public"] and actor["public"]["all_valid"]),
        "selected_offered_target": bool(
            selected
            and (selected["target_path"], selected["target_symbol"])
            in base270.offered_pairs(parent)
        ),
        "workspace_public_only": base270.seed_excludes_sealed(
            root / "actor" / "seed", package, result280
        ),
        "independent_2_of_6_contradiction": bool(
            world
            and world["result"]["all_valid"]
            and world["result"]["matches"] == 2
            and world["outcome"] == "unresolved"
        ),
        "offer_consumed_into_new_epoch": bool(
            world
            and final.get("active_streamed_world_offer") is None
            and len(final["actor_authored_environment_epochs"])
            == len(parent["actor_authored_environment_epochs"]) + 1
        ),
        "failed_priority_claim_preserved": stake_exact
        and priority_exact
        and result305["observer_disposition"] == "rejected"
        and result305["e11"]["priority_bearing_contact"] is False,
        "consequence_selects_correction": bool(
            world and b.base272.derive(final, p82) == "outward-correct"
        ),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "evaluation_epoch": result305["evaluation_epoch"],
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0305_receipt_digest": result305["receipt_digest"],
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
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
