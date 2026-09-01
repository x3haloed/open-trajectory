from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from open_trajectory_harness.continuation_pulse import InvocationCallbacks, continue_once, pulse_eligible


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0221_cross_invocation_continuation_pulse.py"
BASE_SHA256 = "207d1ccc0d295105c7ab78193fa388d70069b15a77df55c5d9438da6d4d355d8"
INVOKER_PATH = REPO / "src/open_trajectory_harness/continuation_pulse.py"
INVOKER_SHA256 = "9eaf93754954b844608e2ad90989129fc4f65751fae2e9b950afb253315576b9"
PARENT_DIGEST = "b5c955a4d025b261983114f17392b76cd1dd1fcc8cac293b2f115a8210c98ab2"
OT221_RECEIPT = "3d5cdb3456ec7485903f67b8cacadfe5ab3b64d7b99e59e123ad20bd325bf328"
AUTHORITY = "ot-0222-reusable-pulse-driven-invoker-v1"
INVOCATION_COUNT = 2


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0221 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0222_frozen_ot0221", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base221 = load_base()
base220 = base221.base220
base219 = base220.base219
base213 = base220.base213
authority_base = base220.authority_base


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def callbacks_for(context, prior131, p82, root: Path) -> InvocationCallbacks:
    root.mkdir(parents=True)

    def contact_world(subject: dict[str, Any]) -> dict[str, Any]:
        encounter = subject["fixed_g6_recurrence_driver"]["encounters"] + 1
        package = subject["pending_contact_bearing_continuations"][-1]["package"]
        world = base220.execute_hidden(root / "world", subject, package, encounter, p82)
        write_json(root / "world-receipt.json", world)
        return world

    def compile_world(subject: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
        return base220.compile_world(subject, world, p82)

    def assimilate(subject: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
        return base220.run_contact_actor(context, prior131, p82, root / "assimilation", subject, "assimilator", resolved)

    def compile_pending(subject: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
        return base220.compile_pending(subject, action, p82)

    def observer_stop(subject: dict[str, Any]) -> dict[str, Any]:
        return base220.observer_stop(subject, p82)

    def correct(subject: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        correction = base220.run_corrector(context, prior131, p82, root / "correction", subject, world)
        summary: dict[str, Any] = {"accepted": correction["accepted"], "binding_digest": correction["binding"]["binding_digest"] if correction["accepted"] else None}
        if not correction["accepted"]:
            return subject, summary
        followup = base220.evaluate_correction(root / "correction-world", subject, correction, world, p82)
        write_json(root / "correction-world-receipt.json", followup)
        summary["followup"] = followup
        if not followup["promotion_gate"]:
            return subject, summary
        return base220.compile_correction(subject, correction, followup, p82), summary

    return InvocationCallbacks(
        dispatch=base220.dispatch,
        contact_world=contact_world,
        compile_world=compile_world,
        resolve_for_assimilation=base220.resolved_for_assimilation,
        assimilate=assimilate,
        compile_pending=compile_pending,
        observer_stop=observer_stop,
        correct=correct,
    )


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
    run = (args.evidence_root or store / "runs/OT-0222").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0221", "open-subject-after-continuation-pulse.json")
    result221 = selector_base.load_artifact(p82, repo, store, "OT-0221", "cross-invocation-continuation-pulse-aggregate.json")

    fixture_root = run.parent / "OT-0222-preflight"
    import shutil
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    pending = parent["pending_contact_bearing_continuations"][-1]
    environment = fixture_root / "environment"
    available = base220.available_at(environment, parent)
    registry = base220.completed_registry(parent, available)
    replay = base219.g6(base219.decision(parent["continuation"]["next_opening"], pending["package"]), registry, available)
    fixture_world = base220.execute_hidden(fixture_root / "world", parent, pending["package"], 4, p82)
    unit = subprocess.run([sys.executable, "-m", "unittest", "tests.test_continuation_pulse"], cwd=repo, env={"PYTHONPATH": str(repo / "src")}, capture_output=True)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    invoker_text = INVOKER_PATH.read_text()
    controls = {
        "closed_rejected": not pulse_eligible({**parent, "continuation": {**parent["continuation"], "status": "closed"}}),
        "task_content_absent": "target_symbol" not in invoker_text and "next_pursuit" not in invoker_text,
    }
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "invoker_hash_exact": hashlib.sha256(INVOKER_PATH.read_bytes()).hexdigest() == INVOKER_SHA256,
        "parent_exact_eligible": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and pulse_eligible(parent),
        "ot0221_exact_promotion": result221["observer_disposition"] == "promoted" and result221["receipt_digest"] == OT221_RECEIPT and result221["final_subject_digest"] == PARENT_DIGEST,
        "pending_g6_replays": replay["accepted"] and replay["projected_identity"] == pending["contact_identity"],
        "fixture_world_6_of_6": fixture_world["outcome"] == "success" and fixture_world["result"]["matches"] == 6,
        "invoker_unit_tests_pass": unit.returncode == 0,
        "controls_pass": all(controls.values()),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "invoker_sha256": INVOKER_SHA256, "g6_replay": replay, "fixture_world": fixture_world, "controls": controls, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0222 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")

    started = time.time()
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    current = parent
    invocations = []
    intermediates = []
    for index in range(1, INVOCATION_COUNT + 1):
        if not pulse_eligible(current):
            break
        before = current
        current, trace = continue_once(current, digest=p82.digest, seal=p82.seal, authority=AUTHORITY, callbacks=callbacks_for(context, prior131, p82, run / f"invocation-{index}"))
        trace_summary = {
            "index": index,
            "status": trace["status"],
            "source_subject_digest": before["artifact_digest"],
            "final_subject_digest": current["artifact_digest"],
            "pulse_receipt_digest": trace["pulse"]["receipt_digest"],
            "world": trace.get("world"),
            "correction": trace.get("correction"),
            "assimilation_accepted": bool(trace.get("assimilation") and trace["assimilation"].get("accepted")),
            "assimilation_binding_digest": trace["assimilation"]["binding"]["binding_digest"] if trace.get("assimilation") and trace["assimilation"].get("accepted") else None,
            "input_target": trace.get("world", {}).get("target_symbol"),
            "output_target": current["pending_contact_bearing_continuations"][-1]["package"]["target_symbol"] if trace["status"] == "completed" else None,
        }
        invocations.append(trace_summary)
        write_json(run / f"invocation-{index}-summary.json", trace_summary)
        if trace["status"] != "completed" or not runtime.identity_conforms(current):
            break
        intermediates.append(current)
        write_json(run / f"subject-after-invocation-{index}.json", current)

    final_ok = runtime.identity_conforms(current)
    completed = [row for row in invocations if row["status"] == "completed"]
    fresh_actors = sum(1 for row in completed if row["assimilation_accepted"]) + sum(1 for row in completed if row.get("correction") and row["correction"].get("accepted"))
    gates = {
        "preflight_passed": checks["passed"],
        "two_same_invoker_calls_completed": len(completed) == 2,
        "two_decisive_worlds": len(completed) == 2 and all(row["world"]["outcome"] in {"success", "surrender"} for row in completed),
        "all_opened_actors_accepted": len(completed) == 2 and all(row["assimilation_accepted"] for row in completed),
        "both_outputs_conform": len(intermediates) == 2,
        "adjacent_targets_change": len(completed) == 2 and all(row["input_target"] != row["output_target"] for row in completed),
        "final_exact_open_subject": final_ok and current["continuation"]["status"] == "open",
        "final_g6_live_pending": current["continuation_liveness"]["status"] == "live" and current["pending_contact_bearing_continuations"][-1]["consequence_status"] == "unreceipted",
        "final_observer_stop_is_eligible": base220.dispatch(current) == "observer-stop" and pulse_eligible(current),
        "controls_pass": all(controls.values()),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invoker_sha256": INVOKER_SHA256,
        "invocations": invocations,
        "score": {"completed_invocations": len(completed), "decisive_worlds": sum(row["world"]["outcome"] in {"success", "surrender"} for row in completed), "fresh_accepted_actors": fresh_actors, "exact_reopenings": len(intermediates)},
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "continuation_liveness": current.get("continuation_liveness"),
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "fresh_actor_count": fresh_actors,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", current)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
