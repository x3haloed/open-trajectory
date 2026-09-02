from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0265_content_free_epoch_to_wait_recurrence.py"
BASE_SHA256 = "cd69e4b8f30c0b4407b0da6f1ce3187dbdd8c148235e38f86e665ea83c857460"
PARENT_DIGEST = "d62f5fc2043bfe52b83cdb032f5001f6c18f13d21070513ac4317c8778754091"
OT265_RECEIPT = "a3a72f2071e31e7b217eff1b4d34cb37d4d0749f83e08cce885c67548b049305"
AUTHORITY = "ot-0266-second-wake-to-live-contact"
WORLD_ID = "continuity-fourth-epoch-v1"
PULSE = None
EXPECTED = ("observe-provider", "expand-environment")

HEAD = '''def _greedy(items, capacity, magnitude):
    remaining, chosen = capacity, []
    for item in sorted(items, key=lambda row: (-row[magnitude], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"])
            remaining -= item["effort"]
    return chosen
'''

REFERENCE_HEAD = '''def _best(items, capacity, value):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > capacity:
            continue
        score = sum(value(item) for item in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])
'''

CANDIDATES = {
    "stage_microgrids": (
        "coordination/power.py",
        "sites",
        "critical_load",
        "outage_hours",
        "cascade_risk",
    ),
    "allocate_field_clinics": (
        "coordination/medical.py",
        "zones",
        "patients",
        "travel_hours",
        "mortality_risk",
    ),
    "schedule_tanker_routes": (
        "coordination/water.py",
        "routes",
        "residents",
        "delay_hours",
        "contamination_risk",
    ),
}

WORLD_SOURCES = {
    "coordination/power.py": HEAD
    + '''
def stage_microgrids(case):
    return _greedy(case["sites"], case["capacity"], "critical_load")
''',
    "coordination/medical.py": HEAD
    + '''
def allocate_field_clinics(case):
    return _greedy(case["zones"], case["capacity"], "patients")
''',
    "coordination/water.py": HEAD
    + '''
def schedule_tanker_routes(case):
    return _greedy(case["routes"], case["capacity"], "residents")
''',
}

REFERENCE_SOURCES = {
    "coordination/power.py": REFERENCE_HEAD
    + '''
def stage_microgrids(case):
    return _best(case["sites"], case["capacity"], lambda row: row["critical_load"] * row["outage_hours"] * row["cascade_risk"])
''',
    "coordination/medical.py": REFERENCE_HEAD
    + '''
def allocate_field_clinics(case):
    return _best(case["zones"], case["capacity"], lambda row: row["patients"] * row["travel_hours"] * row["mortality_risk"])
''',
    "coordination/water.py": REFERENCE_HEAD
    + '''
def schedule_tanker_routes(case):
    return _best(case["routes"], case["capacity"], lambda row: row["residents"] * row["delay_hours"] * row["contamination_risk"])
''',
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0265 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0266_frozen_ot0265", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base265 = load_base()
base264 = base265.base264
base261 = base265.base261
base260 = base265.base260
base259 = base265.base259
base258 = base259.base258
base248 = base265.base248
base244 = base265.base244
base242 = base265.base242
authority_base = base265.authority_base

base258.WORLD_ID = WORLD_ID
base258.WORLD_SOURCES = WORLD_SOURCES
base258.CANDIDATES = CANDIDATES
base258.REFERENCE_SOURCES = REFERENCE_SOURCES
base258.HIDDEN_CASES = {
    target: base258.hidden_cases(target) for target in CANDIDATES
}
base242.CANDIDATES = {**base242.CANDIDATES, **CANDIDATES}
base242.REFERENCE_SOURCES = {**base242.REFERENCE_SOURCES, **REFERENCE_SOURCES}
base242.HIDDEN_CASES = {**base242.HIDDEN_CASES, **base258.HIDDEN_CASES}


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0266").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0265", "open-subject-at-second-durable-wait.json"
    )
    result265 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0265",
        "content-free-epoch-to-wait-recurrence-aggregate.json",
    )
    return repo, run, p82, runtime, parent, result265, base, base130


def provider_observation(subject, p82, extended=True):
    seen = sorted(
        {
            row["world_id"]
            for row in subject.get("environment_stream_receipts", [])
            if isinstance(row, dict) and isinstance(row.get("world_id"), str)
        }
    )
    offer = subject.get("active_streamed_world_offer")
    if isinstance(offer, dict) and isinstance(offer.get("world_id"), str):
        seen = sorted({*seen, offer["world_id"]})
    catalog = sorted({*seen, *([WORLD_ID] if extended else [])})
    unseen = [world_id for world_id in catalog if world_id not in seen]
    available = unseen[0] if unseen else None
    body = {
        "authority": AUTHORITY + "-provider-observation",
        "source_subject_digest": subject["artifact_digest"],
        "prior_provider_interface_authority": subject["active_streamed_world_interface"][
            "authority"
        ],
        "catalog_world_ids": catalog,
        "seen_world_ids": seen,
        "cursor_digest": p82.digest({"catalog": catalog, "seen": seen}),
        "result": "world-available" if available else "empty",
        "available_world_id": available,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def wait_satisfied(subject, observation):
    wait = subject.get("active_world_stream_wait")
    return bool(
        wait
        and wait["status"] == "waiting"
        and wait["resume_condition"] == "unseen-world-available"
        and observation["result"] == "world-available"
        and observation["available_world_id"] not in observation["seen_world_ids"]
        and observation["cursor_digest"] != wait["provider_cursor_digest"]
    )


def compile_offer(subject, observation, p82):
    existing = subject.get("active_streamed_world_offer")
    if existing and existing.get("world_id") == WORLD_ID:
        return subject, True
    if not wait_satisfied(subject, observation):
        return subject, False
    wait = subject["active_world_stream_wait"]
    transition_body = {
        "authority": AUTHORITY + "-provider-interface-transition",
        "source_subject_digest": subject["artifact_digest"],
        "from_authority": subject["active_streamed_world_interface"]["authority"],
        "to_authority": AUTHORITY + "-extended-provider-interface",
        "provider_observation_receipt_digest": observation["receipt_digest"],
        "catalog_digest": p82.digest(observation["catalog_world_ids"]),
    }
    transition = {**transition_body, "receipt_digest": p82.digest(transition_body)}
    discharge_body = {
        "authority": AUTHORITY + "-wait-discharge",
        "source_subject_digest": subject["artifact_digest"],
        "wait_handle_digest": wait["wait_handle_digest"],
        "resume_condition": wait["resume_condition"],
        "provider_observation_receipt_digest": observation["receipt_digest"],
        "available_world_id": WORLD_ID,
        "outcome": "satisfied",
    }
    discharge = {**discharge_body, "receipt_digest": p82.digest(discharge_body)}
    offer_body = {
        "authority": AUTHORITY + "-world-offer",
        "source_subject_digest": subject["artifact_digest"],
        "provider_observation_receipt_digest": observation["receipt_digest"],
        "wait_discharge_receipt_digest": discharge["receipt_digest"],
        "world_id": WORLD_ID,
        "visible_sources": {
            path: {"source": source, "source_digest": p82.digest(source)}
            for path, source in sorted(WORLD_SOURCES.items())
        },
        "selection_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
    }
    offer = {**offer_body, "offer_receipt_digest": p82.digest(offer_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["streamed_world_interface_transitions"] = [
        *child.get("streamed_world_interface_transitions", []),
        transition,
    ]
    child["active_streamed_world_interface"] = {
        "authority": transition["to_authority"],
        "catalog_digest": transition["catalog_digest"],
        "transition_receipt_digest": transition["receipt_digest"],
    }
    child["world_stream_wait_discharge_receipts"] = [
        *child.get("world_stream_wait_discharge_receipts", []),
        discharge,
    ]
    child["active_world_stream_wait"] = None
    child["streamed_world_offer_receipts"] = [
        *child.get("streamed_world_offer_receipts", []),
        offer,
    ]
    child["active_streamed_world_offer"] = offer
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Inspect the newly available world and choose one coherent bounded contact.",
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "world-stream-extension-available",
        "wait_discharge_receipt_digest": discharge["receipt_digest"],
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "resume_operation": "expand-environment",
    }
    child["unresolved"] = "Resume environment expansion from the retained world offer."
    return p82.seal(child), False


def derive(subject, p82):
    if subject.get("active_world_stream_wait"):
        return "observe-provider"
    if subject.get("active_streamed_world_offer"):
        return "expand-environment"
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


def fixture_actor(root, offered, target, p82):
    decision = base258.fixture_decision(target)
    seed = base258.seed_actor(root / target, offered, decision)
    checker = subprocess.run(
        ["python3", "check_expansion.py"], cwd=seed, capture_output=True
    )
    structural = base258.structural(decision, seed, offered["local_frontier_ledger"])
    public = base258.execute_public(seed, decision)
    pulse = {
        "authority": AUTHORITY + "-fixture-pulse",
        "content": None,
        "source_subject_digest": offered["artifact_digest"],
        "derived_operation": "expand-environment",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    action = {
        "decision": decision,
        "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
    }
    intermediate = base258.compile_intermediate(offered, action, pulse, p82)
    world = base258.sealed_world(intermediate, action, p82, root / f"world-{target}")
    final = base258.compile_world(intermediate, world, p82)
    return {
        "checker": checker.returncode == 0,
        "structural": structural,
        "public": public,
        "world": world,
        "intermediate": intermediate,
        "final": final,
        "prompt": (seed / "README.md").read_text(),
    }


def preflight(run, p82, runtime, parent, result265):
    fixture_root = run.parent / "OT-0266-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    old_observation = provider_observation(parent, p82, extended=False)
    observation = provider_observation(parent, p82, extended=True)
    offered, reused = compile_offer(parent, observation, p82)
    repeated, repeated_reused = compile_offer(
        offered, provider_observation(offered, p82, extended=True), p82
    )
    seen_control = copy.deepcopy(parent)
    seen_control.pop("artifact_digest", None)
    seen_control["environment_stream_receipts"] = [
        *seen_control["environment_stream_receipts"],
        {"world_id": WORLD_ID},
    ]
    seen_control = p82.seal(seen_control)
    rows = {
        target: fixture_actor(fixture_root, offered, target, p82)
        for target in sorted(CANDIDATES)
    }
    route, identity = floors(parent)
    prompts = [row["prompt"] for row in rows.values()]
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_second_wait": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and derive(parent, p82) == "observe-provider"
        and runtime.identity_conforms(parent),
        "ot0265_exact_promotion": result265["observer_disposition"] == "promoted"
        and result265["receipt_digest"] == OT265_RECEIPT
        and result265["final_subject_digest"] == PARENT_DIGEST,
        "old_provider_empty": old_observation["result"] == "empty",
        "extended_provider_one_unseen": observation["result"] == "world-available"
        and observation["available_world_id"] == WORLD_ID,
        "seen_control_empty": provider_observation(
            seen_control, p82, extended=True
        )["result"]
        == "empty",
        "exact_wait_satisfied": wait_satisfied(parent, observation),
        "offer_installed_without_authority": not reused
        and offered["active_streamed_world_offer"]["world_id"] == WORLD_ID
        and not any(
            offered["active_streamed_world_offer"][key]
            for key in ("selection_authority", "scoring_authority", "admission_authority")
        ),
        "wait_retained_and_discharged": offered["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and offered["active_world_stream_wait"] is None
        and len(offered["world_stream_wait_discharge_receipts"])
        == len(parent["world_stream_wait_discharge_receipts"]) + 1,
        "wake_actor_and_epoch_free": offered["actor_authored_environment_epochs"]
        == parent["actor_authored_environment_epochs"]
        and offered["fixed_g6_recurrence_driver"]
        == parent["fixed_g6_recurrence_driver"],
        "offer_repeat_idempotent": repeated_reused
        and repeated["artifact_digest"] == offered["artifact_digest"],
        "prompts_name_no_candidate": not any(
            token in prompt
            for prompt in prompts
            for target, candidate in CANDIDATES.items()
            for token in (target, candidate[0])
        ),
        "all_actor_paths_2_of_6": all(
            row["checker"]
            and row["structural"]
            and row["public"]["all_valid"]
            and row["world"]["result"]["matches"] == 2
            and runtime.identity_conforms(row["intermediate"])
            and runtime.identity_conforms(row["final"])
            and base261.challenger(row["final"], p82) == "outward-correct"
            for row in rows.values()
        ),
        "offered_conformant": runtime.identity_conforms(offered),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "world_id": WORLD_ID,
        "expected_operations": list(EXPECTED),
        "checks": checks,
    }, route, identity


def advance(repo, run, p82, runtime, parent, fixtures, route, identity, base, base130):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0266 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0266 evidence")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    if not runtime.identity_conforms(subject):
        raise SystemExit("serialized checkpoint invalid")
    index = len(results) + 1
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
        "content_free_expected_operation": index <= len(EXPECTED)
        and pulse["content"] is None
        and operation == EXPECTED[index - 1]
    }
    if operation == "observe-provider":
        world = provider_observation(subject, p82, extended=True)
        final, reused = compile_offer(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            changed_cursor_world_available=world["result"] == "world-available"
            and wait_satisfied(subject, world),
            exact_wait_discharged=not reused
            and final["active_world_stream_wait"] is None
            and final["world_stream_wait_discharge_receipts"][-1]["wait_handle_digest"]
            == subject["active_world_stream_wait"]["wait_handle_digest"],
            nonselecting_offer=final["active_streamed_world_offer"]["world_id"]
            == WORLD_ID,
            next_is_expansion=derive(final, p82) == "expand-environment",
        )
    elif operation == "expand-environment":
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
            base.typed.base.make_context(runtime, root, repo)
        )
        actor = base258.run_actor(context, p82, root / "actor", subject)
        intermediate = (
            base258.compile_intermediate(subject, actor, pulse, p82)
            if actor["accepted"]
            else subject
        )
        world = (
            base258.sealed_world(intermediate, actor, p82, root / "world")
            if actor["accepted"]
            else None
        )
        final = base258.compile_world(intermediate, world, p82) if world else intermediate
        if world:
            write_json(root / "world-receipt.json", world)
        selected = actor["decision"]["next_contact"] if actor and actor.get("decision") else None
        checks.update(
            actor_accepted=bool(actor and actor["accepted"]),
            selected_offered_surface=bool(
                selected
                and selected["target_symbol"] in CANDIDATES
                and CANDIDATES[selected["target_symbol"]][0] == selected["target_path"]
            ),
            g10_accepted=bool(actor and actor["g10_disposition"]),
            public_executable=bool(actor and actor["public"]["all_valid"]),
            sealed_2_of_6=bool(world and world["result"]["matches"] == 2),
            offer_consumed=final["active_streamed_world_offer"] is None,
            new_epoch_added=len(final["actor_authored_environment_epochs"])
            == len(subject["actor_authored_environment_epochs"]) + 1,
            correction_before_refresh=base260.needs_refresh(final, p82)
            and base261.challenger(final, p82) == "outward-correct",
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
    if index == 1:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    all_results = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_same_entry_invocations": len(all_results) == 2
        and [row["pulse"]["derived_operation"] for row in all_results]
        == list(EXPECTED)
        and all(row["pulse"]["content"] is None for row in all_results),
        "all_invocation_gates_pass": all(row["checks"]["passed"] for row in all_results),
        "exactly_one_fresh_actor": sum(row["fresh_actor_count"] for row in all_results) == 1,
        "both_waits_and_discharges_retained": final["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and len(final["world_stream_wait_discharge_receipts"])
        == len(parent["world_stream_wait_discharge_receipts"]) + 1,
        "new_epoch_and_unresolved_contact": len(final["actor_authored_environment_epochs"])
        == len(parent["actor_authored_environment_epochs"]) + 1
        and final["fixed_g6_recurrence_driver"]["phase"] == "correct",
        "final_correction_before_refresh": base260.needs_refresh(final, p82)
        and base261.challenger(final, p82) == "outward-correct",
        "final_open_conformant": final["continuation"]["status"] == "open"
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
        "fresh_actor_count": 1,
        "invocation_count": 2,
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
    repo, run, p82, runtime, parent, result265, base, base130 = setup(args)
    fixtures, route, identity = preflight(run, p82, runtime, parent, result265)
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
