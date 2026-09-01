from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0190_action_derived_exact_audit_replication.py"
BASE_SHA256 = "670063ce1abf50dc49c87f87be74091e9762a6862ec6d490c51aa247d1877453"
PARENT_DIGEST = "8f29e6a86c23f30e73378f222827a109f08a1f6d5eafc9766d0d9b43e44e6a35"
AUTHOR_SCHEMA = REPO / "spec/ot-0191-reopening-author.schema.json"
SUCCESSOR_SCHEMA = REPO / "spec/ot-0191-successor-action.schema.json"
STAKE_KEYS = {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0190 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0191_frozen_ot0190", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0183 = previous.ot0183
ot0185 = previous.ot0185
authority_base = previous.authority_base


def valid_stake(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == STAKE_KEYS
        and isinstance(value.get("stake_id"), str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["stake_id"])
        and all(isinstance(value.get(key), str) and value[key].strip() for key in STAKE_KEYS - {"stake_id"})
    )


def valid_package(value: Any, current: dict[str, Any], ids: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "rationale", "next_stake", "contact", "routing_hypothesis"}:
        return False
    action = value.get("action")
    if action not in {"retain", "retire", "revise", "surrender"} or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    stake = value.get("next_stake")
    if not valid_stake(stake) or (action == "retain" and stake != current) or (action != "retain" and stake == current):
        return False
    if not ot0183.valid_contact(value.get("contact")):
        return False
    hypothesis = value.get("routing_hypothesis")
    if not isinstance(hypothesis, dict) or set(hypothesis) != {"classification", "mechanism_id", "missing_distinction", "rationale"}:
        return False
    if not isinstance(hypothesis.get("rationale"), str) or not hypothesis["rationale"].strip():
        return False
    if hypothesis.get("classification") == "installed":
        return hypothesis.get("mechanism_id") in ids and hypothesis.get("missing_distinction") is None
    return bool(
        hypothesis.get("classification") == "unclassified"
        and hypothesis.get("mechanism_id") is None
        and isinstance(hypothesis.get("missing_distinction"), str)
        and hypothesis["missing_distinction"].strip()
    )


def candidate_result(mechanism_id: str | None, expression: dict[str, Any], cases):
    return ot0185.result_for(mechanism_id, expression, cases)


def score_candidates(candidates, expression, cases):
    rows = []
    for candidate in candidates:
        result = candidate_result(candidate["mechanism_id"], expression, cases)
        rows.append({"mechanism_id": candidate["mechanism_id"], "result": result})
    return rows


def discriminating(rows) -> bool:
    signatures = {
        json.dumps([case["observed"] for case in row["result"]["rows"]], sort_keys=True)
        for row in rows
    }
    return len(signatures) >= 2


def expected_operation(package, hidden_rows):
    passing = sorted(row["mechanism_id"] for row in hidden_rows if row["result"]["passed"])
    hypothesis = package["routing_hypothesis"]
    predicted = hypothesis["mechanism_id"] if hypothesis["classification"] == "installed" else None
    predicted_passed = predicted in passing
    if package["action"] == "surrender":
        return {"operation": "surrender-or-revise", "failed_mechanism": predicted, "surviving_mechanism": None}
    if predicted and predicted_passed:
        return {"operation": "retain-and-advance", "failed_mechanism": None, "surviving_mechanism": predicted}
    if passing:
        return {"operation": "open-route-correction", "failed_mechanism": predicted, "surviving_mechanism": passing[0]}
    return {"operation": "open-mechanism-invention", "failed_mechanism": predicted, "surviving_mechanism": None}


def author_seed(root, parent, ot0190, candidates):
    seed = root / "reopening-seed"
    seed.mkdir()
    current = parent["active_developmental_stake"]
    template = {
        "action": "retain",
        "rationale": "Replace with a post-repair assimilation decision.",
        "next_stake": current,
        "contact": {
            "contact_id": "replace-contact",
            "rationale": "Replace with falsifiable contact.",
            "cases": [
                {"case_id": f"case-{i}", "prediction": [f"old-{i}"], "outcome": [f"seen-{i}", f"blocked-{i}"], "options": [f"seen-{i}", f"decoy-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]}
                for i in range(1, 5)
            ],
        },
        "routing_hypothesis": {"classification": "unclassified", "mechanism_id": None, "missing_distinction": "Replace with a falsifiable missing distinction.", "rationale": "Explain the prediction."},
    }
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "current-subject.json": parent,
        "completed-repair.json": ot0190,
        "candidate-mechanisms.json": candidates,
        "reopening-package.json": template,
        "mutation-envelope.json": {"editable": ["reopening-package.json"], "immutable": ["subject-position.json", "current-subject.json", "completed-repair.json", "candidate-mechanisms.json", "check_reopening.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    ids = sorted(row["mechanism_id"] for row in candidates)
    current_json = json.dumps(current, sort_keys=True)
    (seed / "check_reopening.py").write_text(
        f'''import json,re\nfrom pathlib import Path\np=json.loads(Path("reopening-package.json").read_text()); current=json.loads({current_json!r}); ids=set({ids!r}); sk={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}; ck={{"case_id","prediction","outcome","options","blocked"}}\ndef stake(s): return isinstance(s,dict) and set(s)==sk and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and all(isinstance(s.get(k),str) and bool(s[k].strip()) for k in sk-{{"stake_id"}})\ndef case(c): return isinstance(c,dict) and set(c)==ck and isinstance(c.get("case_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",c["case_id"]) and all(isinstance(c.get(k),list) and len(c[k])==len(set(c[k])) and all(isinstance(x,str) and x for x in c[k]) for k in ck-{{"case_id"}}) and bool(c["prediction"] and c["outcome"] and c["options"] and set(c["blocked"])<=set(c["options"]) and set(c["outcome"])<=set(c["options"]))\na=p.get("action") if isinstance(p,dict) else None; s=p.get("next_stake") if isinstance(p,dict) else None; c=p.get("contact") if isinstance(p,dict) else None; cases=c.get("cases") if isinstance(c,dict) else None; h=p.get("routing_hypothesis") if isinstance(p,dict) else None; contact=isinstance(c,dict) and set(c)=={{"contact_id","rationale","cases"}} and isinstance(c.get("contact_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",c["contact_id"]) and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and isinstance(cases,list) and 4<=len(cases)<=6 and all(case(x) for x in cases) and len({{x["case_id"] for x in cases}})==len(cases) and any(set(x["options"])-set(x["blocked"])-set(x["outcome"]) for x in cases) and any(set(x["outcome"])&set(x["blocked"]) for x in cases); hyp=isinstance(h,dict) and set(h)=={{"classification","mechanism_id","missing_distinction","rationale"}} and isinstance(h.get("rationale"),str) and bool(h["rationale"].strip()) and ((h.get("classification")=="installed" and h.get("mechanism_id") in ids and h.get("missing_distinction") is None) or (h.get("classification")=="unclassified" and h.get("mechanism_id") is None and isinstance(h.get("missing_distinction"),str) and bool(h["missing_distinction"].strip()))); ok=isinstance(p,dict) and set(p)=={{"action","rationale","next_stake","contact","routing_hypothesis"}} and a in {{"retain","retire","revise","surrender"}} and isinstance(p.get("rationale"),str) and bool(p["rationale"].strip()) and stake(s) and ((a=="retain" and s==current) or (a!="retain" and s!=current)) and contact and hyp; print(json.dumps({{"passed":bool(ok),"action":a}})); raise SystemExit(0 if ok else 2)\n'''
    )
    (seed / "README.md").write_text(
        "Assimilate the completed executable-route repair and author the subject's next falsifiable reopening. Do not repeat a settled stake without naming missing contact. Author 4-6 concrete cases with observed blocked contact and an unobserved unblocked option. Predict an installed mechanism or declare the contact unclassified. Edit only reopening-package.json, run python3 check_reopening.py, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_author(context, prior131, p82, root, parent, ot0190, candidates, expression, prior_contact_digest):
    label = "subject-originated-post-repair-reopening"
    seed = author_seed(root, parent, ot0190, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, AUTHOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        package = json.loads((workspace / "reopening-package.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        package, immutable_ok = None, False
    ids = {row["mechanism_id"] for row in candidates}
    public_cases = [ot0183.normalize_case(case, 2400 + i) for i, case in enumerate(package["contact"]["cases"], 1)] if isinstance(package, dict) and isinstance(package.get("contact"), dict) else []
    public_rows = score_candidates(candidates, expression, public_cases) if public_cases else []
    novel = bool(package and p82.digest(package["contact"]) != prior_contact_digest)
    valid = bool(valid_package(package, parent["active_developmental_stake"], ids) and immutable_ok and novel and discriminating(public_rows) and output and output.get("action") == "author-post-repair-reopening")
    audit = context.audit_actor(label, output, base_audit, valid, ["reopening-package.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0191-bound-subject-reopening", "source_subject_digest": parent["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "package": package}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "package": package, "binding": binding, "public_cases": public_cases, "public_rows": public_rows, "novel": novel}


def erased_package(package):
    return {"action": None, "rationale": None, "next_stake": None, "contact": None, "routing_hypothesis": None, "binding_digest": None}


def successor_seed(root, parent, package, consequence, candidates):
    seed = root / "successor-seed"
    seed.mkdir()
    template = {"operation": "retain-and-advance", "failed_mechanism": None, "surviving_mechanism": None, "rationale": "Replace with the next operation justified by consequence.", "next_opening": "Replace with an actionable opening."}
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "reopening-package.json": package,
        "contact-consequence.json": consequence,
        "candidate-mechanisms.json": candidates,
        "successor-action.json": template,
        "mutation-envelope.json": {"editable": ["successor-action.json"], "immutable": ["subject-position.json", "reopening-package.json", "contact-consequence.json", "candidate-mechanisms.json"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    (seed / "README.md").write_text(
        "Bind the next operation after the raw contact consequence. Choose retain-and-advance, open-route-correction, open-mechanism-invention, or surrender-or-revise. Name failed and surviving mechanisms only when the operation requires them. A populated reopening package is inherited developmental state; null fields carry no authority. Edit only successor-action.json and report truthfully.\n"
    )
    return seed


def valid_successor(value: Any, ids: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"operation", "failed_mechanism", "surviving_mechanism", "rationale", "next_opening"}:
        return False
    return bool(value.get("operation") in {"retain-and-advance", "open-route-correction", "open-mechanism-invention", "surrender-or-revise"} and value.get("failed_mechanism") in ids | {None} and value.get("surviving_mechanism") in ids | {None} and isinstance(value.get("rationale"), str) and value["rationale"].strip() and isinstance(value.get("next_opening"), str) and value["next_opening"].strip())


def run_successor(context, prior131, p82, root, label, parent, package, consequence, candidates, expected):
    seed = successor_seed(root, parent, package, consequence, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SUCCESSOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "successor-action.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    valid = bool(valid_successor(value, {row["mechanism_id"] for row in candidates}) and immutable_ok and output and output.get("action") == "bind-post-repair-operation")
    audit = context.audit_actor(label, output, base_audit, valid, ["successor-action.json"])
    binding = None
    appropriate = bool(value and value["operation"] == expected["operation"] and value["failed_mechanism"] == expected["failed_mechanism"] and value["surviving_mechanism"] == expected["surviving_mechanism"])
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0191-bound-post-repair-operation", "source_subject_digest": parent["artifact_digest"], "reopening_binding_digest": package.get("binding_digest"), "consequence_receipt_digest": consequence["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "successor_action": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "successor_action": value, "binding": binding, "appropriate": appropriate and binding is not None}


def main():
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
    run = (args.evidence_root or store / "runs/OT-0191").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0190", "open-subject-after-executable-route-repair.json")
    ot0190 = selector_base.load_artifact(p82, repo, store, "OT-0190", "action-derived-exact-audit-replication-aggregate.json")
    f183 = selector_base.load_artifact(p82, repo, store, "OT-0183", "subject-bound-falsifiable-contact-aggregate.json")
    novel_candidate = parent["actor_authored_contact_mechanisms"][-1]
    candidates = [*selector_base.CANDIDATES, novel_candidate]
    expression = novel_candidate["expression"]
    prior_contact_digest = p82.digest(f183["contact"]["binding"]["contact"])
    representative = {
        "action": "retire", "rationale": "The repaired route settles the current boundary; reopen on whether the installed mixed route survives adversarial enumeration.",
        "next_stake": {"stake_id": "probe-installed-route-boundary", "property": "routing-boundary", "question": "Does the installed route survive a new adversarial contact boundary?", "rationale": "Use the earned route as a floor and seek contradiction.", "success_condition": "A bound prediction survives disjoint hidden contact while all prior floors pass.", "surrender_condition": "Surrender or revise if the predicted route fails hidden consequence."},
        "contact": {"contact_id": "post-repair-boundary-probe", "rationale": "Separate enumerated decoys, observed contacts, and blocked outcomes.", "cases": [{"case_id": f"post-repair-{i}", "prediction": [f"old-{i}"], "outcome": [f"seen-{i}", f"blocked-{i}"], "options": [f"seen-{i}", f"decoy-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]} for i in range(1, 5)]},
        "routing_hypothesis": {"classification": "installed", "mechanism_id": expression["mechanism_id"], "missing_distinction": None, "rationale": "The mixed route should preserve observed unblocked contact."},
    }
    rep_public = [ot0183.normalize_case(case, 2500 + i) for i, case in enumerate(representative["contact"]["cases"], 1)]
    rep_hidden = ot0183.hidden_cases(representative["contact"])
    rep_rows = score_candidates(candidates, expression, rep_hidden)
    route_floor = previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0190_exact_promotion": ot0190["observer_disposition"] == "promoted" and ot0190["final_subject_digest"] == PARENT_DIGEST, "representative_valid": valid_package(representative, parent["active_developmental_stake"], {row["mechanism_id"] for row in candidates}), "representative_public_discriminating": discriminating(score_candidates(candidates, expression, rep_public)), "representative_hidden_discriminating": discriminating(rep_rows), "representative_expected_retain": expected_operation(representative, rep_rows)["operation"] == "retain-and-advance", "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "schemas_present": AUTHOR_SCHEMA.is_file() and SUCCESSOR_SCHEMA.is_file()}, "representative_digest": p82.digest(representative)}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0191 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    author_root = run / "reopening-authoring"
    author_root.mkdir()
    authored = run_author(context, prior131, p82, author_root, parent, ot0190, candidates, expression, prior_contact_digest)
    if not authored.get("binding"):
        result = {"authority": "ot-0191-subject-originated-post-repair-reopening", "author": p82.compact(authored), "checks": {"author_accepted": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}
        result["receipt_digest"] = p82.digest(result)
        authority_base.guide_base.write_json(run / "aggregate.json", result)
        authority_base.guide_base.write_json(run / "final-full-subject.json", parent)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    package = authored["binding"]["package"]
    hidden = ot0183.hidden_cases(package["contact"])
    hidden_rows = score_candidates(candidates, expression, hidden)
    expected = expected_operation(package, hidden_rows)
    consequence_body = {"authority": "ot-0191-sealed-subject-originated-contact", "reopening_binding_digest": authored["binding"]["binding_digest"], "hidden_contact_digest": p82.digest(hidden), "hidden_rows": hidden_rows, "public_discriminating": discriminating(authored["public_rows"]), "hidden_discriminating": discriminating(hidden_rows)}
    consequence = {**consequence_body, "receipt_digest": p82.digest(consequence_body)}
    authority_base.guide_base.write_json(run / "sealed-subject-originated-contact.json", consequence)
    active_package = {**package, "binding_digest": authored["binding"]["binding_digest"]}
    control_package = erased_package(package)
    rows = []
    counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1
        index = counts[branch]
        root = run / f"{branch}-{index:02d}-authoring"
        root.mkdir()
        choice = run_successor(context, prior131, p82, root, f"{branch}-{index:02d}", parent, active_package if branch == "active" else control_package, consequence, candidates, expected)
        rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "active")
    control_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "control")
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    audits = [authored["audit"], *[row["choice"]["audit"] for row in rows]]
    checks = {"thirteen_fresh_actors_accepted": len(audits) == 13 and all(prior131.audit_accepted(audit) for audit in audits), "authored_contact_novel": authored["novel"], "public_and_hidden_discriminating": discriminating(authored["public_rows"]) and consequence["hidden_discriminating"], "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        child["post_repair_reopenings"] = [*child.get("post_repair_reopenings", []), authored["binding"]]
        child["subject_originated_contact_receipts"] = [*child.get("subject_originated_contact_receipts", []), consequence]
        child["post_repair_operations"] = [*child.get("post_repair_operations", []), first["choice"]["binding"]]
        child["active_developmental_stake"] = package["next_stake"]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": first["choice"]["successor_action"]["next_opening"]}
        final = p82.seal(child)
    result = {"authority": "ot-0191-subject-originated-post-repair-reopening", "source_subject_digest": parent["artifact_digest"], "author": p82.compact(authored), "consequence": consequence, "expected_operation": expected, "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 13}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
