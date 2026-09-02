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
BASE_PATH = ROOT / "ot_0290_role_neutral_invalidity_recovery.py"
BASE_SHA256 = "f99aa67866836d70c1ba02284b4adb930ba13d30a9fac64108de66e76aaaca2a"
PARENT_DIGEST = "313a735cde558357ddd06b02d054388802695e37f9f7b56b13c1fc1ea358b312"
OT290_RECEIPT = "b537f4689693474e9e53bc9eda47eea20ea0dfc4628cf6fe36895d9a462676fc"
AUTHORITY = "ot-0291-recovered-world-wake-and-selection"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0290 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0291_frozen_ot0290", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base290 = load_base()
b = base290.b
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base290.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0291").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0290", "open-subject-after-provider-recovery.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json"
    )
    result290 = selector.load_artifact(
        p82, repo, store, "OT-0290", "role-neutral-invalidity-recovery-aggregate.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, package, result290, result280, core, base130


def wake(subject, package, p82):
    evaluation = b.base268.evaluate_package(package, p82.digest)
    observation = b.base267.scan_feed(
        subject, [evaluation["public_package"]], p82.digest
    )
    final, reused = b.base281.base270.compile_offer(subject, observation, p82)
    return evaluation, observation, final, reused


def selected_fixture(root, offered, target, package, evaluation, result280, p82, runtime):
    base270 = b.base281.base270
    decision = base270.fixture_decision(package, evaluation, target)
    seed = base270.seed_actor(root / "actor", offered, decision)
    action = {
        "decision": decision,
        "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
    }
    pulse = {
        "authority": AUTHORITY + "-fixture-pulse",
        "content": None,
        "source_subject_digest": offered["artifact_digest"],
        "derived_operation": "expanded-select",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    intermediate = base270.compile_intermediate(offered, action, pulse, p82)
    world = base270.sealed_world(intermediate, action, package, result280, p82)
    final = base270.compile_world(intermediate, world, p82)
    return {
        "public_only": base270.seed_excludes_sealed(seed, package, result280),
        "matches": world["result"]["matches"],
        "outcome": world["outcome"],
        "conformant": runtime.identity_conforms(final),
        "routes_correction": b.base272.derive(final, p82) == "outward-correct",
        "scars_exact": final.get("invalid_encounter_scars")
        == offered.get("invalid_encounter_scars"),
        "recoveries_exact": final.get("invalid_encounter_recovery_receipts")
        == offered.get("invalid_encounter_recovery_receipts"),
    }


def preflight(root, p82, runtime, parent, package, result290, result280):
    root.mkdir(parents=True, exist_ok=True)
    evaluation, observation, offered, reused = wake(parent, package, p82)
    branches = [
        selected_fixture(
            root / f"selection-{index}",
            offered,
            target,
            package,
            evaluation,
            result280,
            p82,
            runtime,
        )
        for index, target in enumerate(sorted(evaluation["targets"]))
    ]
    route, identity = b.base272.base265.floors(parent)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_recovered_wait": parent["artifact_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "wait-provider"
        and len(parent["world_stream_wait_receipts"]) == 7
        and len(parent["world_stream_wait_discharge_receipts"]) == 6
        and parent.get("active_invalid_encounter_reopening") is None
        and runtime.identity_conforms(parent),
        "ot0290_exact_promotion": result290["receipt_digest"] == OT290_RECEIPT
        and result290["observer_disposition"] == "promoted"
        and result290["final_subject_digest"] == PARENT_DIGEST
        and result290["next_world_full_package_digest"]
        == evaluation["full_package_digest"],
        "three_exact_2_of_6_surfaces": evaluation["valid"]
        and len(evaluation["targets"]) == 3
        and all(
            sum(row["matches"] for row in rows) == 2
            for rows in evaluation["rows"].values()
        ),
        "wake_exact_actor_free": observation["status"] == "world-available"
        and len(observation["catalog"]) == 1
        and not reused
        and offered["active_world_stream_wait"] is None
        and len(offered["world_stream_wait_discharge_receipts"]) == 7
        and offered["local_frontier_ledger"] == parent["local_frontier_ledger"]
        and bool(offered.get("active_streamed_world_offer")),
        "invalidity_lineage_exact_after_wake": offered.get("invalid_encounter_scars")
        == parent.get("invalid_encounter_scars")
        and offered.get("invalid_encounter_recovery_receipts")
        == parent.get("invalid_encounter_recovery_receipts"),
        "three_complete_choice_branches": len(branches) == 3
        and all(
            row["public_only"]
            and row["matches"] == 2
            and row["outcome"] == "unresolved"
            and row["conformant"]
            and row["routes_correction"]
            and row["scars_exact"]
            and row["recoveries_exact"]
            for row in branches
        ),
        "dynamic_world_not_hardcoded": package["world_id"] not in script
        and all(
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
        "world_full_package_digest": evaluation["full_package_digest"],
        "choice_count": len(branches),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_content_free_openings": len(rows) == 2
        and all(row["pulse"]["content"] is None for row in rows),
        "wake_then_selection": [row["transition"] for row in rows]
        == ["wake-world", "expanded-select"],
        "one_fresh_selector": sum(row["fresh_actor_count"] for row in rows) == 1,
        "all_invocations_passed": all(row["checks"]["passed"] for row in rows),
        "correction_live": b.base272.derive(final, p82) == "outward-correct",
        "invalidity_lineage_exact": final.get("invalid_encounter_scars")
        == parent.get("invalid_encounter_scars")
        and final.get("invalid_encounter_recovery_receipts")
        == parent.get("invalid_encounter_recovery_receipts"),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, package, result290, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, package, result290, result280)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0291 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0291 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index not in {1, 2} or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0291 checkpoint")
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    operation = "wake-world" if index == 1 else b.base272.derive(subject, p82)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = None
    context = b.base274.context_for(core, base130, runtime, root, repo)
    if operation == "wake-world":
        _, world, final, reused = wake(subject, package, p82)
        checks = {
            "content_free": True,
            "zero_fresh_actors": True,
            "scanner_found_only_world": world["status"] == "world-available"
            and len(world["catalog"]) == 1,
            "seventh_wait_discharged": not reused
            and len(final["world_stream_wait_discharge_receipts"]) == 7,
            "next_is_expansion": bool(final.get("active_streamed_world_offer")),
            "invalidity_lineage_exact": final.get("invalid_encounter_scars")
            == subject.get("invalid_encounter_scars")
            and final.get("invalid_encounter_recovery_receipts")
            == subject.get("invalid_encounter_recovery_receipts"),
        }
    elif operation == "expanded-select" and subject.get("active_streamed_world_offer"):
        base270 = b.base281.base270
        actor = base270.run_actor(context, p82, root / "actor", subject)
        intermediate = (
            base270.compile_intermediate(subject, actor, pulse, p82)
            if actor["accepted"]
            else subject
        )
        world = (
            base270.sealed_world(intermediate, actor, package, result280, p82)
            if actor["accepted"]
            else None
        )
        final = base270.compile_world(intermediate, world, p82) if world else intermediate
        checks = {
            "content_free": True,
            "workspace_outside_repo": not (root / "actor").resolve().is_relative_to(repo),
            "actor_accepted": actor["accepted"],
            "g10_accepted": actor["g10_disposition"],
            "public_seed_only": base270.seed_excludes_sealed(
                root / "actor" / "seed", package, result280
            ),
            "retained_package_2_of_6": bool(world and world["result"]["matches"] == 2),
            "next_is_correction": b.base272.derive(final, p82) == "outward-correct",
            "invalidity_lineage_exact": final.get("invalid_encounter_scars")
            == subject.get("invalid_encounter_scars")
            and final.get("invalid_encounter_recovery_receipts")
            == subject.get("invalid_encounter_recovery_receipts"),
        }
    else:
        final = subject
        checks = {"known_operation": False}
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"
    checks["identity_conformant"] = runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": operation,
        "actor": copy.deepcopy(actor),
        "world": world,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1 if actor else 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if index == 1:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, final)


if __name__ == "__main__":
    raise SystemExit(main())
