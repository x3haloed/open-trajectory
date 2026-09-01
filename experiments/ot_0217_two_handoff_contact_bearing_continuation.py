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
BASE_PATH = ROOT / "ot_0216_contact_bearing_continuation_liveness.py"
BASE_SHA256 = "c7b349af70f76f12cf36680d7a32848e65d2ddf759eef95ecbb36b4e8c912231"
PARENT_DIGEST = "b579ce631c4f5fdf939c5efb9c5bf7f53e7c65d084bd3fd20ea50edf2f364418"
G5_RECEIPT = "6d45a39d474f4860d9cc052d5ac764962ad88af2ddecba1f3f90b671916915b2"
ORIGINATOR_SCHEMA = REPO / "spec/ot-0217-originator.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0217-assimilator.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0216 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0217_frozen_ot0216", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base216 = load_base()
base215 = base216.base215
base213 = base216.base213
authority_base = base216.authority_base
ABI = base216.ABI
PREDICATES = base216.PREDICATES
CONTACT_CORE = base216.CONTACT_CORE
TARGET_PATH = "operations/system.py"
TARGETS = {"schedule_recovery", "allocate_relief", "schedule_maintenance"}


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def environment_registry() -> dict[str, Any]:
    return {target: {"target_path": TARGET_PATH, "abi": ABI} for target in sorted(TARGETS)}


def registry_for(parent: dict[str, Any], extra_contact: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = base216.completed_registry(parent)
    identities = set(registry["identities"])
    inputs = {target: set(values) for target, values in registry["inputs"].items()}
    if extra_contact:
        identities.add(base216.contact_identity(extra_contact))
        target = extra_contact["target_symbol"]
        inputs.setdefault(target, set()).update(base216.input_key(target, extra_contact["target_path"], extra_contact["abi"], case["input"]) for case in extra_contact["cases"])
    return {"identities": sorted(identities), "inputs": {target: sorted(values) for target, values in sorted(inputs.items())}}


def valid_contact(value: Any, completed: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CONTACT_CORE:
        return {"accepted": False, "reason": "invalid-core"}
    if not all(isinstance(value.get(key), str) and value[key].strip() for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")):
        return {"accepted": False, "reason": "invalid-string"}
    interface = environment_registry().get(value["target_symbol"])
    if not interface or value["target_path"] != interface["target_path"] or value["abi"] != interface["abi"]:
        return {"accepted": False, "reason": "invalid-interface"}
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 4 or len({case.get("case_id") for case in cases if isinstance(case, dict)}) != 4:
        return {"accepted": False, "reason": "invalid-cases"}
    if not all(isinstance(case, dict) and set(case) == {"case_id", "input"} and isinstance(case["case_id"], str) and case["case_id"].strip() and isinstance(case["input"], dict) for case in cases):
        return {"accepted": False, "reason": "invalid-case-shape"}
    if value.get("predicates") != PREDICATES or len(base216.canonical(value)) > 32768:
        return {"accepted": False, "reason": "invalid-predicates-or-size"}
    identity = base216.contact_identity(value)
    if identity in set(completed["identities"]):
        return {"accepted": False, "reason": "already-receipted", "contact_identity": identity}
    prior = set(completed["inputs"].get(value["target_symbol"], []))
    new_count = sum(base216.input_key(value["target_symbol"], value["target_path"], value["abi"], case["input"]) not in prior for case in cases)
    return {"accepted": new_count >= 2, "reason": "executable-unreceipted-contact" if new_count >= 2 else "insufficient-new-inputs", "contact_identity": identity, "new_input_count": new_count}


def installed_source(parent: dict[str, Any]) -> str:
    return parent["semantic_move_capabilities"][-1]["patched_source"]


def write_environment(root: Path, parent: dict[str, Any]) -> None:
    files = {
        "operations/__init__.py": "",
        "operations/system.py": installed_source(parent),
        "operations/reference.py": base215.ordered_source(base215.REFERENCE_SOURCE, base215.ORDER_SCHEDULE[0], ("_best",)),
        "environment-registry.json": json.dumps(environment_registry(), indent=2, sort_keys=True) + "\n",
    }
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute_cases(system_path: Path, reference_path: Path, target: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    system = load_module(system_path, "ot0217_system_" + hashlib.sha256(system_path.read_bytes()).hexdigest()[:12])
    reference = load_module(reference_path, "ot0217_reference_" + hashlib.sha256(reference_path.read_bytes()).hexdigest()[:12])
    rows = []
    for case in cases:
        try:
            observed = getattr(system, target)(copy.deepcopy(case["input"]))
            expected = getattr(reference, target)(copy.deepcopy(case["input"]))
            rows.append({"case_id": case["case_id"], "observed": observed, "expected": expected, "matches": observed == expected, "valid": True})
        except Exception as error:
            rows.append({"case_id": case.get("case_id"), "error_type": type(error).__name__, "matches": False, "valid": False})
    return {"case_count": len(rows), "all_valid": all(row["valid"] for row in rows), "matches": sum(row["matches"] for row in rows), "rows": rows}


def item(identity: str, kind: str, magnitude: int, duration: int, probability: float, effort: int) -> dict[str, Any]:
    names = {"schedule_recovery": "severity", "allocate_relief": "people", "schedule_maintenance": "criticality"}
    row = {"id": identity, names[kind]: magnitude, "effort": effort}
    if kind == "schedule_recovery": row.update(duration=duration, probability=probability)
    elif kind == "allocate_relief": row.update(probability=probability)
    else: row.update(downtime=duration, failure_probability=probability)
    return row


def case(case_id: str, target: str, capacity: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    collections = {"schedule_recovery": "incidents", "allocate_relief": "requests", "schedule_maintenance": "tasks"}
    return {"case_id": case_id, "input": {"capacity": capacity, collections[target]: rows}}


HIDDEN_CASES = {
    target: [
        case(f"{target}-world-1", target, 3, [item("g", target, 9, 1, .2, 3), item("h", target, 6, 7, .9, 3)]),
        case(f"{target}-world-2", target, 4, [item("g", target, 10, 1, .2, 4), item("h", target, 7, 6, .8, 2), item("i", target, 6, 5, .9, 2)]),
        case(f"{target}-world-3", target, 5, [item("g", target, 10, 1, .2, 5), item("h", target, 8, 5, .8, 3), item("i", target, 7, 4, .9, 2)]),
        case(f"{target}-world-4", target, 2, [item("g", target, 8, 8, .8, 2), item("h", target, 10, 1, .2, 2)]),
        case(f"{target}-world-5", target, 4, [item("g", target, 9, 4, .9, 2), item("h", target, 5, 2, .5, 2)]),
        case(f"{target}-world-6", target, 4, [item("g", target, 8, 3, .8, 2), item("h", target, 7, 2, .7, 2)]),
    ] for target in sorted(TARGETS)
}


def contact_template() -> dict[str, Any]:
    return {"contact_id": "replace-contact", "target_path": TARGET_PATH, "target_symbol": "replace-target", "abi": ABI, "stake": "replace-stake", "cases": [], "predicates": copy.deepcopy(PREDICATES)}


CHECKER_SOURCE = '''import copy
import hashlib
import importlib.util
import json
from pathlib import Path
def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def digest(v): return hashlib.sha256(canonical(v)).hexdigest()
def input_key(target,path,abi,value): return digest({"target_symbol":target,"target_path":path,"abi":abi,"input":value})
def identity(c): return digest({"target_symbol":c["target_symbol"],"target_path":c["target_path"],"abi":c["abi"],"case_inputs":sorted(digest(x["input"]) for x in c["cases"]),"predicates":c["predicates"]})
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
root=Path(__file__).parent; contract=json.loads((root/"continuation-contract.json").read_text()); completed=json.loads((root/"completed-contact-registry.json").read_text()); interfaces=json.loads((root/"environment-registry.json").read_text()); d=json.loads((root/"continuation-decision.json").read_text()); core=set(contract["required_decision_fields"]); c=d.get("next_contact") if isinstance(d,dict) else None
shape=isinstance(d,dict) and set(d)==core and isinstance(d.get("next_pursuit"),str) and d["next_pursuit"].strip() and isinstance(c,dict) and set(c)==set(contract["contact_fields"])
if shape:
 interface=interfaces.get(c.get("target_symbol")); cases=c.get("cases"); shape=bool(interface and c.get("target_path")==interface["target_path"] and c.get("abi")==interface["abi"] and all(isinstance(c.get(k),str) and c[k].strip() and not c[k].startswith("replace-") for k in ("contact_id","stake")) and isinstance(cases,list) and len(cases)==4 and len({x.get("case_id") for x in cases if isinstance(x,dict)})==4 and all(isinstance(x,dict) and set(x)=={"case_id","input"} and isinstance(x.get("case_id"),str) and x["case_id"].strip() and isinstance(x.get("input"),dict) for x in cases) and c.get("predicates")==contract["predicates"] and len(canonical(c))<=32768)
if shape:
 ident=identity(c); prior=set(completed["inputs"].get(c["target_symbol"],[])); new=sum(input_key(c["target_symbol"],c["target_path"],c["abi"],x["input"]) not in prior for x in c["cases"]); shape=ident not in set(completed["identities"]) and new>=2 and (not contract.get("forbidden_target") or c["target_symbol"]!=contract["forbidden_target"])
else: ident=None; new=0
if shape and contract["mode"]=="assimilator": shape=d.get("resolved_contact_disposition") in contract["allowed_dispositions"] and d.get("resolved_contact_identity")==contract["resolved_contact_identity"] and d.get("world_receipt_digest")==contract["world_receipt_digest"]
rows=[]
if shape:
 system=load(root/"operations/system.py","system"); reference=load(root/"operations/reference.py","reference")
 for x in c["cases"]:
  try:
   observed=getattr(system,c["target_symbol"])(copy.deepcopy(x["input"])); expected=getattr(reference,c["target_symbol"])(copy.deepcopy(x["input"])); rows.append({"case_id":x["case_id"],"valid":True,"matches":observed==expected})
  except Exception as error: rows.append({"case_id":x.get("case_id"),"valid":False,"matches":False,"error_type":type(error).__name__})
passed=shape and len(rows)==4 and all(x["valid"] for x in rows); print(json.dumps({"passed":bool(passed),"shape_passed":bool(shape),"contact_identity":ident,"new_input_count":new,"matches":sum(x["matches"] for x in rows),"rows":rows},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def projection(parent: dict[str, Any]) -> dict[str, Any]:
    active = authority_base.reuse.worlds.base.active_position(parent)
    active["continuation_liveness"] = copy.deepcopy(parent["continuation_liveness"])
    active["semantic_contact_program"] = copy.deepcopy(parent["semantic_contact_program_capabilities"][-1])
    active["semantic_move_capability"] = copy.deepcopy(parent["semantic_move_capabilities"][-1])
    active["g5_transition"] = copy.deepcopy(parent["evaluation_regime_transitions"][-1])
    if parent.get("pending_contact_bearing_continuations"):
        active["pending_contact_bearing_continuation"] = copy.deepcopy(parent["pending_contact_bearing_continuations"][-1])
    return active


def seed_actor(root: Path, parent: dict[str, Any], completed: dict[str, Any], contract: dict[str, Any], decision_value: dict[str, Any], readme: str, attachments: dict[str, Any] | None = None) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_environment(seed, parent)
    write_json(seed / "subject-position.json", projection(parent))
    write_json(seed / "completed-contact-registry.json", completed)
    write_json(seed / "continuation-contract.json", contract)
    write_json(seed / "continuation-decision.json", decision_value)
    for name, value in (attachments or {}).items():
        write_json(seed / name, value)
    (seed / "check_continuation.py").write_text(CHECKER_SOURCE)
    immutable = ["subject-position.json", "completed-contact-registry.json", "continuation-contract.json", "check_continuation.py", "environment-registry.json", "operations/__init__.py", "operations/system.py", "operations/reference.py", *(attachments or {}).keys(), "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["continuation-decision.json"], "immutable": immutable})
    (seed / "README.md").write_text(readme + " Edit only continuation-decision.json, run python3 check_continuation.py, and inspect the exact diff. Hidden cases are unavailable.\n")
    return seed


def originator_contract() -> dict[str, Any]:
    return {"authority": "ot-0217-originator-contract", "mode": "originator", "required_decision_fields": ["next_pursuit", "next_contact"], "contact_fields": sorted(CONTACT_CORE), "predicates": PREDICATES, "minimum_new_inputs": 2, "forbidden_target": None}


def run_originator(context, prior131, p82, root: Path, parent: dict[str, Any]) -> dict[str, Any]:
    completed = registry_for(parent)
    seed = seed_actor(root, parent, completed, originator_contract(), {"next_pursuit": "replace-next-pursuit", "next_contact": contact_template()}, "Turn the exact liveness-unresolved subject into executable contact from this complete repository without a supplied target.")
    label = "contact-originator"
    output, base_audit, workspace, _ = context.run_actor(label, seed, ORIGINATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision_value = json.loads((workspace / "continuation-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
        contact_check = valid_contact(decision_value.get("next_contact"), completed)
        public = execute_cases(workspace / "operations/system.py", workspace / "operations/reference.py", decision_value["next_contact"]["target_symbol"], decision_value["next_contact"]["cases"]) if contact_check["accepted"] else None
        valid = bool(contact_check["accepted"] and public["all_valid"] and isinstance(decision_value.get("next_pursuit"), str) and decision_value["next_pursuit"].strip())
    except (OSError, json.JSONDecodeError, KeyError):
        decision_value, immutable_ok, contact_check, public, valid = None, False, {"accepted": False}, None, False
    accepted = bool(valid and immutable_ok and output and output.get("action") == "bind-live-contact")
    audit = context.audit_actor(label, output, base_audit, accepted, ["continuation-decision.json"])
    binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": "ot-0217-bound-live-contact", "source_subject_digest": parent["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision_value, "contact_identity": contact_check["contact_identity"], "new_input_count": contact_check["new_input_count"], "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-live-contact.json", binding)
    return {"output": output, "audit": audit, "decision": decision_value, "contact_check": contact_check, "public": public, "binding": binding, "accepted": binding is not None}


def compile_intermediate(parent: dict[str, Any], origin: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    pending = {"authority": "G5-pending-contact-bearing-continuation", "binding_digest": origin["binding"]["binding_digest"], "contact_identity": origin["binding"]["contact_identity"], "package": copy.deepcopy(origin["decision"]["next_contact"]), "package_digest": p82.digest(origin["decision"]["next_contact"]), "consequence_status": "unreceipted"}
    child["pending_contact_bearing_continuations"] = [*child.get("pending_contact_bearing_continuations", []), pending]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": origin["decision"]["next_pursuit"]}
    child["continuation_liveness"] = {"authority": "G5-contact-bearing-continuation-liveness", "status": "live", "contact_identity": pending["contact_identity"], "binding_digest": pending["binding_digest"], "transition_receipt_digest": G5_RECEIPT}
    return p82.seal(child)


def assimilator_contract(origin: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    expected = "retain" if world["outcome"] == "success" else "surrender"
    return {"authority": "ot-0217-assimilator-contract", "mode": "assimilator", "required_decision_fields": ["resolved_contact_disposition", "resolved_contact_identity", "world_receipt_digest", "next_pursuit", "next_contact"], "contact_fields": sorted(CONTACT_CORE), "predicates": PREDICATES, "minimum_new_inputs": 2, "forbidden_target": origin["decision"]["next_contact"]["target_symbol"], "allowed_dispositions": [expected], "resolved_contact_identity": origin["binding"]["contact_identity"], "world_receipt_digest": world["receipt_digest"]}


def run_assimilator(context, prior131, p82, root: Path, intermediate: dict[str, Any], origin: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    completed = registry_for(intermediate, origin["decision"]["next_contact"])
    contract = assimilator_contract(origin, world)
    template = {"resolved_contact_disposition": contract["allowed_dispositions"][0], "resolved_contact_identity": contract["resolved_contact_identity"], "world_receipt_digest": contract["world_receipt_digest"], "next_pursuit": "replace-next-pursuit", "next_contact": contact_template()}
    attachments = {"resolved-contact.json": origin["binding"], "hidden-world-receipt.json": world}
    seed = seed_actor(root, intermediate, completed, contract, template, "Assimilate the exact independently resolved contact and end this turn carrying a different still-unreceipted executable contact chosen from the complete repository.", attachments)
    label = "contact-assimilator"
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision_value = json.loads((workspace / "continuation-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
        contact_check = valid_contact(decision_value.get("next_contact"), completed)
        public = execute_cases(workspace / "operations/system.py", workspace / "operations/reference.py", decision_value["next_contact"]["target_symbol"], decision_value["next_contact"]["cases"]) if contact_check["accepted"] else None
        valid = bool(contact_check["accepted"] and public["all_valid"] and decision_value.get("resolved_contact_disposition") in contract["allowed_dispositions"] and decision_value.get("resolved_contact_identity") == contract["resolved_contact_identity"] and decision_value.get("world_receipt_digest") == contract["world_receipt_digest"] and decision_value["next_contact"]["target_symbol"] != contract["forbidden_target"] and isinstance(decision_value.get("next_pursuit"), str) and decision_value["next_pursuit"].strip())
    except (OSError, json.JSONDecodeError, KeyError):
        decision_value, immutable_ok, contact_check, public, valid = None, False, {"accepted": False}, None, False
    accepted = bool(valid and immutable_ok and output and output.get("action") == "assimilate-and-reopen-contact")
    audit = context.audit_actor(label, output, base_audit, accepted, ["continuation-decision.json"])
    binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": "ot-0217-bound-contact-assimilation", "source_subject_digest": intermediate["artifact_digest"], "resolved_contact_binding_digest": origin["binding"]["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision_value, "next_contact_identity": contact_check["contact_identity"], "next_new_input_count": contact_check["new_input_count"], "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-contact-assimilation.json", binding)
    return {"output": output, "audit": audit, "decision": decision_value, "contact_check": contact_check, "public": public, "binding": binding, "accepted": binding is not None}


def compile_final(intermediate: dict[str, Any], origin: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(intermediate)
    child.pop("artifact_digest", None)
    pending = copy.deepcopy(child["pending_contact_bearing_continuations"])
    pending[-1] = {**pending[-1], "consequence_status": "resolved", "world_receipt_digest": world["receipt_digest"], "disposition": assimilation["decision"]["resolved_contact_disposition"]}
    next_package = assimilation["decision"]["next_contact"]
    next_pending = {"authority": "G5-pending-contact-bearing-continuation", "binding_digest": assimilation["binding"]["binding_digest"], "contact_identity": assimilation["binding"]["next_contact_identity"], "package": copy.deepcopy(next_package), "package_digest": p82.digest(next_package), "consequence_status": "unreceipted"}
    child["pending_contact_bearing_continuations"] = [*pending, next_pending]
    receipt_body = {"authority": "ot-0217-resolved-contact-bearing-continuation", "source_subject_digest": intermediate["artifact_digest"], "contact_binding_digest": origin["binding"]["binding_digest"], "contact_identity": origin["binding"]["contact_identity"], "world_receipt_digest": world["receipt_digest"], "outcome": world["outcome"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["contact_bearing_continuation_receipts"] = [*child.get("contact_bearing_continuation_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": assimilation["decision"]["next_pursuit"]}
    child["continuation_liveness"] = {"authority": "G5-contact-bearing-continuation-liveness", "status": "live", "contact_identity": next_pending["contact_identity"], "binding_digest": next_pending["binding_digest"], "transition_receipt_digest": G5_RECEIPT}
    child["unresolved"] = "Expose the pending different-surface contact to independent consequence, then require another executable reopening."
    return p82.seal(child)


def representative_contact(target: str, suffix: str = "fixture") -> dict[str, Any]:
    return {"contact_id": f"{suffix}-{target.replace('_', '-')}", "target_path": TARGET_PATH, "target_symbol": target, "abi": ABI, "stake": "Test an unreceipted capacity boundary.", "cases": copy.deepcopy(HIDDEN_CASES[target][:4]), "predicates": copy.deepcopy(PREDICATES)}


def main() -> int:
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
    run = (args.evidence_root or store / "runs/OT-0217").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0216", "operational-subject-under-g5-liveness.json")
    result216 = selector_base.load_artifact(p82, repo, store, "OT-0216", "contact-bearing-liveness-transition-aggregate.json")
    completed = registry_for(parent)
    fixture_root = run.parent / "OT-0217-preflight"
    if fixture_root.exists():
        import shutil
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    write_environment(fixture_root, parent)
    hidden = {target: execute_cases(fixture_root / "operations/system.py", fixture_root / "operations/reference.py", target, cases) for target, cases in HIDDEN_CASES.items()}
    valid_contacts = {target: valid_contact(representative_contact(target), completed) for target in sorted(TARGETS)}
    completed_schedule = parent["semantic_move_capabilities"][-1]["package"]
    renamed = {"contact_id": "renamed-completed", "target_path": completed_schedule["target_path"], "target_symbol": completed_schedule["target_symbol"], "abi": ABI, "stake": "Renamed completed contact.", "cases": [{"case_id": f"renamed-{index}", "input": copy.deepcopy(case_value["input"])} for index, case_value in enumerate(reversed(completed_schedule["cases"]), 1)], "predicates": copy.deepcopy(PREDICATES)}
    controls = {"template_rejected": not valid_contact(contact_template(), completed)["accepted"], "renamed_completed_rejected": not valid_contact(renamed, completed)["accepted"], "all_three_new_contacts_valid": all(row["accepted"] and row["new_input_count"] == 4 for row in valid_contacts.values())}
    fixture_origin_decision = {"next_pursuit": "Resolve a fresh recovery-capacity contact.", "next_contact": representative_contact("schedule_recovery", "origin")}
    origin_seed = seed_actor(fixture_root / "origin-checker", parent, completed, originator_contract(), fixture_origin_decision, "Fixture")
    origin_checker = subprocess.run(["python3", "check_continuation.py"], cwd=origin_seed, capture_output=True)
    fixture_origin_check = valid_contact(fixture_origin_decision["next_contact"], completed)
    fixture_origin = {"decision": fixture_origin_decision, "binding": {"binding_digest": "a" * 64, "contact_identity": fixture_origin_check["contact_identity"]}}
    prospective_intermediate = compile_intermediate(parent, fixture_origin, p82)
    fixture_world = {"outcome": "success", "receipt_digest": "b" * 64}
    assimilation_completed = registry_for(prospective_intermediate, fixture_origin_decision["next_contact"])
    fixture_assim_contact = representative_contact("allocate_relief", "assimilation")
    fixture_assim_check = valid_contact(fixture_assim_contact, assimilation_completed)
    fixture_assim_decision = {"resolved_contact_disposition": "retain", "resolved_contact_identity": fixture_origin_check["contact_identity"], "world_receipt_digest": fixture_world["receipt_digest"], "next_pursuit": "Resolve a fresh relief-capacity contact.", "next_contact": fixture_assim_contact}
    fixture_assim = {"decision": fixture_assim_decision, "binding": {"binding_digest": "c" * 64, "next_contact_identity": fixture_assim_check["contact_identity"]}}
    assimilation_seed = seed_actor(fixture_root / "assimilation-checker", prospective_intermediate, assimilation_completed, assimilator_contract(fixture_origin, fixture_world), fixture_assim_decision, "Fixture", {"resolved-contact.json": fixture_origin["binding"], "hidden-world-receipt.json": fixture_world})
    assimilation_checker = subprocess.run(["python3", "check_continuation.py"], cwd=assimilation_seed, capture_output=True)
    prospective_final = compile_final(prospective_intermediate, fixture_origin, fixture_world, fixture_assim, p82)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    schema_text = ORIGINATOR_SCHEMA.read_text() + ASSIMILATOR_SCHEMA.read_text()
    checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_operational_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and parent["continuation_liveness"]["status"] == "unresolved" and runtime.identity_conforms(parent), "ot0216_exact_promotion": result216["observer_disposition"] == "promoted" and result216["final_subject_digest"] == PARENT_DIGEST, "g5_transition_exact": parent["evaluation_regime_transitions"][-1]["receipt_digest"] == G5_RECEIPT, "installed_source_exact": installed_source(parent) == parent["semantic_move_capabilities"][-1]["patched_source"], "registry_exact_three": set(environment_registry()) == TARGETS, "hidden_schedule_6_of_6": hidden["schedule_recovery"]["all_valid"] and hidden["schedule_recovery"]["matches"] == 6, "hidden_other_surfaces_2_of_6": all(hidden[target]["all_valid"] and hidden[target]["matches"] == 2 for target in TARGETS - {"schedule_recovery"}), "g5_controls_passed": all(controls.values()), "originator_checker_passed": origin_checker.returncode == 0, "assimilator_checker_passed": assimilation_checker.returncode == 0 and fixture_assim_check["accepted"], "prospective_intermediate_conforms": runtime.identity_conforms(prospective_intermediate) and prospective_intermediate["continuation_liveness"]["status"] == "live", "prospective_final_conforms": runtime.identity_conforms(prospective_final) and prospective_final["continuation_liveness"]["status"] == "live" and prospective_final["pending_contact_bearing_continuations"][-1]["contact_identity"] == fixture_assim_check["contact_identity"], "schemas_supported": ORIGINATOR_SCHEMA.is_file() and ASSIMILATOR_SCHEMA.is_file() and "uniqueItems" not in schema_text, "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0217-preflight", "source_subject_digest": parent["artifact_digest"], "environment_registry": environment_registry(), "completed_registry_digest": p82.digest(completed), "hidden_results": hidden, "valid_contact_fixtures": valid_contacts, "controls": controls, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0217 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    origin = run_originator(context, prior131, p82, run / "originator", parent)
    intermediate = parent
    intermediate_ok = False
    if origin["accepted"]:
        candidate = compile_intermediate(parent, origin, p82)
        intermediate_ok = runtime.identity_conforms(candidate)
        if intermediate_ok:
            intermediate = candidate
            write_json(run / "intermediate-live-subject.json", intermediate)
    world = None
    if intermediate_ok:
        target = origin["decision"]["next_contact"]["target_symbol"]
        result = execute_cases(fixture_root / "operations/system.py", fixture_root / "operations/reference.py", target, HIDDEN_CASES[target])
        actor_success = result["all_valid"] and result["matches"] >= origin["decision"]["next_contact"]["predicates"]["success"]["minimum_confirmations"]
        outcome = "success" if actor_success else ("surrender" if result["all_valid"] and result["matches"] <= origin["decision"]["next_contact"]["predicates"]["surrender"]["maximum_confirmations"] else "unresolved")
        body = {"authority": "ot-0217-sealed-contact-world", "source_subject_digest": intermediate["artifact_digest"], "contact_binding_digest": origin["binding"]["binding_digest"], "contact_identity": origin["binding"]["contact_identity"], "target_symbol": target, "hidden_cases_digest": p82.digest(HIDDEN_CASES[target]), "result": result, "outcome": outcome, "world_promotion_gate": result["all_valid"] and result["matches"] >= 4}
        world = {**body, "receipt_digest": p82.digest(body)}
        write_json(run / "hidden-world-receipt.json", world)
    assimilation = run_assimilator(context, prior131, p82, run / "assimilation", intermediate, origin, world) if world and world["outcome"] in {"success", "surrender"} and world["world_promotion_gate"] else None
    final = intermediate
    final_ok = False
    if assimilation and assimilation["accepted"]:
        candidate = compile_final(intermediate, origin, world, assimilation, p82)
        final_ok = runtime.identity_conforms(candidate)
        if final_ok: final = candidate
    replay = bool(final_ok and valid_contact(final["pending_contact_bearing_continuations"][-1]["package"], registry_for(final, origin["decision"]["next_contact"]))["accepted"])
    gates = {"preflight_passed": checks["passed"], "originator_accepted": origin["accepted"], "intermediate_live_subject_conforms": intermediate_ok, "independent_world_decisive": bool(world and world["outcome"] in {"success", "surrender"} and world["world_promotion_gate"]), "assimilator_accepted": bool(assimilation and assimilation["accepted"]), "different_target_pending_contact": bool(assimilation and assimilation["accepted"] and assimilation["decision"]["next_contact"]["target_symbol"] != origin["decision"]["next_contact"]["target_symbol"]), "pending_contact_replay": replay, "final_subject_identity_conforms": final_ok, "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    gates["passed"] = all(gates.values())
    if not gates["passed"] and not final_ok: final = intermediate
    result = {"authority": "ot-0217-two-handoff-contact-bearing-continuation", "source_subject_digest": parent["artifact_digest"], "originator": p82.compact(origin), "intermediate_subject_digest": intermediate["artifact_digest"], "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final.get("continuation_liveness"), "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 + (1 if assimilation else 0)}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
