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
BASE_PATH = ROOT / "ot_0272_independent_package_epoch_to_fourth_wait.py"
BASE_SHA256 = "1f9c438a04c5621d1b2aed34bac204e71d7b8fd1321086814da40de66a8b07e1"
PARENT_DIGEST = "2b42db9313ff7f1cb9a887172e9576f9a281d712293ff740837aae99b0b4e7f1"
FAILED_RECEIPT = "f7aeed34cf028a8f12991f68fc21bbccc15e0ccd7afafb4a0b3b946d49f5f22b"
OT268_RECEIPT = "7026047afea9989082ac529770c934b3c63512ebc2de03d6c7d715d74c1743d1"
AUTHORITY = "ot-0273-receipted-correction-counterexample"
EXPECTED = ("retain-correction-feedback", "outward-correct")
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0272 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0273_frozen_ot0272", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base272 = load_base()
base271 = base272.base271
base268 = base272.base268
base236 = base271.base236
authority_base = base272.authority_base
CORRECTION_CORE = base271.CORRECTION_CORE
CORRECTION_PREDICATES = base271.CORRECTION_PREDICATES
SCHEMA = base271.SCHEMA


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0273").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0272",
        "open-partial-subject-at-underdetermined-correction.json",
    )
    failed = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0272",
        "underdetermined-correction-rejected-result.json",
    )
    package = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-three-lantern-world-package.json"
    )
    result268 = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-world-package-aggregate.json"
    )
    return repo, run, p82, runtime, parent, failed, package, result268, base, base130


def selected(subject):
    return base271.selected(subject)


def full_examples(package, digest, subject):
    evaluation = base268.evaluate_package(package, digest)
    target = selected(subject)[4]
    return base271.correction_examples(package, evaluation, target, count=6)


def feedback_receipt(subject, failed, package, p82):
    if not (
        failed.get("receipt_digest") == FAILED_RECEIPT
        and failed.get("source_subject_digest") == subject["artifact_digest"]
        and failed.get("checks", {}).get("actor_accepted")
        and failed.get("checks", {}).get("public_4_of_4")
        and not failed.get("checks", {}).get("retained_package_6_of_6")
        and failed.get("world", {}).get("outcome") == "unresolved"
        and failed.get("world", {}).get("ot0268_aggregate_receipt_digest")
        == OT268_RECEIPT
    ):
        raise RuntimeError("failed correction authority mismatch")
    extension, pending, _, _, target, path = selected(subject)
    actor = failed["actor"]
    world = failed["world"]
    if not (
        actor["binding"]["target_path"] == path
        and actor["decision"]["target_symbol"] == target
        and world["target_symbol"] == target
        and world["target_path"] == path
        and world["source_subject_digest"] == subject["artifact_digest"]
        and world["unchanged_control"]["matches"] == 2
    ):
        raise RuntimeError("failed correction target mismatch")
    mismatches = [row for row in world["result"]["rows"] if not row.get("matches")]
    if not mismatches:
        raise RuntimeError("failed correction has no counterexample")
    mismatch = sorted(mismatches, key=lambda row: row["case_id"])[0]
    index = int(mismatch["case_id"].rsplit("-", 1)[1]) - 1
    examples = full_examples(package, p82.digest, subject)
    counterexample = copy.deepcopy(examples[index])
    if not (
        counterexample["expected"] == mismatch["expected"]
        and actor["binding"]["patched_source_digest"]
        == p82.digest(actor["binding"]["patched_source"])
    ):
        raise RuntimeError("counterexample reconstruction mismatch")
    body = {
        "authority": AUTHORITY + "-failed-attempt-world-feedback",
        "source_subject_digest": subject["artifact_digest"],
        "contact_identity": pending["contact_identity"],
        "failed_actor_binding_digest": actor["binding"]["binding_digest"],
        "failed_world_receipt_digest": world["receipt_digest"],
        "failed_candidate_source": actor["binding"]["patched_source"],
        "failed_candidate_source_digest": actor["binding"]["patched_source_digest"],
        "candidate_matches": world["result"]["matches"],
        "unchanged_matches": world["unchanged_control"]["matches"],
        "counterexample_selection": "lowest-canonical-mismatch",
        "counterexample": counterexample,
        "reference_source_available": False,
        "remaining_sealed_cases_available": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def compile_feedback(subject, failed, package, p82):
    feedback = feedback_receipt(subject, failed, package, p82)
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    initial = full_examples(package, p82.digest, subject)[:4]
    disclosure_body = {
        "authority": AUTHORITY + "-active-correction-disclosure",
        "source_subject_digest": subject["artifact_digest"],
        "feedback_receipt_digest": feedback["receipt_digest"],
        "target_symbol": selected(subject)[4],
        "target_path": selected(subject)[5],
        "cases": [*initial, copy.deepcopy(feedback["counterexample"])],
        "case_count": 5,
        "reference_source_available": False,
        "remaining_sealed_cases_available": False,
        "status": "awaiting-revision",
    }
    disclosure = {**disclosure_body, "disclosure_digest": p82.digest(disclosure_body)}
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
    child["unresolved"] = (
        "The prior correction remains unadmitted; continue from its receipted counterexample."
    )
    return p82.seal(child), feedback


def dynamic_checker_source(count):
    source = base271.CHECKER_SOURCE
    old = 'public["all_valid"] and public["matches"] == 4'
    new = f'public["all_valid"] and public["matches"] == {count}'
    if old not in source:
        raise RuntimeError("correction checker source changed")
    return source.replace(old, new)


def seed_actor(root, subject, package, p82):
    evaluation = base268.evaluate_package(package, p82.digest)
    seed = base271.seed_actor(
        root, subject, package, evaluation, base271.decision_template(subject)
    )
    disclosure = subject["active_correction_disclosure"]
    feedback = subject["retained_failed_correction_attempts"][-1]
    contact = {
        "authority": AUTHORITY + "-visible-receipted-correction-contact",
        "source_subject_digest": subject["artifact_digest"],
        "feedback_receipt_digest": feedback["receipt_digest"],
        "target_symbol": disclosure["target_symbol"],
        "target_path": disclosure["target_path"],
        "case_count": disclosure["case_count"],
        "cases": copy.deepcopy(disclosure["cases"]),
        "reference_source_available": False,
    }
    write_json(seed / "correction-public-contact.json", contact)
    write_json(
        seed / "correction/prior-failed-candidate.json",
        {
            "feedback_receipt_digest": feedback["receipt_digest"],
            "candidate_source": feedback["failed_candidate_source"],
            "candidate_source_digest": feedback["failed_candidate_source_digest"],
            "candidate_matches": feedback["candidate_matches"],
            "case_count": disclosure["case_count"],
        },
    )
    (seed / "check_correction.py").write_text(dynamic_checker_source(disclosure["case_count"]))
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    envelope["immutable"] = sorted(
        set(envelope["immutable"] + ["correction/prior-failed-candidate.json"])
    )
    write_json(seed / "mutation-envelope.json", envelope)
    (seed / "README.md").write_text(
        "Continue the exact unresolved correction after objective feedback rejected a prior "
        "candidate. Inspect the retained failed candidate and the enlarged bounded contact. "
        "Revise only the selected function or surrender truthfully. The reference source and "
        "remaining sealed cases are unavailable. Edit only the permitted source and "
        "correction-decision.json, run python3 check_correction.py, and inspect the exact diff.\n"
    )
    return seed


def evaluate_workspace(seed, workspace, subject):
    _, _, _, _, target, path = selected(subject)
    try:
        decision = json.loads((workspace / "correction-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        source = (workspace / path).read_text()
        baseline = (workspace / "correction/baseline-selected.py").read_text()
        identities = base271.contract(subject)["required_identities"]
        exact = (
            set(decision) == CORRECTION_CORE
            and all(decision.get(key) == value for key, value in identities.items())
            and decision.get("target_symbol") == target
            and decision.get("predicates") == CORRECTION_PREDICATES
            and decision.get("disposition") in {"revise", "surrender"}
        )
        local = source == baseline if decision.get("disposition") == "surrender" else base271.target_only_change(source, baseline, target)
        cases = json.loads((workspace / "correction-public-contact.json").read_text())["cases"]
        public = base271.compare_source(source, target, cases) if exact and local and decision.get("disposition") == "revise" else None
        semantic = bool(exact and local and immutable_ok and (
            decision.get("disposition") == "surrender"
            or (public and public["all_valid"] and public["matches"] == len(cases))
        ))
        return {"decision": decision, "source": source, "public": public, "semantic": semantic, "immutable_ok": immutable_ok, "error_type": None}
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError, TypeError) as error:
        return {"decision": None, "source": None, "public": None, "semantic": False, "immutable_ok": False, "error_type": type(error).__name__}


def run_actor(context, p82, root, subject, package):
    seed = seed_actor(root, subject, package, p82)
    _, pending, world, _, _, path = selected(subject)
    label = "receipted-counterexample-corrector"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    evaluated = evaluate_workspace(seed, workspace, subject)
    decision = evaluated["decision"]
    transport = base271.output_valid(output, path, decision.get("disposition") if decision else None)
    expected = ["correction-decision.json", path] if decision and decision.get("disposition") == "revise" else ["correction-decision.json"]
    audit = context.audit_actor(label, output, base_audit, evaluated["semantic"] and transport, expected)
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(evaluated["semantic"] and transport and base236.g10(normalized))
    binding = None
    if accepted:
        body = {
            "authority": AUTHORITY + "-bound-correction",
            "source_subject_digest": subject["artifact_digest"],
            "contact_identity": pending["contact_identity"],
            "world_receipt_digest": world["receipt_digest"],
            "feedback_receipt_digest": subject["active_correction_disclosure"]["feedback_receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "target_path": path,
            "decision": decision,
            "patched_source": evaluated["source"] if decision["disposition"] == "revise" else None,
            "patched_source_digest": p82.digest(evaluated["source"]) if decision["disposition"] == "revise" else None,
            "public_result": evaluated["public"],
            "denial_provenance": normalized["provenance"],
            "path_claim_authority": "provenance-only",
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-correction.json", binding)
    return {
        "accepted": binding is not None,
        "binding": binding,
        "decision": decision,
        "public": evaluated["public"],
        "audit": audit,
        "g10_disposition": accepted,
        "output": output,
        "workspace_evaluation": {"immutable_ok": evaluated["immutable_ok"], "error_type": evaluated["error_type"]},
    }


def compile_success(subject, actor, world, p82):
    admitted = base271.compile_correction(subject, actor, world, p82)
    child = copy.deepcopy(admitted)
    child.pop("artifact_digest", None)
    child["active_correction_disclosure"] = {
        **child["active_correction_disclosure"],
        "status": "resolved-after-revision",
        "admitted_binding_digest": actor["binding"]["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
    }
    return p82.seal(child)


def seed_excludes_undisclosed(seed, package, subject):
    corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
    target, path = selected(subject)[4:6]
    full = full_examples(package, lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), subject)
    return package["sealed_reference_sources"][path] not in corpus and json.dumps(full, sort_keys=True) not in corpus and target in corpus


def preflight(root, p82, runtime, parent, failed, package, result268):
    root.mkdir(parents=True, exist_ok=True)
    feedback_subject, feedback = compile_feedback(parent, failed, package, p82)
    seed = seed_actor(root / "actor", feedback_subject, package, p82)
    workspace = root / "reference-workspace"
    shutil.copytree(seed, workspace)
    target, path = selected(feedback_subject)[4:6]
    (workspace / path).write_text(package["sealed_reference_sources"][path])
    checker = subprocess.run(["python3", "check_correction.py"], cwd=workspace, capture_output=True)
    evaluated = evaluate_workspace(seed, workspace, feedback_subject)
    decision = base271.decision_template(feedback_subject)
    decision.update(rationale="Prospective complete correction.", next_pursuit="Refresh opportunities.")
    action = {"decision": decision, "binding": {"binding_digest": "a" * 64, "patched_source": evaluated["source"], "patched_source_digest": p82.digest(evaluated["source"]), "feedback_receipt_digest": feedback["receipt_digest"]}}
    world = base271.sealed_followup(feedback_subject, action, package, result268, p82)
    final = compile_success(feedback_subject, action, world, p82)
    failed_on_five = base271.compare_source(feedback["failed_candidate_source"], target, feedback_subject["active_correction_disclosure"]["cases"])

    def rejected_failure(candidate):
        try:
            feedback_receipt(parent, candidate, package, p82)
            return False
        except RuntimeError:
            return True

    wrong_identity = copy.deepcopy(failed)
    wrong_identity["receipt_digest"] = "0" * 64
    false_success = copy.deepcopy(failed)
    false_success["checks"]["retained_package_6_of_6"] = True
    false_success["world"]["outcome"] = "success"
    no_mismatch = copy.deepcopy(failed)
    for row in no_mismatch["world"]["result"]["rows"]:
        row["matches"] = True
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "failed_exact": failed["receipt_digest"] == FAILED_RECEIPT,
        "feedback_identity_conforms": runtime.identity_conforms(feedback_subject),
        "installed_source_unchanged": selected(feedback_subject)[0]["installed_source"] == selected(parent)[0]["installed_source"],
        "route_still_correction": base272.derive(feedback_subject, p82) == "outward-correct",
        "one_canonical_counterexample": feedback["counterexample_selection"] == "lowest-canonical-mismatch" and feedback_subject["active_correction_disclosure"]["case_count"] == 5,
        "failed_candidate_now_4_of_5": failed_on_five["matches"] == 4,
        "checker_reference_5_of_5": checker.returncode == 0 and evaluated["public"]["matches"] == 5 and evaluated["semantic"],
        "sealed_reference_6_of_6": world["result"]["matches"] == 6 and world["unchanged_control"]["matches"] == 2 and world["promotion_gate"],
        "prospective_success_conforms": runtime.identity_conforms(final),
        "seed_excludes_sealed": seed_excludes_undisclosed(seed, package, feedback_subject),
        "dynamic_target": target not in (seed / "README.md").read_text() and path not in (seed / "README.md").read_text(),
        "invalid_failure_identity_fails_closed": rejected_failure(wrong_identity),
        "successful_candidate_fails_closed": rejected_failure(false_success),
        "missing_counterexample_fails_closed": rejected_failure(no_mismatch),
    }
    checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + "-preflight", "checks": checks, "feedback_receipt_digest": feedback["receipt_digest"], "prospective_final_subject_digest": final["artifact_digest"]}
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def advance(repo, run, p82, runtime, parent, failed, package, result268, fixtures, base, base130):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0273 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0273 evidence")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > 2 or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0273 checkpoint")
    operation = "retain-correction-feedback" if index == 1 else base272.derive(subject, p82)
    pulse = {"authority": AUTHORITY + "-pulse", "content": PULSE, "source_subject_digest": subject["artifact_digest"], "derived_operation": operation}
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    final = subject
    checks = {"content_free_expected_operation": pulse["content"] is None and operation == EXPECTED[index - 1]}
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    if index == 1:
        final, feedback = compile_feedback(subject, failed, package, p82)
        checks.update(zero_fresh_actors=True, one_counterexample=final["active_correction_disclosure"]["case_count"] == 5, installed_source_unchanged=selected(final)[0]["installed_source"] == selected(subject)[0]["installed_source"], next_is_correction=base272.derive(final, p82) == "outward-correct")
        write_json(root / "feedback-receipt.json", feedback)
    else:
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, root, repo))
        actor = run_actor(context, p82, root / "actor", subject, package)
        world = base271.sealed_followup(subject, actor, package, result268, p82) if actor["accepted"] else None
        final = compile_success(subject, actor, world, p82) if world and world["promotion_gate"] else subject
        if world:
            write_json(root / "world-receipt.json", world)
        checks.update(actor_accepted=actor["accepted"], g10_accepted=actor["g10_disposition"], disclosed_5_of_5=bool(actor["public"] and actor["public"]["matches"] == 5), retained_package_6_of_6=bool(world and world["result"]["matches"] == 6), unchanged_2_of_6=bool(world and world["unchanged_control"]["matches"] == 2), next_is_refresh=base272.derive(final, p82) == "refresh-opportunity-projection")
    checks["final_open_conformant"] = final["continuation"]["status"] == "open" and runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + f"-invocation-{index:02d}", "invocation_index": index, "source_subject_digest": subject["artifact_digest"], "pulse": pulse, "feedback": feedback, "actor": actor, "world": world, "checks": checks, "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1 if actor else 0}
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
    all_results = [json.loads(path.read_text()) for path in sorted(run.glob("invocation-*-result.json"))]
    gates = {"preflight_passed": fixtures["checks"]["passed"], "two_identical_content_free_calls": len(all_results) == 2 and [row["pulse"]["derived_operation"] for row in all_results] == list(EXPECTED) and all(row["pulse"]["content"] is None for row in all_results), "all_invocation_gates_pass": all(row["checks"]["passed"] for row in all_results), "exactly_one_fresh_actor": sum(row["fresh_actor_count"] for row in all_results) == 1, "failed_attempt_retained": len(final.get("retained_failed_correction_attempts", [])) == len(parent.get("retained_failed_correction_attempts", [])) + 1, "final_open_refresh": base272.derive(final, p82) == "refresh-opportunity-projection" and runtime.identity_conforms(final)}
    gates["passed"] = all(gates.values())
    aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "invocation_receipt_digests": [row["receipt_digest"] for row in all_results], "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1}
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
    repo, run, p82, runtime, parent, failed, package, result268, base, base130 = setup(args)
    fixtures = preflight(run / "preflight", p82, runtime, parent, failed, package, result268)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(repo, run, p82, runtime, parent, failed, package, result268, fixtures, base, base130)


if __name__ == "__main__":
    raise SystemExit(main())
