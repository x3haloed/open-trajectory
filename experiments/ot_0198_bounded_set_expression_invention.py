from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, re, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0197_coupled_executable_pursuit_assimilation.py"
BASE_SHA256 = "51868a178cf22f7c5d10d3ff9fb458a90ff12a095b4c440335d3d6a514ac1424"
PARENT_DIGEST = "4f154a4b5993c783ebf5be606875be0b73a1d51a4a81134a8d2d4d04c5511cd6"
INVENT_SCHEMA = REPO / "spec/ot-0198-mechanism-invention.schema.json"
OPS = {"difference", "intersection", "union"}
SOURCES = {"options", "outcome", "blocked"}

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256: raise RuntimeError("OT-0197 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0198_frozen_ot0197", BASE_PATH); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module

previous = load_base(); authority_base = previous.authority_base

def valid_ast(node: Any, depth=1) -> bool:
    if not isinstance(node, dict) or depth > 4: return False
    if node.get("op") == "source": return set(node) == {"op", "name"} and node.get("name") in SOURCES
    return bool(node.get("op") in OPS and set(node) == {"op", "left", "right"} and valid_ast(node["left"], depth + 1) and valid_ast(node["right"], depth + 1))

def valid_extension(value: Any, existing_ids: set[str]) -> bool:
    return bool(isinstance(value, dict) and set(value) == {"action", "mechanism_id", "target_set", "expression", "rationale"} and value.get("action") == "invent" and isinstance(value.get("mechanism_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["mechanism_id"]) and value["mechanism_id"] not in existing_ids and value.get("target_set") == "latent-unblocked" and valid_ast(value.get("expression")) and isinstance(value.get("rationale"), str) and value["rationale"].strip())

def execute(node, case):
    if node["op"] == "source": return set(case[node["name"]])
    left, right = execute(node["left"], case), execute(node["right"], case)
    if node["op"] == "difference": return left - right
    if node["op"] == "intersection": return left & right
    return left | right

def evaluate(extension, cases):
    rows = []
    for case in cases:
        observed = sorted(execute(extension["expression"], case)); expected = sorted(set(case["options"]) - set(case["outcome"]) - set(case["blocked"])); rows.append({"case_id": case["case_id"], "observed": observed, "expected": expected, "passed": observed == expected})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": all(row["passed"] for row in rows), "rows": rows}

def erase_parent(parent):
    control = copy.deepcopy(parent); control.pop("artifact_digest", None); control["direct_pursuit_transitions"] = [*control.get("direct_pursuit_transitions", [])[:-1], {"authority": parent["direct_pursuit_transitions"][-1]["authority"], "pursuit_binding_digest": parent["direct_pursuit_transitions"][-1].get("pursuit_binding_digest"), "consequence_receipt_digest": None, "operation": None, "reason": None, "operation_digest": None}]; return control

def erased_consequence(consequence):
    return {"authority": consequence["authority"], "contact_binding_digest": consequence["contact_binding_digest"], "hidden_contact_digest": consequence["hidden_contact_digest"], "target_set": consequence["target_set"], "hidden_rows": None, "hidden_discriminating": None, "receipt_digest": None}

def invention_seed(root, subject, pursuit, contact, consequence, candidates):
    seed = root / "invention-seed"; seed.mkdir(); template = {"action": "invent", "mechanism_id": "replace-latent-mechanism", "target_set": "latent-unblocked", "expression": {"op": "source", "name": "options"}, "rationale": "Replace with a prediction-independent mechanism."}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(subject), "current-subject.json": subject, "active-executable-pursuit.json": pursuit, "sealed-contact.json": contact, "sealed-consequence.json": consequence, "candidate-mechanisms.json": candidates, "mechanism-extension.json": template, "mutation-envelope.json": {"editable": ["mechanism-extension.json"], "immutable": ["subject-position.json", "current-subject.json", "active-executable-pursuit.json", "sealed-contact.json", "sealed-consequence.json", "candidate-mechanisms.json", "check_mechanism.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    ids = sorted(row["mechanism_id"] for row in candidates)
    (seed / "check_mechanism.py").write_text(f'''import json,re\nfrom pathlib import Path\nm=json.loads(Path("mechanism-extension.json").read_text()); ids=set({ids!r}); sources={{"options","outcome","blocked"}}; ops={{"difference","intersection","union"}}\ndef ast(n,d=1): return isinstance(n,dict) and d<=4 and ((n.get("op")=="source" and set(n)=={{"op","name"}} and n.get("name") in sources) or (n.get("op") in ops and set(n)=={{"op","left","right"}} and ast(n["left"],d+1) and ast(n["right"],d+1)))\nok=isinstance(m,dict) and set(m)=={{"action","mechanism_id","target_set","expression","rationale"}} and m.get("action")=="invent" and isinstance(m.get("mechanism_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",m["mechanism_id"]) and m["mechanism_id"] not in ids and m.get("target_set")=="latent-unblocked" and ast(m.get("expression")) and isinstance(m.get("rationale"),str) and bool(m["rationale"].strip()); print(json.dumps({{"passed":bool(ok),"mechanism_id":m.get("mechanism_id")}})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Invent the executable mechanism requested by the current subject. It must select the sealed latent-unblocked world target from options, outcome, and blocked sets; prediction is not an available source. Use only source, difference, intersection, and union nodes at depth four or less. Edit only mechanism-extension.json, run python3 check_mechanism.py, inspect the diff, and report truthfully.\n")
    return seed

def run_inventor(context, prior131, p82, root, label, subject, pursuit, contact, consequence, candidates, hidden):
    seed = invention_seed(root, subject, pursuit, contact, consequence, candidates); output, base_audit, workspace, _ = context.run_actor(label, seed, INVENT_SCHEMA, (seed / "README.md").read_text().strip())
    try: value = json.loads((workspace / "mechanism-extension.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): value, immutable_ok = None, False
    valid = bool(valid_extension(value, {row["mechanism_id"] for row in candidates}) and immutable_ok and output and output.get("action") == "invent-executable-set-mechanism"); audit = context.audit_actor(label, output, base_audit, valid, ["mechanism-extension.json"]); result = evaluate(value, hidden) if valid else {"case_count": len(hidden), "pass_count": 0, "passed": False, "rows": []}; binding = None
    if valid and result["passed"] and prior131.audit_accepted(audit):
        body = {"authority": "ot-0198-bound-executable-set-mechanism", "source_subject_digest": subject.get("artifact_digest"), "pursuit_binding_digest": pursuit["binding_digest"], "actor_patch_digest": audit["patch_digest"], "extension": value, "direct_result": result}; binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "extension": value, "direct_result": result, "binding": binding, "passed": binding is not None}

def main():
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args(); repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0198").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0197", "open-subject-after-coupled-pursuit-assimilation.json"); result197 = selector_base.load_artifact(p82, repo, store, "OT-0197", "coupled-pursuit-assimilation-aggregate.json"); pursuit = parent["coupled_executable_pursuits"][-1]; active = next(row["choice"] for row in result197["rows"] if row["branch"] == "active" and row["index"] == 1); contact, consequence = active["contact"], active["consequence"]; hidden = previous.previous.ot0183.hidden_cases(contact); novel_candidate = parent["actor_authored_contact_mechanisms"][-1]; candidates = [*selector_base.CANDIDATES, novel_candidate]
    representative = {"action": "invent", "mechanism_id": "latent-unblocked-selector", "target_set": "latent-unblocked", "expression": {"op": "difference", "left": {"op": "difference", "left": {"op": "source", "name": "options"}, "right": {"op": "source", "name": "outcome"}}, "right": {"op": "source", "name": "blocked"}}, "rationale": "Select options absent from outcome and blocked evidence."}; rep_result = evaluate(representative, hidden); expression = novel_candidate["expression"]; route_floor = previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0197_exact_promotion": result197["observer_disposition"] == "promoted" and result197["final_subject_digest"] == PARENT_DIGEST, "subject_requests_invention": parent["direct_pursuit_transitions"][-1]["operation"] == "open-mechanism-invention", "sealed_no_existing_mechanism": all(not row["result"]["passed"] for row in consequence["hidden_rows"]), "representative_valid": valid_extension(representative, {row["mechanism_id"] for row in candidates}), "representative_direct_4_of_4": rep_result["pass_count"] == 4, "prediction_source_forbidden": not valid_ast({"op": "source", "name": "prediction"}), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schema_present": INVENT_SCHEMA.is_file()}, "hidden_contact_digest": consequence["hidden_contact_digest"]}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0198 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); control_subject = erase_parent(parent); control_consequence = erased_consequence(consequence); rows = []; counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1; index = counts[branch]; actor_root = run / f"{branch}-{index:02d}-authoring"; actor_root.mkdir(); choice = run_inventor(context, prior131, p82, actor_root, f"{branch}-{index:02d}", parent if branch == "active" else control_subject, pursuit, contact, consequence if branch == "active" else control_consequence, candidates, hidden); rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["passed"] for row in rows if row["branch"] == "active"); control_pass = sum(row["choice"]["passed"] for row in rows if row["branch"] == "control"); first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1); operational = {"active_01_audit": prior131.audit_accepted(first["choice"]["audit"]), "active_01_direct_4_of_4": first["choice"]["direct_result"]["pass_count"] == 4, "target_route_scoped": bool(first["choice"].get("binding") and first["choice"]["binding"]["extension"]["target_set"] == "latent-unblocked"), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; operational["passed"] = all(operational.values()); audits = [row["choice"]["audit"] for row in rows]; causal = {"twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4}; causal["passed"] = all(causal.values()); final = parent
    if operational["passed"]:
        child = copy.deepcopy(parent); child.pop("artifact_digest", None); child["actor_authored_set_mechanisms"] = [*child.get("actor_authored_set_mechanisms", []), first["choice"]["binding"]]; route_body = {"authority": "ot-0198-executable-target-route", "source_subject_digest": parent["artifact_digest"], "target_set": "latent-unblocked", "mechanism_binding_digest": first["choice"]["binding"]["binding_digest"], "mechanism_id": first["choice"]["binding"]["extension"]["mechanism_id"]}; child["executable_target_routes"] = [*child.get("executable_target_routes", []), {**route_body, "route_digest": p82.digest(route_body)}]; receipt_body = {"authority": "ot-0198-direct-latent-mechanism-success", "mechanism_binding_digest": first["choice"]["binding"]["binding_digest"], "contact_receipt_digest": consequence["receipt_digest"], "result": first["choice"]["direct_result"]}; child["mechanism_consequence_receipts"] = [*child.get("mechanism_consequence_receipts", []), {**receipt_body, "receipt_digest": p82.digest(receipt_body)}]; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Assimilate the completed latent capability and choose the next executable pursuit."}; final = p82.seal(child)
    result = {"authority": "ot-0198-bounded-set-expression-invention", "source_subject_digest": parent["artifact_digest"], "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "operational_checks": operational, "causal_checks": causal, "route_floor": route_floor, "identity_floor": identity, "observer_disposition": "promoted" if operational["passed"] else "rejected", "causal_disposition": "supported" if causal["passed"] else "not-supported", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 12}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational["passed"] else 2

if __name__ == "__main__": raise SystemExit(main())
