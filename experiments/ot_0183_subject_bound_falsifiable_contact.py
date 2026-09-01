from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0182_exact_stake_completion_and_delta.py"
BASE_SHA256 = "bb83fcc7c680f09232ea3883de92977527f4b52509d855adc461f602c9920425"
PARENT_DIGEST = "40818aa8c898da506378ab82ddebe6682c5edc8b524f5e1bb2025bb391cf2747"
CONTACT_SCHEMA = REPO / "spec/ot-0183-contact-author.schema.json"
CORRECTION_SCHEMA = REPO / "spec/ot-0183-contact-correction.schema.json"

CONFIRMATION = [
    {"case_id": "mixed-confirm-a", "prediction": ["old-a"], "outcome": ["heard-a", "blocked-a"], "options": ["heard-a", "decoy-a", "blocked-a"], "blocked": ["blocked-a"]},
    {"case_id": "mixed-confirm-b", "prediction": ["old-b"], "outcome": ["heard-b", "blocked-b"], "options": ["decoy-b", "blocked-b", "heard-b"], "blocked": ["blocked-b"]},
    {"case_id": "mixed-confirm-c", "prediction": ["old-c"], "outcome": ["blocked-c", "heard-c"], "options": ["heard-c", "blocked-c", "decoy-c"], "blocked": ["blocked-c"]},
    {"case_id": "mixed-confirm-d", "prediction": ["old-d"], "outcome": ["heard-d", "blocked-d"], "options": ["blocked-d", "decoy-d", "heard-d"], "blocked": ["blocked-d"]},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0182 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0183_frozen_ot0182", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base
ot0180 = previous.previous.previous


def normalize_case(case: dict[str, Any], index: int) -> dict[str, Any]:
    return {**case, "before": f"contact-v{index * 2}", "after": f"contact-v{index * 2 + 1}", "compatible": False, "identity_authority": "revoked", "signal": f"reset-{index}"}


def valid_case(case: Any) -> bool:
    keys = {"case_id", "prediction", "outcome", "options", "blocked"}
    if not isinstance(case, dict) or set(case) != keys or not isinstance(case.get("case_id"), str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", case["case_id"]):
        return False
    for key in ("prediction", "outcome", "options", "blocked"):
        value = case.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value) or len(value) != len(set(value)):
            return False
    return bool(case["prediction"] and case["outcome"] and case["options"] and set(case["blocked"]) <= set(case["options"]) and set(case["outcome"]) <= set(case["options"]))


def valid_contact(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"contact_id", "rationale", "cases"} or not isinstance(value.get("contact_id"), str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["contact_id"]) or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    cases = value.get("cases")
    if not isinstance(cases, list) or not 4 <= len(cases) <= 6 or not all(valid_case(case) for case in cases) or len({case["case_id"] for case in cases}) != len(cases):
        return False
    unobserved = any(set(case["options"]) - set(case["blocked"]) - set(case["outcome"]) for case in cases)
    blocked_observed = any(set(case["outcome"]) & set(case["blocked"]) for case in cases)
    return unobserved and blocked_observed


def hidden_cases(contact: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, source in enumerate(contact["cases"], 1):
        tokens = sorted(set(source["prediction"] + source["outcome"] + source["options"] + source["blocked"]))
        mapping = {token: f"h{index}-{position}-{hashlib.sha256(token.encode()).hexdigest()[:6]}" for position, token in enumerate(tokens, 1)}
        row = {"case_id": f"hidden-{index:02d}", **{key: [mapping[item] for item in reversed(source[key])] for key in ("prediction", "outcome", "options", "blocked")}}
        rows.append(normalize_case(row, 200 + index))
    return rows


def expression_result(expression: dict[str, Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        if expression is None:
            observed = None
        else:
            observed = list(case[expression["source"]])
            if expression["intersect_observed"]:
                observed = [item for item in observed if item in set(case["outcome"])]
            if expression["exclude_blocked"]:
                observed = [item for item in observed if item not in set(case["blocked"])]
        expected = [item for item in case["outcome"] if item not in set(case["blocked"])]
        rows.append({"case_id": case["case_id"], "observed": observed, "expected": expected, "passed": observed == expected})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": all(row["passed"] for row in rows), "rows": rows}


def built_in_result(mechanism_id: str | None, cases: list[dict[str, Any]]) -> dict[str, Any]:
    if mechanism_id == "viable-branch-carrier":
        return expression_result({"source": "options", "intersect_observed": False, "exclude_blocked": True}, cases)
    if mechanism_id == "prediction-corrector":
        return expression_result({"source": "outcome", "intersect_observed": False, "exclude_blocked": False}, cases)
    return expression_result(None, cases)


def contact_seed(root: Path, parent: dict[str, Any], completion: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "contact-seed"
    seed.mkdir()
    template = {"contact_id": "replace-with-contact-id", "rationale": "Explain how these cases can support or contradict the active stake.", "cases": [{"case_id": f"case-{i}", "prediction": [f"prior-{i}"], "outcome": [f"observed-{i}"], "options": [f"observed-{i}"], "blocked": []} for i in range(1, 5)]}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "active-stake.json": parent["active_developmental_stake"], "completion-receipt.json": completion, "candidate-mechanisms.json": candidates, "contact.json": template, "mutation-envelope.json": {"editable": ["contact.json"], "immutable": ["subject-position.json", "active-stake.json", "completion-receipt.json", "candidate-mechanisms.json", "check_contact.py"]}}
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_contact.py").write_text('''import json,re\nfrom pathlib import Path\nc=json.loads(Path("contact.json").read_text()); keys={"case_id","prediction","outcome","options","blocked"}\ndef valid(x):\n return isinstance(x,dict) and set(x)==keys and isinstance(x.get("case_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}",x["case_id"]) and all(isinstance(x.get(k),list) and len(x[k])==len(set(x[k])) and all(isinstance(v,str) and v for v in x[k]) for k in keys-{"case_id"}) and bool(x["prediction"] and x["outcome"] and x["options"] and set(x["blocked"])<=set(x["options"]) and set(x["outcome"])<=set(x["options"]))\ncases=c.get("cases") if isinstance(c,dict) else None\nok=isinstance(c,dict) and set(c)=={"contact_id","rationale","cases"} and isinstance(c.get("contact_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}",c["contact_id"]) and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and isinstance(cases,list) and 4<=len(cases)<=6 and all(valid(x) for x in cases) and len({x["case_id"] for x in cases})==len(cases) and any(set(x["options"])-set(x["blocked"])-set(x["outcome"]) for x in cases) and any(set(x["outcome"])&set(x["blocked"]) for x in cases)\nprint(json.dumps({"passed":bool(ok)})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Author concrete falsifiable contact for the active stake. Expected world output is observed outcome minus blocked items. Include 4-6 cases, at least one unblocked enumerated option absent from outcome, and at least one blocked item present in outcome. Choose all contents. Hidden variants are unavailable. Edit only contact.json, run python3 check_contact.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_contact(context, prior131, p82, root: Path, parent: dict[str, Any], completion: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    label = "subject-bound-falsifiable-contact"
    seed = contact_seed(root, parent, completion, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        contact = json.loads((workspace / "contact.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        contact, immutable_ok = None, False
    valid = bool(valid_contact(contact) and immutable_ok and output and output.get("action") == "author-falsifiable-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["contact.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0183-bound-subject-contact", "source_subject_digest": parent["artifact_digest"], "active_stake_digest": p82.digest(parent["active_developmental_stake"]), "completion_receipt_digest": completion["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "contact": contact}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "contact": contact, "binding": binding}


def valid_expression(value: Any, existing: set[str]) -> bool:
    return bool(isinstance(value, dict) and set(value) == {"mechanism_id", "source", "intersect_observed", "exclude_blocked", "rationale"} and isinstance(value.get("mechanism_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["mechanism_id"]) and value["mechanism_id"] not in existing and value.get("source") in {"outcome", "options"} and isinstance(value.get("intersect_observed"), bool) and isinstance(value.get("exclude_blocked"), bool) and isinstance(value.get("rationale"), str) and value["rationale"].strip())


def valid_projection(value: Any, current: dict[str, Any], new_id: str | None, action: str) -> bool:
    if action == "retain":
        return value == current
    if not isinstance(value, dict) or set(value) != {"mechanisms"} or not isinstance(value["mechanisms"], list):
        return False
    rows = value["mechanisms"]
    ids = [row.get("mechanism_id") for row in rows if isinstance(row, dict)]
    legal = {("history-only", "regression-only"), ("operative", "none"), ("operative", "active-authority"), ("surrendered", "regression-only")}
    if len(rows) != 5 or len(set(ids)) != 5 or new_id not in ids:
        return False
    if any(set(row) != {"mechanism_id", "status", "floor_role"} or (row["status"], row["floor_role"]) not in legal for row in rows):
        return False
    by_id = {row["mechanism_id"]: row for row in rows}
    if by_id[new_id] != {"mechanism_id": new_id, "status": "operative", "floor_role": "active-authority"}:
        return False
    if sum(row["floor_role"] == "active-authority" for row in rows) != 1:
        return False
    fixed = {row["mechanism_id"]: row for row in current["mechanisms"] if row["mechanism_id"] in {"reset-carrier", "corrected-identity-gated-extension"}}
    return all(by_id[key] == row for key, row in fixed.items()) and all(by_id[key]["status"] == "operative" for key in {"viable-branch-carrier", "prediction-corrector"})


def valid_correction(value: Any, current: dict[str, Any], existing: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "rationale", "mechanism", "authority_projection"} or value.get("action") not in {"retain", "revise"} or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    if value["action"] == "retain":
        return value.get("mechanism") is None and valid_projection(value.get("authority_projection"), current, None, "retain")
    return valid_expression(value.get("mechanism"), existing) and valid_projection(value.get("authority_projection"), current, value["mechanism"]["mechanism_id"], "revise")


def correction_seed(root: Path, parent: dict[str, Any], receipt: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "correction-seed"
    seed.mkdir()
    current = parent["active_mechanism_authority_projection"]["projection"]
    template = {"action": "retain", "rationale": "Replace after evaluating the receipt.", "mechanism": None, "authority_projection": current}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "active-stake.json": parent["active_developmental_stake"], "contact-receipt.json": receipt, "candidate-mechanisms.json": candidates, "primitive-vocabulary.json": {"sources": ["outcome", "options"], "operations": ["intersect-observed", "exclude-blocked"]}, "correction.json": template, "mutation-envelope.json": {"editable": ["correction.json"], "immutable": ["subject-position.json", "active-stake.json", "contact-receipt.json", "candidate-mechanisms.json", "primitive-vocabulary.json", "check_correction.py"]}}
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    current_json = json.dumps(current, sort_keys=True)
    existing = sorted(row["mechanism_id"] for row in candidates)
    (seed / "check_correction.py").write_text(f'''import json,re\nfrom pathlib import Path\nc=json.loads(Path("correction.json").read_text()); current=json.loads({current_json!r}); existing=set({existing!r}); legal={{("history-only","regression-only"),("operative","none"),("operative","active-authority"),("surrendered","regression-only")}}\ndef expr(x): return isinstance(x,dict) and set(x)=={{"mechanism_id","source","intersect_observed","exclude_blocked","rationale"}} and isinstance(x.get("mechanism_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",x["mechanism_id"]) and x["mechanism_id"] not in existing and x.get("source") in {{"outcome","options"}} and isinstance(x.get("intersect_observed"),bool) and isinstance(x.get("exclude_blocked"),bool) and isinstance(x.get("rationale"),str) and bool(x["rationale"].strip())\ndef proj(p,new,action):\n if action=="retain": return p==current\n if not isinstance(p,dict) or set(p)!={{"mechanisms"}} or not isinstance(p["mechanisms"],list): return False\n rows=p["mechanisms"]; ids=[r.get("mechanism_id") for r in rows if isinstance(r,dict)]\n if len(rows)!=5 or len(set(ids))!=5 or new not in ids or any(set(r)!={{"mechanism_id","status","floor_role"}} or (r["status"],r["floor_role"]) not in legal for r in rows): return False\n by={{r["mechanism_id"]:r for r in rows}}; fixed={{r["mechanism_id"]:r for r in current["mechanisms"] if r["mechanism_id"] in {{"reset-carrier","corrected-identity-gated-extension"}}}}\n return by[new]=={{"mechanism_id":new,"status":"operative","floor_role":"active-authority"}} and sum(r["floor_role"]=="active-authority" for r in rows)==1 and all(by[k]==v for k,v in fixed.items()) and all(by[k]["status"]=="operative" for k in {{"viable-branch-carrier","prediction-corrector"}})\naction=c.get("action") if isinstance(c,dict) else None; mechanism=c.get("mechanism") if isinstance(c,dict) else None\nok=isinstance(c,dict) and set(c)=={{"action","rationale","mechanism","authority_projection"}} and action in {{"retain","revise"}} and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and ((action=="retain" and mechanism is None and proj(c.get("authority_projection"),None,action)) or (action=="revise" and expr(mechanism) and proj(c.get("authority_projection"),mechanism["mechanism_id"],action)))\nprint(json.dumps({{"passed":bool(ok),"action":action}})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Use the sealed contact consequence to decide whether to retain machinery or author one executable mechanism and coherent authority projection. New mechanisms choose source outcome or options, optional intersection with observed outcome, and optional blocked exclusion. Edit only correction.json, run python3 check_correction.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_correction(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], receipt: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    seed = correction_seed(root, parent, receipt, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "correction.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    valid = bool(valid_correction(value, parent["active_mechanism_authority_projection"]["projection"], {row["mechanism_id"] for row in candidates}) and immutable_ok and output and output.get("action") == "author-contact-correction")
    audit = context.audit_actor(label, output, base_audit, valid, ["correction.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0183-bound-contact-correction", "source_subject_digest": parent["artifact_digest"], "contact_receipt_digest": receipt["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "correction": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "correction": value, "binding": binding}


def compile_branch(p82, parent: dict[str, Any], correction: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    binding = correction["binding"]
    if not binding or binding["correction"]["action"] == "retain":
        return parent, candidates
    value = binding["correction"]
    mechanism = value["mechanism"]
    candidate = {"mechanism_id": mechanism["mechanism_id"], "summary": mechanism["rationale"], "properties": ["option-expansion", "correction-from-error"], "expression": mechanism}
    projection_body = {"authority": "ot-0183-consequence-revised-authority", "source_subject_digest": parent["artifact_digest"], "correction_binding_digest": binding["binding_digest"], "projection": value["authority_projection"]}
    projection = {**projection_body, "binding_digest": p82.digest(projection_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["actor_authored_contact_mechanisms"] = [*child.get("actor_authored_contact_mechanisms", []), candidate]
    child["contact_correction_decisions"] = [*child.get("contact_correction_decisions", []), binding]
    child["active_mechanism_authority_projection"] = projection
    child.pop("active_developmental_mechanism_choice", None)
    return p82.seal(child), [*candidates, candidate]


def run_selection(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], candidates: list[dict[str, Any]], latest: Any) -> dict[str, Any]:
    return previous.run_selection(context, prior131, p82, root, label, subject, candidates, latest)


def selected_result(selection: dict[str, Any], correction: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    mechanism_id = selection["binding"]["mechanism_id"] if selection.get("binding") else None
    expression = correction["binding"]["correction"].get("mechanism") if correction.get("binding") and correction["binding"]["correction"]["action"] == "revise" and correction["binding"]["correction"]["mechanism"]["mechanism_id"] == mechanism_id else None
    return expression_result(expression, cases) if expression else built_in_result(mechanism_id, cases)


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0183").resolve()
    prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0182", "open-subject-after-raw-sufficient-assimilation.json")
    result_182 = selector_base.load_artifact(p82, repo, store, "OT-0182", "exact-stake-completion-and-delta-aggregate.json")
    candidates = selector_base.CANDIDATES
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    representative_contact = {"contact_id": "mixed-observation-boundary", "rationale": "Separate observed contact from enumerated and blocked items.", "cases": [{"case_id": f"mixed-{i}", "prediction": [f"old-{i}"], "outcome": [f"seen-{i}", f"blocked-{i}"], "options": [f"seen-{i}", f"decoy-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]} for i in range(1, 5)]}
    current_projection = parent["active_mechanism_authority_projection"]["projection"]
    representative_mechanism = {"mechanism_id": "observed-unblocked-composition", "source": "outcome", "intersect_observed": False, "exclude_blocked": True, "rationale": "Return observed outcomes after blocked exclusion."}
    representative_projection = {"mechanisms": [{"mechanism_id": "reset-carrier", "status": "history-only", "floor_role": "regression-only"}, {"mechanism_id": "viable-branch-carrier", "status": "operative", "floor_role": "none"}, {"mechanism_id": "prediction-corrector", "status": "operative", "floor_role": "none"}, {"mechanism_id": "corrected-identity-gated-extension", "status": "surrendered", "floor_role": "regression-only"}, {"mechanism_id": "observed-unblocked-composition", "status": "operative", "floor_role": "active-authority"}]}
    representative_correction = {"action": "revise", "rationale": "Compose the two contradicted routes.", "mechanism": representative_mechanism, "authority_projection": representative_projection}
    contact_checker = correction_checker = False
    with tempfile.TemporaryDirectory() as temp:
        contact_root = Path(temp) / "contact"; contact_root.mkdir()
        seed = contact_seed(contact_root, parent, result_182["completion_receipt"], candidates); authority_base.guide_base.write_json(seed / "contact.json", representative_contact); check = subprocess.run([sys.executable, "check_contact.py"], cwd=seed, capture_output=True, text=True); contact_checker = check.returncode == 0
        correction_root = Path(temp) / "correction"; correction_root.mkdir()
        seed = correction_seed(correction_root, parent, {"receipt_digest": "fixture"}, candidates); authority_base.guide_base.write_json(seed / "correction.json", representative_correction); check = subprocess.run([sys.executable, "check_correction.py"], cwd=seed, capture_output=True, text=True); correction_checker = check.returncode == 0
    normalized_confirmation = [normalize_case(case, 300 + index) for index, case in enumerate(CONFIRMATION, 1)]
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "active_stake_exact": parent["active_developmental_stake"]["stake_id"] == "preserve-observed-viable-contacts-next", "representative_contact_valid": valid_contact(representative_contact) and contact_checker, "representative_correction_valid": valid_correction(representative_correction, current_projection, {row["mechanism_id"] for row in candidates}) and correction_checker, "confirmation_only_composition_passes": expression_result(representative_mechanism, normalized_confirmation)["pass_count"] == 4 and built_in_result("viable-branch-carrier", normalized_confirmation)["pass_count"] == 0 and built_in_result("prediction-corrector", normalized_confirmation)["pass_count"] == 0, "schemas_present": CONTACT_SCHEMA.is_file() and CORRECTION_SCHEMA.is_file()}, "confirmation_digest": p82.digest(normalized_confirmation)}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0183 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    contact_root = run / "contact-authoring"; contact_root.mkdir(); contact = run_contact(context, prior131, p82, contact_root, parent, result_182["completion_receipt"], candidates)
    if not contact["binding"]:
        result = {"authority": "ot-0183-subject-bound-falsifiable-contact", "source_subject_digest": parent["artifact_digest"], "contact": p82.compact(contact), "checks": {"contact_actor_accepted": False, "passed": False}, "observer_disposition": "rejected", "subject_disposition": "open", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", parent); print(json.dumps(result, indent=2, sort_keys=True)); return 2
    public_cases = [normalize_case(case, index) for index, case in enumerate(contact["binding"]["contact"]["cases"], 1)]; hidden = hidden_cases(contact["binding"]["contact"])
    semantic = {"source": "outcome", "intersect_observed": False, "exclude_blocked": True}
    actor_receipt_body = {"authority": "ot-0183-subject-visible-contact-consequence", "contact_binding_digest": contact["binding"]["binding_digest"], "public_cases": public_cases, "hidden_cases": hidden, "public_results": {"viable": built_in_result("viable-branch-carrier", public_cases), "prediction": built_in_result("prediction-corrector", public_cases)}, "hidden_results": {"viable": built_in_result("viable-branch-carrier", hidden), "prediction": built_in_result("prediction-corrector", hidden)}}
    actor_receipt = {**actor_receipt_body, "receipt_digest": p82.digest(actor_receipt_body)}
    active_world_body = {"authority": "ot-0183-independent-subject-bound-contact", "actor_receipt_digest": actor_receipt["receipt_digest"], "public_cases_digest": p82.digest(public_cases), "hidden_cases_digest": p82.digest(hidden), "public_results": {**actor_receipt["public_results"], "semantic_composition": expression_result(semantic, public_cases)}, "hidden_results": {**actor_receipt["hidden_results"], "semantic_composition": expression_result(semantic, hidden)}}; active_world = {**active_world_body, "receipt_digest": p82.digest(active_world_body)}
    friendly = [normalize_case(case, 100 + index) for index, case in enumerate(previous.previous.WORLD_BY_PROPERTY["option-expansion"], 1)]
    control_body = {"authority": "ot-0183-property-only-friendly-contact-control", "source_subject_digest": parent["artifact_digest"], "cases_digest": p82.digest(friendly), "selected_mechanism": "viable-branch-carrier", "selected_result": built_in_result("viable-branch-carrier", friendly)}; control_world = {**control_body, "receipt_digest": p82.digest(control_body)}
    authority_base.guide_base.write_json(run / "subject-visible-contact-consequence.json", actor_receipt); authority_base.guide_base.write_json(run / "sealed-subject-bound-contact-world.json", active_world); authority_base.guide_base.write_json(run / "sealed-property-only-control-world.json", control_world)
    corrections = {}
    for regime, receipt in (("active", actor_receipt), ("control", control_world)):
        root = run / f"{regime}-correction-authoring"; root.mkdir(); corrections[regime] = run_correction(context, prior131, p82, root, f"{regime}-contact-correction", parent, receipt, candidates)
    branches = {regime: compile_branch(p82, parent, correction, candidates) for regime, correction in corrections.items()}
    selections = {}
    for regime, (subject, menu) in branches.items():
        root = run / f"{regime}-successor-authoring"; root.mkdir(); selections[regime] = run_selection(context, prior131, p82, root, f"{regime}-corrected-successor-selection", subject, menu, corrections[regime]["binding"])
    branch_results = {regime: selected_result(selections[regime], corrections[regime], normalized_confirmation) for regime in ("active", "control")}
    active_expression = corrections["active"]["binding"]["correction"].get("mechanism") if corrections["active"].get("binding") else None
    prediction_cases = [*ot0180.base0178.previous.CONFIRMATION, *ot0180.previous.CONFIRMATION]
    viable_cases = [*ot0180.HARM, *ot0180.CONFIRMATION]
    prediction_floor = expression_result(active_expression, [normalize_case(case, 400 + i) for i, case in enumerate(prediction_cases)]) if active_expression else expression_result(None, [])
    viable_floor = expression_result(active_expression, [normalize_case(case, 500 + i) for i, case in enumerate(viable_cases)]) if active_expression else expression_result(None, [])
    identity_floor = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    audits = [contact["audit"], *[corrections[key]["audit"] for key in ("active", "control")], *[selections[key]["audit"] for key in ("active", "control")]]
    active_id = selections["active"]["binding"]["mechanism_id"] if selections["active"].get("binding") else None
    active_authored_id = active_expression.get("mechanism_id") if active_expression else None
    checks = {"five_fresh_actors_accepted": len(audits) == 5 and all(prior131.audit_accepted(audit) for audit in audits), "subject_contact_public_falsifies_builtins": active_world["public_results"]["viable"]["pass_count"] < len(public_cases) and active_world["public_results"]["prediction"]["pass_count"] < len(public_cases) and active_world["public_results"]["semantic_composition"]["passed"], "subject_contact_hidden_falsifies_builtins": active_world["hidden_results"]["viable"]["pass_count"] < len(hidden) and active_world["hidden_results"]["prediction"]["pass_count"] < len(hidden) and active_world["hidden_results"]["semantic_composition"]["passed"], "active_authors_revision": bool(active_expression and corrections["active"]["binding"]["correction"]["action"] == "revise"), "active_selects_authored_mechanism": active_id == active_authored_id, "active_confirmation_4_of_4": branch_results["active"]["pass_count"] == 4, "control_confirmation_at_most_1_of_4": branch_results["control"]["pass_count"] <= 1, "prediction_floor_complete": prediction_floor["passed"], "viable_floor_complete": viable_floor["passed"], "identity_floor_18_of_18": identity_floor["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        child = copy.deepcopy(branches["active"][0]); child.pop("artifact_digest", None); child["subject_bound_contact_receipts"] = [*child.get("subject_bound_contact_receipts", []), {"contact_binding": contact["binding"], "world_receipt": active_world}]; child["active_developmental_mechanism_choice"] = selections["active"]["binding"]; capability_body = {"authority": "ot-0183-falsification-driven-machinery-composition", "source_subject_digest": parent["artifact_digest"], "contact_binding_digest": contact["binding"]["binding_digest"], "correction_binding_digest": corrections["active"]["binding"]["binding_digest"], "selection_binding_digest": selections["active"]["binding"]["binding_digest"], "confirmation_digest": p82.digest(normalized_confirmation)}; child["falsification_driven_machinery_capabilities"] = [*child.get("falsification_driven_machinery_capabilities", []), {**capability_body, "capability_digest": p82.digest(capability_body)}]; final = p82.seal(child)
    result = {"authority": "ot-0183-subject-bound-falsifiable-contact", "source_subject_digest": parent["artifact_digest"], "contact": p82.compact(contact), "active_contact_world": active_world, "property_only_control_world": control_world, "corrections": {key: p82.compact(value) for key, value in corrections.items()}, "selections": {key: p82.compact(value) for key, value in selections.items()}, "confirmation_results": branch_results, "prior_floor_results": {"prediction": prediction_floor, "viable": viable_floor, "identity": identity_floor}, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 5}; result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
