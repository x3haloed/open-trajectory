from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0219_behavioral_abi_projected_contact_identity.py"
BASE_SHA256 = "51c5f904ca0cc5ce9a388a7492425858fe17f9e20788abfd4ecb144407d90d00"
PARENT_DIGEST = "71e5b9170541f8fb531b8ba5ff99b9e3448a1b4f871c5d4722d64d8966e4002a"
OT219_RECEIPT = "6c0a654829a63f85b32c5f7bfc15cd38d7689cf16d75e785e615cf010f1cb55d"
DRIVER_VERSION = "ot-0220-fixed-g6-recurrence-v1"
ENCOUNTER_LIMIT = 2
ACTOR_LIMIT = 4
ORIGINATOR_SCHEMA = REPO / "spec/ot-0217-originator.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0217-assimilator.schema.json"
CORRECTOR_SCHEMA = REPO / "spec/ot-0218-corrector.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0219 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0220_frozen_ot0219", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base219 = load_base()
base218 = base219.base218
base217 = base219.base217
base216 = base219.base216
base215 = base219.base215
base213 = base219.base213
authority_base = base219.authority_base
PREDICATES = base219.PREDICATES
ABI = base219.ABI


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def installed_source(subject: dict[str, Any]) -> str:
    return subject["semantic_move_capabilities"][-1]["patched_source"]


def available_at(root: Path, subject: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    base218.write_environment(root, installed_source(subject))
    return base219.functions(root / "operations/system.py", root / "operations/reference.py")


def add_contact(registry: dict[str, Any], contact: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> None:
    identity = base219.projected_identity(contact, available)
    registry["identities"].add(identity)
    installed, reference = available[contact["target_symbol"]]
    values = registry["inputs"].setdefault(contact["target_symbol"], set())
    values.update(base219.digest(base219.behavioral_projection(case["input"], installed, reference)) for case in contact["cases"])


def completed_registry(subject: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    registry = base219.completed_registry(subject, available)
    for pending in subject.get("pending_contact_bearing_continuations", []):
        if pending.get("consequence_status") not in {None, "unreceipted"}:
            add_contact(registry, pending["package"], available)
    return registry


def serial_registry(registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "identities": sorted(registry["identities"]),
        "inputs": {key: sorted(value) for key, value in sorted(registry["inputs"].items())},
    }


G6_CHECKER = r'''import copy, hashlib, importlib.util, json, re
from pathlib import Path
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def digest(v): return hashlib.sha256(canon(v)).hexdigest()
def load(path,name):
 s=importlib.util.spec_from_file_location(name+hashlib.sha256(path.read_bytes()).hexdigest()[:8],path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
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
  if not changed: return v
def safe(v,depth=0):
 if depth>4: return False
 if v is None or isinstance(v,(bool,int,float,str)): return True
 if isinstance(v,list): return len(v)<=32 and all(safe(x,depth+1) for x in v)
 if isinstance(v,dict): return len(v)<=32 and all(isinstance(k,str) and safe(x,depth+1) for k,x in v.items())
 return False
root=Path(__file__).parent; contract=json.loads((root/"continuation-contract.json").read_text()); registry=json.loads((root/"completed-contact-registry.json").read_text()); interfaces=json.loads((root/"environment-registry.json").read_text()); d=json.loads((root/"continuation-decision.json").read_text()); system=load(root/"operations/system.py","system"); reference=load(root/"operations/reference.py","reference"); c=d.get("next_contact") if isinstance(d,dict) else None
required=set(contract["required_decision_fields"]); extras={k:v for k,v in d.items() if k not in required} if isinstance(d,dict) else {}; shape=isinstance(d,dict) and required.issubset(d) and len(extras)<=8 and all(re.fullmatch(r"[a-z][a-z0-9_]{0,47}",k) and safe(v) for k,v in extras.items()) and isinstance(d.get("next_pursuit"),str) and d["next_pursuit"].strip() and isinstance(c,dict) and set(c)==set(contract["contact_fields"])
if shape:
 interface=interfaces.get(c.get("target_symbol")); cases=c.get("cases"); shape=bool(interface and c.get("target_path")==interface["target_path"] and c.get("abi")==interface["abi"] and all(isinstance(c.get(k),str) and c[k].strip() and not c[k].startswith("replace-") for k in ("contact_id","stake")) and isinstance(cases,list) and len(cases)==4 and len({x.get("case_id") for x in cases if isinstance(x,dict)})==4 and all(isinstance(x,dict) and set(x)=={"case_id","input"} and isinstance(x.get("case_id"),str) and x["case_id"].strip() and isinstance(x.get("input"),dict) for x in cases) and c.get("predicates")==contract["predicates"] and len(canon(c))<=32768)
if shape:
 a=getattr(system,c["target_symbol"]); b=getattr(reference,c["target_symbol"]); projected=[project(x["input"],a,b) for x in c["cases"]]; ident=digest({"target_symbol":c["target_symbol"],"target_path":c["target_path"],"abi":c["abi"],"case_inputs":sorted(digest(x) for x in projected),"predicates":c["predicates"]}); prior=set(registry["inputs"].get(c["target_symbol"],[])); new=sum(digest(x) not in prior for x in projected); shape=ident not in set(registry["identities"]) and new>=2 and (not contract.get("forbidden_target") or c["target_symbol"]!=contract["forbidden_target"])
else: ident=None; new=0
if shape and contract["mode"]=="assimilator": shape=d.get("resolved_contact_disposition") in contract["allowed_dispositions"] and d.get("resolved_contact_identity")==contract["resolved_contact_identity"] and d.get("world_receipt_digest")==contract["world_receipt_digest"]
rows=[]
if shape:
 for x in c["cases"]:
  try: rows.append({"case_id":x["case_id"],"valid":True,"matches":getattr(system,c["target_symbol"])(copy.deepcopy(x["input"]))==getattr(reference,c["target_symbol"])(copy.deepcopy(x["input"]))})
  except Exception as e: rows.append({"case_id":x.get("case_id"),"valid":False,"matches":False,"error_type":type(e).__name__})
passed=shape and len(rows)==4 and all(x["valid"] for x in rows); print(json.dumps({"passed":bool(passed),"shape_passed":bool(shape),"projected_identity":ident,"new_input_count":new,"matches":sum(x["matches"] for x in rows),"rows":rows},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def driver_state(subject: dict[str, Any]) -> dict[str, Any]:
    return subject["fixed_g6_recurrence_driver"]


def dispatch(subject: dict[str, Any]) -> str:
    state = driver_state(subject)
    phase = state["phase"]
    if phase not in {"originate", "contact", "correct", "assimilate", "observer-stop", "surrendered"}:
        raise ValueError("invalid driver phase")
    return phase


def install_driver(parent: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["fixed_g6_recurrence_driver"] = {
        "authority": DRIVER_VERSION,
        "phase": "originate",
        "encounters": 0,
        "accepted_actors": 0,
        "corrected_contradictions": 0,
        "last_target": None,
        "history": [],
        "observation_limit": ENCOUNTER_LIMIT,
        "actor_limit": ACTOR_LIMIT,
    }
    return p82.seal(child)


def contact_template() -> dict[str, Any]:
    return base217.contact_template()


def seed_contact_actor(root: Path, subject: dict[str, Any], registry: dict[str, Any], mode: str, contract: dict[str, Any], template: dict[str, Any], attachments: dict[str, Any]) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    base217.write_environment(seed, subject)
    write_json(seed / "subject-position.json", base217.projection(subject))
    write_json(seed / "completed-contact-registry.json", serial_registry(registry))
    write_json(seed / "continuation-contract.json", contract)
    write_json(seed / "continuation-decision.json", template)
    for name, value in attachments.items(): write_json(seed / name, value)
    (seed / "check_continuation.py").write_text(G6_CHECKER)
    immutable = ["subject-position.json", "completed-contact-registry.json", "continuation-contract.json", "check_continuation.py", "environment-registry.json", "operations/__init__.py", "operations/system.py", "operations/reference.py", *attachments.keys(), "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["continuation-decision.json"], "immutable": immutable})
    prompt = "Turn the exact liveness-unresolved subject into genuinely behaviorally new executable contact from this complete repository without a supplied target." if mode == "originator" else "Assimilate the exact independent consequence and end carrying genuinely behaviorally new executable contact on a different target."
    (seed / "README.md").write_text(prompt + " Edit only continuation-decision.json, run python3 check_continuation.py, and inspect the exact diff. Hidden cases are unavailable.\n")
    return seed


def contact_contract(mode: str, forbidden: str | None = None, identity: str | None = None, receipt: str | None = None, disposition: str | None = None) -> dict[str, Any]:
    fields = ["next_pursuit", "next_contact"]
    result = {"authority": DRIVER_VERSION, "mode": mode, "required_decision_fields": fields, "contact_fields": sorted(base219.CONTACT_CORE), "predicates": PREDICATES, "forbidden_target": forbidden}
    if mode == "assimilator":
        result.update(required_decision_fields=["resolved_contact_disposition", "resolved_contact_identity", "world_receipt_digest", *fields], allowed_dispositions=[disposition], resolved_contact_identity=identity, world_receipt_digest=receipt)
    return result


def run_contact_actor(context, prior131, p82, root: Path, subject: dict[str, Any], mode: str, resolved: dict[str, Any] | None = None) -> dict[str, Any]:
    env = root / "registry-environment"
    env.mkdir(parents=True)
    available = available_at(env, subject)
    registry = completed_registry(subject, available)
    attachments: dict[str, Any] = {}
    if mode == "originator":
        contract = contact_contract(mode)
        template = {"next_pursuit": "replace-next-pursuit", "next_contact": contact_template()}
        label, schema, action = "recurrence-originator", ORIGINATOR_SCHEMA, "bind-live-contact"
    else:
        contract = contact_contract(mode, resolved["target_symbol"], resolved["contact_identity"], resolved["receipt_digest"], resolved["disposition"])
        template = {"resolved_contact_disposition": resolved["disposition"], "resolved_contact_identity": resolved["contact_identity"], "world_receipt_digest": resolved["receipt_digest"], "next_pursuit": "replace-next-pursuit", "next_contact": contact_template()}
        attachments = {"resolved-contact.json": resolved}
        label, schema, action = f"recurrence-assimilator-{driver_state(subject)['encounters']}", ASSIMILATOR_SCHEMA, "assimilate-and-reopen-contact"
    seed = seed_contact_actor(root, subject, registry, mode, contract, template, attachments)
    output, base_audit, workspace, _ = context.run_actor(label, seed, schema, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "continuation-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        check = base219.g6(decision, registry, available)
        public = base217.execute_cases(workspace / "operations/system.py", workspace / "operations/reference.py", decision["next_contact"]["target_symbol"], decision["next_contact"]["cases"]) if check["accepted"] else None
        exact = mode == "originator" or (decision.get("resolved_contact_disposition") == resolved["disposition"] and decision.get("resolved_contact_identity") == resolved["contact_identity"] and decision.get("world_receipt_digest") == resolved["receipt_digest"] and decision["next_contact"]["target_symbol"] != resolved["target_symbol"])
        valid = bool(check["accepted"] and public and public["all_valid"] and immutable_ok and exact)
    except (OSError, json.JSONDecodeError, KeyError):
        decision, check, public, valid = None, {"accepted": False}, None, False
    accepted = bool(valid and output and output.get("action") == action)
    audit = context.audit_actor(label, output, base_audit, accepted, ["continuation-decision.json"])
    binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": DRIVER_VERSION + "-bound-" + mode, "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision, "projected_contact_identity": check["projected_identity"], "new_projected_input_count": check["new_input_count"], "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-contact-action.json", binding)
    return {"accepted": binding is not None, "binding": binding, "decision": decision, "contact_check": check, "public": public, "audit": audit, "output": output}


def compile_pending(subject: dict[str, Any], action: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None)
    package = action["decision"]["next_contact"]
    pending = {"authority": "G6-pending-contact-bearing-continuation", "binding_digest": action["binding"]["binding_digest"], "contact_identity": action["binding"]["projected_contact_identity"], "package": copy.deepcopy(package), "package_digest": p82.digest(package), "consequence_status": "unreceipted"}
    child["pending_contact_bearing_continuations"] = [*child.get("pending_contact_bearing_continuations", []), pending]
    state = copy.deepcopy(driver_state(subject)); state.update(phase="contact", accepted_actors=state["accepted_actors"] + 1, last_target=package["target_symbol"]); child["fixed_g6_recurrence_driver"] = state
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": action["decision"]["next_pursuit"]}
    child["continuation_liveness"] = {"authority": "G6-behavioral-ABI-projected-contact-identity", "status": "live", "contact_identity": pending["contact_identity"], "binding_digest": pending["binding_digest"], "transition_receipt_digest": child["evaluation_regime_transitions"][-1]["receipt_digest"]}
    child["unresolved"] = "Expose the exact pending G6 contact to independent consequence under the fixed recurrence driver."
    return p82.seal(child)


def execute_hidden(root: Path, subject: dict[str, Any], contact: dict[str, Any], encounter: int, p82) -> dict[str, Any]:
    available_at(root, subject)
    target = contact["target_symbol"]
    cases = copy.deepcopy(base217.HIDDEN_CASES[target])
    for index, case in enumerate(cases, 1): case["case_id"] = f"encounter-{encounter}-{target}-{index}"
    result = base217.execute_cases(root / "operations/system.py", root / "operations/reference.py", target, cases)
    outcome = "success" if result["all_valid"] and result["matches"] >= 4 else ("surrender" if result["all_valid"] and result["matches"] == 0 else "unresolved")
    body = {"authority": DRIVER_VERSION + "-sealed-world", "source_subject_digest": subject["artifact_digest"], "contact_identity": subject["pending_contact_bearing_continuations"][-1]["contact_identity"], "target_symbol": target, "encounter": encounter, "hidden_cases_digest": p82.digest(cases), "result": result, "outcome": outcome}
    return {**body, "receipt_digest": p82.digest(body)}


def compile_world(subject: dict[str, Any], world: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None)
    pending = copy.deepcopy(child["pending_contact_bearing_continuations"]); pending[-1] = {**pending[-1], "consequence_status": world["outcome"], "world_receipt_digest": world["receipt_digest"]}; child["pending_contact_bearing_continuations"] = pending
    child["g6_recurrence_world_receipts"] = [*child.get("g6_recurrence_world_receipts", []), world]
    state = copy.deepcopy(driver_state(subject)); state["encounters"] += 1; state["phase"] = "correct" if world["outcome"] == "unresolved" else "assimilate"; state["history"] = [*state["history"], {"encounter": world["encounter"], "target": world["target_symbol"], "outcome": world["outcome"], "receipt_digest": world["receipt_digest"]}]; child["fixed_g6_recurrence_driver"] = state
    child["continuation_liveness"] = {"authority": "G6-behavioral-ABI-projected-contact-identity", "status": "unresolved" if world["outcome"] == "unresolved" else "awaiting-reopening", "resolved_contact_identity": world["contact_identity"], "world_receipt_digest": world["receipt_digest"], "transition_receipt_digest": child["evaluation_regime_transitions"][-1]["receipt_digest"]}
    return p82.seal(child)


def followup_cases(target: str) -> list[dict[str, Any]]:
    rows = [
        (3, [(9, 1, .25, 3), (6, 9, .85, 3)]),
        (4, [(10, 1, .25, 4), (7, 8, .75, 2), (6, 6, .9, 2)]),
        (5, [(10, 1, .2, 5), (8, 7, .8, 3), (7, 5, .9, 2)]),
        (2, [(8, 10, .8, 2), (10, 1, .2, 2)]),
        (4, [(9, 6, .9, 2), (5, 2, .5, 2)]),
        (4, [(8, 5, .8, 2), (7, 3, .7, 2)]),
    ]
    result = []
    for index, (capacity, values) in enumerate(rows, 1):
        items = [base217.item(chr(105 + n), target, magnitude, duration, probability, effort) for n, (magnitude, duration, probability, effort) in enumerate(values)]
        result.append(base217.case(f"followup-{target}-{index}", target, capacity, items))
    return result


def corrected_fixture_source(subject: dict[str, Any], target: str) -> str:
    current = base215.function_sources(installed_source(subject))
    fixture = base215.function_sources(base215.corrected_fixture_source(base215.ORDER_SCHEDULE[0], target))
    current[target] = fixture[target]
    return "\n\n\n".join(current[name] for name in ("expected_loss", "schedule_recovery", "allocate_relief", "schedule_maintenance")) + "\n"


def correction_seed(root: Path, subject: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "seed"; seed.mkdir(parents=True)
    base218.write_environment(seed, installed_source(subject))
    pending = subject["pending_contact_bearing_continuations"][-1]; target = pending["package"]["target_symbol"]
    contract = {"authority": DRIVER_VERSION + "-correction", "required_fields": sorted(base218.CORRECTION_CORE), "allowed_dispositions": ["revise", "surrender"], "required_identities": {"source_subject_digest": subject["artifact_digest"], "contact_binding_digest": pending["binding_digest"], "contact_identity": pending["contact_identity"], "world_receipt_digest": world["receipt_digest"]}, "target_symbol": target, "predicates": base218.CORRECTION_PREDICATES}
    decision = {"disposition": "revise", **contract["required_identities"], "target_symbol": target, "predicates": base218.CORRECTION_PREDICATES, "rationale": "replace-rationale", "next_pursuit": "replace-next-pursuit"}
    write_json(seed / "subject-position.json", base217.projection(subject)); write_json(seed / "bound-contact.json", {"decision": {"next_contact": pending["package"]}, "binding_digest": pending["binding_digest"], "contact_identity": pending["contact_identity"]}); write_json(seed / "unresolved-world-receipt.json", world); write_json(seed / "correction-contract.json", contract); write_json(seed / "correction-decision.json", decision)
    (seed / "check_correction.py").write_text(base218.CHECK_CORRECTION_SOURCE.replace(f'root=Path(__file__).parent; c=', f'root=Path(__file__).parent; c='))
    immutable = ["subject-position.json", "bound-contact.json", "unresolved-world-receipt.json", "correction-contract.json", "check_correction.py", "operations/__init__.py", "operations/baseline.py", "operations/reference.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["operations/system.py", "correction-decision.json"], "immutable": immutable})
    (seed / "README.md").write_text(f"Continue the exact unresolved {target} contact. Revise only {target} or surrender it under correction-contract.json. Edit only operations/system.py and correction-decision.json, run python3 check_correction.py, and inspect the exact diff. Follow-up hidden cases are unavailable.\n")
    return seed


def run_corrector(context, prior131, p82, root: Path, subject: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    seed = correction_seed(root, subject, world); target = world["target_symbol"]; label = f"recurrence-corrector-{driver_state(subject)['encounters']}"
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "correction-decision.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable); source = (workspace / "operations/system.py").read_text(); exact = all(decision.get(k) == v for k, v in json.loads((seed / "correction-contract.json").read_text())["required_identities"].items()) and decision.get("target_symbol") == target and decision.get("predicates") == base218.CORRECTION_PREDICATES and decision.get("disposition") in {"revise", "surrender"}; local = source == installed_source(subject) if decision.get("disposition") == "surrender" else base215.target_only_change(source, installed_source(subject), target); public = base217.execute_cases(workspace / "operations/system.py", workspace / "operations/reference.py", target, subject["pending_contact_bearing_continuations"][-1]["package"]["cases"]) if exact and local and decision.get("disposition") == "revise" else None; valid = bool(exact and local and immutable_ok and (decision["disposition"] == "surrender" or (public and public["all_valid"] and public["matches"] == 4)))
    except (OSError, json.JSONDecodeError, KeyError): decision, source, public, valid = None, None, None, False
    accepted = bool(valid and output and output.get("action") == "correct-unresolved-contact"); expected = ["correction-decision.json", "operations/system.py"] if decision and decision.get("disposition") == "revise" else ["correction-decision.json"]; audit = context.audit_actor(label, output, base_audit, accepted, expected); binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": DRIVER_VERSION + "-bound-correction", "source_subject_digest": subject["artifact_digest"], "contact_identity": world["contact_identity"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision, "patched_source": source if decision["disposition"] == "revise" else None, "patched_source_digest": p82.digest(source) if decision["disposition"] == "revise" else None, "public_result": public}; binding = {**body, "binding_digest": p82.digest(body)}; write_json(context.evidence(label) / "bound-correction.json", binding)
    return {"accepted": binding is not None, "binding": binding, "decision": decision, "audit": audit, "output": output}


def evaluate_correction(root: Path, subject: dict[str, Any], correction: dict[str, Any], world: dict[str, Any], p82) -> dict[str, Any]:
    root.mkdir(parents=True); base218.write_environment(root, installed_source(subject)); target = world["target_symbol"]; cases = followup_cases(target)
    if correction["decision"]["disposition"] == "revise": (root / "operations/system.py").write_text(correction["binding"]["patched_source"]); observed = base217.execute_cases(root / "operations/system.py", root / "operations/reference.py", target, cases); unchanged = base217.execute_cases(root / "operations/baseline.py", root / "operations/reference.py", target, cases); passed = observed["all_valid"] and observed["matches"] == 6 and unchanged["matches"] <= 2; outcome = "success" if passed else "unresolved"
    else: observed, unchanged, passed, outcome = None, None, True, "surrender"
    body = {"authority": DRIVER_VERSION + "-sealed-correction-world", "source_subject_digest": subject["artifact_digest"], "unresolved_world_receipt_digest": world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "target_symbol": target, "followup_cases_digest": p82.digest(cases), "result": observed, "unchanged_control": unchanged, "outcome": outcome, "promotion_gate": passed}; return {**body, "receipt_digest": p82.digest(body)}


def compile_correction(subject: dict[str, Any], correction: dict[str, Any], followup: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); pending = copy.deepcopy(child["pending_contact_bearing_continuations"]); pending[-1] = {**pending[-1], "consequence_status": "resolved-after-correction", "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}; child["pending_contact_bearing_continuations"] = pending
    if correction["decision"]["disposition"] == "revise": child["semantic_move_capabilities"] = [*child["semantic_move_capabilities"], {"authority": DRIVER_VERSION + "-world-admitted-correction", "target_symbol": followup["target_symbol"], "package": copy.deepcopy(pending[-1]["package"]), "patched_source": correction["binding"]["patched_source"], "patched_source_digest": correction["binding"]["patched_source_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "world_receipt_digest": followup["receipt_digest"]}]
    receipt_body = {"authority": DRIVER_VERSION + "-correction-receipt", "source_subject_digest": subject["artifact_digest"], "contact_identity": pending[-1]["contact_identity"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}; receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}; child["unresolved_contact_correction_receipts"] = [*child.get("unresolved_contact_correction_receipts", []), receipt]
    state = copy.deepcopy(driver_state(subject)); state.update(phase="assimilate", accepted_actors=state["accepted_actors"] + 1, corrected_contradictions=state["corrected_contradictions"] + 1); child["fixed_g6_recurrence_driver"] = state; child["continuation_liveness"] = {"authority": "G6-behavioral-ABI-projected-contact-identity", "status": "awaiting-reopening", "resolved_contact_identity": pending[-1]["contact_identity"], "correction_receipt_digest": receipt["receipt_digest"], "transition_receipt_digest": child["evaluation_regime_transitions"][-1]["receipt_digest"]}
    return p82.seal(child)


def resolved_for_assimilation(subject: dict[str, Any]) -> dict[str, Any]:
    pending = subject["pending_contact_bearing_continuations"][-1]
    if pending["consequence_status"] == "resolved-after-correction": receipt = pending["followup_world_receipt_digest"]
    else: receipt = pending["world_receipt_digest"]
    return {"target_symbol": pending["package"]["target_symbol"], "contact_identity": pending["contact_identity"], "receipt_digest": receipt, "disposition": pending.get("disposition", "retain")}


def observer_stop(subject: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); state = copy.deepcopy(driver_state(subject)); state["phase"] = "observer-stop"; child["fixed_g6_recurrence_driver"] = state; return p82.seal(child)


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0220").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0219", "operational-subject-under-g6-projection.json"); result219 = selector_base.load_artifact(p82, repo, store, "OT-0219", "behavioral-abi-projection-transition-aggregate.json")
    fixture_root = run.parent / "OT-0220-preflight"; import shutil; shutil.rmtree(fixture_root, ignore_errors=True); fixture_root.mkdir(parents=True); available = available_at(fixture_root / "environment", parent); registry = completed_registry(parent, available); stale = base219.g6(base219.decision(parent["continuation"]["next_opening"], parent["pending_contact_bearing_continuations"][-1]["package"]), registry, available); relief = base217.representative_contact("allocate_relief", "ot220-fixture"); live = base219.g6(base219.decision("Open relief contact.", relief), registry, available)
    seeded = install_driver(parent, p82); fixture_binding = {"binding_digest": "a" * 64, "projected_contact_identity": live.get("projected_identity"), "decision": {"next_pursuit": "Continue relief contact.", "next_contact": relief}}; fixture_action = {"decision": fixture_binding["decision"], "binding": fixture_binding}; pending = compile_pending(seeded, fixture_action, p82); fixture_world = execute_hidden(fixture_root / "hidden", pending, relief, 1, p82); contacted = compile_world(pending, fixture_world, p82); corrected_source = corrected_fixture_source(contacted, "allocate_relief"); correction_root = fixture_root / "correction"; available_at(correction_root, contacted); (correction_root / "operations/system.py").write_text(corrected_source); corrected_eval = base217.execute_cases(correction_root / "operations/system.py", correction_root / "operations/reference.py", "allocate_relief", followup_cases("allocate_relief")); unchanged_eval = base217.execute_cases(correction_root / "operations/baseline.py", correction_root / "operations/reference.py", "allocate_relief", followup_cases("allocate_relief"))
    actor_fixture = seed_contact_actor(fixture_root / "actor-checker", seeded, registry, "originator", contact_contract("originator"), fixture_binding["decision"], {}); actor_checker = subprocess.run(["python3", "check_continuation.py"], cwd=actor_fixture, capture_output=True)
    correction_fixture = correction_seed(fixture_root / "correction-checker", contacted, fixture_world); (correction_fixture / "operations/system.py").write_text(corrected_source); correction_decision = json.loads((correction_fixture / "correction-decision.json").read_text()); correction_decision.update(rationale="Expected relief consequence includes probability.", next_pursuit="Recheck corrected relief allocation."); write_json(correction_fixture / "correction-decision.json", correction_decision); correction_checker = subprocess.run(["python3", "check_correction.py"], cwd=correction_fixture, capture_output=True)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"]); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor()); schema_text = ORIGINATOR_SCHEMA.read_text() + ASSIMILATOR_SCHEMA.read_text() + CORRECTOR_SCHEMA.read_text()
    checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0219_exact_promotion": result219["observer_disposition"] == "promoted" and result219["receipt_digest"] == OT219_RECEIPT and result219["final_subject_digest"] == PARENT_DIGEST, "g6_transition_exact": parent["evaluation_regime_transitions"][-1]["to_regime"] == "G6-behavioral-ABI-projected-contact-identity", "stale_pending_rejected": not stale["accepted"] and stale["reason"] == "already-receipted-projected-contact", "genuine_relief_admitted": live["accepted"] and live["new_input_count"] == 4, "actor_g6_checker_passed": actor_checker.returncode == 0, "correction_checker_passed": correction_checker.returncode == 0, "dispatch_seed_originates": dispatch(seeded) == "originate", "dispatch_pending_contacts": dispatch(pending) == "contact", "dispatch_unresolved_corrects": fixture_world["outcome"] == "unresolved" and dispatch(contacted) == "correct", "fixture_relief_2_of_6": fixture_world["result"]["matches"] == 2, "fixture_correction_6_of_6": corrected_eval["matches"] == 6 and unchanged_eval["matches"] == 2, "prospective_states_conform": all(runtime.identity_conforms(value) for value in (seeded, pending, contacted)), "schemas_supported": all(path.is_file() for path in (ORIGINATOR_SCHEMA, ASSIMILATOR_SCHEMA, CORRECTOR_SCHEMA)) and "uniqueItems" not in schema_text, "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); fixtures = {"authority": DRIVER_VERSION + "-preflight", "source_subject_digest": parent["artifact_digest"], "stale_pending": stale, "genuine_relief": live, "fixture_world": fixture_world, "corrected_followup": corrected_eval, "unchanged_followup": unchanged_eval, "checks": checks}
    if args.preflight_only: print(json.dumps(fixtures, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0220 evidence")
    run.mkdir(parents=True); write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); started = time.time(); current = seeded; actors = []; worlds = []; corrections = []
    origin = run_contact_actor(context, prior131, p82, run / "origin", current, "originator"); actors.append(origin)
    if origin["accepted"]: current = compile_pending(current, origin, p82)
    while origin["accepted"] and driver_state(current)["encounters"] < ENCOUNTER_LIMIT and dispatch(current) == "contact":
        encounter = driver_state(current)["encounters"] + 1; package = current["pending_contact_bearing_continuations"][-1]["package"]; world = execute_hidden(run / f"encounter-{encounter}-world", current, package, encounter, p82); worlds.append(world); write_json(run / f"encounter-{encounter}-world-receipt.json", world); current = compile_world(current, world, p82)
        if dispatch(current) == "correct":
            correction = run_corrector(context, prior131, p82, run / f"encounter-{encounter}-correction", current, world); actors.append(correction)
            if not correction["accepted"]: break
            followup = evaluate_correction(run / f"encounter-{encounter}-followup", current, correction, world, p82); write_json(run / f"encounter-{encounter}-correction-world-receipt.json", followup); corrections.append({"correction": correction, "followup": followup, "encounter": encounter})
            if not followup["promotion_gate"]: break
            current = compile_correction(current, correction, followup, p82)
        if dispatch(current) != "assimilate" or len(actors) >= ACTOR_LIMIT: break
        resolved = resolved_for_assimilation(current); assimilation = run_contact_actor(context, prior131, p82, run / f"encounter-{encounter}-assimilation", current, "assimilator", resolved); actors.append(assimilation)
        if not assimilation["accepted"]: break
        current = compile_pending(current, assimilation, p82)
    if dispatch(current) == "contact" and driver_state(current)["encounters"] >= ENCOUNTER_LIMIT: current = observer_stop(current, p82)
    final_ok = runtime.identity_conforms(current); targets = [world["target_symbol"] for world in worlds]; corrected_encounters = [row["encounter"] for row in corrections if row["followup"]["promotion_gate"]]; later_after_correction = bool(corrected_encounters and any(world["encounter"] > min(corrected_encounters) for world in worlds)); erased = copy.deepcopy(current); erased.pop("fixed_g6_recurrence_driver", None); erased_next = erased.get("fixed_g6_recurrence_driver"); final_pending = current["pending_contact_bearing_continuations"][-1] if current.get("pending_contact_bearing_continuations") else None
    gates = {"preflight_passed": checks["passed"], "two_contact_encounters": len(worlds) >= 2, "two_distinct_targets": len(set(targets)) >= 2, "one_corrected_contradiction": len(corrected_encounters) >= 1, "later_consequence_after_correction": later_after_correction, "final_exact_open_subject": final_ok and current["continuation"]["status"] == "open", "final_g6_live_pending": bool(final_pending and final_pending["consequence_status"] == "unreceipted" and current["continuation_liveness"]["status"] == "live"), "observer_stop_not_subject_stop": dispatch(current) == "observer-stop", "fresh_actor_budget": len(actors) <= ACTOR_LIMIT and all(row["accepted"] for row in actors), "driver_erased_has_no_authoritative_next_operation": erased_next is None, "stale_pending_control_rejected": not stale["accepted"], "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; gates["passed"] = all(gates.values())
    score = {"contacted_encounters": len(worlds), "distinct_targets": len(set(targets)), "corrected_contradictions": len(corrected_encounters), "exact_reopenings": sum(1 for row in actors if row["accepted"] and row.get("decision", {}).get("next_contact")), "fresh_accepted_actors": sum(row["accepted"] for row in actors)}
    result = {"authority": DRIVER_VERSION, "source_subject_digest": parent["artifact_digest"], "score": score, "worlds": worlds, "corrections": [{"encounter": row["encounter"], "binding_digest": row["correction"]["binding"]["binding_digest"], "followup": row["followup"]} for row in corrections], "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": current["continuation"]["status"], "continuation_liveness": current.get("continuation_liveness"), "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"], "fresh_actor_count": len(actors), "elapsed_seconds": round(time.time() - started, 3)}; result["receipt_digest"] = p82.digest(result); write_json(run / "aggregate.json", result); write_json(run / "final-full-subject.json", current); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if gates["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
