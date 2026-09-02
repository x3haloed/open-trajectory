from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0264_correction_then_refresh_recurrence.py"
BASE_SHA256 = "d505aeffc3a1c382959f4a66bb3962d9d89a86a36a9b4ddf14d41e0234adfa07"
PARENT_DIGEST = "dd5a5be0b2f5240eca089ffad15e7f2feec28c517b147cae4d9bb85b3fd85ec5"
OT264_RECEIPT = "21b3153fabf158552297c47b38ffff3263e33a51b6d5050dc1fd08e2ed06838a"
AUTHORITY = "ot-0265-content-free-epoch-to-wait-recurrence"
PULSE = None
EXPECTED = (
    "expanded-select",
    "outward-correct",
    "refresh-opportunity-projection",
    "expand-environment",
    "wait-provider",
)


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0264 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0265_frozen_ot0264", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base264 = load_base()
base263 = base264.base263
base261 = base264.base261
base260 = base264.base260
base259 = base264.base259
base257 = base259.base258.base257
base256 = base257.base256
base252 = base264.base252
base248 = base264.base248
base245 = base263.base245
base244 = base264.base244
base243 = base264.base243
base242 = base263.base242
authority_base = base264.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0265").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0264",
        "open-subject-with-one-fresh-opportunity.json",
    )
    result264 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0264",
        "correction-then-refresh-recurrence-aggregate.json",
    )
    return repo, run, p82, runtime, parent, result264, base, base130


def derive(subject, p82):
    wait = subject.get("active_world_stream_wait")
    if isinstance(wait, dict) and wait.get("status") == "waiting":
        return "wait-provider"
    return base261.challenger(subject, p82)


def floors(parent):
    route = (
        base248.base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(
            parent["active_executable_routing_selector"]["route"],
            parent["actor_authored_contact_mechanisms"][-1]["expression"],
        )
    )
    identity = authority_base.reuse.extension_base.evaluate(
        authority_base.reuse.extension_base.load_operation(
            parent["developmental_property_extensions"][0]["operation_source"]
        ),
        authority_base.reuse.accumulated_floor(),
    )
    return route, identity


def prospective_selection(root, subject, p82):
    opportunity = subject["active_opportunity_projection"]["opportunities"][0]
    target = opportunity["target_symbol"]
    decision = base245.fixture_decision(target)
    seed = base252.selection_seed(root / "selection-checker", subject, decision)
    checker = subprocess.run(
        ["python3", "check_selection.py"], cwd=seed, capture_output=True
    )
    evaluated = base252.evaluate_selection_workspace(seed, seed, subject)
    action = {
        "decision": decision,
        "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
    }
    intermediate = base245.compile_intermediate(subject, action, p82)
    world = base245.sealed_world(intermediate, action, p82, root / "selection-world")
    final = base245.compile_world(intermediate, world, p82)
    return {
        "opportunity": opportunity,
        "prompt": (seed / "README.md").read_text(),
        "checker": checker.returncode == 0,
        "evaluated": evaluated,
        "world": world,
        "final": final,
    }


def preflight(run, p82, runtime, parent, result264):
    fixture_root = run.parent / "OT-0265-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    selected = prospective_selection(fixture_root, parent, p82)
    contradiction = selected["final"]
    correction = base259.fixture_correction(
        fixture_root / "correction", contradiction, p82
    )
    corrected = correction["prospective"]
    refreshed = base264.refresh_projection_only(corrected, p82)
    observation = base257.extended_observation(refreshed, p82)
    waiting, wait_reused = base256.compile_wait(refreshed, observation, p82)
    repeated_observation = base257.extended_observation(waiting, p82)
    repeated, repeated_reused = base256.compile_wait(
        waiting, repeated_observation, p82
    )
    opportunity = selected["opportunity"]
    target = opportunity["target_symbol"]
    path = opportunity["target_path"]
    route, identity = floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_open_selection": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and not base260.needs_refresh(parent, p82)
        and derive(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0264_exact_promotion": result264["observer_disposition"] == "promoted"
        and result264["receipt_digest"] == OT264_RECEIPT
        and result264["final_subject_digest"] == PARENT_DIGEST,
        "exact_one_projected_eligible_pair": len(
            parent["active_opportunity_projection"]["opportunities"]
        )
        == 1
        and {(path, target)}
        == {
            (row["target_path"], row["target_symbol"])
            for row in base244.remaining_epoch(parent)
        },
        "selection_prompt_neutral": target not in selected["prompt"]
        and path not in selected["prompt"]
        and target not in Path(__file__).read_text(),
        "selection_registry_free_2_of_6": selected["checker"]
        and selected["evaluated"]["semantic"]
        and selected["evaluated"]["public"]["all_valid"]
        and selected["world"]["result"]["matches"] == 2
        and derive(contradiction, p82) == "outward-correct",
        "correction_prompt_neutral": target not in correction["prompt"]
        and path not in correction["prompt"],
        "correction_4_6_2": correction["checker"]
        and correction["public"]["matches"] == 4
        and correction["corrected"]["matches"] == 6
        and correction["control"]["matches"] == 2
        and derive(corrected, p82) == "refresh-opportunity-projection",
        "refresh_zero_then_expand": len(
            refreshed["active_opportunity_projection"]["opportunities"]
        )
        == 0
        and not base260.needs_refresh(refreshed, p82)
        and derive(refreshed, p82) == "expand-environment",
        "current_provider_empty": observation["result"] == "empty"
        and observation["available_world_id"] is None,
        "one_open_actor_free_wait": not wait_reused
        and waiting["continuation"]["status"] == "open"
        and waiting["active_world_stream_wait"]["actor_authority"] is False
        and derive(waiting, p82) == "wait-provider",
        "wait_reobservation_exact_noop": repeated_reused
        and repeated["artifact_digest"] == waiting["artifact_digest"],
        "all_prospective_states_conform": all(
            runtime.identity_conforms(state)
            for state in (contradiction, corrected, refreshed, waiting, repeated)
        ),
        "wait_wake_history_preserved": waiting["world_stream_wait_receipts"][:-1]
        == parent["world_stream_wait_receipts"]
        and waiting["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "derived_path": path,
        "derived_target": target,
        "expected_operations": list(EXPECTED),
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


def advance(args, repo, run, p82, runtime, parent, fixtures, route, identity, base, base130):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0265 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0265 evidence")
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
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, root, repo)
    )
    if operation == "expanded-select":
        transition, final = base248.continue_once(
            runtime, base, base130, repo, p82, root / "transition", subject
        )
        actor, world = transition["actor"], transition["world"]
        selected = actor["decision"]["next_contact"] if actor and actor.get("decision") else None
        projected = {
            (row["target_path"], row["target_symbol"])
            for row in subject["active_opportunity_projection"]["opportunities"]
        }
        pair = (selected["target_path"], selected["target_symbol"]) if selected else None
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
            projection_zero=len(
                final["active_opportunity_projection"]["opportunities"]
            )
            == 0,
            projection_fresh=not base260.needs_refresh(final, p82),
            next_is_expansion=derive(final, p82) == "expand-environment",
        )
    elif operation == "expand-environment":
        world = base257.extended_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            provider_empty=world["result"] == "empty",
            new_wait_installed=not reused
            and len(final["world_stream_wait_receipts"])
            == len(subject["world_stream_wait_receipts"]) + 1,
            next_is_wait=derive(final, p82) == "wait-provider",
        )
    elif operation == "wait-provider":
        world = base257.extended_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            provider_still_empty=world["result"] == "empty",
            wait_exact_noop=reused
            and final["artifact_digest"] == subject["artifact_digest"],
        )
    else:
        checks["known_operation"] = False
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
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "five_same_entry_invocations": len(all_results) == 5
        and [row["pulse"]["derived_operation"] for row in all_results]
        == list(EXPECTED)
        and all(row["pulse"]["content"] is None for row in all_results),
        "all_invocation_gates_pass": all(row["checks"]["passed"] for row in all_results),
        "exactly_two_fresh_actors": sum(row["fresh_actor_count"] for row in all_results) == 2,
        "active_epoch_saturated": len(base244.remaining_epoch(final)) == 0,
        "projection_fresh_and_empty": not base260.needs_refresh(final, p82)
        and len(final["active_opportunity_projection"]["opportunities"]) == 0,
        "second_durable_wait": len(final["world_stream_wait_receipts"])
        == len(parent["world_stream_wait_receipts"]) + 1
        and final["active_world_stream_wait"]["status"] == "waiting"
        and final["active_world_stream_wait"]["resume_condition"]
        == "unseen-world-available",
        "prior_wait_wake_history_preserved": final["world_stream_wait_receipts"][:-1]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
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
        "invocation_receipt_digests": [row["receipt_digest"] for row in all_results],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 2,
        "invocation_count": 5,
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
    repo, run, p82, runtime, parent, result264, base, base130 = setup(args)
    fixtures, route, identity = preflight(run, p82, runtime, parent, result264)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(
        args,
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
