from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0299_second_developmental_target_correction.py"
BASE_SHA256 = "fea25a376fe35b61fac1245ebf75ae9415292714ea438b7252d9acdde748dde3"
PARENT_DIGEST = "9d0546e6083f8eef301450fc3a0490a0968baff2b84f5565b82e1da73027fad3"
OT299_RECEIPT = "cb2f40eb52213a67cc806fee85c5dc760eb4a7fb50d8628efeb4f6b19f97dcb8"
AUTHORITY = "ot-0300-final-surface-to-eighth-wait"
MAX_CALLS = 8


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0299 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0300_frozen_ot0299", BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


base299 = load_base(); base297 = base299.base297; base295 = base299.base295; b = base299.b
b.AUTHORITY = AUTHORITY; b.base274.AUTHORITY = AUTHORITY; b.base274.MAX_CALLS = MAX_CALLS


def write_json(path, value): base295.write_json(path, value)
def lineage(subject): return base295.lineage_projection(subject)


def setup(args):
    chain = b.authority_base.guide_base.load_base(); selector, core, base130 = chain.selector_base, chain.base, chain.base130
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0300").resolve()
    prior92 = core.mechanism.load_prior(); _, _, _, p82 = core.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(p82, repo, store, "OT-0299", "open-subject-after-second-developmental-correction.json")
    result299 = selector.load_artifact(p82, repo, store, "OT-0299", "second-developmental-target-correction-aggregate.json")
    package = selector.load_artifact(p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json")
    result280 = selector.load_artifact(p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json")
    return repo, run, p82, runtime, parent, result299, package, result280, core, base130


def prospective(root, parent, depth, package, result280, p82, runtime):
    refreshed = b.base264.refresh_projection_only(parent, p82); opportunities = refreshed["active_opportunity_projection"]["opportunities"]
    target = opportunities[0]["target_symbol"]
    selection = b.base272.selection_fixture(root / "selection", refreshed, package, result280, target, p82, runtime)
    seed = root / "selection" / "actor" / "seed"
    selected = selection["final"]
    corrected, correction = b.correction_variant(selected, depth, package, result280, p82, runtime)
    saturated = b.base264.refresh_projection_only(corrected, p82)
    observation = b.base272.empty_feed_observation(saturated, p82); waiting, reused = b.base256.compile_wait(saturated, observation, p82)
    repeat_observation = b.base272.empty_feed_observation(waiting, p82); repeated, repeated_reused = b.base256.compile_wait(waiting, repeat_observation, p82)
    return {
        "selection": selection["checker"] and selection["semantic"] and selection["public"] and selection["prompt_neutral"] and selection["world"]["result"]["matches"] == 2 and selection["routes_correction"] and b.base281.base270.seed_excludes_sealed(seed, package, result280),
        "correction": correction["feedback_passed"] and correction["success_public"] and correction["success_6_2"] and correction["routes_refresh"] and correction["conformant"],
        "all_earned": len(base297.earned_targets(repeated, package)) == 3,
        "saturated": len(b.base244.remaining_epoch(repeated)) == 0 and b.base272.derive(saturated, p82) == "expand-environment",
        "eighth_wait": not reused and repeated_reused and len(repeated["world_stream_wait_receipts"]) == 8 and len(repeated["world_stream_wait_discharge_receipts"]) == 7,
        "exact_reobserve": repeated["artifact_digest"] == waiting["artifact_digest"],
        "renewal_next": b.base279.derive(repeated, [], p82) == "renew-world-feed",
        "lineage_exact": lineage(repeated) == lineage(parent),
        "conformant": runtime.identity_conforms(repeated),
    }


def preflight(root, p82, runtime, parent, result299, package, result280):
    root.mkdir(parents=True, exist_ok=True); refreshed = b.base264.refresh_projection_only(parent, p82); opportunities = refreshed["active_opportunity_projection"]["opportunities"]
    target = opportunities[0]["target_symbol"] if len(opportunities) == 1 else ""
    fixture_selected = b.base272.selection_fixture(root / "capacity", refreshed, package, result280, target, p82, runtime)["final"] if target else parent
    capacity = len(base295.undisclosed(fixture_selected, package, p82)) if target else -1
    branches = [prospective(root / f"depth-{depth}", parent, depth, package, result280, p82, runtime) for depth in range(capacity + 1)]
    route, identity = b.base272.base265.floors(parent); script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_two_earned_refresh": parent["artifact_digest"] == PARENT_DIGEST and b.base272.derive(parent, p82) == "refresh-opportunity-projection" and len(base297.earned_targets(parent, package)) == 2 and runtime.identity_conforms(parent),
        "ot0299_exact_promotion": result299["receipt_digest"] == OT299_RECEIPT and result299["observer_disposition"] == "promoted" and result299["final_subject_digest"] == PARENT_DIGEST,
        "one_remaining_two_hidden_classes": len(opportunities) == 1 and capacity == 2,
        "three_complete_suffixes": len(branches) == 3 and all(all(row.values()) for row in branches),
        "dynamic_final_target": target not in script and opportunities[0]["target_path"] not in script and package["world_id"] not in script,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }; checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "feedback_capacity": capacity, "branch_count": len(branches), "checks": checks}; result["receipt_digest"] = p82.digest(result); write_json(root / "fixture-conformance.json", result); return result


def valid_shape(operations, transitions):
    if operations[:2] != ["refresh-opportunity-projection", "expanded-select"]: return False
    index = 2
    while index < len(operations) and operations[index] == "outward-correct": index += 1
    count = index - 2
    return 1 <= count <= 3 and transitions == ["unresolved-to-more-correction"] * (count - 1) + ["success-to-refresh"] and operations[index:] == ["refresh-opportunity-projection", "expand-environment", "wait-provider"]


def finalize(run, fixtures, p82, runtime, parent, package, final):
    rows = [json.loads(path.read_text()) for path in sorted(run.glob("invocation-*-result.json"))]; operations = [row["pulse"]["derived_operation"] for row in rows]; transitions = [row["transition"] for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    checks = {"preflight_passed": fixtures["checks"]["passed"], "bounded_content_free_suffix": len(rows) <= MAX_CALLS and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows), "world_routed_shape": valid_shape(operations, transitions), "actor_count_matches": sum(row["fresh_actor_count"] for row in rows) == 1 + len(transitions), "all_three_earned": len(base297.earned_targets(final, package)) == 3, "eighth_wait_exact": len(final["world_stream_wait_receipts"]) == 8 and len(final["world_stream_wait_discharge_receipts"]) == 7 and b.base279.derive(final, [], p82) == "renew-world-feed", "lineage_exact": lineage(final) == lineage(parent), "final_open_conformant": final["continuation"]["status"] == "open" and runtime.identity_conforms(final)}; checks["passed"] = all(checks.values())
    aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "invocation_receipt_digests": [row["receipt_digest"] for row in rows], "operations": operations, "correction_transitions": transitions, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": sum(row["fresh_actor_count"] for row in rows)}; aggregate["receipt_digest"] = p82.digest(aggregate); write_json(run / "aggregate.json", aggregate); write_json(run / "final-full-subject.json", final); print(json.dumps(aggregate, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo, run, p82, runtime, parent, result299, package, result280, core, base130 = setup(args); retained = run / "preflight/fixture-conformance.json"; fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(run / "preflight", p82, runtime, parent, result299, package, result280)
    if args.preflight_only: print(json.dumps(fixtures, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists(): raise SystemExit("OT-0300 unavailable")
    paths = sorted(run.glob("invocation-*-result.json")); results = [json.loads(path.read_text()) for path in paths]; checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists(): raise SystemExit("preserve failed OT-0300 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent; index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject): raise SystemExit("invalid OT-0300 checkpoint")
    operation = b.base272.derive(subject, p82); root = run / f"invocation-{index:02d}"; root.mkdir(parents=True); pulse = {"authority": AUTHORITY + "-pulse", "content": None, "source_subject_digest": subject["artifact_digest"], "derived_operation": operation}; pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None; transition = operation; context = b.base274.context_for(core, base130, runtime, root, repo); checks = {"content_free": True}
    if operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82); remaining = len(final["active_opportunity_projection"]["opportunities"]); checks.update(zero_fresh_actors=True, projection_fresh=not b.base260.needs_refresh(final, p82), next_derived=b.base272.derive(final, p82) == ("expanded-select" if remaining else "expand-environment"))
    elif operation == "expanded-select":
        actor, world, final = b.base272.live_selection(context, p82, root, subject, package, result280); checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], public_seed_only=b.base281.base270.seed_excludes_sealed(root / "actor" / "seed", package, result280), retained_2_of_6=bool(world and world["result"]["matches"] == 2), next_is_correction=b.base272.derive(final, p82) == "outward-correct")
    elif operation == "outward-correct":
        _, actor, world, feedback, final, transition = b.base274.run_correction(context, p82, root, subject, package, result280); public_count = actor["public"]["case_count"] if actor and actor.get("public") else 0; checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], disclosed_all_pass=bool(actor["public"] and actor["public"]["matches"] == public_count), unchanged_2_of_6=bool(world and world["unchanged_control"]["matches"] == 2), consequence_routes=transition in {"success-to-refresh", "unresolved-to-more-correction"}, next_matches=b.base272.derive(final, p82) == ("refresh-opportunity-projection" if transition == "success-to-refresh" else "outward-correct"))
    elif operation == "expand-environment":
        world = b.base272.empty_feed_observation(subject, p82); final, reused = b.base256.compile_wait(subject, world, p82); checks.update(zero_fresh_actors=True, saturated=len(b.base244.remaining_epoch(subject)) == 0, eighth_wait_installed=not reused and len(final["world_stream_wait_receipts"]) == 8 and len(final["world_stream_wait_discharge_receipts"]) == 7, next_is_wait=b.base272.derive(final, p82) == "wait-provider")
    elif operation == "wait-provider":
        world = b.base272.empty_feed_observation(subject, p82); final, reused = b.base256.compile_wait(subject, world, p82); checks.update(zero_fresh_actors=True, wait_exact_noop=reused and final["artifact_digest"] == subject["artifact_digest"], renewal_next=b.base279.derive(final, [], p82) == "renew-world-feed")
    else: final = subject; checks["known_operation"] = False
    checks.update(lineage_exact=lineage(final) == lineage(parent), final_open_conformant=final["continuation"]["status"] == "open", identity_conformant=runtime.identity_conforms(final)); checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + f"-invocation-{index:02d}", "invocation_index": index, "source_subject_digest": subject["artifact_digest"], "pulse": pulse, "transition": transition, "actor": copy.deepcopy(actor), "world": world, "feedback": feedback, "checks": checks, "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1 if actor else 0}; result["receipt_digest"] = p82.digest(result); write_json(run / f"invocation-{index:02d}-result.json", result); write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]: print(json.dumps(result, indent=2, sort_keys=True)); return 2
    write_json(checkpoint, final)
    if operation == "wait-provider": return finalize(run, fixtures, p82, runtime, parent, package, final)
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
