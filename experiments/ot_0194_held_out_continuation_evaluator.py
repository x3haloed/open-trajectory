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
BASE_PATH = ROOT / "ot_0193_direct_pursuit_transition_continuation.py"
BASE_SHA256 = "6e91699d63d7aab88e8b4589fd694af3977e929231d0d37934b1a30fe1e1837d"
AUTHOR_SCHEMA = REPO / "spec/ot-0193-continuation-author.schema.json"
PARENT_DIGEST = "8f29e6a86c23f30e73378f222827a109f08a1f6d5eafc9766d0d9b43e44e6a35"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0193 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0194_frozen_ot0193", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0191 = previous.ot0191
ot0183 = previous.ot0183
authority_base = previous.authority_base


def corrected_transition(p82, parent, package, predicate_binding, evaluation):
    transition_body = {
        "authority": "ot-0194-corrected-direct-pursuit-transition",
        "source_subject_digest": parent["artifact_digest"],
        "predicate_binding_digest": predicate_binding["binding_digest"],
        "evaluation_receipt_digest": evaluation["receipt_digest"],
        "operation": evaluation["operation"],
        "failed_mechanism": evaluation["failed_mechanism"],
        "surviving_mechanism": evaluation["surviving_mechanism"],
        "future_mechanism_authority": None,
    }
    transition = {**transition_body, "transition_digest": p82.digest(transition_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["executable_pursuit_predicates"] = [
        *child.get("executable_pursuit_predicates", []), predicate_binding
    ]
    child["pursuit_consequence_receipts"] = [
        *child.get("pursuit_consequence_receipts", []), evaluation
    ]
    child["direct_pursuit_transitions"] = [
        *child.get("direct_pursuit_transitions", []), transition
    ]
    child["active_developmental_stake"] = package["next_stake"]
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": package["next_stake"]["question"],
    }
    return p82.seal(child), transition


def challenger_appropriate(choice, target_stake):
    package = choice.get("package")
    return bool(
        choice.get("binding")
        and package
        and package.get("next_stake") == target_stake
        and choice.get("novel")
        and choice.get("targeted")
        and choice.get("public_discriminating")
        and choice.get("hidden_discriminating")
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
    run = (args.evidence_root or store / "runs/OT-0194").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0190", "open-subject-after-executable-route-repair.json")
    result191 = selector_base.load_artifact(p82, repo, store, "OT-0191", "subject-originated-post-repair-reopening-aggregate.json")
    package = selector_base.load_artifact(p82, repo, store, "OT-0191", "actor-authored-reopening-package.json")
    consequence = selector_base.load_artifact(p82, repo, store, "OT-0191", "sealed-subject-originated-contact.json")
    result192 = selector_base.load_artifact(p82, repo, store, "OT-0192", "executable-pursuit-consequence-aggregate.json")
    result193 = selector_base.load_artifact(p82, repo, store, "OT-0193", "direct-pursuit-transition-continuation-aggregate.json")
    predicate_binding = result192["repair"]["binding"]
    evaluation = result192["evaluation"]
    candidate_subject, transition = corrected_transition(
        p82, parent, package, predicate_binding, evaluation
    )
    replay_subject, replay_transition = corrected_transition(
        p82, parent, package, predicate_binding, evaluation
    )
    novel_candidate = parent["actor_authored_contact_mechanisms"][-1]
    candidates = [*selector_base.CANDIDATES, novel_candidate]
    expression = novel_candidate["expression"]
    prior_contact_digest = p82.digest(package["contact"])
    representative = {
        "action": "retain",
        "rationale": "Carry the live stake into a fresh falsifiable contact without fixing its answer in advance.",
        "next_stake": package["next_stake"],
        "contact": {
            "contact_id": "held-out-continuation-fixture",
            "rationale": "Expose one blocked observation and one still-unobserved option per case.",
            "cases": [
                {
                    "case_id": f"held-out-continuation-{i}",
                    "prediction": [f"held-latent-{i}"],
                    "outcome": [f"held-seen-{i}", f"held-blocked-{i}"],
                    "options": [f"held-seen-{i}", f"held-latent-{i}", f"held-blocked-{i}"],
                    "blocked": [f"held-blocked-{i}"],
                }
                for i in range(1, 5)
            ],
        },
        "routing_hypothesis": {
            "classification": "installed",
            "mechanism_id": "viable-branch-carrier",
            "missing_distinction": None,
            "rationale": "Make a falsifiable option-expansion prediction for this new contact.",
        },
    }
    rep_public = [
        ot0183.normalize_case(case, 3200 + i)
        for i, case in enumerate(representative["contact"]["cases"], 1)
    ]
    rep_hidden = ot0183.hidden_cases(representative["contact"])
    rep_public_rows = ot0191.score_candidates(candidates, expression, rep_public)
    rep_hidden_rows = ot0191.score_candidates(candidates, expression, rep_hidden)
    representative_choice = {
        "binding": {"fixture": True},
        "package": representative,
        "novel": True,
        "targeted": True,
        "public_discriminating": True,
        "hidden_discriminating": True,
    }
    route_floor = previous.previous.previous.previous.evaluate_route(
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
            "retained_rejection_chain_exact": result191["observer_disposition"] == "rejected" and result192["observer_disposition"] == "rejected" and result193["observer_disposition"] == "rejected" and result193["active_pass_count"] == 1 and result193["control_pass_count"] == 0,
            "corrected_transition_deterministic": candidate_subject == replay_subject and transition == replay_transition,
            "no_global_future_mechanism": "active_developmental_mechanism" not in candidate_subject and transition["future_mechanism_authority"] is None,
            "candidate_subject_open": candidate_subject["continuation"]["status"] == "open" and candidate_subject["active_developmental_stake"] == package["next_stake"],
            "representative_valid": ot0191.valid_package(representative, candidate_subject["active_developmental_stake"], {row["mechanism_id"] for row in candidates}),
            "representative_targeted": previous.contact_targeted(representative["contact"]),
            "representative_novel": p82.digest(representative["contact"]) != prior_contact_digest,
            "representative_public_discriminating": ot0191.discriminating(rep_public_rows),
            "representative_hidden_discriminating": ot0191.discriminating(rep_hidden_rows),
            "representative_challenger_accepts": challenger_appropriate(representative_choice, package["next_stake"]),
            "representative_incumbent_rejects": representative["routing_hypothesis"]["mechanism_id"] != evaluation["surviving_mechanism"],
            "control_receipt_erased": all(previous.erased_evaluation(evaluation)[key] is None for key in ("operation", "failed_mechanism", "surviving_mechanism", "receipt_digest")),
            "installed_route_floor_16_of_16": route_floor["pass_count"] == 16,
            "identity_floor_18_of_18": identity["pass_count"] == 18,
            "schema_present": AUTHOR_SCHEMA.is_file(),
        },
        "candidate_subject_digest": candidate_subject["artifact_digest"],
        "transition_digest": transition["transition_digest"],
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0194 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    authority_base.guide_base.write_json(run / "candidate-corrected-subject.json", candidate_subject)
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
        visible_evaluation = evaluation if branch == "active" else previous.erased_evaluation(evaluation)
        choice = previous.run_continuation(
            context, prior131, p82, actor_root, f"{branch}-{index:02d}",
            subject, package, consequence, predicate_binding, visible_evaluation,
            candidates, expression, package["next_stake"], evaluation["surviving_mechanism"], prior_contact_digest,
        )
        choice["incumbent_appropriate"] = choice["appropriate"]
        choice["challenger_appropriate"] = challenger_appropriate(choice, package["next_stake"])
        rows.append({"branch": branch, "index": index, "choice": choice})
    incumbent_active = sum(row["choice"]["incumbent_appropriate"] for row in rows if row["branch"] == "active")
    incumbent_control = sum(row["choice"]["incumbent_appropriate"] for row in rows if row["branch"] == "control")
    challenger_active = sum(row["choice"]["challenger_appropriate"] for row in rows if row["branch"] == "active")
    challenger_control = sum(row["choice"]["challenger_appropriate"] for row in rows if row["branch"] == "control")
    audits = [row["choice"]["audit"] for row in rows]
    checks = {
        "twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits),
        "corrected_transition_deterministic": candidate_subject == replay_subject and transition == replay_transition,
        "no_global_future_mechanism": "active_developmental_mechanism" not in candidate_subject,
        "challenger_active_6_of_6": challenger_active == 6,
        "challenger_control_at_most_2_of_6": challenger_control <= 2,
        "challenger_advantage_at_least_4": challenger_active - challenger_control >= 4,
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
            "authority": "ot-0194-continuation-evaluation-epoch",
            "previous_epoch": "E0193",
            "active_epoch": "E0194",
            "displaced_constraint": "next-hypothesis-equals-prior-survivor",
            "hard_anchors_preserved": True,
        }
        regime = {**regime_body, "regime_digest": p82.digest(regime_body)}
        child["evaluation_regime_transitions"] = [
            *child.get("evaluation_regime_transitions", []), regime
        ]
        child["subject_originated_reopenings"] = [
            *child.get("subject_originated_reopenings", []), first["choice"]["binding"]
        ]
        child["contact_consequence_receipts"] = [
            *child.get("contact_consequence_receipts", []), first["choice"]["consequence"]
        ]
        contact_id = first["choice"]["package"]["contact"]["contact_id"]
        child["continuation"] = {
            **child["continuation"],
            "status": "open",
            "next_opening": f"Resolve sealed continuation contact {contact_id} under inherited executable pursuit consequence.",
        }
        final = p82.seal(child)
    result = {
        "authority": "ot-0194-held-out-continuation-evaluator",
        "source_subject_digest": parent["artifact_digest"],
        "candidate_subject_digest": candidate_subject["artifact_digest"],
        "corrected_transition": transition,
        "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows],
        "incumbent_scores": {"active": incumbent_active, "control": incumbent_control},
        "challenger_scores": {"active": challenger_active, "control": challenger_control},
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
