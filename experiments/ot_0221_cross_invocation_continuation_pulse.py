from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0220_fixed_g6_subject_recurrence.py"
BASE_SHA256 = "732d84419ef38b4809afdd5bb6a14d8a2788e5bcdb5158d396dcb7ac723802c4"
PARENT_DIGEST = "e3dd8685ceeb58e8c22ec8d407c51c20ffae0eb980031a79be2908c0cca8e0e9"
OT220_RECEIPT = "091c8a4b9e2c8a9a1bfdee9a24948f6382c23f3100bdb78bf365c45b539ddaa5"
PENDING_IDENTITY = "248e0d127a0cda78d9fd867e398b97d6685148920370ce76986ee7481d399902"
PULSE_VERSION = "ot-0221-cross-invocation-pulse-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0220 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0221_frozen_ot0220", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base220 = load_base()
base219 = base220.base219
base213 = base220.base213
authority_base = base220.authority_base


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def pulse_eligible(subject: dict[str, Any]) -> bool:
    try:
        state = subject["fixed_g6_recurrence_driver"]
        pending = subject["pending_contact_bearing_continuations"][-1]
        liveness = subject["continuation_liveness"]
        return bool(
            subject["continuation"]["status"] == "open"
            and state["phase"] == "observer-stop"
            and state["encounters"] == state["observation_limit"]
            and state["accepted_actors"] == state["actor_limit"]
            and liveness["status"] == "live"
            and pending["consequence_status"] == "unreceipted"
            and pending["contact_identity"] == liveness["contact_identity"]
        )
    except (KeyError, IndexError, TypeError):
        return False


def apply_pulse(subject: dict[str, Any], p82) -> tuple[dict[str, Any], dict[str, Any]]:
    if not pulse_eligible(subject):
        raise ValueError("subject is not pulse-eligible")
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    state = copy.deepcopy(subject["fixed_g6_recurrence_driver"])
    pending = subject["pending_contact_bearing_continuations"][-1]
    body = {
        "authority": PULSE_VERSION,
        "source_subject_digest": subject["artifact_digest"],
        "from_phase": "observer-stop",
        "to_phase": "contact",
        "pending_contact_identity": pending["contact_identity"],
        "prior_observation_limit": state["observation_limit"],
        "prior_actor_limit": state["actor_limit"],
        "allowance_increment": 1,
        "content_supplied": False,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    state["phase"] = "contact"
    state["observation_limit"] += 1
    state["actor_limit"] += 1
    state["invocations"] = state.get("invocations", 1) + 1
    child["fixed_g6_recurrence_driver"] = state
    child["cross_invocation_pulse_receipts"] = [*child.get("cross_invocation_pulse_receipts", []), receipt]
    return p82.seal(child), receipt


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0221").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0220", "open-subject-after-fixed-g6-observation.json")
    result220 = selector_base.load_artifact(p82, repo, store, "OT-0220", "fixed-g6-recurrence-aggregate.json")
    resumed, pulse = apply_pulse(parent, p82)

    fixture_root = run.parent / "OT-0221-preflight"
    import shutil
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    pending = parent["pending_contact_bearing_continuations"][-1]
    environment = fixture_root / "environment"
    available = base220.available_at(environment, parent)
    registry = base220.completed_registry(parent, available)
    replay = base219.g6(base219.decision(parent["continuation"]["next_opening"], pending["package"]), registry, available)
    fixture_world = base220.execute_hidden(fixture_root / "world", resumed, pending["package"], 3, p82)

    variants = {}
    for name, mutate in {
        "closed": lambda value: value["continuation"].update(status="closed"),
        "unresolved": lambda value: value["continuation_liveness"].update(status="unresolved"),
        "receipted": lambda value: value["pending_contact_bearing_continuations"][-1].update(consequence_status="success"),
        "not_stopped": lambda value: value["fixed_g6_recurrence_driver"].update(phase="contact"),
    }.items():
        candidate = copy.deepcopy(parent)
        mutate(candidate)
        variants[name] = pulse_eligible(candidate)

    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and pulse_eligible(parent),
        "ot0220_exact_rejection": result220["observer_disposition"] == "rejected" and result220["receipt_digest"] == OT220_RECEIPT and result220["final_subject_digest"] == PARENT_DIGEST and not result220["checks"]["later_consequence_after_correction"],
        "pending_identity_exact": pending["contact_identity"] == PENDING_IDENTITY,
        "pending_g6_replays": replay["accepted"] and replay["projected_identity"] == PENDING_IDENTITY,
        "pulse_local": all(resumed.get(key) == value for key, value in parent.items() if key not in {"artifact_digest", "fixed_g6_recurrence_driver", "cross_invocation_pulse_receipts"}),
        "pending_bytes_exact": resumed["pending_contact_bearing_continuations"] == parent["pending_contact_bearing_continuations"],
        "pulse_only_increments_allowances": resumed["fixed_g6_recurrence_driver"]["observation_limit"] == parent["fixed_g6_recurrence_driver"]["observation_limit"] + 1 and resumed["fixed_g6_recurrence_driver"]["actor_limit"] == parent["fixed_g6_recurrence_driver"]["actor_limit"] + 1 and base220.dispatch(resumed) == "contact",
        "ineligible_variants_rejected": not any(variants.values()),
        "task_bearing_pulse_absent": pulse["content_supplied"] is False and set(pulse) == {"authority", "source_subject_digest", "from_phase", "to_phase", "pending_contact_identity", "prior_observation_limit", "prior_actor_limit", "allowance_increment", "content_supplied", "receipt_digest"},
        "fixture_world_recovery_6_of_6": fixture_world["outcome"] == "success" and fixture_world["result"]["matches"] == 6,
        "prospective_resumed_conforms": runtime.identity_conforms(resumed),
        "assimilator_schema_supported": base220.ASSIMILATOR_SCHEMA.is_file() and "uniqueItems" not in base220.ASSIMILATOR_SCHEMA.read_text(),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": PULSE_VERSION + "-preflight", "source_subject_digest": parent["artifact_digest"], "pulse": pulse, "g6_replay": replay, "ineligible_variants": variants, "fixture_world": fixture_world, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0221 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")

    started = time.time()
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    world = base220.execute_hidden(run / "encounter-3-world", resumed, pending["package"], 3, p82)
    write_json(run / "encounter-3-world-receipt.json", world)
    contacted = base220.compile_world(resumed, world, p82)
    assimilation = None
    final = contacted
    if world["outcome"] in {"success", "surrender"} and base220.dispatch(contacted) == "assimilate":
        resolved = base220.resolved_for_assimilation(contacted)
        assimilation = base220.run_contact_actor(context, prior131, p82, run / "assimilation", contacted, "assimilator", resolved)
        if assimilation["accepted"]:
            final = base220.observer_stop(base220.compile_pending(contacted, assimilation, p82), p82)

    final_ok = runtime.identity_conforms(final)
    final_pending = final["pending_contact_bearing_continuations"][-1]
    gates = {
        "preflight_passed": checks["passed"],
        "pulse_applied_exactly": base220.dispatch(resumed) == "contact" and resumed["cross_invocation_pulse_receipts"][-1]["receipt_digest"] == pulse["receipt_digest"],
        "post_correction_world_success": world["outcome"] == "success" and world["result"]["matches"] == 6,
        "later_consequence_after_ot0220_correction": world["encounter"] == 3 and parent["fixed_g6_recurrence_driver"]["corrected_contradictions"] >= 1,
        "fresh_assimilator_accepted": bool(assimilation and assimilation["accepted"]),
        "different_target_reopening": bool(assimilation and assimilation["decision"]["next_contact"]["target_symbol"] != world["target_symbol"]),
        "final_exact_open_subject": final_ok and final["continuation"]["status"] == "open",
        "final_g6_live_pending": final_pending["consequence_status"] == "unreceipted" and final["continuation_liveness"]["status"] == "live",
        "observer_stop_not_subject_stop": base220.dispatch(final) == "observer-stop",
        "one_fresh_actor": bool(assimilation and final["fixed_g6_recurrence_driver"]["accepted_actors"] == parent["fixed_g6_recurrence_driver"]["accepted_actors"] + 1),
        "pulse_erased_control_stops": base220.dispatch(parent) == "observer-stop",
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": PULSE_VERSION,
        "source_subject_digest": parent["artifact_digest"],
        "pulse": pulse,
        "world": world,
        "assimilation": {"accepted": assimilation["accepted"], "binding": assimilation["binding"], "decision": assimilation["decision"], "contact_check": assimilation["contact_check"]} if assimilation else None,
        "score": {"post_correction_contacts": 1 if world else 0, "fresh_accepted_actors": 1 if assimilation and assimilation["accepted"] else 0, "exact_new_reopenings": 1 if gates["final_g6_live_pending"] else 0},
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "continuation_liveness": final.get("continuation_liveness"),
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 1 if assimilation else 0,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
