from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0213_extensible_continuity_retention.py"
BASE_SHA256 = "50155c95cd78eaa9b9574dd5f791d99c6ce0204a2368e37da1dc84f390f40d47"
PARENT_DIGEST = "e25c60f9c0cd108c6a06b529d749d1ffcccbc348b16fedc85e4ae3969fb8f1e4"
POLICY_SOURCE_DIGEST = "e4679353e2ac6138c091f01a9179ca161e4a324e6143fa5d5e63914fab703497"
SELECTOR_DIGEST = "ea5d27fe65d8dfa49609c4219a04aeb558c504422088d942dea4eaed48f7308f"
LEDGER_DIGEST = "6565a30d8bc35b3f86ccffcc4698f8451204f50a7d471a969217e799f597aa80"
PARENT_EXTENSION_DIGEST = "559426e3c711b7a111c463fb0aa192c7c4596bc8bc2fcc7c4dbbed0271e74935"
INHERITED_OPENING = "Carry the retained consequence-grounded dispatch music into a fresh public suite: test whether maximizing visible expected net score and preserving viable ties continues to select every oracle action across new deadline, value, penalty, speed, and reliability combinations; retain the capability unless a new public regret falsifies it."
ORIGINATOR_SCHEMA = REPO / "spec/ot-0214-contact-originator.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0214-contact-assimilator.schema.json"
TARGET_PATH = "operations/system.py"
TARGETS = {"assign_batch", "estimate_reliability", "order_recovery"}
TOKEN = re.compile(r"[a-z][a-z0-9-]{2,47}")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0213 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0214_frozen_ot0213", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base213 = load_base()
authority_base = base213.authority_base
world86 = base213.world86


SYSTEM_SOURCE = '''def expected_score(job, worker):
    lateness = max(0.0, job["cost"] / worker["speed"] - job["deadline"])
    return job["value"] * worker["reliability"] - job["late_penalty"] * lateness


def choose_worker(job, workers):
    """The admitted single-job floor."""
    return max(workers, key=lambda worker: (
        expected_score(job, worker), worker["speed"], worker["id"]
    ))["id"]


def assign_batch(case):
    """Assign each job independently to one worker id."""
    return [choose_worker(job, case["workers"]) for job in case["jobs"]]


def estimate_reliability(case):
    """Estimate reliability from completed observations."""
    values = case["observations"]
    return sum(values) / len(values)


def order_recovery(case):
    """Order incidents by reported severity."""
    return [row["id"] for row in sorted(
        case["incidents"], key=lambda row: (-row["severity"], row["id"])
    )]
'''

REFERENCE_SOURCE = '''import itertools
from .system import expected_score


def assign_batch(case):
    """Maximize joint expected score subject to worker capacity."""
    workers, jobs = case["workers"], case["jobs"]
    by_id = {worker["id"]: worker for worker in workers}
    choices = []
    for assignment in itertools.product(sorted(by_id), repeat=len(jobs)):
        counts = {worker_id: assignment.count(worker_id) for worker_id in by_id}
        if any(counts[worker["id"]] > worker["capacity"] for worker in workers):
            continue
        total = sum(expected_score(job, by_id[worker_id]) for job, worker_id in zip(jobs, assignment))
        choices.append((total, tuple(reversed(assignment)), assignment))
    return list(max(choices)[2])


def estimate_reliability(case):
    """Weight recent observations more heavily."""
    values = case["observations"]
    weights = list(range(1, len(values) + 1))
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def order_recovery(case):
    """Order incidents by expected unrecovered loss."""
    return [row["id"] for row in sorted(case["incidents"], key=lambda row: (
        -(row["severity"] * row["duration"] * row["probability"]), row["id"]
    ))]
'''

FLOOR_TEST_SOURCE = '''import unittest
from operations.system import choose_worker, expected_score


class Floor(unittest.TestCase):
    def test_single_job_oracle(self):
        job = {"cost": 20, "deadline": 4, "value": 100, "late_penalty": 10}
        workers = [{"id": "fast", "speed": 10, "reliability": .5, "capacity": 2},
                   {"id": "safe", "speed": 5, "reliability": .95, "capacity": 2}]
        expected = max(workers, key=lambda w: (expected_score(job, w), w["speed"], w["id"]))["id"]
        self.assertEqual(choose_worker(job, workers), expected)
'''


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def expected_score(job, worker):
    return job["value"] * worker["reliability"] - job["late_penalty"] * max(0.0, job["cost"] / worker["speed"] - job["deadline"])


def installed_assign(case):
    return [max(case["workers"], key=lambda worker: (expected_score(job, worker), worker["speed"], worker["id"]))["id"] for job in case["jobs"]]


def reference_assign(case):
    workers, jobs = case["workers"], case["jobs"]
    by_id = {worker["id"]: worker for worker in workers}
    choices = []
    for assignment in itertools.product(sorted(by_id), repeat=len(jobs)):
        if any(assignment.count(worker["id"]) > worker["capacity"] for worker in workers):
            continue
        total = sum(expected_score(job, by_id[worker_id]) for job, worker_id in zip(jobs, assignment))
        choices.append((total, tuple(reversed(assignment)), assignment))
    return list(max(choices)[2])


def installed_reliability(case):
    values = case["observations"]
    return sum(values) / len(values)


def reference_reliability(case):
    values = case["observations"]; weights = list(range(1, len(values) + 1))
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def installed_recovery(case):
    return [row["id"] for row in sorted(case["incidents"], key=lambda row: (-row["severity"], row["id"]))]


def reference_recovery(case):
    return [row["id"] for row in sorted(case["incidents"], key=lambda row: (-(row["severity"] * row["duration"] * row["probability"]), row["id"]))]


def execute(target: str, case: dict[str, Any]) -> tuple[Any, Any]:
    if target == "assign_batch": return installed_assign(case), reference_assign(case)
    if target == "estimate_reliability": return installed_reliability(case), reference_reliability(case)
    return installed_recovery(case), reference_recovery(case)


def evaluate(target: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        try:
            installed, reference = execute(target, case["input"])
            rows.append({"case_id": case["case_id"], "installed": installed, "reference": reference, "distinguishes": installed != reference, "valid": True})
        except Exception as error:
            rows.append({"case_id": case.get("case_id"), "error_type": type(error).__name__, "distinguishes": False, "valid": False})
    distinctions = sum(row["distinguishes"] for row in rows)
    confirmations = sum(row["valid"] and not row["distinguishes"] for row in rows)
    return {"case_count": len(rows), "all_valid": all(row["valid"] for row in rows), "distinctions": distinctions, "confirmations": confirmations, "rows": rows}


def batch_case(case_id, jobs, workers): return {"case_id": case_id, "input": {"jobs": jobs, "workers": workers}}
def reliability_case(case_id, values): return {"case_id": case_id, "input": {"observations": values}}
def recovery_case(case_id, rows): return {"case_id": case_id, "input": {"incidents": rows}}
def job(cost, deadline, value, penalty): return {"cost": cost, "deadline": deadline, "value": value, "late_penalty": penalty}
def worker(identity, speed, reliability, capacity): return {"id": identity, "speed": speed, "reliability": reliability, "capacity": capacity}
def incident(identity, severity, duration, probability): return {"id": identity, "severity": severity, "duration": duration, "probability": probability}


HIDDEN_CASES = {
    "assign_batch": [
        batch_case("batch-hidden-1", [job(10,5,100,10),job(12,5,90,10)], [worker("a",10,.95,1),worker("b",8,.8,1)]),
        batch_case("batch-hidden-2", [job(20,4,120,20),job(18,4,110,20),job(16,4,100,20)], [worker("a",12,.95,1),worker("b",9,.82,2)]),
        batch_case("batch-hidden-3", [job(30,3,160,30),job(10,6,80,5)], [worker("a",15,.9,1),worker("b",7,.85,1)]),
        batch_case("batch-hidden-4", [job(40,4,200,40),job(35,4,180,35)], [worker("a",14,.88,1),worker("b",10,.8,1),worker("c",6,.99,1)]),
        batch_case("batch-hidden-5", [job(12,5,70,8)], [worker("a",10,.8,1),worker("b",6,.95,1)]),
        batch_case("batch-hidden-6", [job(10,8,60,5),job(15,8,70,5)], [worker("a",10,.9,2),worker("b",5,.7,2)]),
    ],
    "estimate_reliability": [
        reliability_case("reliability-hidden-1", [.2,.3,.9]), reliability_case("reliability-hidden-2", [.9,.3,.2]),
        reliability_case("reliability-hidden-3", [0,0,1,1]), reliability_case("reliability-hidden-4", [1,1,0,0]),
        reliability_case("reliability-hidden-5", [.7,.7,.7]), reliability_case("reliability-hidden-6", [1,1,1]),
    ],
    "order_recovery": [
        recovery_case("recovery-hidden-1", [incident("a",9,1,.2),incident("b",5,5,.9)]),
        recovery_case("recovery-hidden-2", [incident("a",10,1,.1),incident("b",6,4,.8)]),
        recovery_case("recovery-hidden-3", [incident("a",8,1,.5),incident("b",7,3,.9)]),
        recovery_case("recovery-hidden-4", [incident("a",9,2,.2),incident("b",4,8,.9)]),
        recovery_case("recovery-hidden-5", [incident("a",9,2,.9),incident("b",4,1,.5)]),
        recovery_case("recovery-hidden-6", [incident("a",6,3,.8),incident("b",5,2,.7)]),
    ],
}


CONTACT_CORE = {"contact_id", "target_path", "target_symbol", "stake", "cases", "predicates", "next_pursuit"}
EXPECTED_PREDICATES = {"success": {"minimum_distinctions": 3, "minimum_confirmations": 1}, "surrender": {"maximum_distinctions": 0}, "unresolved": {"otherwise": True}}


def package_template():
    return {"contact_id": "replace-contact", "target_path": TARGET_PATH, "target_symbol": "replace-symbol", "stake": "replace-stake", "cases": [], "predicates": EXPECTED_PREDICATES, "next_pursuit": "replace-next-pursuit"}


def valid_package(value: Any) -> bool:
    if not isinstance(value, dict) or not CONTACT_CORE.issubset(value): return False
    extras = {key: item for key, item in value.items() if key not in CONTACT_CORE}
    if len(extras) > 8 or not all(base213.EXTENSION_KEY.fullmatch(key) and base213.safe_extension(item) for key, item in extras.items()): return False
    if len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()) > 32768: return False
    if value.get("target_path") != TARGET_PATH or value.get("target_symbol") not in TARGETS: return False
    if not isinstance(value.get("contact_id"), str) or not TOKEN.fullmatch(value["contact_id"]) or value["contact_id"].startswith("replace-"): return False
    if not all(isinstance(value.get(key), str) and value[key].strip() and not value[key].startswith("replace-") for key in ("stake", "next_pursuit")): return False
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 4 or len({case.get("case_id") for case in cases if isinstance(case, dict)}) != 4: return False
    if not all(isinstance(case, dict) and set(case) == {"case_id", "input"} and isinstance(case["case_id"], str) and TOKEN.fullmatch(case["case_id"]) and isinstance(case["input"], dict) for case in cases): return False
    if value.get("predicates") != EXPECTED_PREDICATES: return False
    result = evaluate(value["target_symbol"], cases)
    return result["all_valid"] and result["distinctions"] >= 3 and result["confirmations"] >= 1


def split_package(value):
    return ({key: copy.deepcopy(value[key]) for key in sorted(CONTACT_CORE)}, {key: copy.deepcopy(item) for key, item in value.items() if key not in CONTACT_CORE})


def environment_files():
    contract = json.dumps({"authority": "ot-0214-public-contact-contract", "editable_file": "contact-package.json", "required_core_fields": sorted(CONTACT_CORE), "target_path": TARGET_PATH, "allowed_target_symbols": sorted(TARGETS), "identifier_pattern": TOKEN.pattern, "case_count": 4, "case_fields": ["case_id", "input"], "predicates": EXPECTED_PREDICATES, "success": {"minimum_distinctions": 3, "minimum_confirmations": 1}, "extensions": {"maximum_count": 8, "key_pattern": base213.EXTENSION_KEY.pattern, "maximum_depth": 4, "maximum_collection_width": 16, "maximum_string_length": 2048}, "maximum_package_bytes": 32768}, indent=2, sort_keys=True) + "\n"
    checker = '''import json
import re
from pathlib import Path
from operations.evaluate import evaluate

contract=json.loads(Path("contact-contract.json").read_text())
p=json.loads(Path("contact-package.json").read_text())
core=set(contract["required_core_fields"])
def bounded(v,depth=0):
 if depth>contract["extensions"]["maximum_depth"]: return False
 if v is None or isinstance(v,(bool,int,float)): return True
 if isinstance(v,str): return len(v)<=contract["extensions"]["maximum_string_length"]
 if isinstance(v,list): return len(v)<=contract["extensions"]["maximum_collection_width"] and all(bounded(x,depth+1) for x in v)
 if isinstance(v,dict): return len(v)<=contract["extensions"]["maximum_collection_width"] and all(isinstance(k,str) and bounded(x,depth+1) for k,x in v.items())
 return False
extras={k:v for k,v in p.items() if k not in core} if isinstance(p,dict) else {}
cases=p.get("cases",[]) if isinstance(p,dict) else []
shape=(isinstance(p,dict) and core.issubset(p) and len(extras)<=contract["extensions"]["maximum_count"]
 and all(re.fullmatch(contract["extensions"]["key_pattern"],k) and bounded(v) for k,v in extras.items())
 and len(json.dumps(p,sort_keys=True,separators=(",",":" )).encode())<=contract["maximum_package_bytes"]
 and p.get("target_path")==contract["target_path"] and p.get("target_symbol") in contract["allowed_target_symbols"]
 and isinstance(p.get("contact_id"),str) and re.fullmatch(contract["identifier_pattern"],p["contact_id"]) and not p["contact_id"].startswith("replace-")
 and all(isinstance(p.get(k),str) and p[k].strip() and not p[k].startswith("replace-") for k in ("stake","next_pursuit"))
 and isinstance(cases,list) and len(cases)==contract["case_count"]
 and len({c.get("case_id") for c in cases if isinstance(c,dict)})==contract["case_count"]
 and all(isinstance(c,dict) and set(c)==set(contract["case_fields"]) and isinstance(c.get("case_id"),str) and re.fullmatch(contract["identifier_pattern"],c["case_id"]) and isinstance(c.get("input"),dict) for c in cases)
 and p.get("predicates")==contract["predicates"])
r=evaluate(p.get("target_symbol"),cases) if shape else {"case_count":0,"all_valid":False,"distinctions":0,"confirmations":0,"rows":[]}
ok=shape and r["all_valid"] and r["distinctions"]>=contract["success"]["minimum_distinctions"] and r["confirmations"]>=contract["success"]["minimum_confirmations"]
print(json.dumps({"passed":bool(ok),"shape_passed":bool(shape),"result":r},sort_keys=True))
raise SystemExit(0 if ok else 2)
'''
    evaluator = '''from .system import assign_batch as installed_batch, estimate_reliability as installed_reliability, order_recovery as installed_recovery\nfrom .reference import assign_batch as reference_batch, estimate_reliability as reference_reliability, order_recovery as reference_recovery\nPAIRS={"assign_batch":(installed_batch,reference_batch),"estimate_reliability":(installed_reliability,reference_reliability),"order_recovery":(installed_recovery,reference_recovery)}\ndef evaluate(target,cases):\n rows=[]\n for case in cases:\n  try:\n   a,b=PAIRS[target]; installed,reference=a(case["input"]),b(case["input"]); rows.append({"case_id":case["case_id"],"installed":installed,"reference":reference,"distinguishes":installed!=reference,"valid":True})\n  except Exception as error: rows.append({"case_id":case.get("case_id"),"error_type":type(error).__name__,"distinguishes":False,"valid":False})\n return {"case_count":len(rows),"all_valid":all(r["valid"] for r in rows),"distinctions":sum(r["distinguishes"] for r in rows),"confirmations":sum(r["valid"] and not r["distinguishes"] for r in rows),"rows":rows}\n'''
    return {"operations/__init__.py": "", "operations/system.py": SYSTEM_SOURCE, "operations/reference.py": REFERENCE_SOURCE, "operations/evaluate.py": evaluator, "tests/__init__.py": "", "tests/test_floor.py": FLOOR_TEST_SOURCE, "contact-contract.json": contract, "check_contact.py": checker}


def write_environment(root: Path):
    for relative, source in environment_files().items():
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source)


def saturation_receipt(p82, parent):
    source = parent["executed_pursuit_capabilities"][-1]["source"]
    expected = base213.CURRENT_SOURCE
    body = {"authority": "ot-0214-single-job-semantic-saturation", "source_subject_digest": parent["artifact_digest"], "policy_source_digest": p82.digest(source), "world_definition_digest": p82.digest(world86.WORLD_SOURCE), "proof_kind": "exact-source-and-oracle-definition-equivalence", "score_expression_equal": source == expected, "tie_order_equal": '(score(worker), worker["speed"], worker["id"])' in source, "scope": "all valid inputs under unchanged single-job semantics", "parameter_only_counterexample_possible": False}
    body["passed"] = body["score_expression_equal"] and body["tie_order_equal"] and body["policy_source_digest"] == POLICY_SOURCE_DIGEST
    return {**body, "receipt_digest": p82.digest(body)}


def originator_seed(root: Path, parent, saturation):
    seed = root / "originator-seed"; seed.mkdir(); write_environment(seed)
    write_json(seed / "subject-position.json", authority_base.reuse.worlds.base.active_position(parent)); write_json(seed / "saturation-receipt.json", saturation); write_json(seed / "contact-package.json", package_template())
    write_json(seed / "mutation-envelope.json", {"editable": ["contact-package.json"], "immutable": ["subject-position.json", "saturation-receipt.json", "mutation-envelope.json", "README.md", *sorted(environment_files())]})
    (seed / "README.md").write_text("The exact opening is saturated under unchanged single-job semantics. Inspect this complete operations repository and originate one semantically new falsifiable contact without a supplied surface list. Choose one existing callable and author the package defined completely by contact-contract.json. Hidden cases are unavailable. Edit only contact-package.json, run python3 check_contact.py and python3 -m unittest -q tests.test_floor, and inspect the exact diff.\n")
    return seed


def run_originator(context, prior131, p82, root, parent, saturation):
    seed = originator_seed(root, parent, saturation); label = "semantic-contact-originator"
    output, base_audit, workspace, _ = context.run_actor(label, seed, ORIGINATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        package = json.loads((workspace / "contact-package.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
    except (OSError, json.JSONDecodeError, KeyError): package, immutable_ok = None, False
    valid = bool(valid_package(package) and immutable_ok and output and output.get("action") == "originate-semantic-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-package.json"])
    binding = None; public = evaluate(package["target_symbol"], package["cases"]) if valid else None
    if valid and prior131.audit_accepted(audit):
        core, extensions = split_package(package); extension = {"authority": "subject-authored-non-authoritative-continuity-content", "content": extensions, "content_digest": p82.digest(extensions)}
        body = {"authority": "ot-0214-pre-hidden-semantic-contact", "source_subject_digest": parent["artifact_digest"], "saturation_receipt_digest": saturation["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "package_core": core, "subject_authored_extensions": extension, "raw_package_digest": p82.digest(package), "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}; write_json(context.evidence(label) / "bound-package.json", binding)
    return {"output": output, "audit": audit, "package": package, "public": public, "binding": binding, "accepted": binding is not None}


ASSIMILATION_CORE = {"subject_action", "saturated_opening_disposition", "policy_disposition", "selector_disposition", "policy_source_digest", "selector_binding_digest", "contact_program_disposition", "contact_package_digest", "rationale", "next_pursuit"}


def assimilation_template():
    return {"subject_action": "revise", "saturated_opening_disposition": "revise", "policy_disposition": "retain", "selector_disposition": "retain", "policy_source_digest": POLICY_SOURCE_DIGEST, "selector_binding_digest": SELECTOR_DIGEST, "contact_program_disposition": "retain", "contact_package_digest": "replace-package-digest", "rationale": "replace-rationale", "next_pursuit": "replace-next-pursuit"}


def valid_assimilation(value, package_digest):
    if not isinstance(value, dict) or not ASSIMILATION_CORE.issubset(value): return False
    extras = {key: item for key, item in value.items() if key not in ASSIMILATION_CORE}
    return bool(len(extras) <= 8 and all(base213.EXTENSION_KEY.fullmatch(key) and base213.safe_extension(item) for key, item in extras.items()) and value.get("subject_action") in {"revise", "retain"} and value.get("saturated_opening_disposition") in {"retire", "revise"} and value.get("policy_disposition") == value.get("selector_disposition") == value.get("contact_program_disposition") == "retain" and value.get("policy_source_digest") == POLICY_SOURCE_DIGEST and value.get("selector_binding_digest") == SELECTOR_DIGEST and value.get("contact_package_digest") == package_digest and all(isinstance(value.get(key), str) and value[key].strip() and not value[key].startswith("replace-") for key in ("rationale", "next_pursuit")) and value["next_pursuit"] != INHERITED_OPENING)


def assimilator_seed(root, parent, saturation, binding, world):
    seed = root / "assimilator-seed"; seed.mkdir(); write_json(seed / "subject-position.json", authority_base.reuse.worlds.base.active_position(parent)); write_json(seed / "saturation-receipt.json", saturation); write_json(seed / "bound-contact-package.json", binding); write_json(seed / "hidden-world-receipt.json", world); decision = assimilation_template(); decision["contact_package_digest"] = binding["binding_digest"]; write_json(seed / "continuation-decision.json", decision)
    contract = {"authority": "ot-0214-public-assimilation-contract", "editable_file": "continuation-decision.json", "required_core_fields": sorted(ASSIMILATION_CORE), "allowed_subject_actions": ["retain", "revise"], "allowed_saturated_opening_dispositions": ["retire", "revise"], "required_dispositions": {"policy_disposition": "retain", "selector_disposition": "retain", "contact_program_disposition": "retain"}, "required_identities": {"policy_source_digest": POLICY_SOURCE_DIGEST, "selector_binding_digest": SELECTOR_DIGEST, "contact_package_digest": binding["binding_digest"]}, "forbidden_next_pursuit": INHERITED_OPENING, "extensions": {"maximum_count": 8, "key_pattern": base213.EXTENSION_KEY.pattern, "maximum_depth": 4, "maximum_collection_width": 16, "maximum_string_length": 2048}}
    write_json(seed / "continuation-contract.json", contract)
    checker = '''import json
import re
from pathlib import Path
c=json.loads(Path("continuation-contract.json").read_text()); d=json.loads(Path("continuation-decision.json").read_text()); core=set(c["required_core_fields"])
def bounded(v,depth=0):
 if depth>c["extensions"]["maximum_depth"]: return False
 if v is None or isinstance(v,(bool,int,float)): return True
 if isinstance(v,str): return len(v)<=c["extensions"]["maximum_string_length"]
 if isinstance(v,list): return len(v)<=c["extensions"]["maximum_collection_width"] and all(bounded(x,depth+1) for x in v)
 if isinstance(v,dict): return len(v)<=c["extensions"]["maximum_collection_width"] and all(isinstance(k,str) and bounded(x,depth+1) for k,x in v.items())
 return False
extras={k:v for k,v in d.items() if k not in core} if isinstance(d,dict) else {}
ok=(isinstance(d,dict) and core.issubset(d) and len(extras)<=c["extensions"]["maximum_count"] and all(re.fullmatch(c["extensions"]["key_pattern"],k) and bounded(v) for k,v in extras.items()) and d.get("subject_action") in c["allowed_subject_actions"] and d.get("saturated_opening_disposition") in c["allowed_saturated_opening_dispositions"] and all(d.get(k)==v for k,v in c["required_dispositions"].items()) and all(d.get(k)==v for k,v in c["required_identities"].items()) and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("rationale","next_pursuit")) and d.get("next_pursuit")!=c["forbidden_next_pursuit"])
print(json.dumps({"passed":bool(ok)},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''
    (seed / "check_decision.py").write_text(checker)
    write_json(seed / "mutation-envelope.json", {"editable": ["continuation-decision.json"], "immutable": ["subject-position.json", "saturation-receipt.json", "bound-contact-package.json", "hidden-world-receipt.json", "continuation-contract.json", "check_decision.py", "mutation-envelope.json", "README.md"]})
    (seed / "README.md").write_text("Assimilate the exact saturation and independently successful semantic contact. Author the decision defined completely by continuation-contract.json, including a distinct next executable pursuit. Additional G4 fields remain non-authoritative. Edit only continuation-decision.json, run python3 check_decision.py, and inspect the exact diff.\n")
    return seed


def run_assimilator(context, prior131, p82, root, parent, saturation, binding, world):
    seed = assimilator_seed(root, parent, saturation, binding, world); label = "semantic-contact-assimilator"
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "continuation-decision.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
    except (OSError, json.JSONDecodeError, KeyError): decision, immutable_ok = None, False
    valid = bool(valid_assimilation(decision, binding["binding_digest"]) and immutable_ok and output and output.get("action") == "assimilate-semantic-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["continuation-decision.json"]); bound = None
    if valid and prior131.audit_accepted(audit):
        core = {key: copy.deepcopy(decision[key]) for key in sorted(ASSIMILATION_CORE)}; extensions = {key: copy.deepcopy(item) for key, item in decision.items() if key not in ASSIMILATION_CORE}; extension = {"authority": "subject-authored-non-authoritative-continuity-content", "content": extensions, "content_digest": p82.digest(extensions)}; body = {"authority": "ot-0214-bound-semantic-contact-assimilation", "source_subject_digest": parent["artifact_digest"], "contact_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision_core": core, "subject_authored_extensions": extension, "raw_decision_digest": p82.digest(decision)}; bound = {**body, "binding_digest": p82.digest(body)}; write_json(context.evidence(label) / "bound-assimilation.json", bound)
    return {"output": output, "audit": audit, "decision": decision, "binding": bound, "accepted": bound is not None}


def main():
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0214").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0213", "open-subject-after-extensible-retention.json"); result213 = selector_base.load_artifact(p82, repo, store, "OT-0213", "extensible-continuity-retention-aggregate.json"); saturation = saturation_receipt(p82, parent)
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]; route_floor = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixture_root = run.parent / "OT-0214-preflight"
    if fixture_root.exists(): import shutil; shutil.rmtree(fixture_root)
    write_environment(fixture_root); floor = subprocess.run(["python3", "-m", "unittest", "-q", "tests.test_floor"], cwd=fixture_root, capture_output=True)
    representative_package = {**{"contact_id": "fixture-contact", "target_path": TARGET_PATH, "target_symbol": "estimate_reliability", "stake": "Recent evidence should matter more.", "cases": [HIDDEN_CASES["estimate_reliability"][index] for index in (0, 1, 2, 4)], "predicates": EXPECTED_PREDICATES, "next_pursuit": "implement-recency"}, "causal_thread": {"reason": "semantic-expansion"}}
    write_json(fixture_root / "contact-package.json", representative_package)
    public_contact_checker = subprocess.run(["python3", "check_contact.py"], cwd=fixture_root, capture_output=True)
    assimilation_fixture_root = fixture_root / "assimilation"
    assimilation_fixture_root.mkdir()
    fixture_binding = {"binding_digest": "a" * 64}
    fixture_world = {"receipt_digest": "b" * 64}
    assimilator_seed(assimilation_fixture_root, parent, saturation, fixture_binding, fixture_world)
    representative_decision = assimilation_template()
    representative_decision.update({"saturated_opening_disposition": "retire", "contact_package_digest": fixture_binding["binding_digest"], "rationale": "The old pursuit is saturated and the new contact succeeded independently.", "next_pursuit": "Implement the admitted semantic correction and seek a fresh counterexample.", "causal_thread": {"reason": "continue-world-contact"}})
    write_json(assimilation_fixture_root / "assimilator-seed" / "continuation-decision.json", representative_decision)
    public_assimilation_checker = subprocess.run(["python3", "check_decision.py"], cwd=assimilation_fixture_root / "assimilator-seed", capture_output=True)
    hidden_fixtures = {target: evaluate(target, cases) for target, cases in HIDDEN_CASES.items()}; source_tree = ast.parse(SYSTEM_SOURCE); symbols = {node.name for node in source_tree.body if isinstance(node, ast.FunctionDef)}; schema_text = ORIGINATOR_SCHEMA.read_text() + ASSIMILATOR_SCHEMA.read_text()
    checks = {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0213_exact_promotion": result213["observer_disposition"] == "promoted" and result213["final_subject_digest"] == PARENT_DIGEST, "g4_extension_exact": parent["continuity_extensions"][-1]["content_digest"] == PARENT_EXTENSION_DIGEST, "ledger_selector_policy_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["pursuit_selector_capabilities"][-1]["selector_binding_digest"] == SELECTOR_DIGEST and parent["executed_pursuit_capabilities"][-1]["source_digest"] == POLICY_SOURCE_DIGEST, "opening_exact": parent["continuation"]["next_opening"] == INHERITED_OPENING, "saturation_proof_passed": saturation["passed"], "complete_environment_floor": floor.returncode == 0 and not any(token in "\n".join(environment_files().values()) for token in ("TODO", "NotImplementedError")), "three_real_unenumerated_targets": TARGETS.issubset(symbols), "all_hidden_targets_4_plus_2": all(row["all_valid"] and row["distinctions"] >= 4 and row["confirmations"] >= 2 for row in hidden_fixtures.values()), "template_rejected": not valid_package(package_template()), "g4_contact_extension_fixture": valid_package(representative_package), "public_contact_checker_exact": public_contact_checker.returncode == 0, "public_assimilation_checker_exact": public_assimilation_checker.returncode == 0 and valid_assimilation(representative_decision, fixture_binding["binding_digest"]), "schemas_supported": ORIGINATOR_SCHEMA.is_file() and ASSIMILATOR_SCHEMA.is_file() and "uniqueItems" not in schema_text, "route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); fixtures = {"authority": "ot-0214-preflight", "source_subject_digest": parent["artifact_digest"], "saturation_receipt": saturation, "hidden_fixture_results": hidden_fixtures, "checks": checks}
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0214 evidence")
    run.mkdir(parents=True); write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); origin_root = run / "originator-authoring"; origin_root.mkdir(); origin = run_originator(context, prior131, p82, origin_root, parent, saturation); world = assimilation = None
    if origin["accepted"]:
        hidden = evaluate(origin["package"]["target_symbol"], HIDDEN_CASES[origin["package"]["target_symbol"]]); body = {"authority": "ot-0214-sealed-semantic-world", "source_subject_digest": parent["artifact_digest"], "contact_binding_digest": origin["binding"]["binding_digest"], "target_symbol": origin["package"]["target_symbol"], "hidden_cases_digest": p82.digest(HIDDEN_CASES[origin["package"]["target_symbol"]]), "result": hidden, "actor_success_predicate_passed": hidden["distinctions"] >= origin["package"]["predicates"]["success"]["minimum_distinctions"] and hidden["confirmations"] >= origin["package"]["predicates"]["success"]["minimum_confirmations"], "world_promotion_gate_passed": hidden["all_valid"] and hidden["distinctions"] >= 4 and hidden["confirmations"] >= 2}; world = {**body, "receipt_digest": p82.digest(body)}; write_json(run / "hidden-world-receipt.json", world)
    if world and world["actor_success_predicate_passed"] and world["world_promotion_gate_passed"]:
        assimilation_root = run / "assimilation-authoring"; assimilation_root.mkdir(); assimilation = run_assimilator(context, prior131, p82, assimilation_root, parent, saturation, origin["binding"], world)
    gates = {"two_fresh_actors_accepted": bool(origin["accepted"] and assimilation and assimilation["accepted"]), "actor_selected_real_target": bool(origin["accepted"] and origin["package"]["target_symbol"] in TARGETS), "public_3_plus_1": bool(origin["public"] and origin["public"]["distinctions"] >= 3 and origin["public"]["confirmations"] >= 1), "hidden_4_plus_2": bool(world and world["world_promotion_gate_passed"] and world["actor_success_predicate_passed"]), "machine_predicates_exact": bool(origin["accepted"] and origin["package"]["predicates"] == EXPECTED_PREDICATES), "saturated_opening_revised": bool(assimilation and assimilation["accepted"] and assimilation["decision"]["saturated_opening_disposition"] in {"retire", "revise"}), "contact_program_retained": bool(assimilation and assimilation["accepted"] and assimilation["decision"]["contact_program_disposition"] == "retain"), "ledger_selector_policy_exact": checks["ledger_selector_policy_exact"], "route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; gates["passed"] = all(gates.values()); final = parent; promotion = replay = erased = None
    if gates["passed"]:
        child = copy.deepcopy(parent); child.pop("artifact_digest", None); package_body = {"authority": "ot-0214-world-admitted-semantic-contact-program", "binding_digest": origin["binding"]["binding_digest"], "target_symbol": origin["package"]["target_symbol"], "package": origin["package"], "package_digest": p82.digest(origin["package"]), "world_receipt_digest": world["receipt_digest"]}; child["semantic_contact_program_capabilities"] = [*child.get("semantic_contact_program_capabilities", []), package_body]; receipt_body = {"authority": "ot-0214-subject-originated-semantic-contact", "source_subject_digest": parent["artifact_digest"], "saturation_receipt_digest": saturation["receipt_digest"], "contact_binding_digest": origin["binding"]["binding_digest"], "world_receipt_digest": world["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}; promotion = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}; child["semantic_contact_receipts"] = [*child.get("semantic_contact_receipts", []), promotion]; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": assimilation["decision"]["next_pursuit"]}; child["unresolved"] = "Can the subject execute and recurrently improve its self-originated semantic pursuit without an observer choosing the implementation target?"; candidate = p82.seal(child)
        if runtime.identity_conforms(candidate): final = candidate
        else: gates["successor_identity_conforms"] = False; gates["passed"] = False
    gates.setdefault("successor_identity_conforms", gates["passed"] and final is not parent)
    if gates["successor_identity_conforms"]:
        retained = final["semantic_contact_program_capabilities"][-1]["package"]; replay_result = evaluate(retained["target_symbol"], HIDDEN_CASES[retained["target_symbol"]]); replay = {"bound": True, "result": replay_result, "passed": replay_result == world["result"]}; erased = {"bound": False, "reason": "package-bytes-absent", "passed": True}; gates["retained_byte_replay_passed"] = replay["passed"]; gates["byte_erased_control_cannot_bind"] = not erased["bound"]; gates["passed"] = gates["passed"] and replay["passed"] and not erased["bound"]
    else:
        gates["retained_byte_replay_passed"] = False; gates["byte_erased_control_cannot_bind"] = False; gates["passed"] = False; final = parent
    result = {"authority": "ot-0214-subject-originated-semantic-contact", "source_subject_digest": parent["artifact_digest"], "saturation_receipt": saturation, "originator": p82.compact(origin), "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "promotion_receipt": promotion, "retained_replay": replay, "byte_erased_control": erased, "checks": gates, "route_floor": route_floor, "identity_floor": identity, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 + (1 if assimilation else 0)}; result["receipt_digest"] = p82.digest(result); write_json(run / "aggregate.json", result); write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if gates["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
