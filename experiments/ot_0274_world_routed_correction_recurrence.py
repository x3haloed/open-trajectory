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
BASE_PATH = ROOT / "ot_0273_receipted_correction_counterexample.py"
BASE_SHA256 = "32e4a0bc9a4cb6af2ffbf6f0c2fe3abec3365ecb32938ba59cf0c280c26d0e20"
PARENT_DIGEST = "c94a481fd5f010feb90fa283ace3f0a5ed556d5f788e70b460dbd0945025f295"
OT273_RECEIPT = "16dcaf51c414812ebede8726270a56807d35f1f70c809a66772c4707273fbd47"
OT268_RECEIPT = "7026047afea9989082ac529770c934b3c63512ebc2de03d6c7d715d74c1743d1"
AUTHORITY = "ot-0274-world-routed-correction-recurrence"
PULSE = None
MAX_CALLS = 8


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0273 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0274_frozen_ot0273", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base273 = load_base()
base272 = base273.base272
base271 = base273.base271
base268 = base273.base268
base264 = base272.base264
base260 = base272.base260
base252 = base272.base252
base245 = base272.base245
base244 = base272.base244
base256 = base272.base256
authority_base = base273.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0274").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0273", "open-subject-after-receipted-correction.json"
    )
    result273 = selector_base.load_artifact(
        p82, repo, store, "OT-0273", "receipted-correction-counterexample-aggregate.json"
    )
    package = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-three-lantern-world-package.json"
    )
    result268 = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-world-package-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result273, package, result268, base, base130


def selected(subject):
    return base271.selected(subject)


def feedback_mode(subject):
    disclosure = subject.get("active_correction_disclosure")
    if not isinstance(disclosure, dict) or disclosure.get("status") != "awaiting-revision":
        return False
    _, _, _, _, target, path = selected(subject)
    return disclosure.get("target_symbol") == target and disclosure.get("target_path") == path


def all_examples(subject, package, p82):
    evaluation = base268.evaluate_package(package, p82.digest)
    return base271.correction_examples(package, evaluation, selected(subject)[4], count=6)


def compile_unresolved_feedback(subject, actor, world, package, p82):
    if not (
        actor.get("accepted")
        and actor.get("binding")
        and world.get("outcome") == "unresolved"
        and not world.get("promotion_gate")
        and world.get("source_subject_digest") == subject["artifact_digest"]
        and world.get("ot0268_aggregate_receipt_digest") == OT268_RECEIPT
        and world.get("unchanged_control", {}).get("matches") == 2
    ):
        raise RuntimeError("unresolved correction authority mismatch")
    _, pending, _, _, target, path = selected(subject)
    binding = actor["binding"]
    if not (
        binding.get("target_path") == path
        and actor.get("decision", {}).get("target_symbol") == target
        and world.get("target_symbol") == target
        and world.get("target_path") == path
        and binding.get("patched_source_digest") == p82.digest(binding.get("patched_source"))
    ):
        raise RuntimeError("unresolved correction binding mismatch")
    prior = (
        copy.deepcopy(subject["active_correction_disclosure"]["cases"])
        if feedback_mode(subject)
        else all_examples(subject, package, p82)[:4]
    )
    disclosed = {row["case_id"] for row in prior}
    mismatches = [
        row
        for row in world["result"]["rows"]
        if not row.get("matches") and row.get("case_id") not in disclosed
    ]
    if not mismatches:
        raise RuntimeError("unresolved consequence has no undisclosed counterexample")
    mismatch = sorted(mismatches, key=lambda row: row["case_id"])[0]
    examples = all_examples(subject, package, p82)
    index = int(mismatch["case_id"].rsplit("-", 1)[1]) - 1
    counterexample = copy.deepcopy(examples[index])
    if counterexample["expected"] != mismatch["expected"]:
        raise RuntimeError("counterexample reconstruction mismatch")
    body = {
        "authority": AUTHORITY + "-failed-attempt-world-feedback",
        "source_subject_digest": subject["artifact_digest"],
        "contact_identity": pending["contact_identity"],
        "failed_actor_binding_digest": binding["binding_digest"],
        "failed_world_receipt_digest": world["receipt_digest"],
        "failed_candidate_source": binding["patched_source"],
        "failed_candidate_source_digest": binding["patched_source_digest"],
        "candidate_matches": world["result"]["matches"],
        "unchanged_matches": world["unchanged_control"]["matches"],
        "counterexample_selection": "lowest-canonical-undisclosed-mismatch",
        "counterexample": counterexample,
        "reference_source_available": False,
        "remaining_sealed_cases_available": False,
    }
    feedback = {**body, "receipt_digest": p82.digest(body)}
    cases = [*prior, counterexample]
    disclosure_body = {
        "authority": AUTHORITY + "-active-correction-disclosure",
        "source_subject_digest": subject["artifact_digest"],
        "feedback_receipt_digest": feedback["receipt_digest"],
        "target_symbol": target,
        "target_path": path,
        "cases": cases,
        "case_count": len(cases),
        "reference_source_available": False,
        "remaining_sealed_cases_available": False,
        "status": "awaiting-revision",
    }
    disclosure = {**disclosure_body, "disclosure_digest": p82.digest(disclosure_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["retained_failed_correction_attempts"] = [
        *child.get("retained_failed_correction_attempts", []),
        feedback,
    ]
    child["active_correction_disclosure"] = disclosure
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Revise the unresolved correction after receipted counterexample contact.",
    }
    child["unresolved"] = "Continue correction from the retained failed hypothesis and new world counterexample."
    return p82.seal(child), feedback


def fixture_action(subject, source, p82):
    decision = base271.decision_template(subject)
    decision.update(
        rationale="Prospective correction branch fixture.",
        next_pursuit="Continue according to objective consequence.",
    )
    body = {
        "authority": AUTHORITY + "-fixture-binding",
        "source_subject_digest": subject["artifact_digest"],
        "target_path": selected(subject)[5],
        "decision": decision,
        "patched_source": source,
        "patched_source_digest": p82.digest(source),
    }
    return {
        "accepted": True,
        "decision": decision,
        "binding": {**body, "binding_digest": p82.digest(body)},
    }


def sabotage(reference, case_input):
    first, rest = reference.split("\n", 1)
    return first + "\n    if case == " + repr(case_input) + ":\n        return None\n" + rest


def finish_branch(subject, p82, runtime):
    refreshed = base264.refresh_projection_only(subject, p82)
    observation = base272.empty_feed_observation(refreshed, p82)
    waiting, reused = base256.compile_wait(refreshed, observation, p82)
    repeated_observation = base272.empty_feed_observation(waiting, p82)
    repeated, repeated_reused = base256.compile_wait(waiting, repeated_observation, p82)
    return {
        "final": repeated,
        "refresh_empty": refreshed["active_opportunity_projection"]["opportunity_count"] == 0,
        "saturated": len(base244.remaining_epoch(refreshed)) == 0,
        "next_after_refresh": base272.derive(refreshed, p82),
        "wait_installed": not reused,
        "wait_reobserved": repeated_reused and repeated["artifact_digest"] == waiting["artifact_digest"],
        "conformant": runtime.identity_conforms(repeated),
    }


def prospective_branch(root, selected_subject, failures, package, result268, p82, runtime):
    subject = selected_subject
    reference = package["sealed_reference_sources"][selected(subject)[5]]
    feedback_receipts = []
    for offset in range(failures):
        examples = all_examples(subject, package, p82)
        source = sabotage(reference, examples[4 + offset]["input"])
        actor = fixture_action(subject, source, p82)
        public_cases = (
            subject["active_correction_disclosure"]["cases"]
            if feedback_mode(subject)
            else examples[:4]
        )
        public = base271.compare_source(source, selected(subject)[4], public_cases)
        world = base271.sealed_followup(subject, actor, package, result268, p82)
        subject, feedback = compile_unresolved_feedback(subject, actor, world, package, p82)
        feedback_receipts.append(
            {
                "public_matches": public["matches"],
                "public_count": len(public_cases),
                "world_matches": world["result"]["matches"],
                "case_count_after": subject["active_correction_disclosure"]["case_count"],
                "receipt_digest": feedback["receipt_digest"],
                "conformant": runtime.identity_conforms(subject),
            }
        )
    actor = fixture_action(subject, reference, p82)
    public_cases = (
        subject["active_correction_disclosure"]["cases"]
        if feedback_mode(subject)
        else all_examples(subject, package, p82)[:4]
    )
    public = base271.compare_source(reference, selected(subject)[4], public_cases)
    world = base271.sealed_followup(subject, actor, package, result268, p82)
    corrected = (
        base273.compile_success(subject, actor, world, p82)
        if feedback_mode(subject)
        else base271.compile_correction(subject, actor, world, p82)
    )
    finished = finish_branch(corrected, p82, runtime)
    return {
        "failure_count": failures,
        "feedback": feedback_receipts,
        "success_public_matches": public["matches"],
        "success_public_count": len(public_cases),
        "success_world_matches": world["result"]["matches"],
        "success_control_matches": world["unchanged_control"]["matches"],
        **finished,
    }


def preflight(root, p82, runtime, parent, result273, package, result268):
    root.mkdir(parents=True, exist_ok=True)
    refreshed = base264.refresh_projection_only(parent, p82)
    remaining = refreshed["active_opportunity_projection"]["opportunities"]
    target = remaining[0]["target_symbol"] if len(remaining) == 1 else None
    selection = base272.selection_fixture(
        root / "selection", refreshed, package, result268, target, p82, runtime
    )
    selected_subject = selection["final"]
    branches = [
        prospective_branch(root / f"branch-{failures}", selected_subject, failures, package, result268, p82, runtime)
        for failures in range(3)
    ]
    route, identity = base272.base265.floors(parent)
    script = Path(__file__).read_text()
    evaluation = base268.evaluate_package(package, p82.digest)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open_refresh": parent["artifact_digest"] == PARENT_DIGEST and base272.derive(parent, p82) == "refresh-opportunity-projection" and runtime.identity_conforms(parent),
        "ot0273_exact_promotion": result273["receipt_digest"] == OT273_RECEIPT and result273["observer_disposition"] == "promoted" and result273["final_subject_digest"] == PARENT_DIGEST,
        "one_remaining_after_refresh": len(remaining) == 1 and target is not None,
        "selection_2_of_6": selection["checker"] and selection["semantic"] and selection["world"]["result"]["matches"] == 2 and selection["routes_correction"],
        "three_consequence_branches": [row["failure_count"] for row in branches] == [0, 1, 2],
        "feedback_adds_one_case": all(all(item["public_matches"] == item["public_count"] and item["world_matches"] < 6 and item["case_count_after"] == 5 + index and item["conformant"] for index, item in enumerate(row["feedback"])) for row in branches),
        "all_success_6_2": all(row["success_public_matches"] == row["success_public_count"] and row["success_world_matches"] == 6 and row["success_control_matches"] == 2 for row in branches),
        "all_reach_fourth_wait": all(row["refresh_empty"] and row["saturated"] and row["wait_installed"] and row["wait_reobserved"] and row["conformant"] and len(row["final"]["world_stream_wait_receipts"]) == 4 for row in branches),
        "refresh_successors_exhaustive": base272.derive(refreshed, p82) == "expanded-select" and all(row["next_after_refresh"] == "expand-environment" for row in branches),
        "dynamic_surface_not_hardcoded": all(token not in script for name, path in evaluation["targets"].items() for token in (name, path)),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "checks": checks, "branches": [{key: value for key, value in row.items() if key != "final"} for row in branches]}
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def run_correction(context, p82, root, subject, package, result268):
    mode = "feedback" if feedback_mode(subject) else "initial"
    actor = (
        base273.run_actor(context, p82, root / "actor", subject, package)
        if mode == "feedback"
        else base271.run_actor(context, p82, root / "actor", subject, package, base268.evaluate_package(package, p82.digest))
    )
    world = base271.sealed_followup(subject, actor, package, result268, p82) if actor["accepted"] else None
    feedback = None
    if world and world["promotion_gate"]:
        final = base273.compile_success(subject, actor, world, p82) if mode == "feedback" else base271.compile_correction(subject, actor, world, p82)
        transition = "success-to-refresh"
    elif world and world["outcome"] == "unresolved":
        final, feedback = compile_unresolved_feedback(subject, actor, world, package, p82)
        transition = "unresolved-to-more-correction"
    else:
        final = subject
        transition = "rejected"
    return mode, actor, world, feedback, final, transition


def advance(repo, run, p82, runtime, parent, package, result268, fixtures, base, base130):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0274 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0274 unavailable")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0274 checkpoint")
    operation = base272.derive(subject, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {"authority": AUTHORITY + "-pulse", "content": PULSE, "source_subject_digest": subject["artifact_digest"], "derived_operation": operation}
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    final = subject
    transition = operation
    checks = {"content_free": pulse["content"] is None}
    if operation == "refresh-opportunity-projection":
        final = base264.refresh_projection_only(subject, p82)
        checks.update(zero_fresh_actors=True, projection_fresh=not base260.needs_refresh(final, p82), next_derived=base272.derive(final, p82) in {"expanded-select", "expand-environment"})
    elif operation == "expanded-select":
        actor, world, final = base272.live_selection(context_for(base, base130, runtime, root, repo), p82, root, subject, package, result268)
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], retained_package_2_of_6=bool(world and world["result"]["matches"] == 2), next_is_correction=base272.derive(final, p82) == "outward-correct")
    elif operation == "outward-correct":
        mode, actor, world, feedback, final, transition = run_correction(context_for(base, base130, runtime, root, repo), p82, root, subject, package, result268)
        public_count = actor["public"]["case_count"] if actor and actor.get("public") else 0
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], disclosed_all_pass=bool(actor["public"] and actor["public"]["matches"] == public_count), unchanged_2_of_6=bool(world and world["unchanged_control"]["matches"] == 2), consequence_routes=transition in {"success-to-refresh", "unresolved-to-more-correction"}, next_matches_consequence=(base272.derive(final, p82) == ("refresh-opportunity-projection" if transition == "success-to-refresh" else "outward-correct")))
    elif operation == "expand-environment":
        world = base272.empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(zero_fresh_actors=True, saturated=len(base244.remaining_epoch(subject)) == 0, fourth_wait_installed=not reused and len(final["world_stream_wait_receipts"]) == 4, next_is_wait=base272.derive(final, p82) == "wait-provider")
    elif operation == "wait-provider":
        world = base272.empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(zero_fresh_actors=True, wait_exact_noop=reused and final["artifact_digest"] == subject["artifact_digest"])
    else:
        checks["known_operation"] = False
    checks["final_open_conformant"] = final["continuation"]["status"] == "open" and runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + f"-invocation-{index:02d}", "invocation_index": index, "source_subject_digest": subject["artifact_digest"], "pulse": pulse, "transition": transition, "actor": actor, "world": world, "feedback": feedback, "checks": checks, "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1 if actor else 0}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    done = operation == "wait-provider" and checks.get("wait_exact_noop")
    if not done:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    rows = effective_results(run)
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_recurrence": 6 <= len(rows) <= 8 and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "structural_sequence": operations[0:2] == ["refresh-opportunity-projection", "expanded-select"] and operations[-3:] == ["refresh-opportunity-projection", "expand-environment", "wait-provider"] and all(value == "outward-correct" for value in operations[2:-3]),
        "world_routed_corrections": 1 <= len(corrections) <= 3 and corrections[-1]["transition"] == "success-to-refresh" and all(row["transition"] == "unresolved-to-more-correction" for row in corrections[:-1]),
        "actor_count_matches": sum(row["fresh_actor_count"] for row in rows) == 1 + len(corrections),
        "fourth_wait_exact": len(final["world_stream_wait_receipts"]) == 4 and len(final["world_stream_wait_discharge_receipts"]) == 3 and base272.derive(final, p82) == "wait-provider",
        "final_open_conformant": final["continuation"]["status"] == "open" and runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "invocation_receipt_digests": [row["receipt_digest"] for row in rows], "checks": gates, "operations": operations, "correction_transitions": [row["transition"] for row in corrections], "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": sum(row["fresh_actor_count"] for row in rows)}
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def context_for(base, base130, runtime, root, repo):
    return base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, root, repo))


def repair_saturated_refresh_report(run, p82, runtime):
    failed_path = run / "invocation-05-result.json"
    subject_path = run / "invocation-05-subject.json"
    repair_path = run / "invocation-05-reconstruction.json"
    checkpoint = run / "checkpoint-subject.json"
    if repair_path.exists() or not failed_path.exists():
        return
    failed = json.loads(failed_path.read_text())
    retained = json.loads(subject_path.read_text())
    prior = json.loads(checkpoint.read_text())
    expected_failed = {
        "content_free": True,
        "final_open_conformant": True,
        "next_is_selection": False,
        "passed": False,
        "projection_fresh": True,
        "zero_fresh_actors": True,
    }
    recomputed = base264.refresh_projection_only(prior, p82)
    if not (
        failed.get("checks") == expected_failed
        and failed.get("pulse", {}).get("derived_operation")
        == "refresh-opportunity-projection"
        and failed.get("source_subject_digest") == prior["artifact_digest"]
        and failed.get("final_subject_digest") == retained["artifact_digest"]
        and retained["artifact_digest"] == recomputed["artifact_digest"]
        and base272.derive(retained, p82) == "expand-environment"
        and runtime.identity_conforms(retained)
    ):
        raise RuntimeError("OT-0274 refresh reconstruction mismatch")
    repaired = copy.deepcopy(failed)
    repaired["authority"] = AUTHORITY + "-invocation-05-reconstruction"
    repaired["checks"] = {
        "content_free": True,
        "final_open_conformant": True,
        "next_derived": True,
        "passed": True,
        "projection_fresh": True,
        "zero_fresh_actors": True,
    }
    repaired["reconstruction"] = {
        "authority": AUTHORITY + "-saturated-refresh-reporter-repair",
        "original_receipt_digest": failed["receipt_digest"],
        "retained_subject_digest": retained["artifact_digest"],
        "correction": "accept-refresh-to-expanded-select-or-expand-environment",
        "actor_resampled": False,
        "subject_recomputed_exactly": True,
    }
    repaired.pop("receipt_digest", None)
    repaired["receipt_digest"] = p82.digest(repaired)
    write_json(repair_path, repaired)
    write_json(checkpoint, retained)


def effective_results(run):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    repair = run / "invocation-05-reconstruction.json"
    if repair.exists():
        replacement = json.loads(repair.read_text())
        rows = [replacement if row["invocation_index"] == 5 else row for row in rows]
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result273, package, result268, base, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(run / "preflight", p82, runtime, parent, result273, package, result268)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    repair_saturated_refresh_report(run, p82, runtime)
    return advance(repo, run, p82, runtime, parent, package, result268, fixtures, base, base130)


if __name__ == "__main__":
    raise SystemExit(main())
