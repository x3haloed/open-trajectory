from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0184_capability_scoped_selector_repair.py"
BASE_SHA256 = "f280505aa25804f9670732add5e3e4e602b864ad51463fc28d53c7c7d39982d8"
PARENT_DIGEST = "40818aa8c898da506378ab82ddebe6682c5edc8b524f5e1bb2025bb391cf2747"
REPAIR_SCHEMA = REPO / "spec/ot-0185-routing-repair.schema.json"
REGIMES = {"observation-led", "blocked-option", "mixed-observed-blocked"}

OBSERVATION = [{"case_id": f"observation-probe-{i}", "prediction": [f"old-{i}"], "outcome": [f"seen-{i}"], "options": [f"decoy-{i}"], "blocked": []} for i in range(1, 5)]
BLOCKED = [{"case_id": f"blocked-probe-{i}", "prediction": [f"old-{i}"], "outcome": [f"allowed-{i}", f"blocked-{i}"], "options": [f"allowed-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]} for i in range(1, 5)]
MIXED = [{"case_id": f"mixed-probe-{i}", "prediction": [f"old-{i}"], "outcome": [f"seen-{i}", f"blocked-{i}"], "options": [f"seen-{i}", f"decoy-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"]} for i in range(1, 7)]

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256: raise RuntimeError("OT-0184 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0185_frozen_ot0184", BASE_PATH); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module

previous = load_base(); ot0183 = previous.previous; authority_base = previous.authority_base

def normalized(cases, start): return [ot0183.normalize_case(case, start + i) for i, case in enumerate(cases)]

def result_for(mechanism_id, expression, cases):
    return ot0183.expression_result(expression, cases) if mechanism_id == expression["mechanism_id"] else ot0183.built_in_result(mechanism_id, cases)

def signature_matrix(p82, candidates, expression):
    regimes = {"observation-led": normalized(OBSERVATION, 100), "blocked-option": normalized(BLOCKED, 200), "mixed-observed-blocked": normalized(MIXED, 300)}
    rows = []
    for candidate in candidates:
        for regime, cases in regimes.items():
            result = result_for(candidate["mechanism_id"], expression, cases); body = {"mechanism_id": candidate["mechanism_id"], "regime": regime, "pass_count": result["pass_count"], "case_count": result["case_count"], "passed": result["passed"]}; rows.append({**body, "receipt_digest": p82.digest(body)})
    body = {"authority": "ot-0185-consequence-certified-routing-signatures", "regime_case_digests": {key: p82.digest(value) for key, value in regimes.items()}, "rows": rows}; return {**body, "matrix_digest": p82.digest(body)}, regimes

def valid_repair(value: Any, ids: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "rationale", "routes"} or value.get("action") not in {"retain", "revise"} or not isinstance(value.get("rationale"), str) or not value["rationale"].strip(): return False
    if value["action"] == "retain": return value.get("routes") is None
    routes = value.get("routes"); return bool(isinstance(routes, list) and len(routes) == 3 and {row.get("regime") for row in routes if isinstance(row, dict)} == REGIMES and all(set(row) == {"regime", "mechanism_id", "rationale"} and row["mechanism_id"] in ids and isinstance(row["rationale"], str) and row["rationale"].strip() for row in routes))

def repair_seed(root, parent, failures, matrix, candidates, authority):
    seed = root / "repair-seed"; seed.mkdir(); template = {"action": "retain", "rationale": "Replace after evaluating certified signatures.", "routes": None}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "active-stake.json": parent["active_developmental_stake"], "prior-failures.json": failures, "certified-signature-matrix.json": matrix, "candidate-mechanisms.json": candidates, "mechanism-authority.json": authority, "routing-repair.json": template, "mutation-envelope.json": {"editable": ["routing-repair.json"], "immutable": ["subject-position.json", "active-stake.json", "prior-failures.json", "certified-signature-matrix.json", "candidate-mechanisms.json", "mechanism-authority.json", "check_repair.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    ids = sorted(row["mechanism_id"] for row in candidates)
    (seed / "check_repair.py").write_text(f'''import json\nfrom pathlib import Path\nr=json.loads(Path("routing-repair.json").read_text()); ids=set({ids!r}); regimes={{"observation-led","blocked-option","mixed-observed-blocked"}}; action=r.get("action") if isinstance(r,dict) else None; routes=r.get("routes") if isinstance(r,dict) else None; valid_routes=isinstance(routes,list) and len(routes)==3 and {{x.get("regime") for x in routes if isinstance(x,dict)}}==regimes and all(set(x)=={{"regime","mechanism_id","rationale"}} and x["mechanism_id"] in ids and isinstance(x["rationale"],str) and bool(x["rationale"].strip()) for x in routes); ok=isinstance(r,dict) and set(r)=={{"action","rationale","routes"}} and action in {{"retain","revise"}} and isinstance(r.get("rationale"),str) and bool(r["rationale"].strip()) and ((action=="retain" and routes is None) or (action=="revise" and valid_routes)); print(json.dumps({{"passed":bool(ok),"action":action}})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Use certified behavioral signatures and retained floor ownership to retain or author one complete routing table. Scores are world-owned evidence; prior actor declarations are hypotheses. Edit only routing-repair.json, run python3 check_repair.py, inspect the diff, and report truthfully.\n"); return seed

def run_repair(context, prior131, p82, root, parent, failures, matrix, candidates, authority):
    label = "consequence-certified-routing-repair"; seed = repair_seed(root, parent, failures, matrix, candidates, authority); output, base_audit, workspace, _ = context.run_actor(label, seed, REPAIR_SCHEMA, (seed / "README.md").read_text().strip())
    try: value = json.loads((workspace / "routing-repair.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): value, immutable_ok = None, False
    valid = bool(valid_repair(value, {row["mechanism_id"] for row in candidates}) and immutable_ok and output and output.get("action") == "author-certified-routing-repair"); audit = context.audit_actor(label, output, base_audit, valid, ["routing-repair.json"]); binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0185-bound-certified-routing-repair", "source_subject_digest": parent["artifact_digest"], "matrix_digest": matrix["matrix_digest"], "actor_patch_digest": audit["patch_digest"], "repair": value}; binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "repair": value, "binding": binding}

def erased_routes(routes): return [{"regime": row["regime"], "mechanism_id": None, "rationale": None} for row in routes]

def selection_seed(root, subject, candidates, failure, matrix, routes, regime, stake):
    seed = root / "selection-seed"; seed.mkdir(); files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(subject), "active-stake.json": stake, "candidate-mechanisms.json": candidates, "mechanism-authority.json": subject["active_mechanism_authority_projection"]["projection"], "selection-guide.md": subject["active_developmental_mechanism_selector"]["guide_text"], "prior-failure.json": failure, "certified-signature-matrix.json": matrix, "active-regime.json": {"regime": regime}, "certified-routes.json": routes, "choice.json": {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"}, "mutation-envelope.json": {"editable": ["choice.json"], "immutable": ["subject-position.json", "active-stake.json", "candidate-mechanisms.json", "mechanism-authority.json", "selection-guide.md", "prior-failure.json", "certified-signature-matrix.json", "active-regime.json", "certified-routes.json"]}}
    for name, data in files.items():
        if name.endswith(".md"): (seed / name).write_text(data)
        else: authority_base.guide_base.write_json(seed / name, data)
    (seed / "README.md").write_text("Choose the mechanism for the active regime and sole stake. A populated certified route is consequence-bound selector state; null route values carry no authority, so use remaining inherited evidence. Edit only choice.json with mechanism_id and rationale, then report the same id.\n"); return seed

def run_selector(context, prior131, p82, root, label, subject, candidates, failure, matrix, routes, regime, stake):
    seed = selection_seed(root, subject, candidates, failure, matrix, routes, regime, stake); output, base_audit, workspace, _ = context.run_actor(label, seed, authority_base.guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
    try: choice = json.loads((workspace / "choice.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): choice, immutable_ok = None, False
    ids = {row["mechanism_id"] for row in candidates}; valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"]); audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"]); binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0185-bound-certified-route-selection", "source_subject_digest": subject["artifact_digest"], "regime": regime, "routes_digest": p82.digest(routes), "actor_patch_digest": audit["patch_digest"], "mechanism_id": choice["mechanism_id"]}; binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "choice": choice, "binding": binding}

def main():
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130; parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args(); repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0185").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0182", "open-subject-after-raw-sufficient-assimilation.json"); f183 = selector_base.load_artifact(p82, repo, store, "OT-0183", "subject-bound-falsifiable-contact-aggregate.json"); f184 = selector_base.load_artifact(p82, repo, store, "OT-0184", "capability-scoped-selector-repair-aggregate.json"); candidates0 = selector_base.CANDIDATES; correction = f183["corrections"]["active"]; subject, candidates = ot0183.compile_branch(p82, parent, correction, candidates0); expression = correction["binding"]["correction"]["mechanism"]; new_id = expression["mechanism_id"]; matrix, regimes = signature_matrix(p82, candidates, expression)
    expected = {(row["mechanism_id"], row["regime"]): row["passed"] for row in matrix["rows"]}; representative = {"action": "revise", "rationale": "Route by certified behavioral regimes and retained floors.", "routes": [{"regime": "observation-led", "mechanism_id": "prediction-corrector", "rationale": "Only this route earns observation-led."}, {"regime": "blocked-option", "mechanism_id": "viable-branch-carrier", "rationale": "Retain the established floor owner among passing routes."}, {"regime": "mixed-observed-blocked", "mechanism_id": new_id, "rationale": "Only the composition earns mixed contact."}]}
    checker = False
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "repair"; root.mkdir(); seed = repair_seed(root, parent, {"ot0183": f183, "ot0184": f184}, matrix, candidates, subject["active_mechanism_authority_projection"]["projection"]); authority_base.guide_base.write_json(seed / "routing-repair.json", representative); checker = subprocess.run([sys.executable, "check_repair.py"], cwd=seed).returncode == 0
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "failures_exact": f183["observer_disposition"] == f184["observer_disposition"] == "rejected", "signature_prediction": expected[("prediction-corrector", "observation-led")] and not expected[("prediction-corrector", "blocked-option")] and not expected[("prediction-corrector", "mixed-observed-blocked")], "signature_viable": not expected[("viable-branch-carrier", "observation-led")] and expected[("viable-branch-carrier", "blocked-option")] and not expected[("viable-branch-carrier", "mixed-observed-blocked")], "signature_novel": not expected[(new_id, "observation-led")] and expected[(new_id, "blocked-option")] and expected[(new_id, "mixed-observed-blocked")], "representative_valid": valid_repair(representative, {row["mechanism_id"] for row in candidates}) and checker, "schema_present": REPAIR_SCHEMA.is_file()}, "matrix_digest": matrix["matrix_digest"]}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0185 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures); authority_base.guide_base.write_json(run / "certified-signature-matrix.json", matrix)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); root = run / "repair-authoring"; root.mkdir(); repair = run_repair(context, prior131, p82, root, parent, {"ot0183": f183, "ot0184": f184}, matrix, candidates, subject["active_mechanism_authority_projection"]["projection"])
    routes = repair["binding"]["repair"]["routes"] if repair.get("binding") and repair["binding"]["repair"]["action"] == "revise" else None
    if routes is None:
        result = {"authority": "ot-0185-consequence-certified-routing-signatures", "repair": p82.compact(repair), "checks": {"repair_authored": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", parent); print(json.dumps(result, indent=2, sort_keys=True)); return 2
    erased = erased_routes(routes); rows = []; counts = {"active": 0, "control": 0}; schedule = ["control", "active", "active", "control", "control", "active", "active", "control", "control", "active", "active", "control"]
    for regime in schedule:
        counts[regime] += 1; i = counts[regime]; root = run / f"{regime}-{i:02d}-authoring"; root.mkdir(); route = routes if regime == "active" else erased; choice = run_selector(context, prior131, p82, root, f"{regime}-{i:02d}", subject, candidates, f184, matrix, route, "mixed-observed-blocked", parent["active_developmental_stake"]); mid = choice["binding"]["mechanism_id"] if choice.get("binding") else None; contact = result_for(mid, expression, regimes["mixed-observed-blocked"]); rows.append({"regime": regime, "index": i, "choice": choice, "mechanism_id": mid, "contact": contact})
    active_pass = sum(row["mechanism_id"] == new_id and row["contact"]["passed"] for row in rows if row["regime"] == "active"); control_pass = sum(row["mechanism_id"] == new_id and row["contact"]["passed"] for row in rows if row["regime"] == "control"); prior_rows = []
    for regime, stake, expected_id in (("observation-led", previous.CORRECTION_STAKE, "prediction-corrector"), ("blocked-option", previous.OPTION_STAKE, "viable-branch-carrier")):
        for i in range(1, 3):
            root = run / f"prior-{regime}-{i}-authoring"; root.mkdir(); choice = run_selector(context, prior131, p82, root, f"prior-{regime}-{i}", subject, candidates, f184, matrix, routes, regime, stake); mid = choice["binding"]["mechanism_id"] if choice.get("binding") else None; contact = result_for(mid, expression, regimes[regime]); prior_rows.append({"regime": regime, "index": i, "choice": choice, "mechanism_id": mid, "expected_mechanism": expected_id, "contact": contact})
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor()); audits = [repair["audit"], *[row["choice"]["audit"] for row in rows], *[row["choice"]["audit"] for row in prior_rows]]; checks = {"seventeen_fresh_actors_accepted": len(audits) == 17 and all(prior131.audit_accepted(audit) for audit in audits), "nontrivial_repair": repair["binding"]["repair"]["action"] == "revise", "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "prior_regimes_4_of_4": all(row["mechanism_id"] == row["expected_mechanism"] and row["contact"]["passed"] for row in prior_rows), "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); final = parent
    if checks["passed"]:
        child = copy.deepcopy(subject); child.pop("artifact_digest", None); artifact_body = {"authority": "ot-0185-certified-routing-selector", "source_subject_digest": parent["artifact_digest"], "repair_binding_digest": repair["binding"]["binding_digest"], "signature_matrix_digest": matrix["matrix_digest"], "routes": routes}; artifact = {**artifact_body, "binding_digest": p82.digest(artifact_body)}; child["certified_routing_selectors"] = [*child.get("certified_routing_selectors", []), artifact]; child["active_certified_routing_selector"] = artifact; child["certified_routing_repairs"] = [*child.get("certified_routing_repairs", []), repair["binding"]]; child["active_developmental_mechanism_choice"] = next(row["choice"]["binding"] for row in rows if row["regime"] == "active"); final = p82.seal(child)
    result = {"authority": "ot-0185-consequence-certified-routing-signatures", "source_subject_digest": parent["artifact_digest"], "signature_matrix": matrix, "repair": p82.compact(repair), "matched_rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "prior_rows": [{**row, "choice": p82.compact(row["choice"])} for row in prior_rows], "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 17}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2

if __name__ == "__main__": raise SystemExit(main())
