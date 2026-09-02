from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0283_morrowglass_reachable_recurrence.py"
BASE_SHA256 = "dcb7bbba7bdb33e0f40a96141b29f1fb4d137697d2be0e261a7070531179e87b"
PARENT_DIGEST = "5cbf027863cc44fe52bbbb547bfbc7e3c5c0f0ecf992418ed25b4a977015cfbc"
OT283_RECEIPT = "5fc6d7f539bdfaeea1bc3d84af0a92c3ed57fae4c378ea4f7e0bce5a78899246"
AUTHORITY = "ot-0284-tideglass-second-renewal-cycle"
MAX_CALLS = 20


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0283 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0284_frozen_ot0283", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base283 = load_base()
b = base283.base282
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY
b.base274.MAX_CALLS = MAX_CALLS


def write_json(path, value):
    b.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0284").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0283", "open-subject-at-sixth-wait.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0283", "subject-blind-tideglass-world-package.json"
    )
    result283 = selector.load_artifact(
        p82, repo, store, "OT-0283", "morrowglass-reachable-recurrence-aggregate.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, package, result283, result280, core, base130


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
    return final, {
        "public_only": base270.seed_excludes_sealed(seed, package, result280),
        "matches": world["result"]["matches"],
        "outcome": world["outcome"],
        "conformant": runtime.identity_conforms(final),
        "routes_correction": b.base272.derive(final, p82) == "outward-correct",
    }


def prospective_suffix(root, subject, order, depths, package, result280, p82, runtime):
    current = subject
    corrections = []
    selections = []
    for index, depth in enumerate(depths):
        current, correction = b.correction_variant(
            current, depth, package, result280, p82, runtime
        )
        corrections.append(correction)
        current = b.base264.refresh_projection_only(current, p82)
        if index < len(order):
            selection = b.base272.selection_fixture(
                root / f"selection-{index}",
                current,
                package,
                result280,
                order[index],
                p82,
                runtime,
            )
            selections.append(selection)
            current = selection["final"]
    observation = b.base272.empty_feed_observation(current, p82)
    waiting, reused = b.base256.compile_wait(current, observation, p82)
    repeated_observation = b.base272.empty_feed_observation(waiting, p82)
    repeated, repeated_reused = b.base256.compile_wait(waiting, repeated_observation, p82)
    return {
        "corrections": all(
            row["feedback_passed"]
            and row["success_public"]
            and row["success_6_2"]
            and row["conformant"]
            and row["routes_refresh"]
            for row in corrections
        ),
        "selections": all(
            row["checker"]
            and row["semantic"]
            and row["world"]["result"]["matches"] == 2
            and row["routes_correction"]
            for row in selections
        ),
        "saturated": len(b.base244.remaining_epoch(repeated)) == 0,
        "seventh_wait": not reused
        and repeated_reused
        and len(repeated["world_stream_wait_receipts"]) == 7
        and len(repeated["world_stream_wait_discharge_receipts"]) == 6,
        "exact_reobserve": repeated["artifact_digest"] == waiting["artifact_digest"],
        "renewal_derived": b.base279.derive(repeated, [], p82) == "renew-world-feed",
        "renewal_preserved": repeated["active_standing_world_renewal"]
        == subject["active_standing_world_renewal"],
        "conformant": runtime.identity_conforms(repeated),
    }


def preflight(root, p82, runtime, parent, package, result283, result280):
    root.mkdir(parents=True, exist_ok=True)
    evaluation = b.base268.evaluate_package(package, p82.digest)
    observation, offered, reused = b.base281.wake(parent, package, p82)
    branches = []
    capacities = {target: base283.feedback_capacity(package, target, p82) for target in evaluation["targets"]}
    for first in sorted(evaluation["targets"]):
        selected, first_checks = selected_fixture(
            root / f"first-{first}", offered, first, package, evaluation, result280, p82, runtime
        )
        remaining = [target for target in sorted(evaluation["targets"]) if target != first]
        for order in itertools.permutations(remaining):
            for depths in itertools.product(*(range(capacities[target] + 1) for target in (first, *order))):
                suffix = prospective_suffix(
                    root / (first + "-" + "-".join(order) + "-" + "".join(map(str, depths))),
                    selected,
                    order,
                    depths,
                    package,
                    result280,
                    p82,
                    runtime,
                )
                branches.append({"first": first, "order": list(order), "depths": list(depths), "first_checks": first_checks, **suffix})
    route, identity = b.base272.base265.floors(parent)
    script = Path(__file__).read_text()
    seed = b.base268.seed_actor(root / "provider-seed", b.base268.EXAMPLE)
    corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_sixth_wait": parent["artifact_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "wait-provider"
        and len(parent["world_stream_wait_receipts"]) == 6
        and len(parent["world_stream_wait_discharge_receipts"]) == 5
        and runtime.identity_conforms(parent),
        "ot0283_exact_promotion": result283["receipt_digest"] == OT283_RECEIPT
        and result283["observer_disposition"] == "promoted"
        and result283["final_subject_digest"] == PARENT_DIGEST
        and result283["next_world_full_package_digest"] == evaluation["full_package_digest"],
        "wake_exact_actor_free": observation["status"] == "world-available"
        and not reused
        and offered["active_world_stream_wait"] is None
        and len(offered["world_stream_wait_discharge_receipts"]) == 6
        and offered["local_frontier_ledger"] == parent["local_frontier_ledger"],
        "three_exact_2_of_6_surfaces": evaluation["valid"]
        and len(evaluation["targets"]) == 3
        and all(sum(row["matches"] for row in rows) == 2 for rows in evaluation["rows"].values()),
        "capacities_exact": sorted(capacities.values()) == [2, 2, 2],
        "one_hundred_sixty_two_complete_branches": len(branches) == 162,
        "all_complete_branches_pass": all(
            all(row["first_checks"].values())
            and row["corrections"]
            and row["selections"]
            and row["saturated"]
            and row["seventh_wait"]
            and row["exact_reobserve"]
            and row["renewal_derived"]
            and row["renewal_preserved"]
            and row["conformant"]
            for row in branches
        ),
        "dynamic_world_not_hardcoded": package["world_id"] not in script
        and all(token not in script for target, path in evaluation["targets"].items() for token in (target, path)),
        "provider_seed_excludes_lineage": PARENT_DIGEST not in corpus
        and all(target not in corpus for target in parent["local_frontier_ledger"]["targets"]),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "branch_count": len(branches),
        "feedback_capacities": capacities,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def derive(subject, results, package, p82):
    if subject.get("active_streamed_world_offer"):
        return "expanded-select"
    operation = b.base272.derive(subject, p82)
    if operation == "wait-provider":
        evaluation = b.base268.evaluate_package(package, p82.digest)
        scan = b.base267.scan_feed(subject, [evaluation["public_package"]], p82.digest)
        if scan["status"] == "world-available":
            return "wake-world"
        if results and results[-1]["transition"] == "wait-provider" and results[-1]["checks"].get("wait_exact_noop") is True:
            return b.base279.derive(subject, [], p82)
    return operation


def valid_shape(operations, correction_transitions):
    if operations[:2] != ["wake-world", "expanded-select"]:
        return False
    index = 2
    transitions = list(correction_transitions)
    for group in range(3):
        count = 0
        while index < len(operations) and operations[index] == "outward-correct":
            count += 1
            index += 1
        if not 1 <= count <= 3:
            return False
        if transitions[: count - 1] != ["unresolved-to-more-correction"] * (count - 1) or transitions[count - 1 : count] != ["success-to-refresh"]:
            return False
        transitions = transitions[count:]
        if index >= len(operations) or operations[index] != "refresh-opportunity-projection":
            return False
        index += 1
        if group < 2:
            if index >= len(operations) or operations[index] != "expanded-select":
                return False
            index += 1
    return operations[index:] == ["expand-environment", "wait-provider", "renew-world-feed"] and not transitions


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [json.loads(path.read_text()) for path in sorted(run.glob("invocation-*-result.json"))]
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    provider = rows[-1]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_cycle": len(rows) <= MAX_CALLS and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "world_routed_operation_shape": valid_shape(operations, [row["transition"] for row in corrections]),
        "three_selections": operations.count("expanded-select") == 3,
        "actor_count_matches": sum(row["fresh_actor_count"] for row in rows) == 4 + len(corrections),
        "tideglass_saturated": len(b.base244.remaining_epoch(final)) == 0,
        "seventh_wait_exact": len(final["world_stream_wait_receipts"]) == 7
        and len(final["world_stream_wait_discharge_receipts"]) == 6
        and b.base272.derive(final, p82) == "wait-provider",
        "renewal_provider_promoted": provider["transition"] == "renew-world-feed"
        and provider["actor"]["accepted"]
        and provider["checks"]["next_world_available"],
        "final_open_conformant": final["continuation"]["status"] == "open" and runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "checks": gates,
        "operations": operations,
        "correction_transitions": [row["transition"] for row in corrections],
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": sum(row["fresh_actor_count"] for row in rows),
        "next_world_id": provider["actor"]["package"].get("world_id"),
        "next_world_full_package_digest": provider["actor"]["evaluation"].get("full_package_digest"),
        "next_world_public_package_digest": provider["actor"]["evaluation"].get("public_package_digest"),
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    write_json(run / "next-world-package.json", provider["actor"]["package"])
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def advance(repo, run, p82, runtime, parent, package, result280, fixtures, core, base130):
    result_paths = sorted(run.glob("invocation-*-result.json"))
    results = [json.loads(path.read_text()) for path in result_paths]
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0284 invocation")
    if (run / "aggregate.json").exists() or not fixtures["checks"]["passed"]:
        raise SystemExit("OT-0284 unavailable")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0284 checkpoint")
    operation = derive(subject, results, package, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {"authority": AUTHORITY + "-pulse", "content": None, "source_subject_digest": subject["artifact_digest"], "derived_operation": operation}
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    final = subject
    transition = operation
    checks = {"content_free": True}
    context = b.base274.context_for(core, base130, runtime, root, repo)
    if operation == "wake-world":
        world, final, reused = b.base281.wake(subject, package, p82)
        checks.update(zero_fresh_actors=True, scanner_found_only_world=world["status"] == "world-available" and len(world["catalog"]) == 1, sixth_wait_discharged=not reused and len(final["world_stream_wait_discharge_receipts"]) == 6, renewal_preserved=final["active_standing_world_renewal"] == subject["active_standing_world_renewal"], next_is_expansion=bool(final.get("active_streamed_world_offer")))
    elif operation == "expanded-select" and subject.get("active_streamed_world_offer"):
        base270 = b.base281.base270
        actor = base270.run_actor(context, p82, root / "actor", subject)
        intermediate = base270.compile_intermediate(subject, actor, pulse, p82) if actor["accepted"] else subject
        world = base270.sealed_world(intermediate, actor, package, result280, p82) if actor["accepted"] else None
        final = base270.compile_world(intermediate, world, p82) if world else intermediate
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], retained_package_2_of_6=bool(world and world["result"]["matches"] == 2), next_is_correction=b.base272.derive(final, p82) == "outward-correct")
    elif operation == "expanded-select":
        actor, world, final = b.base272.live_selection(context, p82, root, subject, package, result280)
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], retained_package_2_of_6=bool(world and world["result"]["matches"] == 2), next_is_correction=b.base272.derive(final, p82) == "outward-correct")
    elif operation == "outward-correct":
        _, actor, world, feedback, final, transition = b.base274.run_correction(context, p82, root, subject, package, result280)
        public_count = actor["public"]["case_count"] if actor and actor.get("public") else 0
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], disclosed_all_pass=bool(actor["public"] and actor["public"]["matches"] == public_count), unchanged_2_of_6=bool(world and world["unchanged_control"]["matches"] == 2), consequence_routes=transition in {"success-to-refresh", "unresolved-to-more-correction"}, next_matches_consequence=b.base272.derive(final, p82) == ("refresh-opportunity-projection" if transition == "success-to-refresh" else "outward-correct"))
    elif operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82)
        checks.update(zero_fresh_actors=True, projection_fresh=not b.base260.needs_refresh(final, p82), next_derived=b.base272.derive(final, p82) in {"expanded-select", "expand-environment"})
    elif operation == "expand-environment":
        world = b.base272.empty_feed_observation(subject, p82)
        final, reused = b.base256.compile_wait(subject, world, p82)
        checks.update(zero_fresh_actors=True, saturated=len(b.base244.remaining_epoch(subject)) == 0, seventh_wait_installed=not reused and len(final["world_stream_wait_receipts"]) == 7 and len(final["world_stream_wait_discharge_receipts"]) == 6, next_is_wait=b.base272.derive(final, p82) == "wait-provider")
    elif operation == "wait-provider":
        world = b.base272.empty_feed_observation(subject, p82)
        final, reused = b.base256.compile_wait(subject, world, p82)
        checks.update(zero_fresh_actors=True, wait_exact_noop=reused and final["artifact_digest"] == subject["artifact_digest"], renewal_next=b.base279.derive(final, [], p82) == "renew-world-feed")
    elif operation == "renew-world-feed":
        actor = b.run_provider(context, p82, root, subject)
        evaluation = actor["evaluation"]
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], exact_one_file_effect=actor["audit"]["exact_changes"] and actor["audit"]["changed_paths"] == ["world-package.json"], three_novel_targets=bool(evaluation.get("valid") and len(evaluation["targets"]) == 3 and not actor["target_collision"] and not actor["world_collision"]), all_three_exact_2_of_6=bool(evaluation.get("valid") and all(sum(row["matches"] for row in rows) == 2 for rows in evaluation["rows"].values())), next_world_available=bool(actor["scanner_observation"] and actor["scanner_observation"]["status"] == "world-available"), subject_exact_during_provision=final["artifact_digest"] == subject["artifact_digest"])
    else:
        checks["known_operation"] = False
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"
    checks["identity_conformant"] = runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    public_actor = copy.deepcopy(actor)
    if operation == "renew-world-feed" and public_actor:
        package_value = public_actor.pop("package")
        write_json(root / "world-package.json", package_value)
        public_actor["package"] = package_value
    result = {"authority": AUTHORITY + f"-invocation-{index:02d}", "invocation_index": index, "source_subject_digest": subject["artifact_digest"], "pulse": pulse, "transition": transition, "actor": public_actor, "world": world, "feedback": feedback, "checks": checks, "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1 if actor else 0}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if operation != "renew-world-feed":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, final)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, package, result283, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(run / "preflight", p82, runtime, parent, package, result283, result280)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(repo, run, p82, runtime, parent, package, result280, fixtures, core, base130)


if __name__ == "__main__":
    raise SystemExit(main())
