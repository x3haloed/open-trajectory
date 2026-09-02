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
BASE_PATH = ROOT / "ot_0255_final_projected_correction_and_saturation.py"
BASE_SHA256 = "b9088534e9de26d9c93b81c9c0410d6538f79a163241970ee4260e2649d15ff3"
PARENT_DIGEST = "d15dbd22bee2eeaa72291bd939d0659113d7821f4a990fc562f8a0127ff49b4d"
OT255_RECEIPT = "78ffa4701e8788da4b61a259ae90081b7c0cdfb18918659fcac23caa0e2d783d"
AUTHORITY = "ot-0256-durable-empty-stream-waiting"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0255 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0256_frozen_ot0255", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base255 = load_base()
base254 = base255.base254
base248 = base255.base248
base247 = base255.base247
base244 = base255.base244
authority_base = base255.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def provider_snapshot(subject, p82):
    seen = sorted(
        {
            row["world_id"]
            for row in subject.get("environment_stream_receipts", [])
            if isinstance(row, dict) and isinstance(row.get("world_id"), str)
        }
    )
    catalog = [base247.WORLD_ID]
    body = {
        "authority": AUTHORITY + "-provider-observation",
        "source_subject_digest": subject["artifact_digest"],
        "provider_interface_authority": subject["active_streamed_world_interface"][
            "authority"
        ],
        "catalog_world_ids": catalog,
        "seen_world_ids": seen,
        "cursor_digest": p82.digest({"catalog": catalog, "seen": seen}),
        "result": "world-available" if base247.next_world(subject) else "empty",
        "available_world_id": (
            base247.next_world(subject)["world_id"]
            if base247.next_world(subject)
            else None
        ),
    }
    return {**body, "receipt_digest": p82.digest(body)}


def compile_wait(subject, observation, p82):
    active = subject.get("active_world_stream_wait")
    if (
        active
        and observation["result"] == "empty"
        and active["provider_cursor_digest"] == observation["cursor_digest"]
        and active["resume_operation"] == "expand-environment"
    ):
        return subject, True
    body = {
        "authority": AUTHORITY + "-wait-handle",
        "source_subject_digest": subject["artifact_digest"],
        "provider_observation_receipt_digest": observation["receipt_digest"],
        "provider_cursor_digest": observation["cursor_digest"],
        "status": "waiting",
        "resume_condition": "unseen-world-available",
        "resume_operation": "expand-environment",
        "closure_authority": False,
        "world_authority": False,
        "actor_authority": False,
    }
    wait = {**body, "wait_handle_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["world_stream_wait_receipts"] = [
        *child.get("world_stream_wait_receipts", []),
        wait,
    ]
    child["active_world_stream_wait"] = wait
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Await an unseen provider world, then resume environment expansion.",
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "awaiting-world-stream-extension",
        "wait_handle_digest": wait["wait_handle_digest"],
        "provider_cursor_digest": observation["cursor_digest"],
        "resume_operation": "expand-environment",
    }
    child["unresolved"] = (
        "No unseen world is currently available; preserve the open continuation "
        "and resume expansion when the provider stream extends."
    )
    return p82.seal(child), False


def operationally_preserved(parent, child):
    allowed = {
        "artifact_digest",
        "continuation",
        "continuation_liveness",
        "unresolved",
        "world_stream_wait_receipts",
        "active_world_stream_wait",
    }
    parent_core = {key: value for key, value in parent.items() if key not in allowed}
    child_core = {key: value for key, value in child.items() if key not in allowed}
    return parent_core == child_core


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0256").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0255",
        "open-saturated-subject-at-empty-world-stream.json",
    )
    result255 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0255",
        "final-projected-correction-saturation-aggregate.json",
    )
    return repo, store, run, p82, runtime, parent, result255


def preflight(parent, result255, p82, runtime):
    observation = provider_snapshot(parent, p82)
    waiting, reused = compile_wait(parent, observation, p82)
    second_observation = provider_snapshot(waiting, p82)
    repeated, second_reused = compile_wait(waiting, second_observation, p82)
    positive = copy.deepcopy(parent)
    positive.pop("artifact_digest", None)
    positive["environment_stream_receipts"] = [
        row
        for row in positive.get("environment_stream_receipts", [])
        if row.get("world_id") != base247.WORLD_ID
    ]
    positive = p82.seal(positive)
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
        "parent_exact_open_saturated": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and len(base244.remaining_epoch(parent)) == 0
        and base248.operation_for(parent) == "expand-environment"
        and runtime.identity_conforms(parent),
        "ot0255_exact_promotion": result255["observer_disposition"] == "promoted"
        and result255["receipt_digest"] == OT255_RECEIPT
        and result255["final_subject_digest"] == PARENT_DIGEST,
        "null_pulse_routes_expansion": PULSE is None
        and base248.operation_for(parent) == "expand-environment",
        "provider_positive_control": base247.next_world(positive)["world_id"]
        == base247.WORLD_ID,
        "live_provider_observation_empty": observation["result"] == "empty"
        and observation["available_world_id"] is None,
        "one_wait_handle_installed": not reused
        and len(waiting.get("world_stream_wait_receipts", []))
        == len(parent.get("world_stream_wait_receipts", [])) + 1,
        "wait_is_open_and_actor_free": waiting["continuation"]["status"] == "open"
        and waiting["continuation_liveness"]["status"]
        == "awaiting-world-stream-extension"
        and waiting["active_world_stream_wait"]["actor_authority"] is False,
        "operational_state_preserved": operationally_preserved(parent, waiting),
        "reobservation_idempotent": second_reused
        and repeated["artifact_digest"] == waiting["artifact_digest"]
        and len(repeated["world_stream_wait_receipts"])
        == len(waiting["world_stream_wait_receipts"]),
        "waiting_subject_conforms": runtime.identity_conforms(waiting),
        "projection_authority_unchanged": waiting["active_opportunity_projection"]
        == parent["active_opportunity_projection"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
    }


def enter(args, run, p82, runtime, parent, fixtures):
    if run.exists():
        raise SystemExit("preserve existing OT-0256 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": base248.operation_for(parent),
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    observation = provider_snapshot(parent, p82)
    waiting, reused = compile_wait(parent, observation, p82)
    result = {
        "authority": AUTHORITY + "-entry",
        "source_subject_digest": parent["artifact_digest"],
        "pulse": pulse,
        "provider_observation": observation,
        "wait_handle_digest": waiting["active_world_stream_wait"][
            "wait_handle_digest"
        ],
        "waiting_subject_digest": waiting["artifact_digest"],
        "installed_new_wait": not reused,
        "fresh_actor_count": 0,
        "subject_disposition": waiting["continuation"]["status"],
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "entry-result.json", result)
    write_json(run / "waiting-subject.json", waiting)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def reobserve(args, run, p82, runtime, parent, fixtures):
    aggregate_path = run / "aggregate.json"
    if aggregate_path.exists():
        raise SystemExit("preserve existing OT-0256 aggregate")
    entry = json.loads((run / "entry-result.json").read_text())
    waiting = json.loads((run / "waiting-subject.json").read_text())
    if (
        waiting["artifact_digest"] != entry["waiting_subject_digest"]
        or not runtime.identity_conforms(waiting)
    ):
        raise SystemExit("serialized waiting subject invalid")
    observation = provider_snapshot(waiting, p82)
    final, reused = compile_wait(waiting, observation, p82)
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "separate_serialized_reobservation": entry["authority"]
        == AUTHORITY + "-entry"
        and waiting["artifact_digest"] != parent["artifact_digest"],
        "zero_fresh_actors": entry["fresh_actor_count"] == 0,
        "explicit_empty_provider_receipts": entry["provider_observation"]["result"]
        == "empty"
        and observation["result"] == "empty",
        "one_durable_wait_handle": len(final["world_stream_wait_receipts"]) == 1
        and final["active_world_stream_wait"]["status"] == "waiting",
        "resume_condition_retained": final["active_world_stream_wait"][
            "resume_condition"
        ]
        == "unseen-world-available"
        and final["active_world_stream_wait"]["resume_operation"]
        == "expand-environment",
        "reobservation_is_exact_noop": reused
        and final["artifact_digest"] == waiting["artifact_digest"],
        "operational_state_preserved": operationally_preserved(parent, final),
        "no_world_or_epoch_fabricated": final["environment_stream_receipts"]
        == parent["environment_stream_receipts"]
        and final["actor_authored_environment_epochs"]
        == parent["actor_authored_environment_epochs"],
        "open_awaiting_world": final["continuation"]["status"] == "open"
        and final["continuation_liveness"]["status"]
        == "awaiting-world-stream-extension",
        "final_conformant": runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "entry_receipt_digest": entry["receipt_digest"],
        "reobservation_provider_receipt_digest": observation["receipt_digest"],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 0,
        "invocation_count": 2,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "reobservation-provider-receipt.json", observation)
    write_json(aggregate_path, result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--mode", choices=("enter", "reobserve"), default="enter")
    args = parser.parse_args()
    _, _, run, p82, runtime, parent, result255 = setup(args)
    fixtures = preflight(parent, result255, p82, runtime)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if args.mode == "enter":
        return enter(args, run, p82, runtime, parent, fixtures)
    return reobserve(args, run, p82, runtime, parent, fixtures)


if __name__ == "__main__":
    raise SystemExit(main())
