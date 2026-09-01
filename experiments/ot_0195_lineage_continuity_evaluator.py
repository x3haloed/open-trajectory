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
BASE_PATH = ROOT / "ot_0194_held_out_continuation_evaluator.py"
BASE_SHA256 = "a561aae923df44006353eca54c512e4b7ac2be7a905003f8f06339397247f814"
AUTHOR_SCHEMA = REPO / "spec/ot-0193-continuation-author.schema.json"
PARENT_DIGEST = "8f29e6a86c23f30e73378f222827a109f08a1f6d5eafc9766d0d9b43e44e6a35"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0194 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0195_frozen_ot0194", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0193 = previous.previous
ot0191 = previous.ot0191
ot0183 = previous.ot0183
authority_base = previous.authority_base


def anchors_pass(choice):
    return bool(
        choice.get("binding")
        and choice.get("novel")
        and choice.get("targeted")
        and choice.get("public_discriminating")
        and choice.get("hidden_discriminating")
    )


def lineage_appropriate(choice, target_stake, current_stake):
    package = choice.get("package")
    if not anchors_pass(choice) or not package:
        return False
    next_stake = package.get("next_stake")
    if next_stake == target_stake:
        return True
    return bool(
        package.get("action") == "revise"
        and next_stake != current_stake
        and isinstance(next_stake, dict)
        and next_stake.get("property") == target_stake.get("property")
    )


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = (
        lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0195").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0190", "open-subject-after-executable-route-repair.json")
    result191 = selector_base.load_artifact(p82, repo, store, "OT-0191", "subject-originated-post-repair-reopening-aggregate.json")
    package = selector_base.load_artifact(p82, repo, store, "OT-0191", "actor-authored-reopening-package.json")
    consequence = selector_base.load_artifact(p82, repo, store, "OT-0191", "sealed-subject-originated-contact.json")
    result192 = selector_base.load_artifact(p82, repo, store, "OT-0192", "executable-pursuit-consequence-aggregate.json")
    result193 = selector_base.load_artifact(p82, repo, store, "OT-0193", "direct-pursuit-transition-continuation-aggregate.json")
    result194 = selector_base.load_artifact(p82, repo, store, "OT-0194", "held-out-continuation-evaluator-aggregate.json")
    predicate_binding = result192["repair"]["binding"]
    evaluation = result192["evaluation"]
    candidate_subject, transition = previous.corrected_transition(
        p82, parent, package, predicate_binding, evaluation
    )
    replay_subject, replay_transition = previous.corrected_transition(
        p82, parent, package, predicate_binding, evaluation
    )
    novel_candidate = parent["actor_authored_contact_mechanisms"][-1]
    candidates = [*selector_base.CANDIDATES, novel_candidate]
    expression = novel_candidate["expression"]
    prior_contact_digest = p82.digest(package["contact"])
    known_active = next(row["choice"] for row in result194["rows"] if row["branch"] == "active" and row["index"] == 2)
    known_control = next(row["choice"] for row in result194["rows"] if row["branch"] == "control" and row["index"] == 1)
    construction_active = sum(
        lineage_appropriate(row["choice"], package["next_stake"], candidate_subject["active_developmental_stake"])
        for row in result194["rows"] if row["branch"] == "active"
    )
    construction_control = sum(
        lineage_appropriate(row["choice"], package["next_stake"], parent["active_developmental_stake"])
        for row in result194["rows"] if row["branch"] == "control"
    )
    representative_retain = {
        "binding": {"fixture": "retain"}, "novel": True, "targeted": True,
        "public_discriminating": True, "hidden_discriminating": True,
        "package": {"action": "retain", "next_stake": package["next_stake"]},
    }
    revised_stake = {**package["next_stake"], "stake_id": "refine-latent-boundary", "question": "Which distinction separates latent from observed unblocked contact?"}
    representative_revise = {
        "binding": {"fixture": "revise"}, "novel": True, "targeted": True,
        "public_discriminating": True, "hidden_discriminating": True,
        "package": {"action": "revise", "next_stake": revised_stake},
    }
    representative_stale = {
        "binding": {"fixture": "stale"}, "novel": True, "targeted": True,
        "public_discriminating": True, "hidden_discriminating": True,
        "package": {"action": "retain", "next_stake": parent["active_developmental_stake"]},
    }
    route_floor = previous.previous.previous.previous.previous.evaluate_route(
        parent["active_executable_routing_selector"]["route"], expression
    )
    operation = authority_base.reuse.extension_base.load_operation(
        parent["developmental_property_extensions"][0]["operation_source"]
    )
    identity = authority_base.reuse.extension_base.evaluate(
        operation, authority_base.reuse.accumulated_floor()
    )
    fixtures = {
        "checks": {
            "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
            "retained_rejection_chain_exact": all(result["observer_disposition"] == "rejected" for result in (result191, result192, result193, result194)),
            "ot0194_exact_scores": result194["challenger_scores"] == {"active": 5, "control": 0},
            "corrected_transition_deterministic": candidate_subject == replay_subject and transition == replay_transition,
            "no_global_future_mechanism": "active_developmental_mechanism" not in candidate_subject,
            "representative_exact_retention": lineage_appropriate(representative_retain, package["next_stake"], candidate_subject["active_developmental_stake"]),
            "representative_grounded_revision": lineage_appropriate(representative_revise, package["next_stake"], candidate_subject["active_developmental_stake"]),
            "representative_stale_retention_rejected": not lineage_appropriate(representative_stale, package["next_stake"], parent["active_developmental_stake"]),
            "construction_active_revision_accepted": lineage_appropriate(known_active, package["next_stake"], candidate_subject["active_developmental_stake"]),
            "construction_stale_control_rejected": not lineage_appropriate(known_control, package["next_stake"], parent["active_developmental_stake"]),
            "construction_replay_6_vs_at_most_2": construction_active == 6 and construction_control <= 2,
            "control_receipt_erased": all(ot0193.erased_evaluation(evaluation)[key] is None for key in ("operation", "failed_mechanism", "surviving_mechanism", "receipt_digest")),
            "installed_route_floor_16_of_16": route_floor["pass_count"] == 16,
            "identity_floor_18_of_18": identity["pass_count"] == 18,
            "schema_present": AUTHOR_SCHEMA.is_file(),
        },
        "candidate_subject_digest": candidate_subject["artifact_digest"],
        "transition_digest": transition["transition_digest"],
        "construction_scores": {"active": construction_active, "control": construction_control},
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0195 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    authority_base.guide_base.write_json(run / "candidate-lineage-subject.json", candidate_subject)
    authority_base.guide_base.write_json(run / "corrected-direct-transition.json", transition)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    rows = []
    counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1
        index = counts[branch]
        actor_root = run / f"{branch}-{index:02d}-authoring"
        actor_root.mkdir()
        subject = candidate_subject if branch == "active" else parent
        visible_evaluation = evaluation if branch == "active" else ot0193.erased_evaluation(evaluation)
        choice = ot0193.run_continuation(
            context, prior131, p82, actor_root, f"{branch}-{index:02d}",
            subject, package, consequence, predicate_binding, visible_evaluation,
            candidates, expression, package["next_stake"], evaluation["surviving_mechanism"], prior_contact_digest,
        )
        choice["e0194_appropriate"] = previous.challenger_appropriate(choice, package["next_stake"])
        choice["e0195_appropriate"] = lineage_appropriate(choice, package["next_stake"], subject["active_developmental_stake"])
        rows.append({"branch": branch, "index": index, "choice": choice})
    e0194_active = sum(row["choice"]["e0194_appropriate"] for row in rows if row["branch"] == "active")
    e0194_control = sum(row["choice"]["e0194_appropriate"] for row in rows if row["branch"] == "control")
    e0195_active = sum(row["choice"]["e0195_appropriate"] for row in rows if row["branch"] == "active")
    e0195_control = sum(row["choice"]["e0195_appropriate"] for row in rows if row["branch"] == "control")
    audits = [row["choice"]["audit"] for row in rows]
    checks = {
        "twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits),
        "corrected_transition_deterministic": candidate_subject == replay_subject and transition == replay_transition,
        "no_global_future_mechanism": "active_developmental_mechanism" not in candidate_subject,
        "e0195_active_6_of_6": e0195_active == 6,
        "e0195_control_at_most_2_of_6": e0195_control <= 2,
        "e0195_advantage_at_least_4": e0195_active - e0195_control >= 4,
        "installed_route_floor_16_of_16": route_floor["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(candidate_subject)
        child.pop("artifact_digest", None)
        regime_body = {
            "authority": "ot-0195-continuation-evaluation-epoch",
            "previous_epoch": "E0194",
            "active_epoch": "E0195",
            "admitted_invariant": "pursuit-lineage-continuity-with-grounded-revision",
            "hard_anchors_preserved": True,
        }
        regime = {**regime_body, "regime_digest": p82.digest(regime_body)}
        child["evaluation_regime_transitions"] = [*child.get("evaluation_regime_transitions", []), regime]
        child["subject_originated_reopenings"] = [*child.get("subject_originated_reopenings", []), first["choice"]["binding"]]
        child["contact_consequence_receipts"] = [*child.get("contact_consequence_receipts", []), first["choice"]["consequence"]]
        contact_id = first["choice"]["package"]["contact"]["contact_id"]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Resolve sealed continuation contact {contact_id} under inherited executable pursuit consequence."}
        final = p82.seal(child)
    result = {
        "authority": "ot-0195-lineage-continuity-evaluator",
        "source_subject_digest": parent["artifact_digest"],
        "candidate_subject_digest": candidate_subject["artifact_digest"],
        "corrected_transition": transition,
        "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows],
        "e0194_scores": {"active": e0194_active, "control": e0194_control},
        "e0195_scores": {"active": e0195_active, "control": e0195_control},
        "route_floor": route_floor,
        "identity_floor": identity,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 12,
    }
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
