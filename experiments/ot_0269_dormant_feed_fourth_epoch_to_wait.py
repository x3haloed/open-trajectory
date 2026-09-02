from __future__ import annotations

import argparse
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
BASE_PATH = ROOT / "ot_0268_independent_world_package.py"
BASE_SHA256 = "5f56b2836f779f1bcdcef8b15f11cb751edb369dae094ecbb3cdc6ca88244f41"
PARENT_DIGEST = "f02cf7cdcd68237b3327dacb2c733f3b67dba26caceb83d7ed83240ff1e4991c"
OT268_RECEIPT = "7026047afea9989082ac529770c934b3c63512ebc2de03d6c7d715d74c1743d1"
AUTHORITY = "ot-0269-dormant-feed-fourth-epoch-to-wait"
PULSE = None
EXPECTED = (
    "outward-correct",
    "refresh-opportunity-projection",
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
        raise RuntimeError("OT-0268 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0269_frozen_ot0268", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base268 = load_base()
base267 = base268.base267
base266 = base268.base266
base265 = base268.base265
base264 = base266.base265.base264
base261 = base268.base261
base260 = base268.base260
base259 = base266.base259
base257 = base259.base258.base257
base256 = base257.base256
base252 = base259.base252
base248 = base266.base248
base245 = base252.base245
base244 = base266.base244
base243 = base252.base243
authority_base = base268.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0269").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0267", "open-subject-with-standing-world-feed.json"
    )
    result268 = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-world-package-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result268, base, base130


def derive(subject, p82):
    wait = subject.get("active_world_stream_wait")
    if isinstance(wait, dict) and wait.get("status") == "waiting":
        return "wait-provider"
    return base261.challenger(subject, p82)


def empty_feed_observation(subject, p82):
    scan = base267.scan_feed(subject, [], p82.digest)
    body = {
        "authority": AUTHORITY + "-empty-standing-feed-observation",
        "source_subject_digest": subject["artifact_digest"],
        "scanner_observation_receipt_digest": scan["receipt_digest"],
        "provider_interface_authority": subject["active_standing_world_provider"][
            "authority"
        ],
        "catalog": scan["catalog"],
        "seen_world_ids": scan["seen_world_ids"],
        "cursor_digest": scan["cursor_digest"],
        "result": "empty",
        "available_world_id": None,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def selection_fixture(root, subject, target, p82):
    decision = base245.fixture_decision(target)
    seed = base252.selection_seed(root / "checker", subject, decision)
    checker = subprocess.run(
        ["python3", "check_selection.py"], cwd=seed, capture_output=True
    )
    evaluated = base252.evaluate_selection_workspace(seed, seed, subject)
    action = {
        "decision": decision,
        "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
    }
    intermediate = base245.compile_intermediate(subject, action, p82)
    world = base245.sealed_world(intermediate, action, p82, root / "world")
    final = base245.compile_world(intermediate, world, p82)
    return {
        "target": target,
        "checker": checker.returncode == 0,
        "evaluated": evaluated,
        "world": world,
        "final": final,
        "prompt": (seed / "README.md").read_text(),
    }


def prospective_branch(root, parent, order, p82, runtime):
    subject = parent
    initial = base259.fixture_correction(root / "initial-correction", subject, p82)
    subject = initial["prospective"]
    initial_route = derive(subject, p82)
    subject = base264.refresh_projection_only(subject, p82)
    steps = []
    for index, target in enumerate(order, 1):
        selection = selection_fixture(root / f"selection-{index}", subject, target, p82)
        subject = selection["final"]
        correction = base259.fixture_correction(
            root / f"correction-{index}", subject, p82
        )
        subject = correction["prospective"]
        correction_route = derive(subject, p82)
        subject = base264.refresh_projection_only(subject, p82)
        steps.append(
            {
                "target": target,
                "selection_checker": selection["checker"],
                "selection_public": bool(
                    selection["evaluated"]["public"]
                    and selection["evaluated"]["public"]["all_valid"]
                ),
                "selection_semantic": selection["evaluated"]["semantic"],
                "selection_hidden": selection["world"]["result"]["matches"],
                "selection_prompt_neutral": target not in selection["prompt"],
                "correction_checker": correction["checker"],
                "correction_public": correction["public"]["matches"],
                "correction_hidden": correction["corrected"]["matches"],
                "correction_control": correction["control"]["matches"],
                "correction_prompt_neutral": target not in correction["prompt"],
                "correction_routes_refresh": correction_route
                == "refresh-opportunity-projection",
                "subject_conformant": runtime.identity_conforms(subject),
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
        "initial": {
            "checker": initial["checker"],
            "public": initial["public"]["matches"],
            "hidden": initial["corrected"]["matches"],
            "control": initial["control"]["matches"],
            "routes_refresh": initial_route == "refresh-opportunity-projection",
        },
        "steps": steps,
        "final": repeated,
        "saturated": len(base244.remaining_epoch(repeated)) == 0,
        "projection_empty": len(
            repeated["active_opportunity_projection"]["opportunities"]
        )
        == 0,
        "empty_feed": observation["result"] == "empty",
        "wait_installed": not reused,
        "wait_reobserved": repeated_reused
        and repeated["artifact_digest"] == waiting["artifact_digest"],
        "final_conformant": runtime.identity_conforms(repeated),
    }


def preflight(run, p82, runtime, parent, result268):
    fixture_root = run.parent / "OT-0269-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    initial = base259.fixture_correction(fixture_root / "derive-initial", parent, p82)
    refreshed = base264.refresh_projection_only(initial["prospective"], p82)
    remaining = [
        row["target_symbol"]
        for row in refreshed["active_opportunity_projection"]["opportunities"]
    ]
    branches = [
        prospective_branch(
            fixture_root / ("branch-" + "-".join(order)),
            parent,
            order,
            p82,
            runtime,
        )
        for order in itertools.permutations(remaining)
    ]
    route, identity = base265.floors(parent)
    script = Path(__file__).read_text()
    branch_pass = all(
        branch["initial"]
        == {
            "checker": True,
            "public": 4,
            "hidden": 6,
            "control": 2,
            "routes_refresh": True,
        }
        and all(
            step["selection_checker"]
            and step["selection_public"]
            and step["selection_semantic"]
            and step["selection_hidden"] == 2
            and step["selection_prompt_neutral"]
            and step["correction_checker"]
            and step["correction_public"] == 4
            and step["correction_hidden"] == 6
            and step["correction_control"] == 2
            and step["correction_prompt_neutral"]
            and step["correction_routes_refresh"]
            and step["subject_conformant"]
            for step in branch["steps"]
        )
        and branch["saturated"]
        and branch["projection_empty"]
        and branch["empty_feed"]
        and branch["wait_installed"]
        and branch["wait_reobserved"]
        and branch["final_conformant"]
        for branch in branches
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_open_correction": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0268_exact_promotion_and_unchanged_subject": result268[
            "observer_disposition"
        ]
        == "promoted"
        and result268["receipt_digest"] == OT268_RECEIPT
        and result268["final_subject_digest"] == PARENT_DIGEST,
        "standing_scanner_exact": parent["active_standing_world_provider"][
            "scanner_source_digest"
        ]
        == p82.digest(base267.SCANNER_SOURCE),
        "exact_two_remaining_two_orders": len(remaining) == 2
        and len(branches) == 2
        and {tuple(branch["order"]) for branch in branches}
        == set(itertools.permutations(remaining)),
        "all_branch_controls_pass": branch_pass,
        "live_targets_not_hardcoded": all(target not in script for target in remaining),
        "dormant_package_not_named": result268["world_id"] not in script
        and result268["public_package_digest"] not in script
        and result268["full_package_digest"] not in script,
        "empty_feed_before_package_injection": empty_feed_observation(parent, p82)[
            "result"
        ]
        == "empty",
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


def correction_step(context, p82, root, subject):
    actor = base252.run_correction(context, p82, root / "actor", subject)
    world = (
        base243.evaluate(root / "world", subject, actor, p82)
        if actor["accepted"]
        else None
    )
    final = (
        base243.compile_correction(subject, actor, world, p82)
        if world and world["promotion_gate"]
        else subject
    )
    if world:
        write_json(root / "world-receipt.json", world)
    return actor, world, final


def advance(repo, run, p82, runtime, parent, fixtures, route, identity, base, base130):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0269 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0269 evidence")
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
        transition, final = base248.continue_once(
            runtime, base, base130, repo, p82, root / "transition", subject
        )
        actor, world = transition["actor"], transition["world"]
        selected = (
            actor["decision"]["next_contact"]
            if actor and actor.get("decision")
            else None
        )
        projected = {
            (row["target_path"], row["target_symbol"])
            for row in subject["active_opportunity_projection"]["opportunities"]
        }
        pair = (
            (selected["target_path"], selected["target_symbol"])
            if selected
            else None
        )
        checks.update(
            actor_accepted=bool(actor and actor["accepted"]),
            selected_projected_pair=pair in projected,
            g10_accepted=bool(actor and actor["g10_disposition"]),
            public_executable=bool(actor and actor["public"]["all_valid"]),
            sealed_2_of_6=bool(world and world["result"]["matches"] == 2),
            next_is_correction=derive(final, p82) == "outward-correct",
        )
    elif operation == "outward-correct":
        actor, world, final = correction_step(context, p82, root, subject)
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            public_4_of_4=bool(actor["public"] and actor["public"]["matches"] == 4),
            sealed_6_of_6=bool(world and world["result"]["matches"] == 6),
            unchanged_2_of_6=bool(
                world and world["unchanged_control"]["matches"] == 2
            ),
            next_is_refresh=derive(final, p82)
            == "refresh-opportunity-projection",
        )
    elif operation == "refresh-opportunity-projection":
        final = base264.refresh_projection_only(subject, p82)
        checks.update(
            zero_fresh_actors=True,
            projection_fresh=not base260.needs_refresh(final, p82),
            next_derived=derive(final, p82)
            in {"expanded-select", "expand-environment"},
            standing_scanner_preserved=final["active_standing_world_provider"]
            == subject["active_standing_world_provider"],
        )
    elif operation == "expand-environment":
        world = empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            standing_feed_empty=world["result"] == "empty",
            new_wait_installed=not reused
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
    checks["final_open_conformant"] = (
        final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final)
    )
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
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "ten_same_entry_invocations": len(all_results) == 10
        and [row["pulse"]["derived_operation"] for row in all_results]
        == list(EXPECTED)
        and all(row["pulse"]["content"] is None for row in all_results),
        "all_invocation_gates_pass": all(
            row["checks"]["passed"] for row in all_results
        ),
        "exactly_five_fresh_actors": sum(
            row["fresh_actor_count"] for row in all_results
        )
        == 5,
        "active_epoch_saturated": len(base244.remaining_epoch(final)) == 0,
        "projection_fresh_and_empty": not base260.needs_refresh(final, p82)
        and len(final["active_opportunity_projection"]["opportunities"]) == 0,
        "third_durable_wait": len(final["world_stream_wait_receipts"])
        == len(parent["world_stream_wait_receipts"]) + 1
        and final["active_world_stream_wait"]["status"] == "waiting",
        "prior_wait_wake_history_preserved": final["world_stream_wait_receipts"][:-1]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "dormant_package_not_consumed": final["environment_stream_receipts"]
        == parent["environment_stream_receipts"]
        and final["streamed_world_offer_receipts"]
        == parent["streamed_world_offer_receipts"],
        "standing_scanner_preserved": final["active_standing_world_provider"]
        == parent["active_standing_world_provider"],
        "final_open_waiting": derive(final, p82) == "wait-provider"
        and final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [
            row["receipt_digest"] for row in all_results
        ],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 5,
        "invocation_count": 10,
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
    repo, run, p82, runtime, parent, result268, base, base130 = setup(args)
    fixtures, route, identity = preflight(run, p82, runtime, parent, result268)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        fixtures,
        route,
        identity,
        base,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
