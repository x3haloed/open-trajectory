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
BASE_PATH = ROOT / "ot_0286_invalid_encounter_scar_reopening.py"
BASE_SHA256 = "df33b9486b1b1aa3743ea8cb6341b82dd2fd036e03cc457a2ddf94b64c335b35"
PARENT_DIGEST = "ce54ab326313a02226976571d37f5fe48db80bcf5044d10b87a680ac4bfcdc37"
OT286_RECEIPT = "5622b7b318d77551534c84043ed3b2a6ae06ecf8184b862b80f00a2d806d92af"
AUTHORITY = "ot-0287-post-invalidity-tideglass-recurrence"
MAX_CALLS = 18


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0286 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0287_frozen_ot0286", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base286 = load_base()
b = base286.b
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY
b.base274.MAX_CALLS = MAX_CALLS


def write_json(path, value):
    base286.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0287").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0286", "open-subject-after-invalidity-recovery-feedback.json"
    )
    result286 = selector.load_artifact(
        p82, repo, store, "OT-0286", "invalid-encounter-scar-reopening-aggregate.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0283", "subject-blind-tideglass-world-package.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result286, package, result280, core, base130


def feedback_capacity(subject, package, target, p82):
    disclosed = {
        p82.digest(row["input"])
        for row in subject.get("active_correction_disclosure", {}).get("cases", [])
    }
    return len(
        {
            p82.digest(row["input"])
            for row in package["sealed_cases"][target]
        }
        - disclosed
    )


def prospective_branch(root, parent, order, depths, package, result280, p82, runtime):
    current = parent
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
    repeated, repeated_reused = b.base256.compile_wait(
        waiting, repeated_observation, p82
    )
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
        "exact_reobserve": repeated["artifact_digest"]
        == waiting["artifact_digest"],
        "renewal_derived": b.base279.derive(repeated, [], p82)
        == "renew-world-feed",
        "scar_preserved": repeated["invalid_encounter_scars"]
        == parent["invalid_encounter_scars"]
        and repeated["active_invalid_encounter_reopening_policy"]
        == parent["active_invalid_encounter_reopening_policy"],
        "conformant": runtime.identity_conforms(repeated),
    }


def preflight(root, p82, runtime, parent, result286, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    evaluation = b.base268.evaluate_package(package, p82.digest)
    active = parent["active_correction_disclosure"]["target_symbol"]
    first_capacity = feedback_capacity(parent, package, active, p82)
    completed, _ = b.correction_variant(
        parent, 0, package, result280, p82, runtime
    )
    refreshed = b.base264.refresh_projection_only(completed, p82)
    remaining = [
        row["target_symbol"]
        for row in refreshed["active_opportunity_projection"]["opportunities"]
    ]
    capacities = {
        target: base286.base285.base284.base283.feedback_capacity(
            package, target, p82
        )
        for target in remaining
    }
    capacities[active] = first_capacity
    branches = []
    for order in itertools.permutations(remaining):
        for depths in itertools.product(
            *(range(capacities[target] + 1) for target in (active, *order))
        ):
            try:
                branch = prospective_branch(
                    root / ("-".join(order) + "-" + "".join(map(str, depths))),
                    parent,
                    order,
                    depths,
                    package,
                    result280,
                    p82,
                    runtime,
                )
            except RuntimeError as error:
                branch = {
                    "constructed": False,
                    "error_type": type(error).__name__,
                    "error_digest": p82.digest(str(error)),
                }
            branches.append(branch)
    route, identity = b.base272.base265.floors(parent)
    script = Path(__file__).read_text()
    seed = b.base268.seed_actor(root / "provider-seed", b.base268.EXAMPLE)
    corpus = "\n".join(
        path.read_text(errors="replace")
        for path in seed.rglob("*")
        if path.is_file()
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_post_recovery": parent["artifact_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0286_exact_promotion": result286["receipt_digest"] == OT286_RECEIPT
        and result286["observer_disposition"] == "promoted"
        and result286["final_subject_digest"] == PARENT_DIGEST,
        "current_contact_five_cases": parent["active_correction_disclosure"][
            "case_count"
        ]
        == 5,
        "reachable_capacities_exact": sorted(capacities.values()) == [1, 2, 2],
        "thirty_six_complete_branches": len(branches) == 36
        and len(remaining) == 2,
        "all_reachable_branches_pass": all(all(row.values()) for row in branches),
        "scar_and_policy_present": len(parent["invalid_encounter_scars"]) == 1
        and parent["active_invalid_encounter_reopening_policy"][
            "invalid_content_authority"
        ]
        is False,
        "dynamic_world_not_hardcoded": package["world_id"] not in script
        and all(
            token not in script
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "provider_seed_excludes_lineage": PARENT_DIGEST not in corpus
        and all(
            target not in corpus
            for target in parent["local_frontier_ledger"]["targets"]
        ),
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


def valid_shape(operations, transitions):
    index = 0
    transitions = list(transitions)
    for group in range(3):
        count = 0
        while index < len(operations) and operations[index] == "outward-correct":
            count += 1
            index += 1
        if not 1 <= count <= 3:
            return False
        if transitions[: count - 1] != ["unresolved-to-more-correction"] * (
            count - 1
        ) or transitions[count - 1 : count] != ["success-to-refresh"]:
            return False
        transitions = transitions[count:]
        if index >= len(operations) or operations[index] != "refresh-opportunity-projection":
            return False
        index += 1
        if group < 2:
            if index >= len(operations) or operations[index] != "expanded-select":
                return False
            index += 1
    return operations[index:] == [
        "expand-environment",
        "wait-provider",
        "renew-world-feed",
    ] and not transitions


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [
        row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"
    ]
    provider = rows[-1]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_cycle": len(rows) <= MAX_CALLS
        and all(
            row["pulse"]["content"] is None and row["checks"]["passed"]
            for row in rows
        ),
        "world_routed_operation_shape": valid_shape(
            operations, [row["transition"] for row in corrections]
        ),
        "two_selections": operations.count("expanded-select") == 2,
        "actor_count_matches": sum(row["fresh_actor_count"] for row in rows)
        == 3 + len(corrections),
        "tideglass_saturated": len(b.base244.remaining_epoch(final)) == 0,
        "seventh_wait_exact": len(final["world_stream_wait_receipts"]) == 7
        and len(final["world_stream_wait_discharge_receipts"]) == 6
        and b.base272.derive(final, p82) == "wait-provider",
        "scar_preserved": final["invalid_encounter_scars"]
        == parent["invalid_encounter_scars"]
        and final["active_invalid_encounter_reopening_policy"]
        == parent["active_invalid_encounter_reopening_policy"],
        "renewal_provider_promoted": provider["transition"]
        == "renew-world-feed"
        and provider["actor"]["accepted"]
        and provider["checks"]["next_world_available"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
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
        "next_world_full_package_digest": provider["actor"]["evaluation"].get(
            "full_package_digest"
        ),
        "next_world_public_package_digest": provider["actor"]["evaluation"].get(
            "public_package_digest"
        ),
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
        raise SystemExit("preserve failed OT-0287 invocation")
    if (run / "aggregate.json").exists() or not fixtures["checks"]["passed"]:
        raise SystemExit("OT-0287 unavailable")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0287 checkpoint")
    operation = b.derived_operation(subject, results, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    final = subject
    transition = operation
    checks = {"content_free": True}
    context = b.base274.context_for(core, base130, runtime, root, repo)
    if operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82)
        checks.update(
            zero_fresh_actors=True,
            projection_fresh=not b.base260.needs_refresh(final, p82),
            next_derived=b.base272.derive(final, p82)
            in {"expanded-select", "expand-environment"},
        )
    elif operation == "expanded-select":
        actor, world, final = b.base272.live_selection(
            context, p82, root, subject, package, result280
        )
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            retained_package_2_of_6=bool(
                world and world["result"]["matches"] == 2
            ),
            next_is_correction=b.base272.derive(final, p82) == "outward-correct",
        )
    elif operation == "outward-correct":
        _, actor, world, feedback, final, transition = b.base274.run_correction(
            context, p82, root, subject, package, result280
        )
        public_count = (
            actor["public"]["case_count"] if actor and actor.get("public") else 0
        )
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            disclosed_all_pass=bool(
                actor["public"] and actor["public"]["matches"] == public_count
            ),
            unchanged_2_of_6=bool(
                world and world["unchanged_control"]["matches"] == 2
            ),
            consequence_routes=transition
            in {"success-to-refresh", "unresolved-to-more-correction"},
            next_matches_consequence=b.base272.derive(final, p82)
            == (
                "refresh-opportunity-projection"
                if transition == "success-to-refresh"
                else "outward-correct"
            ),
        )
    elif operation == "expand-environment":
        world = b.base272.empty_feed_observation(subject, p82)
        final, reused = b.base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            saturated=len(b.base244.remaining_epoch(subject)) == 0,
            seventh_wait_installed=not reused
            and len(final["world_stream_wait_receipts"]) == 7
            and len(final["world_stream_wait_discharge_receipts"]) == 6,
            next_is_wait=b.base272.derive(final, p82) == "wait-provider",
        )
    elif operation == "wait-provider":
        world = b.base272.empty_feed_observation(subject, p82)
        final, reused = b.base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            wait_exact_noop=reused
            and final["artifact_digest"] == subject["artifact_digest"],
            renewal_next=b.base279.derive(final, [], p82) == "renew-world-feed",
        )
    elif operation == "renew-world-feed":
        actor = b.run_provider(context, p82, root, subject)
        evaluation = actor["evaluation"]
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            exact_one_file_effect=actor["audit"]["exact_changes"]
            and actor["audit"]["changed_paths"] == ["world-package.json"],
            three_novel_targets=bool(
                evaluation.get("valid")
                and len(evaluation["targets"]) == 3
                and not actor["target_collision"]
                and not actor["world_collision"]
            ),
            all_three_exact_2_of_6=bool(
                evaluation.get("valid")
                and all(
                    sum(row["matches"] for row in rows) == 2
                    for rows in evaluation["rows"].values()
                )
            ),
            next_world_available=bool(
                actor["scanner_observation"]
                and actor["scanner_observation"]["status"] == "world-available"
            ),
            subject_exact_during_provision=final["artifact_digest"]
            == subject["artifact_digest"],
        )
    else:
        checks["known_operation"] = False
    checks["scar_preserved"] = (
        final["invalid_encounter_scars"] == parent["invalid_encounter_scars"]
    )
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"
    checks["identity_conformant"] = runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    public_actor = copy.deepcopy(actor)
    if operation == "renew-world-feed" and public_actor:
        package_value = public_actor.pop("package")
        write_json(root / "world-package.json", package_value)
        public_actor["package"] = package_value
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": public_actor,
        "world": world,
        "feedback": feedback,
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
    repo, run, p82, runtime, parent, result286, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight", p82, runtime, parent, result286, package, result280
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result280,
        fixtures,
        core,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
