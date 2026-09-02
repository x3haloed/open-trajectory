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
BASE_PATH = ROOT / "ot_0301_consequence_bearing_surrender.py"
BASE_SHA256 = "12c170c3416be1707a559b554251cb986d5d5b6e3727986acda53aa1b87febd0"
PARENT_DIGEST = "e2ee0449d8d6943b0ac9fca36c0296d9a5df423240da5cdfb70e28531bb42bcf"
OT301_RECEIPT = "d8354e26d35c1f66429f80c2e0a97761846cfdacf8930ddf0d39e42e44735432"
AUTHORITY = "ot-0302-surrender-recovery-correction"
MAX_CALLS = 2


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0301 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0302_frozen_ot0301", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base301 = load_base()
base300 = base301.base300
base299 = base301.base299
base297 = base301.base297
base295 = base301.base295
b = base301.b
base273 = b.base274.base273
base271 = b.base274.base271
INHERITED_SEED_ACTOR = base273.seed_actor
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY
b.base274.MAX_CALLS = MAX_CALLS
base273.AUTHORITY = AUTHORITY
base271.AUTHORITY = AUTHORITY


def write_json(path, value):
    base301.write_json(path, value)


def lineage(subject):
    return base295.lineage_projection(subject)


def setup(args):
    chain = b.authority_base.guide_base.load_base()
    selector, core, base130 = chain.selector_base, chain.base, chain.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0302").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0301", "open-subject-after-surrender-feedback.json"
    )
    result301 = selector.load_artifact(
        p82, repo, store, "OT-0301", "consequence-bearing-surrender-aggregate.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result301, package, result280, core, base130


def seed_recovery_actor(root, subject, package, p82):
    seed = INHERITED_SEED_ACTOR(root, subject, package, p82)
    stale = seed / "correction/prior-failed-candidate.json"
    stale.unlink()
    feedback = subject["retained_surrender_feedback"][-1]
    write_json(seed / "correction/prior-surrender-feedback.json", feedback)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    envelope["immutable"] = sorted(
        path
        for path in envelope["immutable"]
        if path != "correction/prior-failed-candidate.json"
    )
    envelope["immutable"].append("correction/prior-surrender-feedback.json")
    envelope["immutable"] = sorted(set(envelope["immutable"]))
    write_json(seed / "mutation-envelope.json", envelope)
    (seed / "README.md").write_text(
        "Continue the exact unresolved correction after a prior actor truthfully "
        "surrendered and objective consequence enlarged the bounded contact. Inspect "
        "the retained surrender receipt and all currently disclosed cases. No prior "
        "candidate source, reference source, or remaining sealed case is available. "
        "Revise only the selected function or surrender truthfully. Edit only the "
        "permitted source and correction-decision.json, run python3 "
        "check_correction.py, and inspect the exact diff.\n"
    )
    return seed


base273.seed_actor = seed_recovery_actor


def clean_audit():
    return {
        "denial_classification_v2": {
            "accepted": True,
            "classification": "clean",
            "sandbox_violation_retained": False,
        }
    }


def fixture_surrender(subject, p82):
    _, pending, world, _, target, path = b.base274.selected(subject)
    decision = base271.decision_template(subject)
    decision.update(
        disposition="surrender",
        rationale="Prospective truthful surrender fixture.",
        next_pursuit="Keep the unresolved correction open under consequence.",
    )
    body = {
        "authority": AUTHORITY + "-fixture-surrender-binding",
        "source_subject_digest": subject["artifact_digest"],
        "contact_identity": pending["contact_identity"],
        "world_receipt_digest": world["receipt_digest"],
        "feedback_receipt_digest": subject["active_correction_disclosure"][
            "feedback_receipt_digest"
        ],
        "actor_patch_digest": "0" * 64,
        "target_path": path,
        "decision": decision,
        "patched_source": None,
        "patched_source_digest": None,
        "public_result": None,
        "denial_provenance": "fixture-clean",
        "path_claim_authority": "provenance-only",
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    return {
        "accepted": True,
        "binding": binding,
        "decision": decision,
        "public": None,
        "audit": clean_audit(),
        "g10_disposition": True,
    }


def valid_surrender(subject, actor, world, p82):
    _, pending, unresolved, _, target, path = b.base274.selected(subject)
    binding = actor.get("binding") or {}
    decision = actor.get("decision") or {}
    denial = actor.get("audit", {}).get("denial_classification_v2", {})
    body = {key: value for key, value in binding.items() if key != "binding_digest"}
    return bool(
        actor.get("accepted")
        and actor.get("g10_disposition")
        and denial.get("accepted")
        and denial.get("classification") == "clean"
        and not denial.get("sandbox_violation_retained")
        and binding.get("binding_digest") == p82.digest(body)
        and binding.get("source_subject_digest") == subject["artifact_digest"]
        and binding.get("contact_identity") == pending["contact_identity"]
        and binding.get("world_receipt_digest") == unresolved["receipt_digest"]
        and binding.get("target_path") == path
        and decision.get("disposition") == "surrender"
        and decision.get("target_symbol") == target
        and decision.get("source_subject_digest") == subject["artifact_digest"]
        and decision.get("contact_identity") == pending["contact_identity"]
        and decision.get("world_receipt_digest") == unresolved["receipt_digest"]
        and binding.get("patched_source") is None
        and binding.get("patched_source_digest") is None
        and binding.get("public_result") is None
        and world.get("source_subject_digest") == subject["artifact_digest"]
        and world.get("correction_binding_digest") == binding["binding_digest"]
        and world.get("target_symbol") == target
        and world.get("target_path") == path
        and world.get("outcome") == "unresolved"
        and world.get("promotion_gate") is False
        and world.get("result", {}).get("all_valid") is False
        and world.get("unchanged_control", {}).get("matches") == 2
    )


def compile_surrender(subject, actor, world, package, p82):
    if not valid_surrender(subject, actor, world, p82):
        raise RuntimeError("invalid surrender authority")
    _, pending, _, _, target, path = b.base274.selected(subject)
    prior = copy.deepcopy(subject["active_correction_disclosure"]["cases"])
    disclosed = {row["case_id"] for row in prior}
    mismatches = [
        row
        for row in world["unchanged_control"]["rows"]
        if not row.get("matches") and row.get("case_id") not in disclosed
    ]
    if not mismatches:
        raise RuntimeError("surrender consequence has no undisclosed counterexample")
    mismatch = sorted(mismatches, key=lambda row: row["case_id"])[0]
    examples = b.base274.all_examples(subject, package, p82)
    index = int(mismatch["case_id"].rsplit("-", 1)[1]) - 1
    counterexample = copy.deepcopy(examples[index])
    if counterexample["expected"] != mismatch["expected"]:
        raise RuntimeError("surrender counterexample mismatch")
    body = {
        "authority": AUTHORITY + "-surrender-feedback",
        "source_subject_digest": subject["artifact_digest"],
        "contact_identity": pending["contact_identity"],
        "surrender_binding_digest": actor["binding"]["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "decision_digest": p82.digest(actor["decision"]),
        "counterexample_selection": "lowest-canonical-undisclosed-unchanged-mismatch",
        "counterexample": counterexample,
        "disposition": "surrender-retained-nonsuccess",
        "candidate_source_admitted": False,
        "success_authority": False,
        "earned_authority": False,
        "next_operation": "outward-correct",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    cases = [*prior, counterexample]
    disclosure_body = {
        "authority": AUTHORITY + "-active-correction-disclosure",
        "source_subject_digest": subject["artifact_digest"],
        "feedback_receipt_digest": receipt["receipt_digest"],
        "target_symbol": target,
        "target_path": path,
        "cases": cases,
        "case_count": len(cases),
        "reference_source_available": False,
        "remaining_sealed_cases_available": False,
        "status": "awaiting-revision",
    }
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["retained_surrender_feedback"] = [
        *child.get("retained_surrender_feedback", []),
        receipt,
    ]
    child["active_correction_disclosure"] = {
        **disclosure_body,
        "disclosure_digest": p82.digest(disclosure_body),
    }
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Continue the surrendered correction from receipted world contact.",
    }
    child["unresolved"] = (
        "Surrender remains non-success; continue from the added world counterexample."
    )
    return p82.seal(child), receipt


def run_correction(context, p82, root, subject, package, result280):
    actor = base273.run_actor(context, p82, root / "actor", subject, package)
    world = (
        base271.sealed_followup(subject, actor, package, result280, p82)
        if actor["accepted"]
        else None
    )
    feedback = None
    disposition = (actor.get("decision") or {}).get("disposition")
    if world and world["promotion_gate"] and disposition == "revise":
        final = base273.compile_success(subject, actor, world, p82)
        transition = "success-to-refresh"
    elif world and world["outcome"] == "unresolved" and disposition == "revise":
        final, feedback = b.base274.compile_unresolved_feedback(
            subject, actor, world, package, p82
        )
        transition = "unresolved-to-more-correction"
    elif world and world["outcome"] == "unresolved" and disposition == "surrender":
        try:
            final, feedback = compile_surrender(subject, actor, world, package, p82)
            transition = "surrender-to-more-correction"
        except RuntimeError:
            final = subject
            transition = "surrender-exhausted"
    else:
        final = subject
        transition = "rejected"
    return actor, world, feedback, final, transition


def surrender_controls(subject, actor, world, package, p82):
    controls = {}
    row = copy.deepcopy(actor)
    row["binding"]["patched_source"] = "def x():\n    pass\n"
    controls["source-bearing-surrender"] = not valid_surrender(subject, row, world, p82)
    row = copy.deepcopy(actor)
    row["decision"]["disposition"] = "revise"
    controls["source-free-revision"] = not valid_surrender(subject, row, world, p82)
    row = copy.deepcopy(actor)
    row["decision"]["contact_identity"] = "0" * 64
    controls["wrong-contact"] = not valid_surrender(subject, row, world, p82)
    row = copy.deepcopy(actor)
    row["g10_disposition"] = False
    controls["g10-failure"] = not valid_surrender(subject, row, world, p82)
    changed = copy.deepcopy(world)
    changed["promotion_gate"] = True
    changed["outcome"] = "success"
    controls["success-world"] = not valid_surrender(subject, actor, changed, p82)
    changed = copy.deepcopy(world)
    changed["unchanged_control"]["matches"] = 3
    controls["changed-control"] = not valid_surrender(subject, actor, changed, p82)
    return controls


def preflight(root, p82, runtime, parent, result301, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    seed = seed_recovery_actor(root / "seed-projection", parent, package, p82)
    seed_corpus = "\n".join(
        path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file()
    )
    immediate, immediate_row = b.correction_variant(
        parent, 0, package, result280, p82, runtime
    )
    one_failure, one_failure_row = b.correction_variant(
        parent, 1, package, result280, p82, runtime
    )
    surrender_actor = fixture_surrender(parent, p82)
    surrender_world = base271.sealed_followup(
        parent, surrender_actor, package, result280, p82
    )
    surrendered, surrender_receipt = compile_surrender(
        parent, surrender_actor, surrender_world, package, p82
    )
    after_surrender, after_surrender_row = b.correction_variant(
        surrendered, 0, package, result280, p82, runtime
    )
    exhausted = False
    second_actor = fixture_surrender(surrendered, p82)
    second_world = base271.sealed_followup(
        surrendered, second_actor, package, result280, p82
    )
    try:
        compile_surrender(surrendered, second_actor, second_world, package, p82)
    except RuntimeError:
        exhausted = True
    controls = surrender_controls(parent, surrender_actor, surrender_world, package, p82)
    route, identity = b.base272.base265.floors(parent)
    feedback = parent["retained_surrender_feedback"][-1]
    common = lambda subject, row: bool(
        row["feedback_passed"]
        and row["success_public"]
        and row["success_6_2"]
        and row["routes_refresh"]
        and row["conformant"]
        and len(base297.earned_targets(subject, package)) == 3
        and lineage(subject) == lineage(parent)
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_surrender_successor": parent["artifact_digest"] == PARENT_DIGEST
        and result301["receipt_digest"] == OT301_RECEIPT
        and result301["observer_disposition"] == "promoted"
        and result301["final_subject_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "one_undisclosed_case": len(base295.undisclosed(parent, package, p82)) == 1
        and parent["active_correction_disclosure"]["case_count"] == 5,
        "surrender_projection_exact": feedback["receipt_digest"]
        == parent["active_correction_disclosure"]["feedback_receipt_digest"]
        and feedback["candidate_source_admitted"] is False
        and "correction/prior-surrender-feedback.json"
        in json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        and "correction/prior-failed-candidate.json" not in seed_corpus,
        "projection_excludes_undisclosed": base273.seed_excludes_undisclosed(
            seed, package, parent
        ),
        "immediate_recovery": common(immediate, immediate_row),
        "one_failed_revision_recovery": common(one_failure, one_failure_row),
        "one_more_surrender_recovery": surrender_receipt["earned_authority"] is False
        and surrendered["active_correction_disclosure"]["case_count"] == 6
        and common(after_surrender, after_surrender_row),
        "repeat_surrender_fails_closed": exhausted,
        "six_surrender_controls_reject": all(controls.values()),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "controls": controls,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def finalize(run, fixtures, p82, runtime, parent, package, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    transitions = [row["transition"] for row in rows]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_recovery": 1 <= len(rows) <= MAX_CALLS
        and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "consequence_selected_path": transitions[-1:] == ["success-to-refresh"]
        and all(
            transition
            in {"unresolved-to-more-correction", "surrender-to-more-correction"}
            for transition in transitions[:-1]
        ),
        "fresh_actor_each_opening": sum(row["fresh_actor_count"] for row in rows)
        == len(rows),
        "surrender_consequence_retained": final.get("retained_surrender_feedback")
        == parent.get("retained_surrender_feedback")
        or len(final.get("retained_surrender_feedback", [])) == 2,
        "all_three_earned": len(base297.earned_targets(final, package)) == 3,
        "refresh_derived": b.base272.derive(final, p82)
        == "refresh-opportunity-projection",
        "lineage_exact": lineage(final) == lineage(parent),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "correction_transitions": transitions,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": len(rows),
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result301, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, result301, package, result280)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0302 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0302 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if (
        index > MAX_CALLS
        or b.base272.derive(subject, p82) != "outward-correct"
        or not runtime.identity_conforms(subject)
    ):
        raise SystemExit("invalid OT-0302 checkpoint")
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": "outward-correct",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    context = b.base274.context_for(core, base130, runtime, root, repo)
    actor, world, feedback, final, transition = run_correction(
        context, p82, root, subject, package, result280
    )
    public_count = actor["public"]["case_count"] if actor.get("public") else 0
    checks = {
        "content_free": True,
        "actor_accepted": actor["accepted"],
        "g10_accepted": actor["g10_disposition"],
        "disclosed_pass_or_surrender": (
            actor.get("decision", {}).get("disposition") == "surrender"
            or bool(actor["public"] and actor["public"]["matches"] == public_count)
        ),
        "unchanged_2_of_6": bool(world and world["unchanged_control"]["matches"] == 2),
        "consequence_routes": transition
        in {
            "success-to-refresh",
            "unresolved-to-more-correction",
            "surrender-to-more-correction",
        },
        "next_matches_consequence": b.base272.derive(final, p82)
        == (
            "refresh-opportunity-projection"
            if transition == "success-to-refresh"
            else "outward-correct"
        ),
        "lineage_exact": lineage(final) == lineage(parent),
        "final_open_conformant": final["continuation"]["status"] == "open",
        "identity_conformant": runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": copy.deepcopy(actor),
        "world": world,
        "feedback": feedback,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if transition != "success-to-refresh":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, package, final)


if __name__ == "__main__":
    raise SystemExit(main())
