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
BASE_PATH = ROOT / "ot_0306_priority_selected_world_contact.py"
BASE_SHA256 = "db3dd0924f15238619e609c67a231ad3a90b0a1787a2829be7fcaa583bf2db34"
PARENT_DIGEST = "2ce0d208d0594441c9d7337a8754c8cb81f0c7434e842d4e058d5d933e01fcfd"
OT306_RECEIPT = "a4094f86f6ef51ca3f1e50dc7df3186ce1377f77ae8853bfb291e141c30533d0"
AUTHORITY = "ot-0307-consequence-routed-correction-recurrence"
MAX_CALLS = 4
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0306 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0307_frozen_ot0306", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base306 = load_base()
base305 = base306.base305
base303 = base305.base303
base302 = base303.base302
b = base306.b
base274 = b.base274
base273 = base274.base273
base271 = base274.base271
base297 = base303.base297
GENERIC_FEEDBACK_SEED = base302.INHERITED_SEED_ACTOR

b.AUTHORITY = AUTHORITY
base274.AUTHORITY = AUTHORITY
base274.MAX_CALLS = MAX_CALLS
base273.AUTHORITY = AUTHORITY
base271.AUTHORITY = AUTHORITY


def write_json(path, value):
    base306.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0307").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0306",
        "open-subject-after-priority-selected-world-contact.json",
    )
    result306 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0306",
        "priority-selected-world-contact-aggregate.json",
    )
    result305 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        "subject-priority-world-selection-aggregate.json",
    )
    selected_world = result305["selection"]["selected_world_id"]
    provider_index = next(
        index
        for index, provider in enumerate(result305["providers"], 1)
        if provider["package"]["world_id"] == selected_world
    )
    package = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        f"subject-blind-provider-{provider_index:02d}-world-package.json",
    )
    result280 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0280",
        "import-stable-world-evaluator-aggregate.json",
    )
    return (
        repo,
        run,
        p82,
        runtime,
        parent,
        result306,
        result305,
        package,
        result280,
        core,
        base130,
    )


def protected(subject):
    keys = (
        "active_developmental_stake",
        "active_standing_world_provider",
        "active_world_seeking_stake",
        "assimilated_developmental_stakes",
        "invalid_encounter_recovery_receipts",
        "invalid_encounter_scars",
        "standing_world_provider_transitions",
        "streamed_world_offer_consumption_receipts",
        "streamed_world_offer_receipts",
        "subject_originated_world_stakes",
        "subject_priority_contact_receipts",
        "surrendered_developmental_stakes",
        "transferred_priority_contradictions",
        "world_seeking_stakes",
        "world_stream_wait_discharge_receipts",
        "world_stream_wait_receipts",
    )
    return {key: subject.get(key) for key in keys}


def current_receipt_kind(subject):
    disclosure = subject.get("active_correction_disclosure") or {}
    active = disclosure.get("feedback_receipt_digest")
    failed = subject.get("retained_failed_correction_attempts") or []
    surrendered = subject.get("retained_surrender_feedback") or []
    if failed and failed[-1].get("receipt_digest") == active:
        return "failed-revision"
    if surrendered and surrendered[-1].get("receipt_digest") == active:
        return "surrender"
    raise RuntimeError("active correction disclosure lacks an exact retained receipt")


def surrender_feedback_seed(root, subject, package, p82):
    seed = GENERIC_FEEDBACK_SEED(root, subject, package, p82)
    stale = seed / "correction/prior-failed-candidate.json"
    stale.unlink()
    feedback = subject["retained_surrender_feedback"][-1]
    if (
        feedback["receipt_digest"]
        != subject["active_correction_disclosure"]["feedback_receipt_digest"]
    ):
        raise RuntimeError("stale surrender feedback")
    write_json(seed / "correction/prior-surrender-feedback.json", feedback)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    envelope["immutable"] = sorted(
        set(
            path
            for path in envelope["immutable"]
            if path != "correction/prior-failed-candidate.json"
        )
        | {"correction/prior-surrender-feedback.json"}
    )
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


def routed_feedback_seed(root, subject, package, p82):
    kind = current_receipt_kind(subject)
    if kind == "failed-revision":
        return GENERIC_FEEDBACK_SEED(root, subject, package, p82)
    return surrender_feedback_seed(root, subject, package, p82)


base273.seed_actor = routed_feedback_seed


def undisclosed(subject, package, p82):
    examples = base274.all_examples(subject, package, p82)
    target, path = base274.selected(subject)[4:6]
    disclosure = subject.get("active_correction_disclosure") or {}
    if (
        base274.feedback_mode(subject)
        and disclosure.get("target_symbol") == target
        and disclosure.get("target_path") == path
    ):
        visible = disclosure["cases"]
    else:
        visible = examples[:4]
    visible_inputs = {p82.digest(row["input"]) for row in visible}
    return [row for row in examples if p82.digest(row["input"]) not in visible_inputs]


def clean_audit():
    return {
        "denial_classification_v2": {
            "accepted": True,
            "classification": "clean",
            "sandbox_violation_retained": False,
        }
    }


def fixture_surrender(subject, p82):
    _, pending, world, _, target, path = base274.selected(subject)
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
        "actor_patch_digest": "0" * 64,
        "target_path": path,
        "decision": decision,
        "patched_source": None,
        "patched_source_digest": None,
        "public_result": None,
        "denial_provenance": "fixture-clean",
        "path_claim_authority": "provenance-only",
    }
    if base274.feedback_mode(subject):
        body["feedback_receipt_digest"] = subject[
            "active_correction_disclosure"
        ]["feedback_receipt_digest"]
    binding = {**body, "binding_digest": p82.digest(body)}
    return {
        "accepted": True,
        "binding": binding,
        "decision": decision,
        "public": None,
        "audit": clean_audit(),
        "g10_disposition": True,
    }


def sealed_surrender_world(subject, actor, package, result280, p82):
    extension, pending, unresolved, _, target, path = base274.selected(subject)
    evaluation = b.base268.evaluate_package(package, p82.digest)
    rows = base271.correction_examples(package, evaluation, target, count=6)
    control = base271.compare_source(extension["installed_source"], target, rows)
    body = {
        "authority": AUTHORITY + "-sealed-surrender-world",
        "source_subject_digest": subject["artifact_digest"],
        "unresolved_world_receipt_digest": unresolved["receipt_digest"],
        "correction_binding_digest": actor["binding"]["binding_digest"],
        "target_symbol": target,
        "target_path": path,
        "ot0280_aggregate_receipt_digest": result280["receipt_digest"],
        "full_package_digest": evaluation["full_package_digest"],
        "followup_cases_digest": p82.digest(package["sealed_cases"][target]),
        "reference_source_digest": p82.digest(
            package["sealed_reference_sources"][path]
        ),
        "candidate_result": None,
        "unchanged_control": control,
        "outcome": "unresolved",
        "promotion_gate": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def valid_surrender(subject, actor, world, p82):
    _, pending, unresolved, _, target, path = base274.selected(subject)
    binding = actor.get("binding") or {}
    decision = actor.get("decision") or {}
    denial = actor.get("audit", {}).get("denial_classification_v2", {})
    body = {key: value for key, value in binding.items() if key != "binding_digest"}
    expected_feedback = (
        subject["active_correction_disclosure"]["feedback_receipt_digest"]
        if base274.feedback_mode(subject)
        else None
    )
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
        and binding.get("feedback_receipt_digest") == expected_feedback
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
        and world.get("candidate_result") is None
        and world.get("outcome") == "unresolved"
        and world.get("promotion_gate") is False
        and world.get("unchanged_control", {}).get("all_valid")
        and world.get("unchanged_control", {}).get("matches") == 2
    )


def compile_surrender(subject, actor, world, package, p82):
    if not valid_surrender(subject, actor, world, p82):
        raise RuntimeError("invalid surrender authority")
    _, pending, _, _, target, path = base274.selected(subject)
    prior = (
        copy.deepcopy(subject["active_correction_disclosure"]["cases"])
        if base274.feedback_mode(subject)
        else copy.deepcopy(base274.all_examples(subject, package, p82)[:4])
    )
    remaining = undisclosed(subject, package, p82)
    mismatches = {
        row["case_id"]: row
        for row in world["unchanged_control"]["rows"]
        if not row.get("matches")
    }
    available = [row for row in remaining if row["case_id"] in mismatches]
    if not available:
        raise RuntimeError("surrender consequence has no undisclosed counterexample")
    counterexample = copy.deepcopy(sorted(available, key=lambda row: row["case_id"])[0])
    if counterexample["expected"] != mismatches[counterexample["case_id"]]["expected"]:
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


def correction_actor(context, p82, root, subject, package):
    if base274.feedback_mode(subject):
        return base273.run_actor(context, p82, root, subject, package)
    evaluation = b.base268.evaluate_package(package, p82.digest)
    return base271.run_actor(context, p82, root, subject, package, evaluation)


def run_correction(context, p82, root, subject, package, result280):
    actor = correction_actor(context, p82, root / "actor", subject, package)
    disposition = (actor.get("decision") or {}).get("disposition")
    if actor.get("accepted") and disposition == "revise":
        world = base271.sealed_followup(subject, actor, package, result280, p82)
    elif actor.get("accepted") and disposition == "surrender":
        world = sealed_surrender_world(subject, actor, package, result280, p82)
    else:
        world = None
    feedback = None
    if world and world["promotion_gate"] and disposition == "revise":
        final = (
            base273.compile_success(subject, actor, world, p82)
            if base274.feedback_mode(subject)
            else base271.compile_correction(subject, actor, world, p82)
        )
        transition = "success-to-refresh"
    elif world and world["outcome"] == "unresolved" and disposition == "revise":
        final, feedback = base274.compile_unresolved_feedback(
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


def fixture_revise(subject, package, result280, p82, success):
    target, path = base274.selected(subject)[4:6]
    reference = package["sealed_reference_sources"][path]
    if success:
        source = reference
    else:
        remaining = undisclosed(subject, package, p82)
        if not remaining:
            raise RuntimeError("failed revision fixture lacks undisclosed case")
        source = base274.sabotage(reference, remaining[0]["input"])
    actor = base274.fixture_action(subject, source, p82)
    public_cases = (
        subject["active_correction_disclosure"]["cases"]
        if base274.feedback_mode(subject)
        else base274.all_examples(subject, package, p82)[:4]
    )
    public = base271.compare_source(source, target, public_cases)
    world = base271.sealed_followup(subject, actor, package, result280, p82)
    return actor, public, world


def fixture_prefix(subject, kinds, package, result280, p82, runtime):
    rows = []
    for kind in kinds:
        before = len(undisclosed(subject, package, p82))
        if kind == "failed-revision":
            actor, public, world = fixture_revise(
                subject, package, result280, p82, success=False
            )
            child, feedback = base274.compile_unresolved_feedback(
                subject, actor, world, package, p82
            )
            transition = "unresolved-to-more-correction"
        elif kind == "surrender":
            actor = fixture_surrender(subject, p82)
            public = None
            world = sealed_surrender_world(subject, actor, package, result280, p82)
            child, feedback = compile_surrender(subject, actor, world, package, p82)
            transition = "surrender-to-more-correction"
        else:
            raise ValueError(kind)
        rows.append(
            {
                "kind": kind,
                "transition": transition,
                "public_passed": public is None
                or public["matches"] == public["case_count"],
                "world_unresolved": world["outcome"] == "unresolved"
                and not world["promotion_gate"],
                "unchanged_2_of_6": world["unchanged_control"]["matches"] == 2,
                "one_case_added": len(undisclosed(child, package, p82)) == before - 1,
                "receipt_routed": current_receipt_kind(child) == kind,
                "nonauthoritative_surrender": kind != "surrender"
                or (
                    feedback["candidate_source_admitted"] is False
                    and feedback["success_authority"] is False
                    and feedback["earned_authority"] is False
                ),
                "conformant": runtime.identity_conforms(child),
            }
        )
        subject = child
    return subject, rows


def fixture_path(kinds, parent, package, result280, p82, runtime):
    subject, prefix = fixture_prefix(
        parent, kinds, package, result280, p82, runtime
    )
    actor, public, world = fixture_revise(
        subject, package, result280, p82, success=True
    )
    corrected = (
        base273.compile_success(subject, actor, world, p82)
        if base274.feedback_mode(subject)
        else base271.compile_correction(subject, actor, world, p82)
    )
    refreshed = b.base264.refresh_projection_only(corrected, p82)
    return {
        "prefix": list(kinds),
        "prefix_rows": prefix,
        "success_public": public["matches"] == public["case_count"],
        "success_6_of_6": world["result"]["matches"] == 6,
        "unchanged_2_of_6": world["unchanged_control"]["matches"] == 2,
        "one_earned": len(base297.earned_targets(corrected, package)) == 1,
        "success_routes_refresh": b.base272.derive(corrected, p82)
        == "refresh-opportunity-projection",
        "refresh_has_two": refreshed["active_opportunity_projection"][
            "opportunity_count"
        ]
        == 2,
        "refresh_routes_selection": b.base272.derive(refreshed, p82)
        == "expanded-select",
        "protected_exact": protected(refreshed) == protected(parent),
        "corrected_conformant": runtime.identity_conforms(corrected),
        "refreshed_conformant": runtime.identity_conforms(refreshed),
    }


def seed_projection_checks(root, parent, package, result280, p82, runtime):
    failed, _ = fixture_prefix(
        parent, ("failed-revision",), package, result280, p82, runtime
    )
    surrendered, _ = fixture_prefix(
        parent, ("surrender",), package, result280, p82, runtime
    )
    failed_seed = routed_feedback_seed(root / "failed", failed, package, p82)
    surrender_seed = routed_feedback_seed(
        root / "surrender", surrendered, package, p82
    )
    failed_envelope = json.loads(
        (failed_seed / "mutation-envelope.json").read_text()
    )["immutable"]
    surrender_envelope = json.loads(
        (surrender_seed / "mutation-envelope.json").read_text()
    )["immutable"]
    failed_receipt = json.loads(
        (failed_seed / "correction/prior-failed-candidate.json").read_text()
    )
    surrender_receipt = json.loads(
        (surrender_seed / "correction/prior-surrender-feedback.json").read_text()
    )
    return {
        "failed_revision_routes_failed_candidate": current_receipt_kind(failed)
        == "failed-revision"
        and "correction/prior-failed-candidate.json" in failed_envelope
        and not (failed_seed / "correction/prior-surrender-feedback.json").exists()
        and failed_receipt["feedback_receipt_digest"]
        == failed["active_correction_disclosure"]["feedback_receipt_digest"],
        "surrender_routes_surrender_receipt": current_receipt_kind(surrendered)
        == "surrender"
        and "correction/prior-surrender-feedback.json" in surrender_envelope
        and "correction/prior-failed-candidate.json" not in surrender_envelope
        and not (surrender_seed / "correction/prior-failed-candidate.json").exists()
        and surrender_receipt["receipt_digest"]
        == surrendered["active_correction_disclosure"]["feedback_receipt_digest"],
        "both_exclude_undisclosed": base273.seed_excludes_undisclosed(
            failed_seed, package, failed
        )
        and base273.seed_excludes_undisclosed(
            surrender_seed, package, surrendered
        ),
    }


def surrender_controls(subject, actor, world, p82):
    controls = {}
    changed = copy.deepcopy(actor)
    changed["binding"]["patched_source"] = "def x():\n    pass\n"
    controls["source-bearing-surrender"] = not valid_surrender(
        subject, changed, world, p82
    )
    changed = copy.deepcopy(actor)
    changed["decision"]["disposition"] = "revise"
    controls["source-free-revision"] = not valid_surrender(
        subject, changed, world, p82
    )
    changed = copy.deepcopy(actor)
    changed["decision"]["contact_identity"] = "0" * 64
    controls["wrong-contact"] = not valid_surrender(subject, changed, world, p82)
    changed = copy.deepcopy(actor)
    changed["g10_disposition"] = False
    controls["g10-failure"] = not valid_surrender(subject, changed, world, p82)
    changed_world = copy.deepcopy(world)
    changed_world["promotion_gate"] = True
    controls["success-world"] = not valid_surrender(
        subject, actor, changed_world, p82
    )
    changed_world = copy.deepcopy(world)
    changed_world["unchanged_control"]["matches"] = 3
    controls["changed-control"] = not valid_surrender(
        subject, actor, changed_world, p82
    )
    return controls


def preflight(
    root, p82, runtime, parent, result306, result305, package, result280
):
    root.mkdir(parents=True, exist_ok=True)
    prefixes = [
        (),
        ("failed-revision",),
        ("surrender",),
        ("failed-revision", "failed-revision"),
        ("failed-revision", "surrender"),
        ("surrender", "failed-revision"),
        ("surrender", "surrender"),
    ]
    branches = [
        fixture_path(prefix, parent, package, result280, p82, runtime)
        for prefix in prefixes
    ]
    projections = seed_projection_checks(
        root / "seed-routing", parent, package, result280, p82, runtime
    )
    first_surrender = fixture_surrender(parent, p82)
    first_world = sealed_surrender_world(
        parent, first_surrender, package, result280, p82
    )
    controls = surrender_controls(parent, first_surrender, first_world, p82)
    exhausted_subject, _ = fixture_prefix(
        parent,
        ("surrender", "surrender"),
        package,
        result280,
        p82,
        runtime,
    )
    exhausted = False
    third_surrender = fixture_surrender(exhausted_subject, p82)
    third_world = sealed_surrender_world(
        exhausted_subject, third_surrender, package, result280, p82
    )
    try:
        compile_surrender(
            exhausted_subject, third_surrender, third_world, package, p82
        )
    except RuntimeError:
        exhausted = True
    evaluation = b.base268.evaluate_package(package, p82.digest)
    route, identity = b.base272.base265.floors(parent)
    priority = parent["subject_priority_contact_receipts"][-1]
    source = Path(__file__).read_text()
    branch_passed = lambda row: bool(
        all(
            step["public_passed"]
            and step["world_unresolved"]
            and step["unchanged_2_of_6"]
            and step["one_case_added"]
            and step["receipt_routed"]
            and step["nonauthoritative_surrender"]
            and step["conformant"]
            for step in row["prefix_rows"]
        )
        and row["success_public"]
        and row["success_6_of_6"]
        and row["unchanged_2_of_6"]
        and row["one_earned"]
        and row["success_routes_refresh"]
        and row["refresh_has_two"]
        and row["refresh_routes_selection"]
        and row["protected_exact"]
        and row["corrected_conformant"]
        and row["refreshed_conformant"]
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "exact_ot0306_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result306["receipt_digest"] == OT306_RECEIPT
        and result306["observer_disposition"] == "promoted"
        and result306["final_subject_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0305_negative_priority_claim_preserved": result305[
            "observer_disposition"
        ]
        == "rejected"
        and result305["e11"]["priority_bearing_contact"] is False
        and priority["selected_world_id"] == priority["blind_control_world_id"],
        "fresh_target_has_two_hidden_classes": len(
            undisclosed(parent, package, p82)
        )
        == 2,
        "seven_reachable_paths_pass": len(branches) == 7
        and all(branch_passed(row) for row in branches),
        "consequence_specific_seed_routing": all(projections.values()),
        "surrender_exhaustion_fails_closed": exhausted,
        "six_surrender_controls_reject": all(controls.values()),
        "dynamic_target_not_hardcoded": all(
            token not in source
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0306_receipt_digest": result306["receipt_digest"],
        "actor_budget": 3,
        "invocation_budget": MAX_CALLS,
        "branch_prefixes": [row["prefix"] for row in branches],
        "seed_routing": projections,
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
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["fresh_actor_count"] == 1]
    transitions = [row["transition"] for row in corrections]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_recurrence": 2 <= len(rows) <= MAX_CALLS
        and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "consequence_routed_corrections": transitions[-1:]
        == ["success-to-refresh"]
        and all(
            transition
            in {
                "unresolved-to-more-correction",
                "surrender-to-more-correction",
            }
            for transition in transitions[:-1]
        ),
        "separate_derived_refresh": operations[-1:]
        == ["refresh-opportunity-projection"]
        and rows[-1]["fresh_actor_count"] == 0,
        "fresh_actor_each_correction": len(corrections) == len(rows) - 1
        and all(row["fresh_actor_count"] == 1 for row in rows[:-1]),
        "one_earned_two_open": len(base297.earned_targets(final, package)) == 1
        and final["active_opportunity_projection"]["opportunity_count"] == 2,
        "selection_derived_next": b.base272.derive(final, p82) == "expanded-select",
        "protected_exact": protected(final) == protected(parent),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "operations": operations,
        "correction_transitions": transitions,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": len(corrections),
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
    (
        repo,
        run,
        p82,
        runtime,
        parent,
        result306,
        result305,
        package,
        result280,
        core,
        base130,
    ) = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight",
            p82,
            runtime,
            parent,
            result306,
            result305,
            package,
            result280,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0307 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results:
        latest = json.loads(results[-1].read_text())
        if not latest["checks"]["passed"]:
            raise SystemExit("preserve failed OT-0307 invocation")
        if not checkpoint.exists():
            raise SystemExit("missing OT-0307 checkpoint")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0307 checkpoint")
    operation = b.base272.derive(subject, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    transition = operation
    if operation == "outward-correct":
        context = base274.context_for(core, base130, runtime, root, repo)
        actor, world, feedback, final, transition = run_correction(
            context, p82, root, subject, package, result280
        )
        disposition = (actor.get("decision") or {}).get("disposition")
        public_count = actor["public"]["case_count"] if actor.get("public") else 0
        checks = {
            "content_free": pulse["content"] is None,
            "workspace_outside_repo": not (root / "actor").resolve().is_relative_to(
                repo
            ),
            "actor_accepted": actor["accepted"],
            "g10_accepted": actor["g10_disposition"],
            "disclosed_pass_or_surrender": disposition == "surrender"
            or bool(
                actor.get("public")
                and actor["public"]["matches"] == public_count
            ),
            "unchanged_2_of_6": bool(
                world and world["unchanged_control"]["matches"] == 2
            ),
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
            "protected_exact": protected(final) == protected(parent),
            "final_open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        fresh_actor_count = 1
    elif operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82)
        checks = {
            "content_free": pulse["content"] is None,
            "zero_fresh_actors": True,
            "projection_has_two": final["active_opportunity_projection"][
                "opportunity_count"
            ]
            == 2,
            "next_is_selection": b.base272.derive(final, p82) == "expanded-select",
            "protected_exact": protected(final) == protected(parent),
            "final_open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        fresh_actor_count = 0
    else:
        final = subject
        checks = {"known_operation": False}
        fresh_actor_count = 0
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": actor,
        "world": world,
        "feedback": feedback,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": fresh_actor_count,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if world:
        write_json(run / f"invocation-{index:02d}-world.json", world)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if operation != "refresh-opportunity-projection":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, package, final)


if __name__ == "__main__":
    raise SystemExit(main())
