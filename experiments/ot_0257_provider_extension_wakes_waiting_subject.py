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
BASE_PATH = ROOT / "ot_0256_durable_empty_stream_waiting.py"
BASE_SHA256 = "2b704af5d5737b052305a585fd2669759d1b627fcde2c67c12a5e37732e9c2cf"
PARENT_DIGEST = "a4eea95bf1a1680dbe9357ca2fe9bb0a965bca9fe8b8d8831b0bed2539314ab6"
OT256_RECEIPT = "8cc27ec733d1127f604f922d98064d58515077c23c650e3f07d1727b9df86399"
AUTHORITY = "ot-0257-provider-extension-wakes-waiting-subject"
WORLD_ID = "coordination-third-epoch-v1"

HEAD = '''def _greedy(items, capacity, magnitude):
    remaining, chosen = capacity, []
    for item in sorted(items, key=lambda row: (-row[magnitude], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"])
            remaining -= item["effort"]
    return chosen
'''

WORLD_SOURCES = {
    "coordination/radio.py": HEAD
    + '''
def assign_relay_windows(case):
    return _greedy(case["windows"], case["capacity"], "urgency")
''',
    "coordination/crews.py": HEAD
    + '''
def sequence_repair_crews(case):
    return _greedy(case["repairs"], case["capacity"], "people_blocked")
''',
    "coordination/supplies.py": HEAD
    + '''
def route_supply_convoys(case):
    return _greedy(case["routes"], case["capacity"], "households")
''',
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0256 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0257_frozen_ot0256", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base256 = load_base()
base248 = base256.base248
base247 = base256.base247
authority_base = base256.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def descriptor():
    return {"world_id": WORLD_ID, "visible_sources": WORLD_SOURCES}


def extended_observation(subject, p82):
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
    catalog = [base247.WORLD_ID, WORLD_ID]
    unseen = [world_id for world_id in catalog if world_id not in seen]
    available = unseen[0] if unseen else None
    body = {
        "authority": AUTHORITY + "-extended-provider-observation",
        "source_subject_digest": subject["artifact_digest"],
        "prior_provider_interface_authority": subject[
            "active_streamed_world_interface"
        ]["authority"],
        "catalog_world_ids": catalog,
        "seen_world_ids": seen,
        "cursor_digest": p82.digest({"catalog": catalog, "seen": seen}),
        "result": "world-available" if available else "empty",
        "available_world_id": available,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def wait_condition_satisfied(subject, observation):
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
    if existing:
        already_reserved = (
            observation["result"] == "empty"
            and existing.get("world_id") in observation["seen_world_ids"]
        )
        same_offer = existing.get("world_id") == observation["available_world_id"]
        if already_reserved or same_offer:
            return subject, True
    if not wait_condition_satisfied(subject, observation):
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
        "available_world_id": observation["available_world_id"],
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
        "next_opening": (
            "Inspect the newly available coordination world and choose one "
            "coherent bounded contact."
        ),
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "world-stream-extension-available",
        "wait_discharge_receipt_digest": discharge["receipt_digest"],
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "resume_operation": "expand-environment",
    }
    child["unresolved"] = (
        "Resume environment expansion by inspecting the retained streamed-world offer."
    )
    return p82.seal(child), False


def operational_core_preserved(parent, child):
    keys = (
        "fixed_g6_recurrence_driver",
        "local_frontier_ledger",
        "actor_authored_environment_epochs",
        "actor_authored_environment_extensions",
        "pending_contact_bearing_continuations",
        "active_opportunity_projection",
        "active_pursuit",
        "active_content_free_operation_selector",
    )
    return all(parent[key] == child[key] for key in keys)


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0257").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0256", "open-subject-waiting-on-world-stream.json"
    )
    result256 = selector_base.load_artifact(
        p82, repo, store, "OT-0256", "durable-empty-stream-waiting-aggregate.json"
    )
    old_observation = base256.provider_snapshot(parent, p82)
    observation = extended_observation(parent, p82)
    prospective, reused = compile_offer(parent, observation, p82)
    repeated_observation = extended_observation(prospective, p82)
    repeated, repeated_reused = compile_offer(prospective, repeated_observation, p82)
    seen_control = copy.deepcopy(parent)
    seen_control.pop("artifact_digest", None)
    seen_control["environment_stream_receipts"] = [
        *seen_control["environment_stream_receipts"],
        {"world_id": WORLD_ID},
    ]
    seen_control = p82.seal(seen_control)
    seen_observation = extended_observation(seen_control, p82)
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
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_waiting": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation_liveness"]["status"]
        == "awaiting-world-stream-extension"
        and runtime.identity_conforms(parent),
        "ot0256_exact_promotion": result256["observer_disposition"] == "promoted"
        and result256["receipt_digest"] == OT256_RECEIPT
        and result256["final_subject_digest"] == PARENT_DIGEST,
        "old_provider_still_empty": old_observation["result"] == "empty",
        "extended_provider_one_unseen": observation["result"] == "world-available"
        and observation["available_world_id"] == WORLD_ID,
        "seen_world_control_empty": seen_observation["result"] == "empty",
        "wait_condition_exactly_satisfied": wait_condition_satisfied(
            parent, observation
        ),
        "offer_installed_not_reused": not reused
        and prospective["active_streamed_world_offer"]["world_id"] == WORLD_ID,
        "old_wait_retained_and_discharged": prospective[
            "world_stream_wait_receipts"
        ]
        == parent["world_stream_wait_receipts"]
        and prospective["active_world_stream_wait"] is None
        and prospective["world_stream_wait_discharge_receipts"][-1]["outcome"]
        == "satisfied",
        "operational_core_preserved": operational_core_preserved(
            parent, prospective
        ),
        "no_actor_or_epoch_fabricated": prospective[
            "actor_authored_environment_epochs"
        ]
        == parent["actor_authored_environment_epochs"]
        and prospective["fixed_g6_recurrence_driver"]["accepted_actors"]
        == parent["fixed_g6_recurrence_driver"]["accepted_actors"],
        "open_world_available": prospective["continuation"]["status"] == "open"
        and prospective["continuation_liveness"]["status"]
        == "world-stream-extension-available",
        "repeat_offer_idempotent": repeated_reused
        and repeated["artifact_digest"] == prospective["artifact_digest"],
        "prospective_conformant": runtime.identity_conforms(prospective),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0257 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    final, _ = compile_offer(parent, observation, p82)
    gates = {
        "preflight_passed": checks["passed"],
        "zero_fresh_actors": True,
        "old_empty_cursor_changed": old_observation["cursor_digest"]
        != observation["cursor_digest"],
        "retained_wait_condition_satisfied": wait_condition_satisfied(
            parent, observation
        ),
        "one_wait_discharge": len(final["world_stream_wait_discharge_receipts"])
        == 1,
        "one_durable_world_offer": len(final["streamed_world_offer_receipts"])
        == 1
        and final["active_streamed_world_offer"]["world_id"] == WORLD_ID,
        "no_actor_epoch_or_ledger_change": operational_core_preserved(parent, final),
        "open_for_resumed_expansion": final["continuation"]["status"] == "open"
        and final["continuation_liveness"]["resume_operation"]
        == "expand-environment",
        "final_conformant": runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "provider_observation": observation,
        "wait_discharge_receipt_digest": final[
            "world_stream_wait_discharge_receipts"
        ][-1]["receipt_digest"],
        "world_offer_receipt_digest": final["active_streamed_world_offer"][
            "offer_receipt_digest"
        ],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "provider-observation.json", observation)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
