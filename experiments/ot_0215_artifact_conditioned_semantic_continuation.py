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
BASE_PATH = ROOT / "ot_0214_subject_originated_semantic_contact.py"
BASE_SHA256 = "f0495a96c407b1e6165a59e168534a0eb159673202b11dd6beebfd5d77b0a785"
PARENT_DIGEST = "3f439d586161ce9a96759e28f89ffcea4e90a961824e0888f47341e5ac51666f"
CONTACT_BINDING = "9acf7197e8aa80fe18971e6c92e6f02540e6442ab48f4dc337fcc07d87428ee3"
CONTACT_PACKAGE = "0774a284373c4000deacd644705c78f6f72621b37a0d7849d8b02579505a0e53"
OPENING = "Retire the saturated single-job opening and execute a fresh sealed multi-job recovery-order test that checks whether the retained expected-loss capability remains correct when jobs compete for recovery capacity."
NEUTRAL_OPENING = "Inspect the complete operations repository and make one locally warranted executable improvement."
MOVE_SCHEMA = REPO / "spec/ot-0215-move.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0215-assimilator.schema.json"
TARGET_PATH = "operations/system.py"
TARGETS = {"schedule_recovery", "allocate_relief", "schedule_maintenance"}
TOKEN = re.compile(r"[a-z][a-z0-9-]{2,47}")
EXPECTED_PREDICATES = {"success": {"minimum_improvements": 3, "minimum_confirmations": 1}, "surrender": {"maximum_improvements": 0}, "unresolved": {"otherwise": True}}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0214 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0215_frozen_ot0214", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base214 = load_base()
base213 = base214.base213
authority_base = base214.authority_base


SYSTEM_SOURCE = '''def expected_loss(item):
    return item["severity"] * item["duration"] * item["probability"]


def schedule_recovery(case):
    """Choose incidents for the available recovery capacity."""
    remaining = case["capacity"]
    chosen = []
    for item in sorted(case["incidents"], key=lambda row: (-row["severity"], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"])
            remaining -= item["effort"]
    return chosen


def allocate_relief(case):
    """Choose requests for the available relief capacity."""
    remaining = case["capacity"]
    chosen = []
    for item in sorted(case["requests"], key=lambda row: (-row["people"], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"])
            remaining -= item["effort"]
    return chosen


def schedule_maintenance(case):
    """Choose tasks for the available maintenance capacity."""
    remaining = case["capacity"]
    chosen = []
    for item in sorted(case["tasks"], key=lambda row: (-row["criticality"], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"])
            remaining -= item["effort"]
    return chosen
'''

REFERENCE_SOURCE = '''import itertools


def _best(items, capacity, value):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > capacity:
            continue
        score = sum(value(item) for item in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])


def schedule_recovery(case):
    return _best(case["incidents"], case["capacity"], lambda row: row["severity"] * row["duration"] * row["probability"])


def allocate_relief(case):
    return _best(case["requests"], case["capacity"], lambda row: row["people"] * row["probability"])


def schedule_maintenance(case):
    return _best(case["tasks"], case["capacity"], lambda row: row["criticality"] * row["downtime"] * row["failure_probability"])
'''

BASELINE_SOURCE = SYSTEM_SOURCE


def incident(identity, severity, duration, probability, effort):
    return {"id": identity, "severity": severity, "duration": duration, "probability": probability, "effort": effort}


def request(identity, people, probability, effort):
    return {"id": identity, "people": people, "probability": probability, "effort": effort}


def task(identity, criticality, downtime, failure_probability, effort):
    return {"id": identity, "criticality": criticality, "downtime": downtime, "failure_probability": failure_probability, "effort": effort}


HIDDEN_CASES = {
    "schedule_recovery": [
        {"case_id": "recovery-sealed-1", "input": {"capacity": 2, "incidents": [incident("a", 9, 1, .2, 2), incident("b", 6, 6, .9, 2)]}},
        {"case_id": "recovery-sealed-2", "input": {"capacity": 3, "incidents": [incident("a", 10, 1, .1, 3), incident("b", 5, 8, .9, 3)]}},
        {"case_id": "recovery-sealed-3", "input": {"capacity": 4, "incidents": [incident("a", 9, 1, .3, 4), incident("b", 6, 5, .9, 2), incident("c", 5, 4, .8, 2)]}},
        {"case_id": "recovery-sealed-4", "input": {"capacity": 5, "incidents": [incident("a", 10, 1, .2, 5), incident("b", 7, 6, .8, 3), incident("c", 6, 4, .9, 2)]}},
        {"case_id": "recovery-sealed-5", "input": {"capacity": 4, "incidents": [incident("a", 9, 4, .9, 2), incident("b", 5, 2, .5, 2)]}},
        {"case_id": "recovery-sealed-6", "input": {"capacity": 4, "incidents": [incident("a", 8, 3, .8, 2), incident("b", 7, 2, .7, 2)]}},
    ],
    "allocate_relief": [
        {"case_id": "relief-sealed-1", "input": {"capacity": 2, "requests": [request("a", 100, .1, 2), request("b", 60, .9, 2)]}},
        {"case_id": "relief-sealed-2", "input": {"capacity": 3, "requests": [request("a", 120, .2, 3), request("b", 80, .9, 3)]}},
        {"case_id": "relief-sealed-3", "input": {"capacity": 4, "requests": [request("a", 100, .2, 4), request("b", 70, .9, 2), request("c", 60, .8, 2)]}},
        {"case_id": "relief-sealed-4", "input": {"capacity": 5, "requests": [request("a", 130, .2, 5), request("b", 90, .8, 3), request("c", 70, .9, 2)]}},
        {"case_id": "relief-sealed-5", "input": {"capacity": 4, "requests": [request("a", 90, .9, 2), request("b", 50, .5, 2)]}},
        {"case_id": "relief-sealed-6", "input": {"capacity": 4, "requests": [request("a", 80, .8, 2), request("b", 70, .7, 2)]}},
    ],
    "schedule_maintenance": [
        {"case_id": "maintenance-sealed-1", "input": {"capacity": 2, "tasks": [task("a", 10, 1, .1, 2), task("b", 6, 8, .9, 2)]}},
        {"case_id": "maintenance-sealed-2", "input": {"capacity": 3, "tasks": [task("a", 9, 1, .2, 3), task("b", 5, 9, .9, 3)]}},
        {"case_id": "maintenance-sealed-3", "input": {"capacity": 4, "tasks": [task("a", 10, 1, .2, 4), task("b", 7, 6, .8, 2), task("c", 6, 5, .9, 2)]}},
        {"case_id": "maintenance-sealed-4", "input": {"capacity": 5, "tasks": [task("a", 10, 1, .2, 5), task("b", 8, 5, .8, 3), task("c", 7, 4, .9, 2)]}},
        {"case_id": "maintenance-sealed-5", "input": {"capacity": 4, "tasks": [task("a", 9, 5, .9, 2), task("b", 6, 2, .4, 2)]}},
        {"case_id": "maintenance-sealed-6", "input": {"capacity": 4, "tasks": [task("a", 8, 4, .8, 2), task("b", 7, 3, .7, 2)]}},
    ],
}


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_sources(system_path: Path, reference_path: Path, target: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    system = load_module(system_path, "ot0215_system_" + hashlib.sha256(system_path.read_bytes()).hexdigest()[:12])
    reference = load_module(reference_path, "ot0215_reference_" + hashlib.sha256(reference_path.read_bytes()).hexdigest()[:12])
    baseline_path = system_path.parent / "baseline.py"
    baseline = load_module(baseline_path, "ot0215_baseline")
    rows = []
    for case in cases:
        try:
            before = getattr(baseline, target)(copy.deepcopy(case["input"]))
            after = getattr(system, target)(copy.deepcopy(case["input"]))
            expected = getattr(reference, target)(copy.deepcopy(case["input"]))
            rows.append({"case_id": case["case_id"], "before": before, "after": after, "expected": expected, "baseline_correct": before == expected, "patched_correct": after == expected, "improved": before != expected and after == expected, "valid": True})
        except Exception as error:
            rows.append({"case_id": case.get("case_id"), "error_type": type(error).__name__, "baseline_correct": False, "patched_correct": False, "improved": False, "valid": False})
    return {"case_count": len(rows), "all_valid": all(row["valid"] for row in rows), "improvements": sum(row["improved"] for row in rows), "confirmations": sum(row["baseline_correct"] and row["patched_correct"] for row in rows), "patched_correct": sum(row["patched_correct"] for row in rows), "rows": rows}


def function_sources(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    return {node.name: ast.unparse(node) for node in tree.body if isinstance(node, ast.FunctionDef)}


def module_shell(source: str, target: str) -> str:
    tree = ast.parse(source)
    body = [node for node in tree.body if not (isinstance(node, ast.FunctionDef) and node.name == target)]
    return ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)


def target_only_change(source: str, baseline_source: str, target: str) -> bool:
    try:
        baseline, candidate = function_sources(baseline_source), function_sources(source)
    except SyntaxError:
        return False
    return set(candidate) == set(baseline) and candidate[target] != baseline[target] and all(candidate[name] == baseline[name] for name in baseline if name != target) and module_shell(source, target) == module_shell(baseline_source, target)


CORE = {"move_id", "target_path", "target_symbol", "stake", "cases", "predicates", "next_pursuit"}


def move_template():
    return {"move_id": "replace-move", "target_path": TARGET_PATH, "target_symbol": "replace-symbol", "stake": "replace-stake", "cases": [], "predicates": EXPECTED_PREDICATES, "next_pursuit": "replace-next-pursuit"}


def valid_move(value: Any, system_path: Path, reference_path: Path) -> tuple[bool, dict[str, Any] | None]:
    if not isinstance(value, dict) or set(value) != CORE: return False, None
    if value.get("target_path") != TARGET_PATH or value.get("target_symbol") not in TARGETS: return False, None
    if not isinstance(value.get("move_id"), str) or not TOKEN.fullmatch(value["move_id"]) or value["move_id"].startswith("replace-"): return False, None
    if not all(isinstance(value.get(key), str) and value[key].strip() and not value[key].startswith("replace-") for key in ("stake", "next_pursuit")): return False, None
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 4 or len({case.get("case_id") for case in cases if isinstance(case, dict)}) != 4: return False, None
    if not all(isinstance(case, dict) and set(case) == {"case_id", "input"} and isinstance(case["case_id"], str) and TOKEN.fullmatch(case["case_id"]) and isinstance(case["input"], dict) for case in cases): return False, None
    if value.get("predicates") != EXPECTED_PREDICATES: return False, None
    if not target_only_change(system_path.read_text(), (system_path.parent / "baseline.py").read_text(), value["target_symbol"]): return False, None
    result = evaluate_sources(system_path, reference_path, value["target_symbol"], cases)
    return bool(result["all_valid"] and result["improvements"] >= 3 and result["confirmations"] >= 1 and result["patched_correct"] == 4), result


ORDER_SCHEDULE = [
    ("schedule_recovery", "allocate_relief", "schedule_maintenance"),
    ("allocate_relief", "schedule_maintenance", "schedule_recovery"),
    ("schedule_maintenance", "schedule_recovery", "allocate_relief"),
]


def ordered_source(source: str, order: tuple[str, ...], helpers: tuple[str, ...]) -> str:
    definitions = function_sources(source)
    return "\n\n\n".join(definitions[name] for name in (*helpers, *order)) + "\n"


def contract_value() -> dict[str, Any]:
    return {
        "authority": "ot-0215-public-move-contract",
        "editable_files": [TARGET_PATH, "move-package.json"],
        "required_package_fields": sorted(CORE),
        "target_rule": "public function defined in both operations/system.py and operations/reference.py",
        "target_path": TARGET_PATH,
        "identifier_pattern": TOKEN.pattern,
        "case_count": 4,
        "case_fields": ["case_id", "input"],
        "predicates": EXPECTED_PREDICATES,
        "success": {"minimum_improvements": 3, "minimum_confirmations": 1, "required_patched_correct": 4},
        "source_change": "change exactly the selected function; preserve every other function exactly",
    }


EVALUATOR_SOURCE = '''import ast
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path

def load(path,prefix):
 spec=importlib.util.spec_from_file_location(prefix+hashlib.sha256(path.read_bytes()).hexdigest()[:12],path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def functions(source):
 return {node.name:ast.unparse(node) for node in ast.parse(source).body if isinstance(node,ast.FunctionDef)}
def shell(source,target):
 tree=ast.parse(source); return ast.dump(ast.Module(body=[node for node in tree.body if not (isinstance(node,ast.FunctionDef) and node.name==target)],type_ignores=[]),include_attributes=False)
def evaluate(target,cases):
 root=Path(__file__).parent; baseline=load(root/"baseline.py","baseline_"); system=load(root/"system.py","system_"); reference=load(root/"reference.py","reference_"); rows=[]
 for case in cases:
  try:
   before=getattr(baseline,target)(copy.deepcopy(case["input"])); after=getattr(system,target)(copy.deepcopy(case["input"])); expected=getattr(reference,target)(copy.deepcopy(case["input"])); rows.append({"case_id":case["case_id"],"before":before,"after":after,"expected":expected,"baseline_correct":before==expected,"patched_correct":after==expected,"improved":before!=expected and after==expected,"valid":True})
  except Exception as error: rows.append({"case_id":case.get("case_id"),"error_type":type(error).__name__,"baseline_correct":False,"patched_correct":False,"improved":False,"valid":False})
 return {"case_count":len(rows),"all_valid":all(row["valid"] for row in rows),"improvements":sum(row["improved"] for row in rows),"confirmations":sum(row["baseline_correct"] and row["patched_correct"] for row in rows),"patched_correct":sum(row["patched_correct"] for row in rows),"rows":rows}
def validate(package):
 root=Path(__file__).parent.parent; c=json.loads((root/"move-contract.json").read_text()); core=set(c["required_package_fields"]); cases=package.get("cases",[]) if isinstance(package,dict) else []; target=package.get("target_symbol") if isinstance(package,dict) else None
 try:
  before=functions((root/"operations/baseline.py").read_text()); after=functions((root/"operations/system.py").read_text()); reference=functions((root/"operations/reference.py").read_text())
 except Exception: before=after=reference={}
 common=(set(before)&set(reference))-{"_best"}; before_source=(root/"operations/baseline.py").read_text(); after_source=(root/"operations/system.py").read_text(); source_ok=target in common and set(after)==set(before) and after.get(target)!=before.get(target) and all(after.get(name)==before.get(name) for name in before if name!=target) and shell(after_source,target)==shell(before_source,target)
 shape=(isinstance(package,dict) and set(package)==core and package.get("target_path")==c["target_path"] and target in common and isinstance(package.get("move_id"),str) and re.fullmatch(c["identifier_pattern"],package["move_id"]) and not package["move_id"].startswith("replace-") and all(isinstance(package.get(k),str) and package[k].strip() and not package[k].startswith("replace-") for k in ("stake","next_pursuit")) and isinstance(cases,list) and len(cases)==c["case_count"] and len({case.get("case_id") for case in cases if isinstance(case,dict)})==c["case_count"] and all(isinstance(case,dict) and set(case)==set(c["case_fields"]) and isinstance(case.get("case_id"),str) and re.fullmatch(c["identifier_pattern"],case["case_id"]) and isinstance(case.get("input"),dict) for case in cases) and package.get("predicates")==c["predicates"] and source_ok)
 result=evaluate(target,cases) if shape else {"case_count":0,"all_valid":False,"improvements":0,"confirmations":0,"patched_correct":0,"rows":[]}; success=c["success"]; passed=shape and result["all_valid"] and result["improvements"]>=success["minimum_improvements"] and result["confirmations"]>=success["minimum_confirmations"] and result["patched_correct"]==success["required_patched_correct"]
 return {"passed":bool(passed),"shape_passed":bool(shape),"source_change_passed":bool(source_ok),"result":result}
'''

CHECKER_SOURCE = '''import json
from pathlib import Path
from operations.evaluate import validate
result=validate(json.loads(Path("move-package.json").read_text())); print(json.dumps(result,sort_keys=True)); raise SystemExit(0 if result["passed"] else 2)
'''

FLOOR_SOURCE = '''import unittest
from operations import system

class Floor(unittest.TestCase):
 def test_public_functions_remain_callable(self):
  self.assertTrue(callable(system.schedule_recovery)); self.assertTrue(callable(system.allocate_relief)); self.assertTrue(callable(system.schedule_maintenance))
'''


def write_environment(root: Path, order: tuple[str, ...]) -> None:
    system = ordered_source(SYSTEM_SOURCE, order, ("expected_loss",))
    reference = ordered_source(REFERENCE_SOURCE, order, ("_best",))
    files = {
        "operations/__init__.py": "",
        "operations/system.py": system,
        "operations/baseline.py": system,
        "operations/reference.py": reference,
        "operations/evaluate.py": EVALUATOR_SOURCE,
        "tests/__init__.py": "",
        "tests/test_floor.py": FLOOR_SOURCE,
        "move-contract.json": json.dumps(contract_value(), indent=2, sort_keys=True) + "\n",
        "check_move.py": CHECKER_SOURCE,
    }
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def exact_projection(parent: dict[str, Any]) -> dict[str, Any]:
    projection = authority_base.reuse.worlds.base.active_position(parent)
    projection["semantic_contact_program"] = copy.deepcopy(parent["semantic_contact_program_capabilities"][-1])
    projection["semantic_contact_receipt"] = copy.deepcopy(parent["semantic_contact_receipts"][-1])
    return projection


def branch_projection(parent: dict[str, Any], opening: bool, contact: bool) -> dict[str, Any]:
    projection = exact_projection(parent)
    if not opening:
        projection["continuation"] = {**projection["continuation"], "next_opening": NEUTRAL_OPENING}
    if not contact:
        projection.pop("semantic_contact_program")
        projection.pop("semantic_contact_receipt")
    return projection


def seed_move(root: Path, projection: dict[str, Any], order: tuple[str, ...]) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_environment(seed, order)
    write_json(seed / "subject-position.json", projection)
    write_json(seed / "move-package.json", move_template())
    immutable = ["subject-position.json", "move-contract.json", "check_move.py", "operations/__init__.py", "operations/baseline.py", "operations/reference.py", "operations/evaluate.py", "tests/__init__.py", "tests/test_floor.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": [TARGET_PATH, "move-package.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue from subject-position.json in this complete operations repository. Choose the next locally warranted semantic move without a supplied target list. Follow move-contract.json exactly: edit only operations/system.py and move-package.json, run python3 check_move.py and python3 -m unittest -q tests.test_floor, and inspect the exact diff. Hidden cases are unavailable.\n")
    return seed


def run_move(context, prior131, p82, root: Path, parent: dict[str, Any], opening: bool, contact: bool, order: tuple[str, ...], label: str) -> dict[str, Any]:
    seed = seed_move(root, branch_projection(parent, opening, contact), order)
    output, base_audit, workspace, _ = context.run_actor(label, seed, MOVE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        package = json.loads((workspace / "move-package.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
        valid, public = valid_move(package, workspace / TARGET_PATH, workspace / "operations/reference.py")
    except (OSError, json.JSONDecodeError, KeyError):
        package, immutable_ok, valid, public = None, False, False, None
    accepted = bool(valid and immutable_ok and output and output.get("action") == "author-semantic-move")
    audit = context.audit_actor(label, output, base_audit, accepted, [TARGET_PATH, "move-package.json"])
    binding = None
    if accepted and prior131.audit_accepted(audit):
        patch_source = (workspace / TARGET_PATH).read_text()
        body = {"authority": "ot-0215-bound-semantic-move", "source_subject_digest": parent["artifact_digest"], "projection_digest": p82.digest(branch_projection(parent, opening, contact)), "actor_patch_digest": audit["patch_digest"], "package": package, "package_digest": p82.digest(package), "patched_source": patch_source, "patched_source_digest": p82.digest(patch_source), "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-move.json", binding)
    return {"output": output, "audit": audit, "package": package, "public": public, "binding": binding, "accepted": binding is not None}


def evaluate_binding(binding: dict[str, Any], order: tuple[str, ...], root: Path) -> dict[str, Any]:
    root.mkdir(parents=True)
    write_environment(root, order)
    (root / TARGET_PATH).write_text(binding["patched_source"])
    target = binding["package"]["target_symbol"]
    return evaluate_sources(root / TARGET_PATH, root / "operations/reference.py", target, HIDDEN_CASES[target])


ASSIMILATION_CORE = {"subject_action", "opening_disposition", "move_disposition", "move_binding_digest", "target_symbol", "rationale", "next_pursuit"}


def assimilation_template(binding: dict[str, Any]) -> dict[str, Any]:
    return {"subject_action": "revise", "opening_disposition": "revise", "move_disposition": "retain", "move_binding_digest": binding["binding_digest"], "target_symbol": binding["package"]["target_symbol"], "rationale": "replace-rationale", "next_pursuit": "replace-next-pursuit"}


def valid_assimilation(value: Any, binding: dict[str, Any]) -> bool:
    return bool(isinstance(value, dict) and set(value) == ASSIMILATION_CORE and value.get("subject_action") in {"retain", "revise"} and value.get("opening_disposition") in {"retire", "revise"} and value.get("move_disposition") == "retain" and value.get("move_binding_digest") == binding["binding_digest"] and value.get("target_symbol") == binding["package"]["target_symbol"] and all(isinstance(value.get(key), str) and value[key].strip() and not value[key].startswith("replace-") for key in ("rationale", "next_pursuit")) and value["next_pursuit"] != OPENING)


def seed_assimilator(root: Path, parent: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "subject-position.json", exact_projection(parent))
    write_json(seed / "bound-move.json", binding)
    write_json(seed / "hidden-world-receipt.json", world)
    write_json(seed / "continuation-decision.json", assimilation_template(binding))
    contract = {"authority": "ot-0215-assimilation-contract", "editable_file": "continuation-decision.json", "required_fields": sorted(ASSIMILATION_CORE), "allowed_subject_actions": ["retain", "revise"], "allowed_opening_dispositions": ["retire", "revise"], "required_move_disposition": "retain", "required_move_binding_digest": binding["binding_digest"], "required_target_symbol": binding["package"]["target_symbol"], "forbidden_next_pursuit": OPENING}
    write_json(seed / "continuation-contract.json", contract)
    checker = '''import json
from pathlib import Path
c=json.loads(Path("continuation-contract.json").read_text()); d=json.loads(Path("continuation-decision.json").read_text()); ok=(isinstance(d,dict) and set(d)==set(c["required_fields"]) and d.get("subject_action") in c["allowed_subject_actions"] and d.get("opening_disposition") in c["allowed_opening_dispositions"] and d.get("move_disposition")==c["required_move_disposition"] and d.get("move_binding_digest")==c["required_move_binding_digest"] and d.get("target_symbol")==c["required_target_symbol"] and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("rationale","next_pursuit")) and d.get("next_pursuit")!=c["forbidden_next_pursuit"]); print(json.dumps({"passed":bool(ok)},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''
    (seed / "check_decision.py").write_text(checker)
    immutable = ["subject-position.json", "bound-move.json", "hidden-world-receipt.json", "continuation-contract.json", "check_decision.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["continuation-decision.json"], "immutable": immutable})
    (seed / "README.md").write_text("Assimilate the exact subject move and its independently sealed consequence. Follow continuation-contract.json exactly, edit only continuation-decision.json, run python3 check_decision.py, and inspect the exact diff. Preserve or set down the inherited opening according to consequence and author the next executable pursuit.\n")
    return seed


def run_assimilator(context, prior131, p82, root: Path, parent: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    seed = seed_assimilator(root, parent, binding, world)
    label = "move-assimilator"
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "continuation-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        decision, immutable_ok = None, False
    accepted = bool(valid_assimilation(decision, binding) and immutable_ok and output and output.get("action") == "assimilate-semantic-move")
    audit = context.audit_actor(label, output, base_audit, accepted, ["continuation-decision.json"])
    bound = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": "ot-0215-bound-move-assimilation", "source_subject_digest": parent["artifact_digest"], "move_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision, "decision_digest": p82.digest(decision)}
        bound = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-assimilation.json", bound)
    return {"output": output, "audit": audit, "decision": decision, "binding": bound, "accepted": bound is not None}


def corrected_fixture_source(order: tuple[str, ...], target: str) -> str:
    baseline = function_sources(ordered_source(SYSTEM_SOURCE, order, ("expected_loss",)))
    reference = function_sources(ordered_source(REFERENCE_SOURCE, order, ("_best",)))
    # Fixtures use a local exhaustive implementation so the public runtime has no hidden helper dependency.
    values = {
        "schedule_recovery": ('incidents', 'row["severity"] * row["duration"] * row["probability"]'),
        "allocate_relief": ('requests', 'row["people"] * row["probability"]'),
        "schedule_maintenance": ('tasks', 'row["criticality"] * row["downtime"] * row["failure_probability"]'),
    }
    collection, expression = values[target]
    replacement = f'''def {target}(case):
    items = case["{collection}"]
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > case["capacity"]:
            continue
        score = sum({expression} for row in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])'''
    baseline[target] = ast.unparse(ast.parse(replacement).body[0])
    return "\n\n\n".join(baseline[name] for name in ("expected_loss", *order)) + "\n"


def representative_package(target: str) -> dict[str, Any]:
    return {"move_id": "fixture-semantic-move", "target_path": TARGET_PATH, "target_symbol": target, "stake": "Capacity should maximize consequence-weighted value rather than the largest visible magnitude.", "cases": [copy.deepcopy(HIDDEN_CASES[target][index]) for index in (0, 1, 2, 4)], "predicates": EXPECTED_PREDICATES, "next_pursuit": "Seek the next capacity boundary after sealed consequence."}


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
    run = (args.evidence_root or store / "runs/OT-0215").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0214", "open-subject-after-semantic-contact.json")
    result214 = selector_base.load_artifact(p82, repo, store, "OT-0214", "subject-originated-semantic-contact-aggregate.json")
    full = branch_projection(parent, True, True)
    opening_only = branch_projection(parent, True, False)
    contact_only = branch_projection(parent, False, True)
    neither = branch_projection(parent, False, False)

    fixture_root = run.parent / "OT-0215-preflight"
    if fixture_root.exists():
        import shutil
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    hidden_fixtures = {}
    checker_fixtures = {}
    for order_index, order in enumerate(ORDER_SCHEDULE):
        for target in sorted(TARGETS):
            root = fixture_root / f"order-{order_index + 1}" / target
            root.mkdir(parents=True)
            write_environment(root, order)
            (root / TARGET_PATH).write_text(corrected_fixture_source(order, target))
            package = representative_package(target)
            write_json(root / "move-package.json", package)
            valid, public = valid_move(package, root / TARGET_PATH, root / "operations/reference.py")
            checker = subprocess.run(["python3", "check_move.py"], cwd=root, capture_output=True)
            hidden = evaluate_sources(root / TARGET_PATH, root / "operations/reference.py", target, HIDDEN_CASES[target])
            checker_fixtures[f"{order_index + 1}:{target}"] = {"valid": valid, "checker_returncode": checker.returncode, "public": public}
            hidden_fixtures[f"{order_index + 1}:{target}"] = hidden
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    schema_text = MOVE_SCHEMA.read_text() + ASSIMILATOR_SCHEMA.read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "ot0214_promoted_exact": result214["observer_disposition"] == "promoted" and result214["final_subject_digest"] == PARENT_DIGEST,
        "opening_exact": parent["continuation"]["next_opening"] == OPENING,
        "contact_exact": parent["semantic_contact_program_capabilities"][-1]["binding_digest"] == CONTACT_BINDING and parent["semantic_contact_program_capabilities"][-1]["package_digest"] == CONTACT_PACKAGE,
        "full_projection_exact": full["continuation"]["next_opening"] == OPENING and full["semantic_contact_program"]["binding_digest"] == CONTACT_BINDING,
        "opening_only_exact": opening_only["continuation"]["next_opening"] == OPENING and "semantic_contact_program" not in opening_only and "semantic_contact_receipt" not in opening_only,
        "contact_only_exact": contact_only["continuation"]["next_opening"] == NEUTRAL_OPENING and contact_only["semantic_contact_program"]["binding_digest"] == CONTACT_BINDING,
        "neither_exact": neither["continuation"]["next_opening"] == NEUTRAL_OPENING and "semantic_contact_program" not in neither and "semantic_contact_receipt" not in neither,
        "all_public_contract_fixtures": all(row["valid"] and row["checker_returncode"] == 0 and row["public"]["improvements"] == 3 and row["public"]["confirmations"] == 1 for row in checker_fixtures.values()),
        "all_hidden_fixtures_4_plus_2": all(row["all_valid"] and row["improvements"] == 4 and row["confirmations"] == 2 and row["patched_correct"] == 6 for row in hidden_fixtures.values()),
        "schemas_supported": MOVE_SCHEMA.is_file() and ASSIMILATOR_SCHEMA.is_file() and "uniqueItems" not in schema_text,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0215-preflight", "source_subject_digest": parent["artifact_digest"], "projection_digests": {"full": p82.digest(full), "opening_only": p82.digest(opening_only), "contact_only": p82.digest(contact_only), "neither": p82.digest(neither)}, "hidden_fixtures": hidden_fixtures, "checker_fixtures": checker_fixtures, "checks": checks}
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0215 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    actor_number = 1
    primary_root = run / f"move-{actor_number:02d}"
    primary = run_move(context, prior131, p82, primary_root, parent, True, True, ORDER_SCHEDULE[0], f"move-actor-{actor_number:02d}")
    primary_hidden = evaluate_binding(primary["binding"], ORDER_SCHEDULE[0], run / "primary-hidden-evaluation") if primary["accepted"] else None
    primary_coherent = bool(primary["accepted"] and primary["package"]["target_symbol"] == "schedule_recovery" and primary_hidden["all_valid"] and primary_hidden["improvements"] >= 4 and primary_hidden["confirmations"] >= 2 and primary_hidden["patched_correct"] == 6)
    world = None
    if primary["accepted"]:
        body = {"authority": "ot-0215-sealed-primary-world", "source_subject_digest": parent["artifact_digest"], "move_binding_digest": primary["binding"]["binding_digest"], "target_symbol": primary["package"]["target_symbol"], "hidden_cases_digest": p82.digest(HIDDEN_CASES[primary["package"]["target_symbol"]]), "result": primary_hidden, "local_success": bool(primary_hidden["all_valid"] and primary_hidden["improvements"] >= 4 and primary_hidden["confirmations"] >= 2 and primary_hidden["patched_correct"] == 6), "coherent_continuation": primary_coherent}
        world = {**body, "receipt_digest": p82.digest(body)}
        write_json(run / "primary-hidden-world.json", world)
    assimilation = run_assimilator(context, prior131, p82, run / "assimilation", parent, primary["binding"], world) if primary_coherent else None
    operational = bool(primary_coherent and assimilation and assimilation["accepted"])
    final = parent
    promotion = None
    if operational:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        capability = {"authority": "ot-0215-world-admitted-semantic-move", "move_binding_digest": primary["binding"]["binding_digest"], "target_symbol": primary["package"]["target_symbol"], "package": primary["package"], "patched_source": primary["binding"]["patched_source"], "patched_source_digest": primary["binding"]["patched_source_digest"], "world_receipt_digest": world["receipt_digest"]}
        child["semantic_move_capabilities"] = [*child.get("semantic_move_capabilities", []), capability]
        receipt_body = {"authority": "ot-0215-artifact-conditioned-semantic-continuation", "source_subject_digest": parent["artifact_digest"], "move_binding_digest": primary["binding"]["binding_digest"], "world_receipt_digest": world["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
        promotion = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
        child["semantic_move_receipts"] = [*child.get("semantic_move_receipts", []), promotion]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": assimilation["decision"]["next_pursuit"]}
        child["unresolved"] = "Does carried subject content recurrently improve coherent semantic continuation across qualitatively new objective worlds?"
        candidate = p82.seal(child)
        operational = runtime.identity_conforms(candidate)
        if operational:
            final = candidate
            write_json(run / "provisional-open-successor.json", final)

    rows = []
    if operational:
        rows.append({"actor_id": "move-actor-01", "branch": "full", "order_index": 1, "move": p82.compact(primary), "hidden": primary_hidden, "coherent": primary_coherent})
        schedule = [("full", True, True, 1), ("full", True, True, 2)]
        schedule += [("opening_only", True, False, index) for index in range(3)]
        schedule += [("contact_only", False, True, index) for index in range(3)]
        schedule += [("neither", False, False, index) for index in range(3)]
        for branch, has_opening, has_contact, order_index in schedule:
            actor_number += 1
            label = f"move-actor-{actor_number:02d}"
            move = run_move(context, prior131, p82, run / f"move-{actor_number:02d}", parent, has_opening, has_contact, ORDER_SCHEDULE[order_index], label)
            hidden = evaluate_binding(move["binding"], ORDER_SCHEDULE[order_index], run / f"hidden-{actor_number:02d}") if move["accepted"] else None
            coherent = bool(move["accepted"] and move["package"]["target_symbol"] == "schedule_recovery" and hidden["all_valid"] and hidden["improvements"] >= 4 and hidden["confirmations"] >= 2 and hidden["patched_correct"] == 6)
            rows.append({"actor_id": label, "branch": branch, "order_index": order_index + 1, "move": p82.compact(move), "hidden": hidden, "coherent": coherent})
    counts = {branch: {"actors": sum(row["branch"] == branch for row in rows), "accepted": sum(row["branch"] == branch and row["move"]["accepted"] for row in rows), "recovery_selected": sum(row["branch"] == branch and row["move"]["accepted"] and row["move"]["package"]["target_symbol"] == "schedule_recovery" for row in rows), "coherent": sum(row["branch"] == branch and row["coherent"] for row in rows)} for branch in ("full", "opening_only", "contact_only", "neither")}
    comparison_checks = {"three_actors_per_branch": all(row["actors"] == 3 for row in counts.values()), "full_at_least_two_coherent": counts["full"]["coherent"] >= 2, "neither_at_most_one_coherent": counts["neither"]["coherent"] <= 1, "full_exceeds_neither": counts["full"]["coherent"] > counts["neither"]["coherent"]}
    comparison_checks["passed"] = all(comparison_checks.values())
    operational_checks = {"preflight_passed": checks["passed"], "primary_actor_accepted": primary["accepted"], "primary_selected_recovery_capacity": primary_coherent, "primary_hidden_4_plus_2": bool(primary_hidden and primary_hidden["improvements"] >= 4 and primary_hidden["confirmations"] >= 2 and primary_hidden["patched_correct"] == 6), "assimilation_accepted": bool(assimilation and assimilation["accepted"]), "successor_identity_conforms": operational, "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    operational_checks["passed"] = all(operational_checks.values())
    result = {"authority": "ot-0215-artifact-conditioned-semantic-continuation", "source_subject_digest": parent["artifact_digest"], "primary": p82.compact(primary), "primary_hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "promotion_receipt": promotion, "operational_checks": operational_checks, "comparison_rows": rows, "branch_counts": counts, "comparison_checks": comparison_checks, "causal_interpretation": "supported" if comparison_checks["passed"] else "not-established", "observer_disposition": "promoted" if operational_checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": actor_number + (1 if assimilation else 0)}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
