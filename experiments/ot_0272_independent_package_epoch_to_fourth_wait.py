from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0271_descriptor_derived_independent_package_correction.py"
BASE_SHA256 = "22c477f27ebb9fb15826ba7b5589f5a31a8ee7dd0464b17b9763087cf1ed6515"
PARENT_DIGEST = "cc0d83441283f4b25125ab20375ca7b58514b8f89d7d1cc7dd3c2fa380c69eb9"
OT271_RECEIPT = "453c87cec19391db2bb6772d8902264743431c8fcec5c6d07650aa5d4d2d5a98"
OT268_RECEIPT = "7026047afea9989082ac529770c934b3c63512ebc2de03d6c7d715d74c1743d1"
AUTHORITY = "ot-0272-independent-package-epoch-to-fourth-wait"
PULSE = None
EXPECTED = (
    "expanded-select",
    "outward-correct",
    "refresh-opportunity-projection",
    "expanded-select",
    "outward-correct",
    "refresh-opportunity-projection",
    "expand-environment",
    "wait-provider",
)


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0271 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0272_frozen_ot0271", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base271 = load_base()
base270 = base271.base270
base269 = base271.base269
base268 = base271.base268
base265 = base271.base265
base264 = base271.base264
base261 = base271.base261
base260 = base271.base260
base244 = base271.base244
base256 = base269.base256
base252 = base269.base252
base245 = base252.base245
base242 = base252.base242
authority_base = base271.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def recurring_selected(subject):
    extension = subject["actor_authored_environment_extensions"][-1]
    pending = subject["pending_contact_bearing_continuations"][-1]
    epoch = subject["actor_authored_environment_epochs"][-1]
    wanted = pending.get("world_receipt_digest")
    world = None
    for collection in (
        "cross_epoch_world_receipts",
        "retained_epoch_world_receipts",
        "environment_expansion_world_receipts",
        "outward_world_receipts",
    ):
        for row in reversed(subject.get(collection, [])):
            if row.get("receipt_digest") == wanted:
                world = row
                break
        if world:
            break
    if world is None:
        raise RuntimeError("unresolved recurring world receipt unavailable")
    target = extension["target_symbol"]
    path = extension["target_path"]
    descriptor = epoch.get("visible_sources", {}).get(path)
    if not (
        target == pending["package"]["target_symbol"] == world["target_symbol"]
        and path == pending["package"]["target_path"] == world["target_path"]
        and isinstance(descriptor, dict)
        and target in descriptor.get("top_level_callables", [])
        and extension["environment_id"] == epoch["environment_id"]
    ):
        raise RuntimeError("recurring descriptor correction state misaligned")
    return extension, pending, world, epoch, target, path


# OT-0271's first-contact resolver also equated the epoch's original selected
# target with the latest retained-epoch selection. Preserve its promoted result,
# but use the actual recurring authorities prospectively: extension, pending
# contact, receipted world, and the latest epoch source descriptor.
base271.selected = recurring_selected


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0272").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0271", "open-subject-at-independent-package-selection.json"
    )
    result271 = selector_base.load_artifact(
        p82, repo, store, "OT-0271", "descriptor-derived-independent-package-correction-aggregate.json"
    )
    package = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-three-lantern-world-package.json"
    )
    result268 = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-world-package-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result271, package, result268, base, base130


def derive(subject, p82):
    return base271.derive(subject, p82)


def projected_pairs(subject):
    return {
        (row["target_path"], row["target_symbol"])
        for row in subject["active_opportunity_projection"]["opportunities"]
    }


def current_correction_seed_is_public_only(seed, package, target, path):
    files = [candidate for candidate in seed.rglob("*") if candidate.is_file()]
    corpus = "\n".join(candidate.read_text(errors="replace") for candidate in files)
    return (
        package["sealed_reference_sources"][path] not in corpus
        and json.dumps(package["sealed_cases"][target], sort_keys=True) not in corpus
    )


def selection_fixture(root, subject, package, result268, target, p82, runtime):
    evaluation = base268.evaluate_package(package, p82.digest)
    decision = base270.fixture_decision(package, evaluation, target)
    seed = base252.selection_seed(root / "actor", subject, decision)
    checker = subprocess.run(
        ["python3", "check_selection.py"], cwd=seed, capture_output=True
    )
    evaluated = base252.evaluate_selection_workspace(seed, seed, subject)
    action = {
        "decision": decision,
        "binding": {
            "binding_digest": "a" * 64,
            "contact_identity": "b" * 64,
        },
    }
    intermediate = base245.compile_intermediate(subject, action, p82)
    world = base270.sealed_world(intermediate, action, package, result268, p82)
    final = base245.compile_world(intermediate, world, p82)
    return {
        "target": target,
        "path": evaluation["targets"][target],
        "checker": checker.returncode == 0,
        "semantic": evaluated["semantic"],
        "public": bool(evaluated["public"] and evaluated["public"]["all_valid"]),
        "world": world,
        "final": final,
        "conformant": runtime.identity_conforms(intermediate)
        and runtime.identity_conforms(final),
        "routes_correction": derive(final, p82) == "outward-correct",
        "prompt_neutral": target not in (seed / "README.md").read_text()
        and evaluation["targets"][target] not in (seed / "README.md").read_text(),
    }


def correction_fixture(root, subject, package, result268, p82, runtime):
    evaluation = base268.evaluate_package(package, p82.digest)
    extension, _, _, _, target, path = base271.selected(subject)
    decision = base271.decision_template(subject)
    decision.update(
        rationale="Revise the selected visible policy to satisfy bounded correction contact.",
        next_pursuit="Assimilate the corrected package surface and continue.",
    )
    seed = base271.seed_actor(root / "actor", subject, package, evaluation, decision)
    workspace = root / "workspace"
    shutil.copytree(seed, workspace)
    (workspace / path).write_text(package["sealed_reference_sources"][path])
    checker = subprocess.run(
        ["python3", "check_correction.py"], cwd=workspace, capture_output=True
    )
    evaluated = base271.evaluate_workspace(seed, workspace, subject)
    action = {
        "decision": decision,
        "binding": {
            "binding_digest": "c" * 64,
            "patched_source": evaluated["source"],
            "patched_source_digest": p82.digest(evaluated["source"]),
        },
    }
    world = base271.sealed_followup(subject, action, package, result268, p82)
    corrected = base271.compile_correction(subject, action, world, p82)
    refreshed = base264.refresh_projection_only(corrected, p82)
    return {
        "target": target,
        "path": path,
        "checker": checker.returncode == 0,
        "semantic": evaluated["semantic"],
        "public": evaluated["public"],
        "world": world,
        "corrected": corrected,
        "refreshed": refreshed,
        "seed_public_only": current_correction_seed_is_public_only(
            seed, package, target, path
        ),
        "conformant": runtime.identity_conforms(corrected)
        and runtime.identity_conforms(refreshed),
        "routes_refresh": derive(corrected, p82) == "refresh-opportunity-projection",
    }


def empty_feed_observation(subject, p82):
    return base269.empty_feed_observation(subject, p82)


def prospective_branch(root, parent, package, result268, order, p82, runtime):
    subject = parent
    steps = []
    for index, target in enumerate(order, 1):
        selection = selection_fixture(
            root / f"selection-{index}",
            subject,
            package,
            result268,
            target,
            p82,
            runtime,
        )
        subject = selection["final"]
        correction = correction_fixture(
            root / f"correction-{index}",
            subject,
            package,
            result268,
            p82,
            runtime,
        )
        subject = correction["refreshed"]
        steps.append(
            {
                "target": target,
                "selection_checker": selection["checker"],
                "selection_semantic": selection["semantic"],
                "selection_public": selection["public"],
                "selection_matches": selection["world"]["result"]["matches"],
                "selection_conformant": selection["conformant"],
                "selection_routes_correction": selection["routes_correction"],
                "selection_prompt_neutral": selection["prompt_neutral"],
                "correction_checker": correction["checker"],
                "correction_semantic": correction["semantic"],
                "correction_public": correction["public"]["matches"],
                "correction_matches": correction["world"]["result"]["matches"],
                "correction_control": correction["world"]["unchanged_control"]["matches"],
                "correction_public_only": correction["seed_public_only"],
                "correction_conformant": correction["conformant"],
                "correction_routes_refresh": correction["routes_refresh"],
            }
        )
    observation = empty_feed_observation(subject, p82)
    waiting, reused = base256.compile_wait(subject, observation, p82)
    repeated_observation = empty_feed_observation(waiting, p82)
    repeated, repeated_reused = base256.compile_wait(
        waiting, repeated_observation, p82
    )
    return {
        "order": list(order),
        "steps": steps,
        "final": repeated,
        "saturated": len(base244.remaining_epoch(repeated)) == 0,
        "projection_empty": repeated["active_opportunity_projection"]["opportunity_count"] == 0,
        "wait_installed": not reused,
        "wait_reobserved": repeated_reused
        and repeated["artifact_digest"] == waiting["artifact_digest"],
        "final_conformant": runtime.identity_conforms(repeated),
    }


def preflight(run, p82, runtime, parent, result271, package, result268):
    fixture_root = run.parent / "OT-0272-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    evaluation = base268.evaluate_package(package, p82.digest)
    remaining = [
        row["target_symbol"]
        for row in parent["active_opportunity_projection"]["opportunities"]
    ]
    branches = [
        prospective_branch(
            fixture_root / ("branch-" + "-".join(order)),
            parent,
            package,
            result268,
            order,
            p82,
            runtime,
        )
        for order in itertools.permutations(remaining)
    ]
    route, identity = base265.floors(parent)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open_selection": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and derive(parent, p82) == "expanded-select"
        and not base260.needs_refresh(parent, p82)
        and runtime.identity_conforms(parent),
        "ot0271_exact_promotion": result271["observer_disposition"] == "promoted"
        and result271["receipt_digest"] == OT271_RECEIPT
        and result271["final_subject_digest"] == PARENT_DIGEST,
        "ot0268_exact_package": result268["observer_disposition"] == "promoted"
        and result268["receipt_digest"] == OT268_RECEIPT
        and evaluation.get("valid")
        and evaluation["full_package_digest"] == result268["full_package_digest"],
        "exactly_two_remaining_two_orders": len(remaining) == 2
        and len(branches) == 2
        and {tuple(branch["order"]) for branch in branches}
        == set(itertools.permutations(remaining)),
        "all_package_targets_absent_inherited_registries": all(
            target not in base242.CANDIDATES
            and evaluation["targets"][target] not in base242.REFERENCE_SOURCES
            for target in remaining
        ),
        "all_branch_steps_pass": all(
            all(
                step["selection_checker"]
                and step["selection_semantic"]
                and step["selection_public"]
                and step["selection_matches"] == 2
                and step["selection_conformant"]
                and step["selection_routes_correction"]
                and step["selection_prompt_neutral"]
                and step["correction_checker"]
                and step["correction_semantic"]
                and step["correction_public"] == 4
                and step["correction_matches"] == 6
                and step["correction_control"] == 2
                and step["correction_public_only"]
                and step["correction_conformant"]
                and step["correction_routes_refresh"]
                for step in branch["steps"]
            )
            for branch in branches
        ),
        "all_branches_reach_fourth_wait": all(
            branch["saturated"]
            and branch["projection_empty"]
            and branch["wait_installed"]
            and branch["wait_reobserved"]
            and len(branch["final"]["world_stream_wait_receipts"])
            == len(parent["world_stream_wait_receipts"]) + 1
            and branch["final_conformant"]
            for branch in branches
        ),
        "dynamic_surfaces_not_hardcoded": not any(
            token in script
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "expected_operations": list(EXPECTED),
        "remaining_count": len(remaining),
        "branch_orders": [branch["order"] for branch in branches],
        "checks": checks,
    }, route, identity


def live_selection(context, p82, root, subject, package, result268):
    actor = base252.run_selection(context, p82, root / "actor", subject)
    intermediate = (
        base245.compile_intermediate(subject, actor, p82)
        if actor["accepted"]
        else subject
    )
    world = (
        base270.sealed_world(intermediate, actor, package, result268, p82)
        if actor["accepted"]
        else None
    )
    final = base245.compile_world(intermediate, world, p82) if world else intermediate
    if world:
        write_json(root / "world-receipt.json", world)
    return actor, world, final


def live_correction(context, p82, root, subject, package, result268):
    evaluation = base268.evaluate_package(package, p82.digest)
    actor = base271.run_actor(
        context, p82, root / "actor", subject, package, evaluation
    )
    world = (
        base271.sealed_followup(subject, actor, package, result268, p82)
        if actor["accepted"]
        else None
    )
    final = (
        base271.compile_correction(subject, actor, world, p82)
        if world and world["promotion_gate"]
        else subject
    )
    if world:
        write_json(root / "world-receipt.json", world)
    return actor, world, final


def advance(
    repo,
    run,
    p82,
    runtime,
    parent,
    package,
    result268,
    fixtures,
    route,
    identity,
    base,
    base130,
):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0272 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0272 evidence")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    if not runtime.identity_conforms(subject):
        raise SystemExit("serialized checkpoint invalid")
    index = len(results) + 1
    if index > len(EXPECTED):
        raise SystemExit("unexpected invocation count")
    operation = derive(subject, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = None
    world = None
    final = subject
    checks = {
        "content_free_expected_operation": pulse["content"] is None
        and operation == EXPECTED[index - 1]
    }
    if operation in {"expanded-select", "outward-correct"}:
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
            base.typed.base.make_context(runtime, root, repo)
        )
    if operation == "expanded-select":
        actor, world, final = live_selection(
            context, p82, root, subject, package, result268
        )
        selected = actor["decision"]["next_contact"] if actor.get("decision") else None
        pair = (
            (selected["target_path"], selected["target_symbol"])
            if selected
            else None
        )
        checks.update(
            actor_accepted=actor["accepted"],
            selected_projected_pair=pair in projected_pairs(subject),
            target_absent_inherited_registry=bool(
                selected
                and selected["target_symbol"] not in base242.CANDIDATES
                and selected["target_path"] not in base242.REFERENCE_SOURCES
            ),
            g10_accepted=actor["g10_disposition"],
            public_executable=bool(actor["public"] and actor["public"]["all_valid"]),
            retained_package_2_of_6=bool(
                world
                and world["result"]["matches"] == 2
                and world["ot0268_aggregate_receipt_digest"] == OT268_RECEIPT
            ),
            next_is_correction=derive(final, p82) == "outward-correct",
        )
    elif operation == "outward-correct":
        actor, world, final = live_correction(
            context, p82, root, subject, package, result268
        )
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            public_4_of_4=bool(actor["public"] and actor["public"]["matches"] == 4),
            retained_package_6_of_6=bool(
                world
                and world["result"]["matches"] == 6
                and world["ot0268_aggregate_receipt_digest"] == OT268_RECEIPT
            ),
            unchanged_2_of_6=bool(world and world["unchanged_control"]["matches"] == 2),
            next_is_refresh=derive(final, p82) == "refresh-opportunity-projection",
        )
    elif operation == "refresh-opportunity-projection":
        final = base264.refresh_projection_only(subject, p82)
        checks.update(
            zero_fresh_actors=True,
            projection_fresh=not base260.needs_refresh(final, p82),
            opportunity_count_decreased=final["active_opportunity_projection"]["opportunity_count"]
            == subject["active_opportunity_projection"]["opportunity_count"] - 1,
            next_derived=derive(final, p82) in {"expanded-select", "expand-environment"},
        )
    elif operation == "expand-environment":
        world = empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            active_epoch_saturated=len(base244.remaining_epoch(subject)) == 0,
            standing_feed_empty=world["result"] == "empty",
            fourth_wait_installed=not reused
            and len(final["world_stream_wait_receipts"])
            == len(subject["world_stream_wait_receipts"]) + 1,
            next_is_wait=derive(final, p82) == "wait-provider",
        )
    elif operation == "wait-provider":
        world = empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            standing_feed_still_empty=world["result"] == "empty",
            wait_exact_noop=reused
            and final["artifact_digest"] == subject["artifact_digest"],
        )
    else:
        checks["known_operation"] = False
    checks["standing_scanner_preserved"] = final["active_standing_world_provider"] == subject[
        "active_standing_world_provider"
    ]
    checks["final_open_conformant"] = final["continuation"]["status"] == "open" and runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "actor": actor,
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
    if index < len(EXPECTED):
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    all_results = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    selections = [row for row in all_results if row["pulse"]["derived_operation"] == "expanded-select"]
    corrections = [row for row in all_results if row["pulse"]["derived_operation"] == "outward-correct"]
    selected_targets = [row["actor"]["decision"]["next_contact"]["target_symbol"] for row in selections]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "eight_same_entry_invocations": len(all_results) == 8
        and [row["pulse"]["derived_operation"] for row in all_results]
        == list(EXPECTED)
        and all(row["pulse"]["content"] is None for row in all_results),
        "all_invocation_gates_pass": all(row["checks"]["passed"] for row in all_results),
        "exactly_four_fresh_actors": sum(row["fresh_actor_count"] for row in all_results) == 4,
        "two_distinct_selections_2_of_6": len(selections) == 2
        and len(set(selected_targets)) == 2
        and all(row["world"]["result"]["matches"] == 2 for row in selections),
        "two_corrections_4_6_2": len(corrections) == 2
        and all(
            row["actor"]["public"]["matches"] == 4
            and row["world"]["result"]["matches"] == 6
            and row["world"]["unchanged_control"]["matches"] == 2
            for row in corrections
        ),
        "fifth_epoch_saturated": len(base244.remaining_epoch(final)) == 0
        and final["active_opportunity_projection"]["opportunity_count"] == 0,
        "fourth_durable_wait": len(final["world_stream_wait_receipts"])
        == len(parent["world_stream_wait_receipts"]) + 1
        == 4
        and final["active_world_stream_wait"]["status"] == "waiting",
        "prior_wait_wake_history_preserved": final["world_stream_wait_receipts"][:-1]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "final_open_waiting": derive(final, p82) == "wait-provider"
        and final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
        "standing_scanner_preserved": final["active_standing_world_provider"]
        == parent["active_standing_world_provider"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "ot0268_package_receipt_digest": OT268_RECEIPT,
        "invocation_receipt_digests": [row["receipt_digest"] for row in all_results],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 4,
        "invocation_count": 8,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result271, package, result268, base, base130 = setup(args)
    fixtures, route, identity = preflight(
        run, p82, runtime, parent, result271, package, result268
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
        result268,
        fixtures,
        route,
        identity,
        base,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
