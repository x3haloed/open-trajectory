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
BASE_PATH = ROOT / "ot_0183_subject_bound_falsifiable_contact.py"
BASE_SHA256 = "7e1822f50cf7f90289a972fd39259a2e90f861707c35180334821116eb981dbe"
PARENT_DIGEST = "40818aa8c898da506378ab82ddebe6682c5edc8b524f5e1bb2025bb391cf2747"
REPAIR_SCHEMA = REPO / "spec/ot-0184-selector-repair.schema.json"
CAPABILITIES = {"observed-source", "blocked-exclusion"}
CONTEXTS = {"correction-from-error", "option-expansion"}

MIXED = [
    {"case_id": f"scoped-mixed-{i}", "prediction": [f"old-{i}"], "outcome": [f"heard-{i}", f"blocked-{i}"], "options": [f"heard-{i}", f"decoy-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]}
    for i in range(1, 7)
]

CORRECTION_STAKE = {"stake_id": "prior-observation-led-correction", "property": "correction-from-error", "question": "Can the stale prediction be replaced by the observed outcome?", "rationale": "This retained context requires observation grounding without option filtering.", "success_condition": "Returned values equal observed outcomes.", "surrender_condition": "Surrender if observed outcomes are not returned exactly."}
OPTION_STAKE = {"stake_id": "prior-blocked-option-filtering", "property": "option-expansion", "question": "Can every unblocked option be returned without blocked options?", "rationale": "This retained context requires option filtering without observation membership.", "success_condition": "Returned values contain all and only unblocked options.", "surrender_condition": "Surrender if an unblocked option is omitted or a blocked option survives."}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0183 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0184_frozen_ot0183", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def valid_projection(value: Any, mechanism_ids: set[str], active_stake_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"capability_vocabulary", "mechanism_capabilities", "active_stake", "context_requirements", "selection_rule"}:
        return False
    if value.get("capability_vocabulary") != sorted(CAPABILITIES):
        return False
    declarations = value.get("mechanism_capabilities")
    if not isinstance(declarations, list) or len(declarations) != len(mechanism_ids) or {row.get("mechanism_id") for row in declarations if isinstance(row, dict)} != mechanism_ids:
        return False
    if any(set(row) != {"mechanism_id", "capabilities"} or not isinstance(row["capabilities"], list) or len(row["capabilities"]) != len(set(row["capabilities"])) or not set(row["capabilities"]) <= CAPABILITIES for row in declarations):
        return False
    active = value.get("active_stake")
    if not isinstance(active, dict) or set(active) != {"stake_id", "requirements"} or active.get("stake_id") != active_stake_id or not isinstance(active.get("requirements"), list) or not active["requirements"] or not set(active["requirements"]) <= CAPABILITIES or len(active["requirements"]) != len(set(active["requirements"])):
        return False
    contexts = value.get("context_requirements")
    if not isinstance(contexts, list) or {row.get("property") for row in contexts if isinstance(row, dict)} != CONTEXTS or any(set(row) != {"property", "requirements"} or not isinstance(row["requirements"], list) or not row["requirements"] or not set(row["requirements"]) <= CAPABILITIES or len(row["requirements"]) != len(set(row["requirements"])) for row in contexts):
        return False
    return value.get("selection_rule") in {"exact-match-then-active-authority-then-id", "minimal-superset-then-active-authority-then-id"}


def valid_repair(value: Any, mechanism_ids: set[str], active_stake_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "rationale", "selector_projection"} or value.get("action") not in {"retain", "revise"} or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    return value.get("selector_projection") is None if value["action"] == "retain" else valid_projection(value.get("selector_projection"), mechanism_ids, active_stake_id)


def repair_seed(root: Path, parent: dict[str, Any], failure: dict[str, Any], candidates: list[dict[str, Any]], authority: dict[str, Any]) -> Path:
    seed = root / "repair-seed"; seed.mkdir()
    template = {"action": "retain", "rationale": "Replace after evaluating the exact selection failure.", "selector_projection": None}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "active-stake.json": parent["active_developmental_stake"], "ot-0183-failure.json": failure, "candidate-mechanisms.json": candidates, "mechanism-authority.json": authority, "selector-guide.md": parent["active_developmental_mechanism_selector"]["guide_text"], "capability-vocabulary.json": sorted(CAPABILITIES), "selector-repair.json": template, "mutation-envelope.json": {"editable": ["selector-repair.json"], "immutable": ["subject-position.json", "active-stake.json", "ot-0183-failure.json", "candidate-mechanisms.json", "mechanism-authority.json", "selector-guide.md", "capability-vocabulary.json", "check_repair.py"]}}
    for name, data in files.items():
        if name.endswith(".md"): (seed / name).write_text(data)
        else: authority_base.guide_base.write_json(seed / name, data)
    ids = sorted(row["mechanism_id"] for row in candidates); stake_id = parent["active_developmental_stake"]["stake_id"]
    (seed / "check_repair.py").write_text(f'''import json\nfrom pathlib import Path\nr=json.loads(Path("selector-repair.json").read_text()); ids=set({ids!r}); caps={{"observed-source","blocked-exclusion"}}; contexts={{"correction-from-error","option-expansion"}}; stake={stake_id!r}\ndef projection(v):\n if not isinstance(v,dict) or set(v)!={{"capability_vocabulary","mechanism_capabilities","active_stake","context_requirements","selection_rule"}} or v.get("capability_vocabulary")!=sorted(caps): return False\n ds=v.get("mechanism_capabilities"); active=v.get("active_stake"); cs=v.get("context_requirements")\n return isinstance(ds,list) and len(ds)==len(ids) and {{x.get("mechanism_id") for x in ds if isinstance(x,dict)}}==ids and all(set(x)=={{"mechanism_id","capabilities"}} and isinstance(x["capabilities"],list) and len(x["capabilities"])==len(set(x["capabilities"])) and set(x["capabilities"])<=caps for x in ds) and isinstance(active,dict) and set(active)=={{"stake_id","requirements"}} and active.get("stake_id")==stake and isinstance(active.get("requirements"),list) and bool(active["requirements"]) and len(active["requirements"])==len(set(active["requirements"])) and set(active["requirements"])<=caps and isinstance(cs,list) and {{x.get("property") for x in cs if isinstance(x,dict)}}==contexts and all(set(x)=={{"property","requirements"}} and isinstance(x["requirements"],list) and bool(x["requirements"]) and len(x["requirements"])==len(set(x["requirements"])) and set(x["requirements"])<=caps for x in cs) and v.get("selection_rule") in {{"exact-match-then-active-authority-then-id","minimal-superset-then-active-authority-then-id"}}\naction=r.get("action") if isinstance(r,dict) else None; ok=isinstance(r,dict) and set(r)=={{"action","rationale","selector_projection"}} and action in {{"retain","revise"}} and isinstance(r.get("rationale"),str) and bool(r["rationale"].strip()) and ((action=="retain" and r.get("selector_projection") is None) or (action=="revise" and projection(r.get("selector_projection"))))\nprint(json.dumps({{"passed":bool(ok),"action":action}})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Repair the selection failure or retain the selector. A revision must declare capabilities for every mechanism, requirements for the exact active stake and both retained context properties, and one deterministic rule from the visible vocabulary. Hidden future worlds are unavailable. Edit only selector-repair.json, run python3 check_repair.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_repair(context, prior131, p82, root: Path, parent: dict[str, Any], failure: dict[str, Any], candidates: list[dict[str, Any]], authority: dict[str, Any]) -> dict[str, Any]:
    label = "capability-scoped-selector-repair"; seed = repair_seed(root, parent, failure, candidates, authority)
    output, base_audit, workspace, _ = context.run_actor(label, seed, REPAIR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "selector-repair.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): value, immutable_ok = None, False
    valid = bool(valid_repair(value, {row["mechanism_id"] for row in candidates}, parent["active_developmental_stake"]["stake_id"]) and immutable_ok and output and output.get("action") == "author-selector-repair")
    audit = context.audit_actor(label, output, base_audit, valid, ["selector-repair.json"]); binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0184-bound-selector-repair", "source_subject_digest": parent["artifact_digest"], "failure_receipt_digest": failure["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "repair": value}; binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "repair": value, "binding": binding}


def erased_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {"capability_vocabulary": value["capability_vocabulary"], "mechanism_capabilities": [{"mechanism_id": row["mechanism_id"], "capabilities": []} for row in value["mechanism_capabilities"]], "active_stake": {"stake_id": value["active_stake"]["stake_id"], "requirements": []}, "context_requirements": [{"property": row["property"], "requirements": []} for row in value["context_requirements"]], "selection_rule": None}


def selector_seed(root: Path, subject: dict[str, Any], candidates: list[dict[str, Any]], failure: dict[str, Any], projection: dict[str, Any], stake: dict[str, Any]) -> Path:
    seed = root / "selection-seed"; seed.mkdir()
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(subject), "active-stake.json": stake, "candidate-mechanisms.json": candidates, "mechanism-authority.json": subject["active_mechanism_authority_projection"]["projection"], "authority-semantics.json": authority_base.AUTHORITY_SEMANTICS, "selection-guide.md": subject["active_developmental_mechanism_selector"]["guide_text"], "latest-consequence.json": failure, "capability-selector.json": projection, "choice.json": {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"}, "mutation-envelope.json": {"editable": ["choice.json"], "immutable": ["subject-position.json", "active-stake.json", "candidate-mechanisms.json", "mechanism-authority.json", "authority-semantics.json", "selection-guide.md", "latest-consequence.json", "capability-selector.json"]}}
    for name, data in files.items():
        if name.endswith(".md"): (seed / name).write_text(data)
        else: authority_base.guide_base.write_json(seed / name, data)
    (seed / "README.md").write_text("Choose the mechanism that best satisfies the sole active stake. Use the inherited guide, authority, latest consequence, and capability selector together. A populated capability selector is consequence-bound selection machinery; an erased one carries no capability authority. Edit only choice.json with mechanism_id and rationale, then report the same id truthfully.\n")
    return seed


def run_selector(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], candidates: list[dict[str, Any]], failure: dict[str, Any], projection: dict[str, Any], stake: dict[str, Any]) -> dict[str, Any]:
    seed = selector_seed(root, subject, candidates, failure, projection, stake)
    output, base_audit, workspace, _ = context.run_actor(label, seed, authority_base.guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        choice = json.loads((workspace / "choice.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): choice, immutable_ok = None, False
    ids = {row["mechanism_id"] for row in candidates}; valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
    audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"]); binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0184-bound-capability-selection", "source_subject_digest": subject["artifact_digest"], "active_stake_digest": p82.digest(stake), "selector_projection_digest": p82.digest(projection), "latest_consequence_digest": p82.digest(failure), "actor_patch_digest": audit["patch_digest"], "mechanism_id": choice["mechanism_id"]}; binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "choice": choice, "binding": binding}


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0184").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0182", "open-subject-after-raw-sufficient-assimilation.json"); failure = selector_base.load_artifact(p82, repo, store, "OT-0183", "subject-bound-falsifiable-contact-aggregate.json")
    base_candidates = selector_base.CANDIDATES; correction = failure["corrections"]["active"]; candidate_subject, candidates = previous.compile_branch(p82, parent, correction, base_candidates); new_id = correction["binding"]["correction"]["mechanism"]["mechanism_id"]; expression = correction["binding"]["correction"]["mechanism"]
    representative = {"action": "revise", "rationale": "Match exact semantic requirements rather than a coarse property label.", "selector_projection": {"capability_vocabulary": sorted(CAPABILITIES), "mechanism_capabilities": [{"mechanism_id": row["mechanism_id"], "capabilities": (["blocked-exclusion"] if row["mechanism_id"] == "viable-branch-carrier" else ["observed-source"] if row["mechanism_id"] == "prediction-corrector" else sorted(CAPABILITIES) if row["mechanism_id"] == new_id else [])} for row in candidates], "active_stake": {"stake_id": parent["active_developmental_stake"]["stake_id"], "requirements": sorted(CAPABILITIES)}, "context_requirements": [{"property": "correction-from-error", "requirements": ["observed-source"]}, {"property": "option-expansion", "requirements": ["blocked-exclusion"]}], "selection_rule": "exact-match-then-active-authority-then-id"}}
    checker = False
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "repair"; root.mkdir(); seed = repair_seed(root, parent, failure, candidates, candidate_subject["active_mechanism_authority_projection"]["projection"]); authority_base.guide_base.write_json(seed / "selector-repair.json", representative); check = subprocess.run([sys.executable, "check_repair.py"], cwd=seed, capture_output=True, text=True); checker = check.returncode == 0
    normalized_mixed = [previous.normalize_case(case, 600 + i) for i, case in enumerate(MIXED)]
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0183_rejected_exact": failure["observer_disposition"] == "rejected" and failure["final_subject_digest"] == PARENT_DIGEST, "novel_mechanism_exact": previous.expression_result(expression, [previous.normalize_case(case, 700 + i) for i, case in enumerate(previous.CONFIRMATION)])["pass_count"] == 4, "mixed_only_novel_passes": previous.expression_result(expression, normalized_mixed)["pass_count"] == 6 and previous.built_in_result("viable-branch-carrier", normalized_mixed)["pass_count"] == 0 and previous.built_in_result("prediction-corrector", normalized_mixed)["pass_count"] == 0, "representative_repair_valid": valid_repair(representative, {row["mechanism_id"] for row in candidates}, parent["active_developmental_stake"]["stake_id"]) and checker, "schema_present": REPAIR_SCHEMA.is_file()}, "mixed_digest": p82.digest(normalized_mixed)}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0184 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); repair_root = run / "repair-authoring"; repair_root.mkdir(); repair = run_repair(context, prior131, p82, repair_root, parent, failure, candidates, candidate_subject["active_mechanism_authority_projection"]["projection"])
    projection = repair["binding"]["repair"]["selector_projection"] if repair.get("binding") and repair["binding"]["repair"]["action"] == "revise" else None
    if projection is None:
        result = {"authority": "ot-0184-capability-scoped-selector-repair", "source_subject_digest": parent["artifact_digest"], "repair": p82.compact(repair), "checks": {"repair_authored": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", parent); print(json.dumps(result, indent=2, sort_keys=True)); return 2
    erased = erased_projection(projection); rows = []
    schedule = ["control", "active", "active", "control", "control", "active", "active", "control", "control", "active", "active", "control"]
    counts = {"active": 0, "control": 0}
    for regime in schedule:
        counts[regime] += 1; index = counts[regime]; root = run / f"{regime}-{index:02d}-authoring"; root.mkdir(); selected_projection = projection if regime == "active" else erased; choice = run_selector(context, prior131, p82, root, f"{regime}-selector-{index:02d}", candidate_subject, candidates, failure, selected_projection, parent["active_developmental_stake"]); mechanism = choice["binding"]["mechanism_id"] if choice.get("binding") else None; contact = previous.expression_result(expression, normalized_mixed) if mechanism == new_id else previous.built_in_result(mechanism, normalized_mixed); rows.append({"regime": regime, "index": index, "choice": choice, "mechanism_id": mechanism, "contact": contact})
    active_pass = sum(row["mechanism_id"] == new_id and row["contact"]["passed"] for row in rows if row["regime"] == "active"); control_pass = sum(row["mechanism_id"] == new_id and row["contact"]["passed"] for row in rows if row["regime"] == "control")
    prior_rows = []
    for context_name, stake, expected, cases in (("prediction", CORRECTION_STAKE, "prediction-corrector", previous.ot0180.previous.CONFIRMATION), ("viable", OPTION_STAKE, "viable-branch-carrier", previous.ot0180.CONFIRMATION)):
        for index in range(1, 3):
            root = run / f"prior-{context_name}-{index:02d}-authoring"; root.mkdir(); choice = run_selector(context, prior131, p82, root, f"prior-{context_name}-{index:02d}", candidate_subject, candidates, failure, projection, stake); mechanism = choice["binding"]["mechanism_id"] if choice.get("binding") else None; normalized = [previous.normalize_case(case, 800 + index * 20 + i) for i, case in enumerate(cases)]; contact = previous.built_in_result(mechanism, normalized); prior_rows.append({"context": context_name, "index": index, "choice": choice, "mechanism_id": mechanism, "expected_mechanism": expected, "contact": contact})
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor()); audits = [repair["audit"], *[row["choice"]["audit"] for row in rows], *[row["choice"]["audit"] for row in prior_rows]]
    checks = {"seventeen_fresh_actors_accepted": len(audits) == 17 and all(prior131.audit_accepted(audit) for audit in audits), "nontrivial_repair": repair["binding"]["repair"]["action"] == "revise", "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "prior_contexts_4_of_4": len(prior_rows) == 4 and all(row["mechanism_id"] == row["expected_mechanism"] and row["contact"]["passed"] for row in prior_rows), "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        child = copy.deepcopy(candidate_subject); child.pop("artifact_digest", None); selector_body = {"authority": "ot-0184-capability-scoped-selector", "source_subject_digest": parent["artifact_digest"], "repair_binding_digest": repair["binding"]["binding_digest"], "projection": projection}; selector_artifact = {**selector_body, "binding_digest": p82.digest(selector_body)}; child["capability_scoped_selector_projections"] = [*child.get("capability_scoped_selector_projections", []), selector_artifact]; child["active_capability_scoped_selector_projection"] = selector_artifact; child["active_developmental_mechanism_selector"] = {**child["active_developmental_mechanism_selector"], "selector_kind": "capability-scoped-semantic-selector", "capability_projection_binding_digest": selector_artifact["binding_digest"]}; child["active_developmental_mechanism_selector"].pop("binding_digest", None); child["active_developmental_mechanism_selector"]["binding_digest"] = p82.digest(child["active_developmental_mechanism_selector"]); child["selector_repair_decisions"] = [*child.get("selector_repair_decisions", []), repair["binding"]]; child["active_developmental_mechanism_choice"] = next(row["choice"]["binding"] for row in rows if row["regime"] == "active"); final = p82.seal(child)
    result = {"authority": "ot-0184-capability-scoped-selector-repair", "source_subject_digest": parent["artifact_digest"], "repair": p82.compact(repair), "candidate_subject_digest": candidate_subject["artifact_digest"], "matched_rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "prior_context_rows": [{**row, "choice": p82.compact(row["choice"])} for row in prior_rows], "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 17}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
