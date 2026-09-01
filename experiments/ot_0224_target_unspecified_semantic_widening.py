from __future__ import annotations

import argparse
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
BASE_PATH = ROOT / "ot_0223_verification_debt_frontier_liveness.py"
BASE_SHA256 = "bb29af0cfc144c156296acf12e5fb869d6f3fd7c2aa09c69cd6e6d63374034d0"
PARENT_DIGEST = "03b6c4d6199a261a8607dd712f42079499d7a94d835dc5b6faa93786d1acec4f"
OT223_RECEIPT = "8d408412f38f0f25c81f344cf8fe3325e989a6989cc342db75422ea3f8fc3fe4"
SCHEMA = REPO / "spec/ot-0224-widening.schema.json"
AUTHORITY = "ot-0224-target-unspecified-semantic-widening"
ABI = "case-object-to-ordered-identifier-list-v1"
NEW_TARGETS = {"schedule_evacuation", "prioritize_inspections", "allocate_backup_power"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0223 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0224_frozen_ot0223", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base223 = load_base()
base222 = base223.base222
base220 = base223.base220
base219 = base223.base219
base217 = base223.base217
base213 = base223.base213
authority_base = base223.authority_base
PREDICATES = base219.PREDICATES


PLANNING_SOURCE = '''def schedule_evacuation(case):
    remaining = case["capacity"]
    chosen = []
    for item in sorted(case["zones"], key=lambda row: (-row["population"], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"]); remaining -= item["effort"]
    return chosen


def prioritize_inspections(case):
    remaining = case["capacity"]
    chosen = []
    for item in sorted(case["sites"], key=lambda row: (-row["criticality"], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"]); remaining -= item["effort"]
    return chosen


def allocate_backup_power(case):
    remaining = case["capacity"]
    chosen = []
    for item in sorted(case["loads"], key=lambda row: (-row["load"], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"]); remaining -= item["effort"]
    return chosen
'''


REFERENCE_PLANNING_SOURCE = '''def _best(items, capacity, value):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > capacity: continue
        score = sum(value(item) for item in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])


def schedule_evacuation(case):
    return _best(case["zones"], case["capacity"], lambda row: row["population"] * row["delay"] * row["hazard_probability"])


def prioritize_inspections(case):
    return _best(case["sites"], case["capacity"], lambda row: row["criticality"] * row["exposure"] * row["defect_probability"])


def allocate_backup_power(case):
    return _best(case["loads"], case["capacity"], lambda row: row["load"] * row["outage_duration"] * row["failure_probability"])
'''


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def registry() -> dict[str, Any]:
    old = {target: {"target_path": "operations/system.py", "reference_path": "operations/reference.py", "abi": ABI} for target in sorted(base217.TARGETS)}
    new = {target: {"target_path": "operations/planning.py", "reference_path": "operations/reference_planning.py", "abi": ABI} for target in sorted(NEW_TARGETS)}
    return {**old, **new}


def write_environment(root: Path, subject: dict[str, Any]) -> None:
    files = {
        "operations/__init__.py": "",
        "operations/system.py": base220.installed_source(subject),
        "operations/reference.py": base220.base218.base215.ordered_source(base220.base218.base215.REFERENCE_SOURCE, base220.base218.base215.ORDER_SCHEDULE[0], ("_best",)),
        "operations/planning.py": PLANNING_SOURCE,
        "operations/reference_planning.py": REFERENCE_PLANNING_SOURCE,
        "environment-registry.json": json.dumps(registry(), indent=2, sort_keys=True) + "\n",
    }
    for relative, content in files.items():
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name + hashlib.sha256(path.read_bytes()).hexdigest()[:10], path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def available(root: Path) -> dict[str, tuple[Any, Any]]:
    modules = {}
    result = {}
    for target, interface in registry().items():
        pair = (interface["target_path"], interface["reference_path"])
        if pair not in modules: modules[pair] = (load_module(root / pair[0], "installed_"), load_module(root / pair[1], "reference_"))
        result[target] = (getattr(modules[pair][0], target), getattr(modules[pair][1], target))
    return result


def structural(contact: Any) -> bool:
    if not isinstance(contact, dict) or set(contact) != base219.CONTACT_CORE: return False
    if not all(isinstance(contact.get(key), str) and contact[key].strip() for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")): return False
    interface = registry().get(contact["target_symbol"])
    cases = contact.get("cases")
    return bool(interface and contact["target_path"] == interface["target_path"] and contact["abi"] == interface["abi"] and isinstance(cases, list) and len(cases) == 4 and len({row.get("case_id") for row in cases if isinstance(row, dict)}) == 4 and all(isinstance(row, dict) and set(row) == {"case_id", "input"} and isinstance(row["case_id"], str) and row["case_id"].strip() and isinstance(row["input"], dict) for row in cases) and contact.get("predicates") == PREDICATES and len(base219.canonical(contact)) <= 32768)


def completed_registry(subject: dict[str, Any], functions: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    contacts = []
    for capability in subject.get("semantic_contact_program_capabilities", []): contacts.append(base219.historical_contact(capability["package"]))
    for capability in subject.get("semantic_move_capabilities", []): contacts.append(base219.historical_contact(capability["package"]))
    for pending in subject.get("pending_contact_bearing_continuations", []):
        if pending.get("consequence_status") not in {None, "unreceipted"}: contacts.append(copy.deepcopy(pending["package"]))
    identities = set(); inputs: dict[str, set[str]] = {}
    for contact in contacts:
        if contact["target_symbol"] not in functions: continue
        identities.add(base219.projected_identity(contact, functions)); installed, reference = functions[contact["target_symbol"]]
        inputs.setdefault(contact["target_symbol"], set()).update(base219.digest(base219.behavioral_projection(row["input"], installed, reference)) for row in contact["cases"])
    return {"identities": identities, "inputs": inputs}


def g6(decision: Any, completed: dict[str, Any], functions: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    if not isinstance(decision, dict) or not {"next_pursuit", "next_contact"}.issubset(decision) or not isinstance(decision.get("next_pursuit"), str) or not decision["next_pursuit"].strip(): return {"accepted": False, "reason": "invalid-decision"}
    contact = decision["next_contact"]
    if not structural(contact): return {"accepted": False, "reason": "invalid-contact"}
    identity = base219.projected_identity(contact, functions)
    if identity in completed["identities"]: return {"accepted": False, "reason": "already-receipted", "projected_identity": identity}
    installed, reference = functions[contact["target_symbol"]]; projected = [base219.behavioral_projection(row["input"], installed, reference) for row in contact["cases"]]; prior = completed["inputs"].get(contact["target_symbol"], set()); count = sum(base219.digest(value) not in prior for value in projected)
    return {"accepted": count >= 2, "reason": "behaviorally-new-contact" if count >= 2 else "insufficient-new-inputs", "projected_identity": identity, "new_input_count": count, "projected_inputs": projected}


def g7(decision: Any, completed: dict[str, Any], functions: dict[str, tuple[Any, Any]], ledger: dict[str, Any]) -> dict[str, Any]:
    floor = g6(decision, completed, functions)
    if not floor["accepted"]: return {"action": "reject", "reason": floor["reason"], "g6": floor}
    target = decision["next_contact"]["target_symbol"]; status = ledger["targets"].get(target, {"status": "uncontacted"})["status"]
    action = "contact" if status in {"uncontacted", "verification-due"} else ("correct" if status == "unresolved" else "widen")
    return {"action": action, "target_status": status, "g6": floor}


FIELDS = {
    "schedule_evacuation": ("zones", "population", "delay", "hazard_probability"),
    "prioritize_inspections": ("sites", "criticality", "exposure", "defect_probability"),
    "allocate_backup_power": ("loads", "load", "outage_duration", "failure_probability"),
}


def item(target: str, identity: str, magnitude: int, duration: int, probability: float, effort: int) -> dict[str, Any]:
    _, magnitude_name, duration_name, probability_name = FIELDS[target]
    return {"id": identity, magnitude_name: magnitude, duration_name: duration, probability_name: probability, "effort": effort}


def cases(target: str, prefix: str) -> list[dict[str, Any]]:
    collection = FIELDS[target][0]
    values = [
        (3, [(10, 1, .2, 3), (6, 8, .9, 3)]),
        (4, [(10, 1, .2, 4), (7, 7, .8, 2), (6, 6, .9, 2)]),
        (5, [(10, 1, .2, 5), (8, 6, .8, 3), (7, 5, .9, 2)]),
        (2, [(8, 8, .8, 2), (10, 1, .2, 2)]),
        (4, [(9, 5, .9, 2), (5, 2, .5, 2)]),
        (4, [(8, 4, .8, 2), (7, 3, .7, 2)]),
    ]
    return [{"case_id": f"{prefix}-{index}", "input": {"capacity": capacity, collection: [item(target, chr(103 + row), *value) for row, value in enumerate(rows)]}} for index, (capacity, rows) in enumerate(values, 1)]


HIDDEN_CASES = {target: cases(target, f"sealed-{target}") for target in sorted(NEW_TARGETS)}


def contact(target: str, prefix: str) -> dict[str, Any]:
    return {"contact_id": f"{prefix}-{target}", "target_path": registry()[target]["target_path"], "target_symbol": target, "abi": ABI, "stake": "Determine whether magnitude-only planning preserves the largest consequence-weighted feasible set.", "cases": copy.deepcopy(HIDDEN_CASES[target][:4]), "predicates": copy.deepcopy(PREDICATES)}


def execute(root: Path, target: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    functions = available(root); installed, reference = functions[target]; result = []
    for row in rows:
        try:
            observed = installed(copy.deepcopy(row["input"])); expected = reference(copy.deepcopy(row["input"])); result.append({"case_id": row["case_id"], "observed": observed, "expected": expected, "matches": observed == expected, "valid": True})
        except Exception as error: result.append({"case_id": row.get("case_id"), "error_type": type(error).__name__, "matches": False, "valid": False})
    return {"case_count": len(result), "all_valid": all(row["valid"] for row in result), "matches": sum(row["matches"] for row in result), "rows": result}


CHECKER = r'''import copy, hashlib, importlib.util, json
from pathlib import Path
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def digest(v): return hashlib.sha256(canon(v)).hexdigest()
def load(path,name): s=importlib.util.spec_from_file_location(name+hashlib.sha256(path.read_bytes()).hexdigest()[:8],path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def outcome(fn,v):
 try: return {"status":"ok","value":fn(copy.deepcopy(v))}
 except Exception as e: return {"status":"error","error_type":type(e).__name__}
def paths(v,p=()):
 out=[]
 if isinstance(v,dict):
  for k in sorted(v): out.append((*p,k)); out.extend(paths(v[k],(*p,k)))
 elif isinstance(v,list):
  for i,x in enumerate(v): out.extend(paths(x,(*p,i)))
 return out
def remove(v,p):
 v=copy.deepcopy(v); c=v
 for x in p[:-1]: c=c[x]
 del c[p[-1]]; return v
def project(v,a,b):
 v=copy.deepcopy(v)
 while True:
  baseline=(outcome(a,v),outcome(b,v)); changed=False
  for p in sorted(paths(v),key=lambda x:(-len(x),tuple(str(y) for y in x))):
   candidate=remove(v,p)
   if (outcome(a,candidate),outcome(b,candidate))==baseline: v=candidate; changed=True; break
  if not changed:return v
root=Path(__file__).parent; d=json.loads((root/"widening-decision.json").read_text()); contract=json.loads((root/"widening-contract.json").read_text()); registry=json.loads((root/"environment-registry.json").read_text()); completed=json.loads((root/"completed-contact-registry.json").read_text()); ledger=json.loads((root/"local-frontier-ledger.json").read_text()); c=d.get("next_contact") if isinstance(d,dict) else None; shape=isinstance(d,dict) and set(d)==set(contract["required_fields"]) and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("next_pursuit","selected_surface_rationale")) and isinstance(c,dict) and set(c)==set(contract["contact_fields"])
if shape:
 interface=registry.get(c.get("target_symbol")); rows=c.get("cases"); shape=bool(interface and c["target_path"]==interface["target_path"] and c["abi"]==interface["abi"] and c["target_symbol"] not in ledger["targets"] and all(isinstance(c.get(k),str) and c[k].strip() and not c[k].startswith("replace-") for k in ("contact_id","stake")) and isinstance(rows,list) and len(rows)==4 and len({x.get("case_id") for x in rows if isinstance(x,dict)})==4 and all(isinstance(x,dict) and set(x)=={"case_id","input"} and isinstance(x.get("input"),dict) for x in rows) and c.get("predicates")==contract["predicates"] and len(canon(c))<=32768)
if shape:
 a=load(root/interface["target_path"],"a"); b=load(root/interface["reference_path"],"b"); installed=getattr(a,c["target_symbol"]); reference=getattr(b,c["target_symbol"]); projected=[project(x["input"],installed,reference) for x in c["cases"]]; ident=digest({"target_symbol":c["target_symbol"],"target_path":c["target_path"],"abi":c["abi"],"case_inputs":sorted(digest(x) for x in projected),"predicates":c["predicates"]}); prior=set(completed["inputs"].get(c["target_symbol"],[])); new=sum(digest(x) not in prior for x in projected); shape=ident not in set(completed["identities"]) and new>=2
else: ident=None; new=0
rows=[]
if shape:
 for x in c["cases"]:
  try: rows.append({"case_id":x["case_id"],"valid":True,"matches":installed(copy.deepcopy(x["input"]))==reference(copy.deepcopy(x["input"]))})
  except Exception as e: rows.append({"case_id":x.get("case_id"),"valid":False,"matches":False,"error_type":type(e).__name__})
passed=shape and len(rows)==4 and all(x["valid"] for x in rows); print(json.dumps({"passed":bool(passed),"projected_identity":ident,"new_input_count":new,"rows":rows},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def serial_completed(value: dict[str, Any]) -> dict[str, Any]: return {"identities": sorted(value["identities"]), "inputs": {key: sorted(rows) for key, rows in sorted(value["inputs"].items())}}


def seed_actor(root: Path, subject: dict[str, Any], completed: dict[str, Any], template: dict[str, Any]) -> Path:
    seed = root / "seed"; seed.mkdir(parents=True); write_environment(seed, subject); write_json(seed / "subject-position.json", base217.projection(subject)); write_json(seed / "local-frontier-ledger.json", subject["local_frontier_ledger"]); write_json(seed / "completed-contact-registry.json", serial_completed(completed)); contract_value = {"authority": AUTHORITY, "required_fields": ["next_pursuit", "selected_surface_rationale", "next_contact"], "contact_fields": sorted(base219.CONTACT_CORE), "predicates": PREDICATES}; write_json(seed / "widening-contract.json", contract_value); write_json(seed / "widening-decision.json", template); (seed / "check_widening.py").write_text(CHECKER)
    immutable = ["subject-position.json", "local-frontier-ledger.json", "completed-contact-registry.json", "widening-contract.json", "check_widening.py", "environment-registry.json", "operations/__init__.py", "operations/system.py", "operations/reference.py", "operations/planning.py", "operations/reference_planning.py", "mutation-envelope.json", "README.md"]; write_json(seed / "mutation-envelope.json", {"editable": ["widening-decision.json"], "immutable": immutable}); (seed / "README.md").write_text("The subject has locally verified every target in its current frontier. Select and bind one genuinely new semantic surface from this complete repository without an assigned target. Edit only widening-decision.json, run python3 check_widening.py, and inspect the exact diff. Hidden cases are unavailable.\n"); return seed


def decision_template() -> dict[str, Any]: return {"next_pursuit": "replace-next-pursuit", "selected_surface_rationale": "replace-rationale", "next_contact": {"contact_id": "replace-contact", "target_path": "replace-path", "target_symbol": "replace-target", "abi": ABI, "stake": "replace-stake", "cases": [], "predicates": copy.deepcopy(PREDICATES)}}


def run_actor(context, prior131, p82, root: Path, subject: dict[str, Any]) -> dict[str, Any]:
    environment = root / "environment"; write_environment(environment, subject); functions = available(environment); completed = completed_registry(subject, functions); seed = seed_actor(root, subject, completed, decision_template()); label = "semantic-widening-actor"; output, base_audit, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "widening-decision.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable); floor = g6(decision, completed, functions); disposition = g7(decision, completed, functions, subject["local_frontier_ledger"]); target = decision["next_contact"]["target_symbol"]; public = execute(workspace, target, decision["next_contact"]["cases"]) if floor["accepted"] else None; valid = bool(immutable_ok and target in NEW_TARGETS and floor["accepted"] and disposition["action"] == "contact" and public and public["all_valid"] and isinstance(decision.get("selected_surface_rationale"), str) and decision["selected_surface_rationale"].strip())
    except (OSError, json.JSONDecodeError, KeyError): decision, floor, disposition, target, public, valid = None, {"accepted": False}, {"action": "reject"}, None, None, False
    accepted = bool(valid and output and output.get("action") == "widen-local-frontier" and output.get("selected_target") == target); audit = context.audit_actor(label, output, base_audit, accepted, ["widening-decision.json"]); binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": AUTHORITY + "-bound-contact", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision, "projected_contact_identity": floor["projected_identity"], "new_projected_input_count": floor["new_input_count"], "public_result": public}; binding = {**body, "binding_digest": p82.digest(body)}; write_json(context.evidence(label) / "bound-widening-contact.json", binding)
    return {"accepted": binding is not None, "binding": binding, "decision": decision, "g6": floor, "g7": disposition, "public": public, "audit": audit, "output": output}


def load_retained_action(run: Path, subject: dict[str, Any], completed: dict[str, Any], functions: dict[str, tuple[Any, Any]], prior131, p82) -> dict[str, Any]:
    actor_root = run / "semantic-widening-actor"
    workspace = actor_root / "actor-workspace"
    seed = run / "widening" / "seed"
    decision = json.loads((workspace / "widening-decision.json").read_text())
    output = json.loads((actor_root / "output.json").read_text())
    audit = json.loads((actor_root / "actor-audit.json").read_text())
    binding = json.loads((actor_root / "bound-widening-contact.json").read_text())
    immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
    immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    floor = g6(decision, completed, functions)
    disposition = g7(decision, completed, functions, subject["local_frontier_ledger"])
    target = decision["next_contact"]["target_symbol"]
    public = execute(workspace, target, decision["next_contact"]["cases"]) if floor["accepted"] else None
    body = {"authority": AUTHORITY + "-bound-contact", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision, "projected_contact_identity": floor.get("projected_identity"), "new_projected_input_count": floor.get("new_input_count"), "public_result": public}
    expected_binding = {**body, "binding_digest": p82.digest(body)}
    accepted = bool(immutable_ok and target in NEW_TARGETS and floor["accepted"] and disposition["action"] == "contact" and public and public["all_valid"] and output.get("action") == "widen-local-frontier" and output.get("selected_target") == target and prior131.audit_accepted(audit) and binding == expected_binding)
    if not accepted:
        raise RuntimeError("retained actor action does not reconstruct exactly")
    return {"accepted": True, "binding": binding, "decision": decision, "g6": floor, "g7": disposition, "public": public, "audit": audit, "output": output}


def compile_intermediate(subject: dict[str, Any], action: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); package = action["decision"]["next_contact"]; target = package["target_symbol"]
    child["expanded_semantic_environment"] = {"authority": AUTHORITY + "-environment", "registry": registry(), "planning_source": PLANNING_SOURCE, "reference_planning_source": REFERENCE_PLANNING_SOURCE, "planning_source_digest": p82.digest(PLANNING_SOURCE), "reference_source_digest": p82.digest(REFERENCE_PLANNING_SOURCE)}
    child["semantic_widening_contacts"] = [*child.get("semantic_widening_contacts", []), action["binding"]]
    pending = {"authority": "G7-pending-widened-contact", "binding_digest": action["binding"]["binding_digest"], "contact_identity": action["binding"]["projected_contact_identity"], "package": copy.deepcopy(package), "package_digest": p82.digest(package), "consequence_status": "unreceipted"}; child["pending_contact_bearing_continuations"] = [*child["pending_contact_bearing_continuations"], pending]
    ledger = copy.deepcopy(child["local_frontier_ledger"]); ledger["targets"][target] = {"status": "verification-due", "admitted_capability_receipts": [], "correction_receipts": [], "independent_success_receipts": [], "latest_world_receipt_digest": None, "latest_world_outcome": None}; child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"]); state.update(phase="contact", last_target=target, accepted_actors=state["accepted_actors"] + 1); child["fixed_g6_recurrence_driver"] = state; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": action["decision"]["next_pursuit"]}; child["continuation_liveness"] = {"authority": base223.AUTHORITY, "status": "live", "contact_identity": pending["contact_identity"], "binding_digest": pending["binding_digest"], "target_status": "verification-due", "transition_receipt_digest": child["evaluation_regime_transitions"][-1]["receipt_digest"]}; child["unresolved"] = "Expose the widened pending contact to independent consequence."; return p82.seal(child)


def compile_world(subject: dict[str, Any], world: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); pending = copy.deepcopy(child["pending_contact_bearing_continuations"]); pending[-1] = {**pending[-1], "consequence_status": world["outcome"], "world_receipt_digest": world["receipt_digest"]}; child["pending_contact_bearing_continuations"] = pending; child["semantic_widening_world_receipts"] = [*child.get("semantic_widening_world_receipts", []), world]
    target = world["target_symbol"]; ledger = copy.deepcopy(child["local_frontier_ledger"]); ledger["targets"][target].update(status="unresolved" if world["outcome"] == "unresolved" else "verified-local", latest_world_receipt_digest=world["receipt_digest"], latest_world_outcome=world["outcome"], independent_success_receipts=[world["receipt_digest"]] if world["outcome"] == "success" else []); child["local_frontier_ledger"] = ledger; state = copy.deepcopy(child["fixed_g6_recurrence_driver"]); state["phase"] = "correct" if world["outcome"] == "unresolved" else "assimilate"; state["encounters"] += 1; state["history"] = [*state["history"], {"encounter": state["encounters"], "target": target, "outcome": world["outcome"], "receipt_digest": world["receipt_digest"]}]; child["fixed_g6_recurrence_driver"] = state; child["continuation_liveness"] = {"authority": base223.AUTHORITY, "status": "unresolved" if world["outcome"] == "unresolved" else "awaiting-reopening", "resolved_contact_identity": world["contact_identity"], "world_receipt_digest": world["receipt_digest"], "target_status": ledger["targets"][target]["status"], "transition_receipt_digest": child["evaluation_regime_transitions"][-1]["receipt_digest"]}; return p82.seal(child)


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130; parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); parser.add_argument("--resume-observer", action="store_true"); args = parser.parse_args(); repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0224").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0223", "open-subject-at-local-saturation.json"); result223 = selector_base.load_artifact(p82, repo, store, "OT-0223", "verification-debt-liveness-transition-aggregate.json"); fixture_root = run.parent / "OT-0224-preflight"; import shutil; shutil.rmtree(fixture_root, ignore_errors=True); fixture_root.mkdir(parents=True); write_environment(fixture_root / "environment", parent); functions = available(fixture_root / "environment"); completed = completed_registry(parent, functions); expanded_ledger = copy.deepcopy(parent["local_frontier_ledger"]); new_results = {target: g7(base219.decision("Fixture widening.", contact(target, "fixture")), completed, functions, expanded_ledger) for target in sorted(NEW_TARGETS)}; old_results = {target: g7(base219.decision("Old target.", base223.fresh_contact(target, 70 + index)), completed, functions, expanded_ledger) for index, target in enumerate(sorted(base217.TARGETS))}; hidden = {target: execute(fixture_root / "environment", target, HIDDEN_CASES[target]) for target in sorted(NEW_TARGETS)}
    fixture_target = sorted(NEW_TARGETS)[0]; fixture_decision = {"next_pursuit": "Continue independent contact on a newly selected planning surface.", "selected_surface_rationale": "This target is absent from the local ledger and exposes consequence-weighted planning.", "next_contact": contact(fixture_target, "checker")}; checker_seed = seed_actor(fixture_root / "checker", parent, completed, fixture_decision); checker = subprocess.run(["python3", "check_widening.py"], cwd=checker_seed, capture_output=True); fixture_floor = g6(fixture_decision, completed, functions); fixture_action = {"decision": fixture_decision, "binding": {"binding_digest": "a" * 64, "projected_contact_identity": fixture_floor["projected_identity"]}}; intermediate = compile_intermediate(parent, fixture_action, p82); fixture_world_body = {"authority": AUTHORITY + "-sealed-world", "source_subject_digest": intermediate["artifact_digest"], "contact_identity": fixture_floor["projected_identity"], "target_symbol": fixture_target, "hidden_cases_digest": p82.digest(HIDDEN_CASES[fixture_target]), "result": hidden[fixture_target], "outcome": "unresolved"}; fixture_world = {**fixture_world_body, "receipt_digest": p82.digest(fixture_world_body)}; final_fixture = compile_world(intermediate, fixture_world, p82)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"]); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor()); prompt = (checker_seed / "README.md").read_text()
    checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_widen": parent["artifact_digest"] == PARENT_DIGEST and parent["fixed_g6_recurrence_driver"]["phase"] == "widen" and runtime.identity_conforms(parent), "ot0223_exact_promotion": result223["observer_disposition"] == "promoted" and result223["receipt_digest"] == OT223_RECEIPT and result223["final_subject_digest"] == PARENT_DIGEST, "registry_six_targets": set(registry()) == set(base217.TARGETS) | NEW_TARGETS, "all_new_targets_g7_contact": all(row["action"] == "contact" and row["g6"]["accepted"] for row in new_results.values()), "all_old_targets_g7_widen": all(row["action"] == "widen" for row in old_results.values()), "hidden_all_2_of_6": all(row["all_valid"] and row["matches"] == 2 for row in hidden.values()), "actor_checker_passed": checker.returncode == 0, "prompt_has_no_selected_target": not any(target in prompt for target in NEW_TARGETS), "template_rejected": not g6(decision_template(), completed, functions)["accepted"], "prospective_states_conform": runtime.identity_conforms(intermediate) and runtime.identity_conforms(final_fixture), "schema_supported": SCHEMA.is_file() and "uniqueItems" not in SCHEMA.read_text(), "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); fixtures = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "registry": registry(), "new_target_results": new_results, "old_target_results": old_results, "hidden_results": hidden, "checks": checks}
    if args.preflight_only: print(json.dumps(fixtures, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2
    if not checks["passed"]: raise SystemExit("preflight failed")
    if args.resume_observer:
        if not run.is_dir(): raise SystemExit("no retained OT-0224 evidence to reconstruct")
        if json.loads((run / "fixture-conformance.json").read_text()) != fixtures: raise SystemExit("retained preflight does not reconstruct exactly")
        action = load_retained_action(run, parent, completed, functions, prior131, p82)
        intermediate_live = json.loads((run / "intermediate-live-subject.json").read_text())
        if intermediate_live != compile_intermediate(parent, action, p82): raise SystemExit("retained intermediate does not reconstruct exactly")
        world = json.loads((run / "hidden-world-receipt.json").read_text())
        target = action["decision"]["next_contact"]["target_symbol"]
        result = hidden[target]
        outcome = "success" if result["all_valid"] and result["matches"] >= 4 else ("surrender" if result["all_valid"] and result["matches"] == 0 else "unresolved")
        body = {"authority": AUTHORITY + "-sealed-world", "source_subject_digest": intermediate_live["artifact_digest"], "contact_binding_digest": action["binding"]["binding_digest"], "contact_identity": action["binding"]["projected_contact_identity"], "target_symbol": target, "hidden_cases_digest": p82.digest(HIDDEN_CASES[target]), "result": result, "outcome": outcome}
        if world != {**body, "receipt_digest": p82.digest(body)}: raise SystemExit("retained world does not reconstruct exactly")
        final = compile_world(intermediate_live, world, p82)
    else:
        if run.exists(): raise SystemExit("preserve existing OT-0224 evidence")
        run.mkdir(parents=True); write_json(run / "fixture-conformance.json", fixtures)
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); action = run_actor(context, prior131, p82, run / "widening", parent); intermediate_live = parent
        if action["accepted"]:
            candidate = compile_intermediate(parent, action, p82)
            if runtime.identity_conforms(candidate): intermediate_live = candidate; write_json(run / "intermediate-live-subject.json", intermediate_live)
        world = None; final = intermediate_live
        if action["accepted"] and intermediate_live is not parent:
            world_root = run / "world"; write_environment(world_root, intermediate_live); target = action["decision"]["next_contact"]["target_symbol"]; result = execute(world_root, target, HIDDEN_CASES[target]); outcome = "success" if result["all_valid"] and result["matches"] >= 4 else ("surrender" if result["all_valid"] and result["matches"] == 0 else "unresolved"); body = {"authority": AUTHORITY + "-sealed-world", "source_subject_digest": intermediate_live["artifact_digest"], "contact_binding_digest": action["binding"]["binding_digest"], "contact_identity": action["binding"]["projected_contact_identity"], "target_symbol": target, "hidden_cases_digest": p82.digest(HIDDEN_CASES[target]), "result": result, "outcome": outcome}; world = {**body, "receipt_digest": p82.digest(body)}; write_json(run / "hidden-world-receipt.json", world); candidate = compile_world(intermediate_live, world, p82); final = candidate if runtime.identity_conforms(candidate) else intermediate_live
    target = action["decision"]["next_contact"]["target_symbol"] if action["accepted"] else None; gates = {"preflight_passed": checks["passed"], "fresh_actor_accepted": action["accepted"], "selected_previously_uncontacted_target": target in NEW_TARGETS if target else False, "generalized_g6_passed": bool(action["accepted"] and action["g6"]["accepted"]), "g7_dispatched_contact": bool(action["accepted"] and action["g7"]["action"] == "contact"), "public_cases_valid": bool(action["public"] and action["public"]["all_valid"]), "intermediate_subject_conforms": intermediate_live is not parent, "independent_world_valid": bool(world and world["result"]["all_valid"]), "world_changes_ledger_state": bool(world and final["local_frontier_ledger"]["targets"][target]["status"] in {"unresolved", "verified-local"}), "final_subject_conforms": runtime.identity_conforms(final), "final_subject_open_actionable": final["continuation"]["status"] == "open" and final["fixed_g6_recurrence_driver"]["phase"] in {"correct", "assimilate"}, "historical_pending_prefix_exact": final["pending_contact_bearing_continuations"][:-1] == parent["pending_contact_bearing_continuations"], "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; gates["passed"] = all(gates.values()); aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "widening": {"accepted": action["accepted"], "binding": action["binding"], "decision": action["decision"], "g6": action["g6"], "g7": action["g7"], "public": action["public"]}, "intermediate_subject_digest": intermediate_live["artifact_digest"], "world": world, "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final["continuation_liveness"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1}; aggregate["receipt_digest"] = p82.digest(aggregate); write_json(run / "aggregate.json", aggregate); write_json(run / "final-full-subject.json", final); print(json.dumps(aggregate, indent=2, sort_keys=True)); return 0 if gates["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
