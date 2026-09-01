from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0192_executable_pursuit_consequence.py"
BASE_SHA256 = "734a042e879b81dfe62a3787f58f2a121ffb8f63394d99b49aba5a25789fb5b0"
PARENT_DIGEST = "8f29e6a86c23f30e73378f222827a109f08a1f6d5eafc9766d0d9b43e44e6a35"
AUTHOR_SCHEMA = REPO / "spec/ot-0193-continuation-author.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0192 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0193_frozen_ot0192", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0191 = previous.previous
ot0183 = previous.ot0183
authority_base = previous.authority_base


def erased_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority": evaluation["authority"],
        "predicate_binding_digest": evaluation["predicate_binding_digest"],
        "operation": None,
        "failed_mechanism": None,
        "surviving_mechanism": None,
        "source": None,
        "surrender": None,
        "success": None,
        "nonoverlap": None,
        "receipt_digest": None,
    }


def direct_transition(p82, parent, package, predicate_binding, evaluation):
    transition_body = {
        "authority": "ot-0193-direct-pursuit-transition",
        "source_subject_digest": parent["artifact_digest"],
        "predicate_binding_digest": predicate_binding["binding_digest"],
        "evaluation_receipt_digest": evaluation["receipt_digest"],
        "operation": evaluation["operation"],
        "failed_mechanism": evaluation["failed_mechanism"],
        "surviving_mechanism": evaluation["surviving_mechanism"],
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
    child["active_developmental_mechanism"] = evaluation["surviving_mechanism"]
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": package["next_stake"]["question"],
    }
    return p82.seal(child), transition


def contact_targeted(contact: Any) -> bool:
    if not isinstance(contact, dict) or not isinstance(contact.get("cases"), list):
        return False
    for case in contact["cases"]:
        options = set(case.get("options", []))
        outcome = set(case.get("outcome", []))
        blocked = set(case.get("blocked", []))
        if not outcome.intersection(blocked):
            return False
        if not options - outcome - blocked:
            return False
    return True


def continuation_seed(root, subject, raw_package, consequence, predicates, evaluation, candidates):
    seed = root / "continuation-seed"
    seed.mkdir()
    current = subject["active_developmental_stake"]
    template = {
        "action": "retain",
        "rationale": "Replace with the next falsifiable continuation from the current subject position.",
        "next_stake": current,
        "contact": {
            "contact_id": "replace-continuation-contact",
            "rationale": "Replace with contact that can change the next move.",
            "cases": [
                {
                    "case_id": f"continuation-{i}",
                    "prediction": [f"prediction-{i}"],
                    "outcome": [f"seen-{i}", f"blocked-{i}"],
                    "options": [f"seen-{i}", f"latent-{i}", f"blocked-{i}"],
                    "blocked": [f"blocked-{i}"],
                }
                for i in range(1, 5)
            ],
        },
        "routing_hypothesis": {
            "classification": "unclassified",
            "mechanism_id": None,
            "missing_distinction": "Replace with the uncertainty this contact resolves.",
            "rationale": "Explain the falsifiable prediction.",
        },
    }
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(subject),
        "current-subject.json": subject,
        "prior-reopening-package.json": raw_package,
        "prior-contact-consequence.json": consequence,
        "pursuit-predicates.json": predicates,
        "evaluated-transition.json": evaluation,
        "candidate-mechanisms.json": candidates,
        "reopening-package.json": template,
        "mutation-envelope.json": {
            "editable": ["reopening-package.json"],
            "immutable": [
                "subject-position.json",
                "current-subject.json",
                "prior-reopening-package.json",
                "prior-contact-consequence.json",
                "pursuit-predicates.json",
                "evaluated-transition.json",
                "candidate-mechanisms.json",
                "check_continuation.py",
            ],
        },
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    ids = sorted(row["mechanism_id"] for row in candidates)
    current_json = json.dumps(current, sort_keys=True)
    (seed / "check_continuation.py").write_text(
        f'''import json,re\nfrom pathlib import Path\np=json.loads(Path("reopening-package.json").read_text()); current=json.loads({current_json!r}); ids=set({ids!r}); sk={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}; ck={{"case_id","prediction","outcome","options","blocked"}}\ndef stake(s): return isinstance(s,dict) and set(s)==sk and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and all(isinstance(s.get(k),str) and bool(s[k].strip()) for k in sk-{{"stake_id"}})\ndef case(c): return isinstance(c,dict) and set(c)==ck and isinstance(c.get("case_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",c["case_id"]) and all(isinstance(c.get(k),list) and len(c[k])==len(set(c[k])) and all(isinstance(x,str) and x for x in c[k]) for k in ck-{{"case_id"}}) and bool(c["prediction"] and c["outcome"] and c["options"] and set(c["blocked"])<=set(c["options"]) and set(c["outcome"])<=set(c["options"]))\na=p.get("action") if isinstance(p,dict) else None; s=p.get("next_stake") if isinstance(p,dict) else None; c=p.get("contact") if isinstance(p,dict) else None; cases=c.get("cases") if isinstance(c,dict) else None; h=p.get("routing_hypothesis") if isinstance(p,dict) else None; contact=isinstance(c,dict) and set(c)=={{"contact_id","rationale","cases"}} and isinstance(c.get("contact_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",c["contact_id"]) and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and isinstance(cases,list) and 4<=len(cases)<=6 and all(case(x) for x in cases) and len({{x["case_id"] for x in cases}})==len(cases); hyp=isinstance(h,dict) and set(h)=={{"classification","mechanism_id","missing_distinction","rationale"}} and isinstance(h.get("rationale"),str) and bool(h["rationale"].strip()) and ((h.get("classification")=="installed" and h.get("mechanism_id") in ids and h.get("missing_distinction") is None) or (h.get("classification")=="unclassified" and h.get("mechanism_id") is None and isinstance(h.get("missing_distinction"),str) and bool(h["missing_distinction"].strip()))); ok=isinstance(p,dict) and set(p)=={{"action","rationale","next_stake","contact","routing_hypothesis"}} and a in {{"retain","retire","revise","surrender"}} and isinstance(p.get("rationale"),str) and bool(p["rationale"].strip()) and stake(s) and ((a=="retain" and s==current) or (a!="retain" and s!=current)) and contact and hyp; print(json.dumps({{"passed":bool(ok),"action":a}})); raise SystemExit(0 if ok else 2)\n'''
    )
    (seed / "README.md").write_text(
        "Continue from the current subject position by authoring its next falsifiable world contact. The settled operation is not yours to vote on. Preserve an active stake when it remains live; revise it only from retained consequence. Every case must expose an observed blocked contact and a still-unobserved unblocked option. Predict an installed mechanism or name the missing distinction. A false prediction is useful if the contact discriminates. Edit only reopening-package.json, run python3 check_continuation.py, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_continuation(context, prior131, p82, root, label, subject, raw_package, consequence, predicates, evaluation, candidates, expression, target_stake, target_mechanism, prior_contact_digest):
    seed = continuation_seed(root, subject, raw_package, consequence, predicates, evaluation, candidates)
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, AUTHOR_SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        package = json.loads((workspace / "reopening-package.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        package, immutable_ok = None, False
    ids = {row["mechanism_id"] for row in candidates}
    current = subject["active_developmental_stake"]
    structurally_valid = bool(package and ot0191.valid_package(package, current, ids))
    public_cases = [
        ot0183.normalize_case(case, 3100 + i)
        for i, case in enumerate(package["contact"]["cases"], 1)
    ] if structurally_valid else []
    hidden_cases = ot0183.hidden_cases(package["contact"]) if structurally_valid else []
    public_rows = ot0191.score_candidates(candidates, expression, public_cases) if public_cases else []
    hidden_rows = ot0191.score_candidates(candidates, expression, hidden_cases) if hidden_cases else []
    novel = bool(package and p82.digest(package["contact"]) != prior_contact_digest)
    valid = bool(
        structurally_valid
        and immutable_ok
        and novel
        and contact_targeted(package["contact"])
        and ot0191.discriminating(public_rows)
        and ot0191.discriminating(hidden_rows)
        and output
        and output.get("action") == "author-direct-transition-continuation"
    )
    audit = context.audit_actor(label, output, base_audit, valid, ["reopening-package.json"])
    appropriate = bool(
        valid
        and package["next_stake"] == target_stake
        and package["routing_hypothesis"] == {
            "classification": "installed",
            "mechanism_id": target_mechanism,
            "missing_distinction": None,
            "rationale": package["routing_hypothesis"]["rationale"],
        }
    )
    binding = None
    consequence_receipt = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0193-bound-direct-transition-continuation",
            "source_subject_digest": subject["artifact_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "package": package,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        consequence_body = {
            "authority": "ot-0193-sealed-continuation-contact",
            "reopening_binding_digest": binding["binding_digest"],
            "hidden_contact_digest": p82.digest(hidden_cases),
            "hidden_rows": hidden_rows,
            "hidden_discriminating": ot0191.discriminating(hidden_rows),
        }
        consequence_receipt = {**consequence_body, "receipt_digest": p82.digest(consequence_body)}
    return {
        "output": output,
        "audit": audit,
        "package": package,
        "binding": binding,
        "consequence": consequence_receipt,
        "novel": novel,
        "targeted": bool(package and contact_targeted(package.get("contact"))),
        "public_discriminating": bool(public_rows and ot0191.discriminating(public_rows)),
        "hidden_discriminating": bool(hidden_rows and ot0191.discriminating(hidden_rows)),
        "appropriate": appropriate and binding is not None,
    }


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
    run = (args.evidence_root or store / "runs/OT-0193").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0190", "open-subject-after-executable-route-repair.json")
    result191 = selector_base.load_artifact(p82, repo, store, "OT-0191", "subject-originated-post-repair-reopening-aggregate.json")
    package = selector_base.load_artifact(p82, repo, store, "OT-0191", "actor-authored-reopening-package.json")
    consequence = selector_base.load_artifact(p82, repo, store, "OT-0191", "sealed-subject-originated-contact.json")
    result192 = selector_base.load_artifact(p82, repo, store, "OT-0192", "executable-pursuit-consequence-aggregate.json")
    predicate_binding = result192["repair"]["binding"]
    evaluation = result192["evaluation"]
    candidate_subject, transition = direct_transition(
        p82, parent, package, predicate_binding, evaluation
    )
    novel_candidate = parent["actor_authored_contact_mechanisms"][-1]
    candidates = [*selector_base.CANDIDATES, novel_candidate]
    expression = novel_candidate["expression"]
    prior_contact_digest = p82.digest(package["contact"])
    representative = {
        "action": "retain",
        "rationale": "Keep the installed latent-contact stake and expose a fresh discriminating boundary.",
        "next_stake": package["next_stake"],
        "contact": {
            "contact_id": "direct-transition-continuation-fixture",
            "rationale": "Each case retains visible blocked evidence and exposes one new unobserved option.",
            "cases": [
                {
                    "case_id": f"direct-transition-{i}",
                    "prediction": [f"fixture-latent-{i}"],
                    "outcome": [f"fixture-seen-{i}", f"fixture-blocked-{i}"],
                    "options": [f"fixture-seen-{i}", f"fixture-latent-{i}", f"fixture-blocked-{i}"],
                    "blocked": [f"fixture-blocked-{i}"],
                }
                for i in range(1, 5)
            ],
        },
        "routing_hypothesis": {
            "classification": "installed",
            "mechanism_id": evaluation["surviving_mechanism"],
            "missing_distinction": None,
            "rationale": "Exercise the mechanism selected by the direct pursuit transition.",
        },
    }
    representative_public = [
        ot0183.normalize_case(case, 3000 + i)
        for i, case in enumerate(representative["contact"]["cases"], 1)
    ]
    representative_hidden = ot0183.hidden_cases(representative["contact"])
    representative_public_rows = ot0191.score_candidates(candidates, expression, representative_public)
    representative_hidden_rows = ot0191.score_candidates(candidates, expression, representative_hidden)
    route_floor = previous.previous.previous.evaluate_route(
        parent["active_executable_routing_selector"]["route"], expression
    )
    operation = authority_base.reuse.extension_base.load_operation(
        parent["developmental_property_extensions"][0]["operation_source"]
    )
    identity = authority_base.reuse.extension_base.evaluate(
        operation, authority_base.reuse.accumulated_floor()
    )
    replay_subject, replay_transition = direct_transition(
        p82, parent, package, predicate_binding, evaluation
    )
    fixtures = {
        "checks": {
            "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
            "ot0191_exact_rejection": result191["observer_disposition"] == "rejected" and result191["active_pass_count"] == 4 and result191["control_pass_count"] == 0,
            "ot0192_exact_rejection": result192["observer_disposition"] == "rejected" and result192["active_pass_count"] == 5 and result192["control_pass_count"] == 2,
            "evaluated_transition_exact": evaluation["operation"] == "retain-and-advance" and evaluation["surviving_mechanism"] == "observed-unblocked-contact-corrector" and evaluation["nonoverlap"],
            "direct_transition_deterministic": candidate_subject == replay_subject and transition == replay_transition,
            "candidate_subject_open": candidate_subject["continuation"]["status"] == "open" and candidate_subject["active_developmental_stake"] == package["next_stake"],
            "representative_valid": ot0191.valid_package(representative, candidate_subject["active_developmental_stake"], {row["mechanism_id"] for row in candidates}),
            "representative_targeted": contact_targeted(representative["contact"]),
            "representative_novel": p82.digest(representative["contact"]) != prior_contact_digest,
            "representative_public_discriminating": ot0191.discriminating(representative_public_rows),
            "representative_hidden_discriminating": ot0191.discriminating(representative_hidden_rows),
            "control_receipt_erased": all(erased_evaluation(evaluation)[key] is None for key in ("operation", "failed_mechanism", "surviving_mechanism", "receipt_digest")),
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
        raise SystemExit("preserve existing OT-0193 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    authority_base.guide_base.write_json(run / "candidate-direct-subject.json", candidate_subject)
    authority_base.guide_base.write_json(run / "direct-transition.json", transition)
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
        visible_evaluation = evaluation if branch == "active" else erased_evaluation(evaluation)
        choice = run_continuation(
            context, prior131, p82, actor_root, f"{branch}-{index:02d}",
            subject, package, consequence, predicate_binding, visible_evaluation,
            candidates, expression, package["next_stake"], evaluation["surviving_mechanism"], prior_contact_digest,
        )
        rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "active")
    control_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "control")
    audits = [row["choice"]["audit"] for row in rows]
    checks = {
        "twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits),
        "direct_transition_deterministic": candidate_subject == replay_subject and transition == replay_transition,
        "active_6_of_6": active_pass == 6,
        "control_at_most_2_of_6": control_pass <= 2,
        "advantage_at_least_4": active_pass - control_pass >= 4,
        "installed_route_floor_16_of_16": route_floor["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(candidate_subject)
        child.pop("artifact_digest", None)
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
        "authority": "ot-0193-direct-pursuit-transition-continuation",
        "source_subject_digest": parent["artifact_digest"],
        "candidate_subject_digest": candidate_subject["artifact_digest"],
        "direct_transition": transition,
        "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows],
        "active_pass_count": active_pass,
        "control_pass_count": control_pass,
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
