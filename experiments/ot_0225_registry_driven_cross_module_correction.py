from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0224_target_unspecified_semantic_widening.py"
BASE_SHA256 = "10e6247c6219f4e359526cdf021d922bd5f22888c2d603fd06787c205ba54581"
PARENT_DIGEST = "ade85ab1e63d53913f18cca47e9d3a0892133687974e05be2691e3b8ef2d8d52"
OT224_RECEIPT = "ff01c4050caa99727ae6b7f977c2675daed78791043b2aba75d1b9264ab86997"
AUTHORITY = "ot-0225-registry-driven-cross-module-correction"
CORRECTOR_SCHEMA = REPO / "spec/ot-0218-corrector.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0224 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0225_frozen_ot0224", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base224 = load_base()
base223 = base224.base223
base220 = base224.base220
base218 = base220.base218
base217 = base224.base217
base215 = base218.base215
base213 = base224.base213
authority_base = base224.authority_base


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def write_environment(root: Path, subject: dict[str, Any]) -> None:
    base224.write_environment(root, subject)
    for relative, source in subject.get("registry_installed_sources", {}).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def selected(subject: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    pending = subject["pending_contact_bearing_continuations"][-1]
    target = pending["package"]["target_symbol"]
    interface = subject["expanded_semantic_environment"]["registry"][target]
    world = subject["semantic_widening_world_receipts"][-1]
    return pending, world, target, interface


def source_functions(source: str) -> tuple[list[str], dict[str, str]]:
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
    return [node.name for node in nodes], {node.name: ast.unparse(node) for node in nodes}


def target_only_change(after: str, before: str, target: str) -> bool:
    before_order, before_functions = source_functions(before)
    after_order, after_functions = source_functions(after)
    return before_order == after_order and after_functions.get(target) != before_functions.get(target) and all(after_functions[name] == before_functions[name] for name in before_order if name != target)


def corrected_fixture_source(source: str, target: str) -> str:
    order, functions = source_functions(source)
    collection, magnitude, duration, probability = base224.FIELDS[target]
    functions[target] = f'''def {target}(case):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(case["{collection}"])):
        selected = [item for item, take in zip(case["{collection}"], mask) if take]
        if sum(item["effort"] for item in selected) > case["capacity"]:
            continue
        score = sum(item["{magnitude}"] * item["{duration}"] * item["{probability}"] for item in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])'''
    return "\n\n\n".join(functions[name] for name in order) + "\n"


def followup_cases(target: str) -> list[dict[str, Any]]:
    collection = base224.FIELDS[target][0]
    rows = [
        (3, [(11, 1, .2, 3), (7, 8, .9, 3)]),
        (4, [(12, 1, .2, 4), (8, 7, .8, 2), (7, 6, .9, 2)]),
        (5, [(12, 1, .2, 5), (9, 6, .8, 3), (8, 5, .9, 2)]),
        (2, [(9, 8, .8, 2), (11, 1, .2, 2)]),
        (4, [(10, 5, .9, 2), (6, 2, .5, 2)]),
        (4, [(9, 4, .8, 2), (8, 3, .7, 2)]),
    ]
    return [{"case_id": f"followup-{index}", "input": {"capacity": capacity, collection: [base224.item(target, chr(109 + item_index), *values) for item_index, values in enumerate(items)]}} for index, (capacity, items) in enumerate(rows, 1)]


CHECKER = r'''import ast, copy, hashlib, importlib.util, json
from pathlib import Path
def load(path,name):
 s=importlib.util.spec_from_file_location(name+hashlib.sha256(path.read_bytes()).hexdigest()[:8],path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def funcs(source): return ([n.name for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)],{n.name:ast.unparse(n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)})
root=Path(__file__).parent; c=json.loads((root/"correction-contract.json").read_text()); d=json.loads((root/"correction-decision.json").read_text()); target=c["target_symbol"]; target_path=root/c["target_path"]; reference_path=root/c["reference_path"]; baseline=(root/c["baseline_path"]).read_text(); source=target_path.read_text(); bo,bf=funcs(baseline); ao,af=funcs(source); local=bo==ao and af.get(target)!=bf.get(target) and all(af.get(k)==bf.get(k) for k in bo if k!=target); shape=isinstance(d,dict) and set(d)==set(c["required_fields"]) and d.get("disposition") in c["allowed_dispositions"] and all(d.get(k)==v for k,v in c["required_identities"].items()) and d.get("target_symbol")==target and d.get("predicates")==c["predicates"] and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("rationale","next_pursuit")); rows=[]
if shape and d["disposition"]=="revise" and local:
 a=load(target_path,"installed"); b=load(reference_path,"reference"); cases=json.loads((root/"bound-contact.json").read_text())["package"]["cases"]
 for x in cases:
  try: rows.append({"case_id":x["case_id"],"valid":True,"matches":getattr(a,target)(copy.deepcopy(x["input"]))==getattr(b,target)(copy.deepcopy(x["input"]))})
  except Exception as e: rows.append({"case_id":x.get("case_id"),"valid":False,"matches":False,"error_type":type(e).__name__})
passed=shape and ((d["disposition"]=="revise" and local and len(rows)==4 and all(x["valid"] and x["matches"] for x in rows)) or (d["disposition"]=="surrender" and source==baseline)); print(json.dumps({"passed":bool(passed),"shape_passed":bool(shape),"target_local_change":bool(local),"matches":sum(x["matches"] for x in rows),"rows":rows},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def contract(subject: dict[str, Any]) -> dict[str, Any]:
    pending, world, target, interface = selected(subject)
    identities = {"source_subject_digest": subject["artifact_digest"], "contact_binding_digest": pending["binding_digest"], "contact_identity": pending["contact_identity"], "world_receipt_digest": world["receipt_digest"]}
    return {"authority": AUTHORITY, "required_fields": sorted(base218.CORRECTION_CORE), "allowed_dispositions": ["revise", "surrender"], "required_identities": identities, "target_symbol": target, "target_path": interface["target_path"], "reference_path": interface["reference_path"], "baseline_path": "operations/baseline-selected.py", "predicates": base218.CORRECTION_PREDICATES}


def decision_template(subject: dict[str, Any]) -> dict[str, Any]:
    value = contract(subject)
    return {"disposition": "revise", **value["required_identities"], "target_symbol": value["target_symbol"], "predicates": copy.deepcopy(value["predicates"]), "rationale": "replace-rationale", "next_pursuit": "replace-next-pursuit"}


def seed_actor(root: Path, subject: dict[str, Any], template: dict[str, Any]) -> Path:
    seed = root / "seed"; seed.mkdir(parents=True); write_environment(seed, subject)
    pending, world, target, interface = selected(subject); baseline = (seed / interface["target_path"]).read_text(); (seed / "operations/baseline-selected.py").write_text(baseline)
    write_json(seed / "subject-position.json", base217.projection(subject)); write_json(seed / "bound-contact.json", pending); write_json(seed / "unresolved-world-receipt.json", world); write_json(seed / "correction-contract.json", contract(subject)); write_json(seed / "correction-decision.json", template); (seed / "check_correction.py").write_text(CHECKER)
    environment_files = sorted({item[key] for item in subject["expanded_semantic_environment"]["registry"].values() for key in ("target_path", "reference_path")})
    immutable = ["subject-position.json", "bound-contact.json", "unresolved-world-receipt.json", "correction-contract.json", "check_correction.py", "environment-registry.json", "operations/__init__.py", "operations/baseline-selected.py", *[path for path in environment_files if path != interface["target_path"]], "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": [interface["target_path"], "correction-decision.json"], "immutable": immutable})
    (seed / "README.md").write_text(f"Continue the exact unresolved {target} contact using the registry-selected interface. Revise only its target function or surrender it under correction-contract.json. Edit only {interface['target_path']} and correction-decision.json as required, run python3 check_correction.py, and inspect the exact diff. Follow-up hidden cases are unavailable.\n")
    return seed


def run_corrector(context, prior131, p82, root: Path, subject: dict[str, Any]) -> dict[str, Any]:
    seed = seed_actor(root, subject, decision_template(subject)); pending, world, target, interface = selected(subject); label = "registry-driven-corrector"; output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "correction-decision.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable); source = (workspace / interface["target_path"]).read_text(); baseline = (workspace / "operations/baseline-selected.py").read_text(); exact = set(decision) == base218.CORRECTION_CORE and all(decision.get(key) == value for key, value in contract(subject)["required_identities"].items()) and decision.get("target_symbol") == target and decision.get("predicates") == base218.CORRECTION_PREDICATES and decision.get("disposition") in {"revise", "surrender"}; local = source == baseline if decision.get("disposition") == "surrender" else target_only_change(source, baseline, target); public = base224.execute(workspace, target, pending["package"]["cases"]) if exact and local and decision.get("disposition") == "revise" else None; valid = bool(exact and local and immutable_ok and (decision["disposition"] == "surrender" or (public and public["all_valid"] and public["matches"] == 4)))
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError): decision, source, public, valid = None, None, None, False
    accepted = bool(valid and output and output.get("action") == "correct-unresolved-contact"); expected = ["correction-decision.json", interface["target_path"]] if decision and decision.get("disposition") == "revise" else ["correction-decision.json"]; audit = context.audit_actor(label, output, base_audit, accepted, expected); binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": AUTHORITY + "-bound-correction", "source_subject_digest": subject["artifact_digest"], "contact_identity": pending["contact_identity"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "target_path": interface["target_path"], "decision": decision, "patched_source": source if decision["disposition"] == "revise" else None, "patched_source_digest": p82.digest(source) if decision["disposition"] == "revise" else None, "public_result": public}; binding = {**body, "binding_digest": p82.digest(body)}; write_json(context.evidence(label) / "bound-correction.json", binding)
    return {"accepted": binding is not None, "binding": binding, "decision": decision, "public": public, "audit": audit, "output": output}


def evaluate_correction(root: Path, subject: dict[str, Any], correction: dict[str, Any], p82) -> dict[str, Any]:
    pending, world, target, interface = selected(subject); revised_root = root / "revised"; unchanged_root = root / "unchanged"; write_environment(revised_root, subject); write_environment(unchanged_root, subject); rows = followup_cases(target)
    if correction["decision"]["disposition"] == "revise":
        (revised_root / interface["target_path"]).write_text(correction["binding"]["patched_source"]); observed = base224.execute(revised_root, target, rows); unchanged = base224.execute(unchanged_root, target, rows); passed = observed["all_valid"] and observed["matches"] == 6 and unchanged["all_valid"] and unchanged["matches"] == 2; outcome = "success" if passed else "unresolved"
    else: observed, unchanged, passed, outcome = None, base224.execute(unchanged_root, target, rows), True, "surrender"
    body = {"authority": AUTHORITY + "-sealed-correction-world", "source_subject_digest": subject["artifact_digest"], "unresolved_world_receipt_digest": world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "target_symbol": target, "target_path": interface["target_path"], "followup_cases_digest": p82.digest(rows), "result": observed, "unchanged_control": unchanged, "outcome": outcome, "promotion_gate": passed}; return {**body, "receipt_digest": p82.digest(body)}


def compile_correction(subject: dict[str, Any], correction: dict[str, Any], followup: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); pending, unresolved_world, target, interface = selected(subject); pendings = copy.deepcopy(child["pending_contact_bearing_continuations"]); pendings[-1] = {**pendings[-1], "consequence_status": "resolved-after-correction", "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}; child["pending_contact_bearing_continuations"] = pendings
    if correction["decision"]["disposition"] == "revise": child["registry_installed_sources"] = {**child.get("registry_installed_sources", {}), interface["target_path"]: correction["binding"]["patched_source"]}
    capability = {"authority": AUTHORITY + "-world-admitted-correction", "target_symbol": target, "target_path": interface["target_path"], "package": copy.deepcopy(pending["package"]), "patched_source": correction["binding"]["patched_source"], "patched_source_digest": correction["binding"]["patched_source_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}; child["generalized_semantic_correction_capabilities"] = [*child.get("generalized_semantic_correction_capabilities", []), capability]
    receipt_body = {"authority": AUTHORITY + "-correction-receipt", "source_subject_digest": subject["artifact_digest"], "contact_identity": pending["contact_identity"], "unresolved_world_receipt_digest": unresolved_world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"], "outcome": followup["outcome"]}; receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}; child["unresolved_contact_correction_receipts"] = [*child.get("unresolved_contact_correction_receipts", []), receipt]
    ledger = copy.deepcopy(child["local_frontier_ledger"]); ledger["targets"][target]["status"] = "verified-local"; ledger["targets"][target]["correction_receipts"] = [*ledger["targets"][target]["correction_receipts"], receipt["receipt_digest"]]; ledger["targets"][target]["latest_world_receipt_digest"] = followup["receipt_digest"]; ledger["targets"][target]["latest_world_outcome"] = followup["outcome"]; ledger["targets"][target]["independent_success_receipts"] = [followup["receipt_digest"]] if followup["outcome"] == "success" else []; child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"]); state["phase"] = "assimilate"; state["accepted_actors"] += 1; state["corrected_contradictions"] += int(followup["outcome"] == "success"); child["fixed_g6_recurrence_driver"] = state; child["continuation_liveness"] = {"authority": base223.AUTHORITY, "status": "awaiting-reopening", "resolved_contact_identity": pending["contact_identity"], "correction_receipt_digest": receipt["receipt_digest"], "target_status": "verified-local", "transition_receipt_digest": child["evaluation_regime_transitions"][-1]["receipt_digest"]}; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": correction["decision"]["next_pursuit"]}; child["unresolved"] = "Assimilate the generalized correction and select the next G7 operation."; return p82.seal(child)


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130; parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args(); repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0225").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0224", "open-subject-after-semantic-widening-contact.json"); result224 = selector_base.load_artifact(p82, repo, store, "OT-0224", "target-unspecified-semantic-widening-aggregate.json"); pending, world, target, interface = selected(parent); fixture_root = run.parent / "OT-0225-preflight"; import shutil; shutil.rmtree(fixture_root, ignore_errors=True); fixture_root.mkdir(parents=True); environment = fixture_root / "environment"; write_environment(environment, parent); baseline = (environment / interface["target_path"]).read_text(); fixture_source = corrected_fixture_source(baseline, target); fixture_revised = fixture_root / "fixture-revised"; fixture_unchanged = fixture_root / "fixture-unchanged"; write_environment(fixture_revised, parent); write_environment(fixture_unchanged, parent); (fixture_revised / interface["target_path"]).write_text(fixture_source); public = base224.execute(fixture_revised, target, pending["package"]["cases"]); corrected = base224.execute(fixture_revised, target, followup_cases(target)); unchanged = base224.execute(fixture_unchanged, target, followup_cases(target)); fixture_decision = decision_template(parent); fixture_decision.update(rationale="Use consequence-weighted bounded selection exposed by the retained reference.", next_pursuit="Assimilate the corrected selected surface and choose the next live frontier operation."); checker_seed = seed_actor(fixture_root / "checker", parent, fixture_decision); (checker_seed / interface["target_path"]).write_text(fixture_source); checker = subprocess.run(["python3", "check_correction.py"], cwd=checker_seed, capture_output=True); fixture_binding = {"binding_digest": "a" * 64, "patched_source": fixture_source, "patched_source_digest": p82.digest(fixture_source)}; fixture_correction = {"decision": fixture_decision, "binding": fixture_binding}; fixture_followup = {"target_symbol": target, "receipt_digest": "b" * 64, "outcome": "success"}; prospective = compile_correction(parent, fixture_correction, fixture_followup, p82)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"]); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor()); checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_correct": parent["artifact_digest"] == PARENT_DIGEST and parent["fixed_g6_recurrence_driver"]["phase"] == "correct" and runtime.identity_conforms(parent), "ot0224_exact_promotion": result224["observer_disposition"] == "promoted" and result224["receipt_digest"] == OT224_RECEIPT and result224["final_subject_digest"] == PARENT_DIGEST, "selected_target_not_hardcoded": target not in Path(__file__).read_text(), "registry_resolves_pending": interface == base224.registry()[target] and world["target_symbol"] == target and world["outcome"] == "unresolved" and world["result"]["matches"] == 2, "target_only_fixture_change": target_only_change(fixture_source, baseline, target), "fixture_public_4_of_4": public["all_valid"] and public["matches"] == 4, "fixture_followup_6_of_6": corrected["all_valid"] and corrected["matches"] == 6, "unchanged_followup_2_of_6": unchanged["all_valid"] and unchanged["matches"] == 2, "actor_checker_passed": checker.returncode == 0, "prospective_subject_conforms": runtime.identity_conforms(prospective) and prospective["fixed_g6_recurrence_driver"]["phase"] == "assimilate", "schema_supported": CORRECTOR_SCHEMA.is_file() and "uniqueItems" not in CORRECTOR_SCHEMA.read_text(), "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); fixtures = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "selected_interface": interface, "public": public, "corrected_followup": corrected, "unchanged_followup": unchanged, "checks": checks}
    if args.preflight_only: print(json.dumps(fixtures, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0225 evidence")
    run.mkdir(parents=True); write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); correction = run_corrector(context, prior131, p82, run / "correction", parent); followup = evaluate_correction(run / "followup", parent, correction, p82) if correction["accepted"] else None; final = parent
    if followup: write_json(run / "correction-world-receipt.json", followup); candidate = compile_correction(parent, correction, followup, p82); final = candidate if runtime.identity_conforms(candidate) else parent
    gates = {"preflight_passed": checks["passed"], "corrector_accepted": correction["accepted"], "correction_revised": bool(correction["accepted"] and correction["decision"]["disposition"] == "revise"), "public_4_of_4": bool(correction["public"] and correction["public"]["matches"] == 4), "followup_6_of_6": bool(followup and followup["result"] and followup["result"]["matches"] == 6), "unchanged_2_of_6": bool(followup and followup["unchanged_control"]["matches"] == 2), "followup_promotion_gate": bool(followup and followup["promotion_gate"]), "pending_resolved_exactly": bool(followup and final["pending_contact_bearing_continuations"][-1]["followup_world_receipt_digest"] == followup["receipt_digest"]), "environment_installs_patch": bool(correction["accepted"] and correction["decision"]["disposition"] == "revise" and final["registry_installed_sources"][interface["target_path"]] == correction["binding"]["patched_source"]), "g7_target_verified_local": bool(followup and final["local_frontier_ledger"]["targets"][target]["status"] == "verified-local"), "driver_dispatches_assimilate": final["fixed_g6_recurrence_driver"]["phase"] == "assimilate", "final_subject_open_conformant": final["continuation"]["status"] == "open" and runtime.identity_conforms(final), "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; gates["passed"] = all(gates.values()); aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "selected_target": target, "selected_interface": interface, "correction": p82.compact(correction), "followup_world": followup, "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final["continuation_liveness"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1}; aggregate["receipt_digest"] = p82.digest(aggregate); write_json(run / "aggregate.json", aggregate); write_json(run / "final-full-subject.json", final); print(json.dumps(aggregate, indent=2, sort_keys=True)); return 0 if gates["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
