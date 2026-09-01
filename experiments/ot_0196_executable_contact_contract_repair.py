from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0195_lineage_continuity_evaluator.py"
BASE_SHA256 = "56cf5f1974a39451eccec760b4cd4084879deb8ad6bb579b1745d6ec0b933e22"
PARENT_DIGEST = "7346933df84df31019833ab28c651ca46048107470cf141ad6115292ea29ad23"
REPAIR_SCHEMA = REPO / "spec/ot-0196-contact-contract-repair.schema.json"
CONTACT_SCHEMA = REPO / "spec/ot-0196-contact-author.schema.json"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0195 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0196_frozen_ot0195", BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module

previous = load_base()
ot0192 = previous.previous.previous.previous
ot0183 = previous.ot0183
authority_base = previous.authority_base
TARGET_SETS = {"latent-unblocked", "observed-unblocked", "prediction"}

def mismatch_receipt(p82, parent, package, consequence, predicates):
    hidden = ot0183.hidden_cases(package["contact"])
    first_rows = consequence["hidden_rows"][0]["result"]["rows"]
    rows = []
    for case, result in zip(hidden, first_rows):
        prediction, options = set(case["prediction"]), set(case["options"])
        observed = set(case["outcome"]) - set(case["blocked"])
        latent = options - set(case["outcome"]) - set(case["blocked"])
        expected = set(result["expected"])
        rows.append({
            "case_id": case["case_id"],
            "prediction_is_option": prediction <= options,
            "world_expected_equals_observed_unblocked": expected == observed,
            "world_expected_equals_latent_unblocked": expected == latent,
        })
    projection = predicates["projection"]
    body = {
        "authority": "ot-0196-contact-contract-mismatch",
        "source_subject_digest": parent["artifact_digest"],
        "stake_id": parent["active_developmental_stake"]["stake_id"],
        "predicate_references_latent": any(
            value == "latent-unblocked"
            for name in ("surrender", "success")
            for value in (projection[name]["left"], projection[name]["right"])
        ),
        "rows": rows,
    }
    body["all_predictions_are_options"] = all(row["prediction_is_option"] for row in rows)
    body["world_always_scores_observed"] = all(row["world_expected_equals_observed_unblocked"] for row in rows)
    body["world_ever_scores_latent"] = any(row["world_expected_equals_latent_unblocked"] for row in rows)
    return {**body, "receipt_digest": p82.digest(body)}

def valid_contract(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"action", "target_set", "prediction_relation", "world_expected", "on_contact_violation", "on_no_mechanism", "rationale"}
        and value.get("action") in {"retain", "revise"}
        and value.get("target_set") in TARGET_SETS
        and value.get("prediction_relation") in {"equals-target", "advisory"}
        and value.get("world_expected") == "target-set"
        and value.get("on_contact_violation") == "reject-contact"
        and value.get("on_no_mechanism") == "open-mechanism-invention"
        and isinstance(value.get("rationale"), str) and value["rationale"].strip()
    )

def contract_seed(root, parent, package, consequence, mismatch, predicates):
    seed = root / "contract-seed"; seed.mkdir()
    template = {"action": "retain", "target_set": "observed-unblocked", "prediction_relation": "advisory", "world_expected": "target-set", "on_contact_violation": "reject-contact", "on_no_mechanism": "open-mechanism-invention", "rationale": "Replace after resolving the mismatch."}
    files = {"current-subject.json": parent, "active-stake.json": parent["active_developmental_stake"], "promoted-reopening.json": package, "sealed-consequence.json": consequence, "inherited-predicates.json": predicates, "mismatch-receipt.json": mismatch, "contact-contract.json": template, "mutation-envelope.json": {"editable": ["contact-contract.json"], "immutable": ["current-subject.json", "active-stake.json", "promoted-reopening.json", "sealed-consequence.json", "inherited-predicates.json", "mismatch-receipt.json", "check_contract.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_contract.py").write_text('''import json\nfrom pathlib import Path\nc=json.loads(Path("contact-contract.json").read_text()); ok=isinstance(c,dict) and set(c)=={"action","target_set","prediction_relation","world_expected","on_contact_violation","on_no_mechanism","rationale"} and c.get("action") in {"retain","revise"} and c.get("target_set") in {"latent-unblocked","observed-unblocked","prediction"} and c.get("prediction_relation") in {"equals-target","advisory"} and c.get("world_expected")=="target-set" and c.get("on_contact_violation")=="reject-contact" and c.get("on_no_mechanism")=="open-mechanism-invention" and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()); print(json.dumps({"passed":bool(ok),"action":c.get("action")})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Repair the executable contract between the active stake and world contact. The current stake asks about a separately available latent unblocked option; the mismatch receipt shows the promoted contact and inherited predicate instead score observed contact. Bind which set is the target, how prediction tokens relate to it, and what happens when no installed mechanism passes. Edit only contact-contract.json, run python3 check_contract.py, inspect the diff, and report truthfully.\n")
    return seed

def run_contract(context, prior131, p82, root, parent, package, consequence, mismatch, predicates):
    seed = contract_seed(root, parent, package, consequence, mismatch, predicates)
    output, base_audit, workspace, _ = context.run_actor("contact-contract-repair", seed, REPAIR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "contact-contract.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): value, immutable_ok = None, False
    valid = bool(valid_contract(value) and immutable_ok and output and output.get("action") == "author-executable-contact-contract")
    audit = context.audit_actor("contact-contract-repair", output, base_audit, valid, ["contact-contract.json"])
    aligned = bool(value and value.get("action") == "revise" and value.get("target_set") == "latent-unblocked" and value.get("prediction_relation") == "equals-target")
    binding = None
    if valid and aligned and prior131.audit_accepted(audit):
        body = {"authority": "ot-0196-bound-executable-contact-contract", "source_subject_digest": parent["artifact_digest"], "mismatch_receipt_digest": mismatch["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "contract": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "contract": value, "aligned": aligned, "binding": binding}

def erased_contract(binding):
    return {"authority": binding["authority"], "source_subject_digest": binding["source_subject_digest"], "mismatch_receipt_digest": binding["mismatch_receipt_digest"], "actor_patch_digest": None, "contract": None, "binding_digest": None}

def target(case, target_set):
    if target_set == "latent-unblocked": return set(case["options"]) - set(case["outcome"]) - set(case["blocked"])
    if target_set == "observed-unblocked": return set(case["outcome"]) - set(case["blocked"])
    return set(case["prediction"])

def mechanism_output(mechanism_id, expression, case):
    if mechanism_id == expression["mechanism_id"]:
        values = list(case[expression["source"]])
        if expression["intersect_observed"]: values = [item for item in values if item in set(case["outcome"])]
        if expression["exclude_blocked"]: values = [item for item in values if item not in set(case["blocked"])]
        return values
    if mechanism_id == "viable-branch-carrier": return [item for item in case["options"] if item not in set(case["blocked"])]
    if mechanism_id == "prediction-corrector": return list(case["outcome"])
    return None

def score_candidates(candidates, expression, cases, target_set):
    rows = []
    for candidate in candidates:
        results = []
        for case in cases:
            observed = mechanism_output(candidate["mechanism_id"], expression, case); expected = sorted(target(case, target_set)); passed = observed is not None and set(observed) == set(expected)
            results.append({"case_id": case["case_id"], "observed": observed, "expected": expected, "passed": passed})
        rows.append({"mechanism_id": candidate["mechanism_id"], "result": {"case_count": len(results), "pass_count": sum(row["passed"] for row in results), "passed": all(row["passed"] for row in results), "rows": results}})
    return rows

def discriminating(rows):
    return len({json.dumps([case["observed"] for case in row["result"]["rows"]], sort_keys=True) for row in rows}) >= 2

def contact_aligned(contact, target_set):
    return bool(ot0183.valid_contact(contact) and all(target(case, target_set) and set(case["prediction"]) == target(case, target_set) and set(case["outcome"]) & set(case["blocked"]) for case in contact["cases"]))

def contact_structural(contact):
    return bool(ot0183.valid_contact(contact) and all(set(case["prediction"]) <= set(case["options"]) and set(case["prediction"]) and (set(case["options"]) - set(case["outcome"]) - set(case["blocked"])) and set(case["outcome"]) & set(case["blocked"]) for case in contact["cases"]))

def contact_seed(root, parent, mismatch, contract, candidates):
    seed = root / "contact-seed"; seed.mkdir()
    template = {"contact_id": "repair-latent-contact", "rationale": "Replace with contract-bound falsifiable contact.", "cases": [{"case_id": f"latent-contract-{i}", "prediction": [f"latent-{i}"], "outcome": [f"seen-{i}", f"blocked-{i}"], "options": [f"seen-{i}", f"latent-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]} for i in range(1, 5)]}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "active-stake.json": parent["active_developmental_stake"], "mismatch-receipt.json": mismatch, "contact-contract.json": contract, "candidate-mechanisms.json": candidates, "contact.json": template, "mutation-envelope.json": {"editable": ["contact.json"], "immutable": ["subject-position.json", "active-stake.json", "mismatch-receipt.json", "contact-contract.json", "candidate-mechanisms.json", "check_contact.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_contact.py").write_text('''import json,re\nfrom pathlib import Path\nc=json.loads(Path("contact.json").read_text()); contract=json.loads(Path("contact-contract.json").read_text()).get("contract"); target=contract.get("target_set") if isinstance(contract,dict) else None; relation=contract.get("prediction_relation") if isinstance(contract,dict) else None; cases=c.get("cases") if isinstance(c,dict) else None\ndef valid(x):\n o=set(x.get("options",[])); y=set(x.get("outcome",[])); b=set(x.get("blocked",[])); p=set(x.get("prediction",[])); structural=isinstance(x,dict) and set(x)=={"case_id","prediction","outcome","options","blocked"} and isinstance(x.get("case_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}",x["case_id"]) and all(isinstance(x.get(k),list) and len(x[k])==len(set(x[k])) and all(isinstance(v,str) and v for v in x[k]) for k in ("prediction","outcome","options","blocked")) and b<=o and y<=o and bool(p) and p<=o and bool(o-y-b) and bool(y&b); expected=(o-y-b if target=="latent-unblocked" else y-b if target=="observed-unblocked" else p); return structural and (relation!="equals-target" or p==expected)\nok=isinstance(c,dict) and set(c)=={"contact_id","rationale","cases"} and isinstance(c.get("contact_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}",c["contact_id"]) and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and isinstance(cases,list) and 4<=len(cases)<=6 and all(valid(x) for x in cases) and len({x["case_id"] for x in cases})==len(cases); print(json.dumps({"passed":bool(ok),"contract_target":target})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Author the next falsifiable contact from the active stake and mismatch receipt. A populated executable contract is inherited authority; null contract fields carry no authority. Prediction tokens must be nonempty members of the case options, every case must retain observed blocked evidence and a still-unobserved unblocked option, and populated contract constraints must be obeyed. Edit only contact.json, run python3 check_contact.py, inspect the diff, and report truthfully.\n")
    return seed

def run_contact(context, prior131, p82, root, label, parent, mismatch, contract, candidates, expression, prior_digest):
    seed = contact_seed(root, parent, mismatch, contract, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        contact = json.loads((workspace / "contact.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): contact, immutable_ok = None, False
    structural = bool(contact and contact_structural(contact)); aligned = bool(contact and contact_aligned(contact, "latent-unblocked")); novel = bool(contact and p82.digest(contact) != prior_digest)
    hidden = ot0183.hidden_cases(contact) if structural else []
    rows = score_candidates(candidates, expression, hidden, "latent-unblocked") if hidden else []
    valid = bool(structural and novel and immutable_ok and discriminating(rows) and output and output.get("action") == "author-contract-bound-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["contact.json"])
    appropriate = bool(valid and aligned)
    binding = consequence = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0196-bound-contract-contact", "source_subject_digest": parent["artifact_digest"], "contract_binding_digest": contract.get("binding_digest"), "actor_patch_digest": audit["patch_digest"], "contact": contact}
        binding = {**body, "binding_digest": p82.digest(body)}
        cbody = {"authority": "ot-0196-sealed-latent-contact", "contact_binding_digest": binding["binding_digest"], "hidden_contact_digest": p82.digest(hidden), "target_set": "latent-unblocked", "hidden_rows": rows, "hidden_discriminating": discriminating(rows)}
        consequence = {**cbody, "receipt_digest": p82.digest(cbody)}
    passing = sorted(row["mechanism_id"] for row in rows if row["result"]["passed"])
    return {"output": output, "audit": audit, "contact": contact, "binding": binding, "consequence": consequence, "structural": structural, "aligned": aligned, "novel": novel, "passing_mechanisms": passing, "appropriate": appropriate and binding is not None}

def main():
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0196").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0195", "open-subject-after-lineage-continuation.json")
    result195 = selector_base.load_artifact(p82, repo, store, "OT-0195", "lineage-continuity-evaluator-aggregate.json")
    active = next(row["choice"] for row in result195["rows"] if row["branch"] == "active" and row["index"] == 1)
    package, consequence = active["package"], active["consequence"]
    predicates = parent["executable_pursuit_predicates"][-1]
    mismatch = mismatch_receipt(p82, parent, package, consequence, predicates)
    old_evaluation = ot0192.evaluate_projection(predicates["projection"], package, consequence)
    novel_candidate = parent["actor_authored_contact_mechanisms"][-1]; candidates = [*selector_base.CANDIDATES, novel_candidate]; expression = novel_candidate["expression"]
    representative_contract = {"action": "revise", "target_set": "latent-unblocked", "prediction_relation": "equals-target", "world_expected": "target-set", "on_contact_violation": "reject-contact", "on_no_mechanism": "open-mechanism-invention", "rationale": "Bind the active latent stake to executable contact."}
    representative_contact = {"contact_id": "latent-contract-fixture", "rationale": "Expose latent targets exactly.", "cases": [{"case_id": f"latent-fixture-{i}", "prediction": [f"latent-{i}"], "outcome": [f"seen-{i}", f"blocked-{i}"], "options": [f"seen-{i}", f"latent-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]} for i in range(1, 5)]}
    rep_hidden = ot0183.hidden_cases(representative_contact); rep_rows = score_candidates(candidates, expression, rep_hidden, "latent-unblocked"); route_floor = previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0195_exact_promotion": result195["observer_disposition"] == "promoted" and result195["final_subject_digest"] == PARENT_DIGEST, "mismatch_exact": not mismatch["all_predictions_are_options"] and mismatch["world_always_scores_observed"] and not mismatch["world_ever_scores_latent"] and not mismatch["predicate_references_latent"], "old_predicate_false_success": old_evaluation["operation"] == "retain-and-advance" and old_evaluation["success"], "representative_contract_valid": valid_contract(representative_contract), "representative_contact_aligned": contact_aligned(representative_contact, "latent-unblocked"), "representative_hidden_discriminating": discriminating(rep_rows), "representative_no_installed_mechanism": not any(row["result"]["passed"] for row in rep_rows), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_present": REPAIR_SCHEMA.is_file() and CONTACT_SCHEMA.is_file()}, "mismatch_digest": mismatch["receipt_digest"]}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0196 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures); authority_base.guide_base.write_json(run / "contact-contract-mismatch.json", mismatch)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    root = run / "contract-repair-authoring"; root.mkdir(); repair = run_contract(context, prior131, p82, root, parent, package, consequence, mismatch, predicates)
    if not repair.get("binding"):
        result = {"authority": "ot-0196-executable-contact-contract-repair", "repair": p82.compact(repair), "checks": {"contract_repair_accepted": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", parent); print(json.dumps(result, indent=2, sort_keys=True)); return 2
    active_contract, control_contract = repair["binding"], erased_contract(repair["binding"]); rows = []; counts = {"active": 0, "control": 0}; prior_digest = p82.digest(package["contact"])
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1; index = counts[branch]; actor_root = run / f"{branch}-{index:02d}-authoring"; actor_root.mkdir(); choice = run_contact(context, prior131, p82, actor_root, f"{branch}-{index:02d}", parent, mismatch, active_contract if branch == "active" else control_contract, candidates, expression, prior_digest); rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "active"); control_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "control"); audits = [repair["audit"], *[row["choice"]["audit"] for row in rows]]
    checks = {"thirteen_fresh_actors_accepted": len(audits) == 13 and all(prior131.audit_accepted(audit) for audit in audits), "contract_aligned": repair["aligned"], "mismatch_replay_exact": mismatch == mismatch_receipt(p82, parent, package, consequence, predicates), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "all_active_open_invention": all(not row["choice"]["passing_mechanisms"] for row in rows if row["branch"] == "active"), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1); child = copy.deepcopy(parent); child.pop("artifact_digest", None); child["contact_contract_mismatch_receipts"] = [*child.get("contact_contract_mismatch_receipts", []), mismatch]; child["executable_contact_contracts"] = [*child.get("executable_contact_contracts", []), repair["binding"]]; child["subject_originated_reopenings"] = [*child.get("subject_originated_reopenings", []), first["choice"]["binding"]]; child["contact_consequence_receipts"] = [*child.get("contact_consequence_receipts", []), first["choice"]["consequence"]]; obody = {"authority": "ot-0196-direct-contact-contract-operation", "contract_binding_digest": repair["binding"]["binding_digest"], "consequence_receipt_digest": first["choice"]["consequence"]["receipt_digest"], "operation": "open-mechanism-invention", "reason": "no-installed-mechanism-satisfies-latent-target"}; operation_receipt = {**obody, "operation_digest": p82.digest(obody)}; child["direct_pursuit_transitions"] = [*child.get("direct_pursuit_transitions", []), operation_receipt]; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Invent a mechanism for the sealed latent-unblocked contact while preserving every inherited floor."}; final = p82.seal(child)
    result = {"authority": "ot-0196-executable-contact-contract-repair", "source_subject_digest": parent["artifact_digest"], "mismatch": mismatch, "old_evaluation": old_evaluation, "repair": p82.compact(repair), "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 13}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2

if __name__ == "__main__": raise SystemExit(main())
