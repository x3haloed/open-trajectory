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
BASE_PATH = ROOT / "ot_0217_two_handoff_contact_bearing_continuation.py"
BASE_SHA256 = "5b297e1caa925359f784bad2b9548e70517e57d53562205080b1bd9e6f2f4e4b"
PARENT_DIGEST = "ee5b552a12d8f1c6378cca143dcb44af5db287b432c9e7a01884a41c294ff193"
WORLD_RECEIPT = "0dd175ffefc08ffaf70f92e2a43c62f95a33fad296eb060b87a823fc51298f1b"
CONTACT_BINDING = "8770ed1d66c47588fc28e34e2caa854306a98f58b9cb547301b8610bb332532a"
CONTACT_IDENTITY = "895aa8ed9d2b0bf2cffdec1afb4ebff6c070f04013abdf36bae1b9846648bdb5"
TARGET = "schedule_maintenance"
CORRECTOR_SCHEMA = REPO / "spec/ot-0218-corrector.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0218-assimilator.schema.json"
CORRECTION_PREDICATES = {"success": {"minimum_matches": 6}, "surrender": {"maximum_matches": 0}, "unresolved": {"otherwise": True}}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0217 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0218_frozen_ot0217", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base217 = load_base()
base216 = base217.base216
base215 = base217.base215
base213 = base217.base213
authority_base = base217.authority_base
ABI = base217.ABI
PREDICATES = base217.PREDICATES


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installed_source(parent: dict[str, Any]) -> str:
    return parent["semantic_move_capabilities"][-1]["patched_source"]


def write_environment(root: Path, source: str) -> None:
    reference = base215.ordered_source(base215.REFERENCE_SOURCE, base215.ORDER_SCHEDULE[0], ("_best",))
    files = {"operations/__init__.py": "", "operations/system.py": source, "operations/baseline.py": source, "operations/reference.py": reference}
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def execute(system_path: Path, reference_path: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    system = load_module(system_path, "ot0218_system_" + hashlib.sha256(system_path.read_bytes()).hexdigest()[:12])
    reference = load_module(reference_path, "ot0218_reference_" + hashlib.sha256(reference_path.read_bytes()).hexdigest()[:12])
    rows = []
    for case in cases:
        try:
            observed = getattr(system, TARGET)(copy.deepcopy(case["input"]))
            expected = getattr(reference, TARGET)(copy.deepcopy(case["input"]))
            rows.append({"case_id": case["case_id"], "observed": observed, "expected": expected, "matches": observed == expected, "valid": True})
        except Exception as error:
            rows.append({"case_id": case.get("case_id"), "error_type": type(error).__name__, "matches": False, "valid": False})
    return {"case_count": len(rows), "all_valid": all(row["valid"] for row in rows), "matches": sum(row["matches"] for row in rows), "rows": rows}


def target_only_change(candidate: str, baseline: str) -> bool:
    return base215.target_only_change(candidate, baseline, TARGET)


def task(identity: str, criticality: int, downtime: int, probability: float, effort: int) -> dict[str, Any]:
    return {"id": identity, "criticality": criticality, "downtime": downtime, "failure_probability": probability, "effort": effort}


FOLLOWUP_CASES = [
    {"case_id": "maintenance-followup-1", "input": {"capacity": 3, "tasks": [task("j", 9, 1, .2, 3), task("k", 6, 9, .9, 3)]}},
    {"case_id": "maintenance-followup-2", "input": {"capacity": 4, "tasks": [task("j", 10, 1, .2, 4), task("k", 7, 7, .8, 2), task("l", 6, 6, .9, 2)]}},
    {"case_id": "maintenance-followup-3", "input": {"capacity": 5, "tasks": [task("j", 10, 1, .2, 5), task("k", 8, 6, .8, 3), task("l", 7, 5, .9, 2)]}},
    {"case_id": "maintenance-followup-4", "input": {"capacity": 2, "tasks": [task("j", 8, 9, .8, 2), task("k", 10, 1, .2, 2)]}},
    {"case_id": "maintenance-followup-5", "input": {"capacity": 4, "tasks": [task("j", 9, 5, .9, 2), task("k", 5, 2, .5, 2)]}},
    {"case_id": "maintenance-followup-6", "input": {"capacity": 4, "tasks": [task("j", 8, 4, .8, 2), task("k", 7, 3, .7, 2)]}},
]


CORRECTION_CORE = {"disposition", "source_subject_digest", "contact_binding_digest", "contact_identity", "world_receipt_digest", "target_symbol", "predicates", "rationale", "next_pursuit"}


def correction_template() -> dict[str, Any]:
    return {"disposition": "revise", "source_subject_digest": PARENT_DIGEST, "contact_binding_digest": CONTACT_BINDING, "contact_identity": CONTACT_IDENTITY, "world_receipt_digest": WORLD_RECEIPT, "target_symbol": TARGET, "predicates": copy.deepcopy(CORRECTION_PREDICATES), "rationale": "replace-rationale", "next_pursuit": "replace-next-pursuit"}


def valid_decision(value: Any, system_path: Path, baseline: str, original_cases: list[dict[str, Any]], reference_path: Path) -> tuple[bool, dict[str, Any] | None]:
    if not isinstance(value, dict) or set(value) != CORRECTION_CORE: return False, None
    exact = value.get("source_subject_digest") == PARENT_DIGEST and value.get("contact_binding_digest") == CONTACT_BINDING and value.get("contact_identity") == CONTACT_IDENTITY and value.get("world_receipt_digest") == WORLD_RECEIPT and value.get("target_symbol") == TARGET and value.get("predicates") == CORRECTION_PREDICATES
    prose = all(isinstance(value.get(key), str) and value[key].strip() and not value[key].startswith("replace-") for key in ("rationale", "next_pursuit"))
    if not exact or not prose or value.get("disposition") not in {"revise", "surrender"}: return False, None
    source = system_path.read_text()
    if value["disposition"] == "surrender": return source == baseline, None
    if not target_only_change(source, baseline): return False, None
    public = execute(system_path, reference_path, original_cases)
    return bool(public["all_valid"] and public["matches"] == 4), public


CHECK_CORRECTION_SOURCE = '''import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
def load(path,name):
 s=importlib.util.spec_from_file_location(name+hashlib.sha256(path.read_bytes()).hexdigest()[:10],path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def functions(source): return {n.name:ast.unparse(n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
def shell(source,target):
 tree=ast.parse(source); return ast.dump(ast.Module(body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name==target)],type_ignores=[]),include_attributes=False)
root=Path(__file__).parent; c=json.loads(Path("correction-contract.json").read_text()); d=json.loads(Path("correction-decision.json").read_text()); source=Path("operations/system.py").read_text(); baseline=Path("operations/baseline.py").read_text(); target=c["target_symbol"]; before=functions(baseline); after=functions(source); exact_change=set(after)==set(before) and after.get(target)!=before.get(target) and all(after.get(k)==before.get(k) for k in before if k!=target) and shell(source,target)==shell(baseline,target)
shape=isinstance(d,dict) and set(d)==set(c["required_fields"]) and d.get("disposition") in c["allowed_dispositions"] and all(d.get(k)==v for k,v in c["required_identities"].items()) and d.get("target_symbol")==target and d.get("predicates")==c["predicates"] and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("rationale","next_pursuit"))
rows=[]
if shape and d["disposition"]=="revise" and exact_change:
 system=load(Path("operations/system.py"),"system"); reference=load(Path("operations/reference.py"),"reference"); cases=json.loads(Path("bound-contact.json").read_text())["decision"]["next_contact"]["cases"]
 for x in cases:
  try:
   observed=getattr(system,target)(copy.deepcopy(x["input"])); expected=getattr(reference,target)(copy.deepcopy(x["input"])); rows.append({"case_id":x["case_id"],"valid":True,"matches":observed==expected})
  except Exception as error: rows.append({"case_id":x.get("case_id"),"valid":False,"matches":False,"error_type":type(error).__name__})
passed=shape and ((d["disposition"]=="revise" and exact_change and len(rows)==4 and all(x["valid"] and x["matches"] for x in rows)) or (d["disposition"]=="surrender" and source==baseline)); print(json.dumps({"passed":bool(passed),"shape_passed":bool(shape),"exact_change":bool(exact_change),"matches":sum(x["matches"] for x in rows),"rows":rows},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def correction_contract() -> dict[str, Any]:
    return {"authority": "ot-0218-correction-contract", "required_fields": sorted(CORRECTION_CORE), "allowed_dispositions": ["revise", "surrender"], "required_identities": {"source_subject_digest": PARENT_DIGEST, "contact_binding_digest": CONTACT_BINDING, "contact_identity": CONTACT_IDENTITY, "world_receipt_digest": WORLD_RECEIPT}, "target_symbol": TARGET, "predicates": CORRECTION_PREDICATES}


def correction_seed(root: Path, parent: dict[str, Any], origin_binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_environment(seed, installed_source(parent))
    write_json(seed / "subject-position.json", base217.projection(parent))
    write_json(seed / "bound-contact.json", origin_binding)
    write_json(seed / "unresolved-world-receipt.json", world)
    write_json(seed / "correction-contract.json", correction_contract())
    write_json(seed / "correction-decision.json", correction_template())
    (seed / "check_correction.py").write_text(CHECK_CORRECTION_SOURCE)
    immutable = ["subject-position.json", "bound-contact.json", "unresolved-world-receipt.json", "correction-contract.json", "check_correction.py", "operations/__init__.py", "operations/baseline.py", "operations/reference.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["operations/system.py", "correction-decision.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the exact pending maintenance contact from its unresolved public and sealed consequence. Revise exactly schedule_maintenance or surrender it under correction-contract.json. Edit only operations/system.py and correction-decision.json as your disposition requires, run python3 check_correction.py, and inspect the exact diff. Follow-up hidden cases are unavailable.\n")
    return seed


def run_corrector(context, prior131, p82, root: Path, parent: dict[str, Any], origin_binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    seed = correction_seed(root, parent, origin_binding, world)
    label = "unresolved-contact-corrector"
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision_value = json.loads((workspace / "correction-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
        valid, public = valid_decision(decision_value, workspace / "operations/system.py", (workspace / "operations/baseline.py").read_text(), origin_binding["decision"]["next_contact"]["cases"], workspace / "operations/reference.py")
    except (OSError, json.JSONDecodeError, KeyError):
        decision_value, immutable_ok, valid, public = None, False, False, None
    expected_paths = ["correction-decision.json", "operations/system.py"] if decision_value and decision_value.get("disposition") == "revise" else ["correction-decision.json"]
    accepted = bool(valid and immutable_ok and output and output.get("action") == "correct-unresolved-contact")
    audit = context.audit_actor(label, output, base_audit, accepted, expected_paths)
    binding = None
    if accepted and prior131.audit_accepted(audit):
        source = (workspace / "operations/system.py").read_text()
        body = {"authority": "ot-0218-bound-unresolved-contact-correction", "source_subject_digest": parent["artifact_digest"], "contact_binding_digest": CONTACT_BINDING, "world_receipt_digest": WORLD_RECEIPT, "actor_patch_digest": audit["patch_digest"], "decision": decision_value, "patched_source": source if decision_value["disposition"] == "revise" else None, "patched_source_digest": p82.digest(source) if decision_value["disposition"] == "revise" else None, "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-correction.json", binding)
    return {"output": output, "audit": audit, "decision": decision_value, "public": public, "binding": binding, "accepted": binding is not None}


def corrected_fixture_source(parent: dict[str, Any]) -> str:
    current = base215.function_sources(installed_source(parent))
    fixture = base215.function_sources(base215.corrected_fixture_source(base215.ORDER_SCHEDULE[0], TARGET))
    current[TARGET] = fixture[TARGET]
    return "\n\n\n".join(current[name] for name in ("expected_loss", "schedule_recovery", "allocate_relief", "schedule_maintenance")) + "\n"


def compile_corrected(parent: dict[str, Any], origin_binding: dict[str, Any], unresolved_world: dict[str, Any], correction: dict[str, Any], followup: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    pending = copy.deepcopy(child["pending_contact_bearing_continuations"])
    pending[-1] = {**pending[-1], "consequence_status": "resolved-after-correction", "unresolved_world_receipt_digest": unresolved_world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}
    child["pending_contact_bearing_continuations"] = pending
    if correction["decision"]["disposition"] == "revise":
        capability = {"authority": "ot-0218-world-admitted-maintenance-correction", "target_symbol": TARGET, "package": copy.deepcopy(origin_binding["decision"]["next_contact"]), "patched_source": correction["binding"]["patched_source"], "patched_source_digest": correction["binding"]["patched_source_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "world_receipt_digest": followup["receipt_digest"]}
        child["semantic_move_capabilities"] = [*child.get("semantic_move_capabilities", []), capability]
    receipt_body = {"authority": "ot-0218-unresolved-contact-correction", "source_subject_digest": parent["artifact_digest"], "contact_identity": CONTACT_IDENTITY, "unresolved_world_receipt_digest": unresolved_world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"], "outcome": followup["outcome"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["unresolved_contact_correction_receipts"] = [*child.get("unresolved_contact_correction_receipts", []), receipt]
    child["continuation_liveness"] = {"authority": "G5-contact-bearing-continuation-liveness", "status": "awaiting-reopening", "resolved_contact_identity": CONTACT_IDENTITY, "correction_receipt_digest": receipt["receipt_digest"], "transition_receipt_digest": base217.G5_RECEIPT}
    return p82.seal(child)


def run_assimilator(context, prior131, p82, root: Path, corrected: dict[str, Any], origin_binding: dict[str, Any], unresolved_world: dict[str, Any], correction: dict[str, Any], followup: dict[str, Any]) -> dict[str, Any]:
    completed = base217.registry_for(corrected, origin_binding["decision"]["next_contact"])
    contract = {"authority": "ot-0218-assimilator-contract", "mode": "assimilator", "required_decision_fields": ["resolved_contact_disposition", "resolved_contact_identity", "world_receipt_digest", "next_pursuit", "next_contact"], "contact_fields": sorted(base216.CONTACT_CORE), "predicates": PREDICATES, "minimum_new_inputs": 2, "forbidden_target": TARGET, "allowed_dispositions": [correction["decision"]["disposition"]], "resolved_contact_identity": CONTACT_IDENTITY, "world_receipt_digest": followup["receipt_digest"]}
    template = {"resolved_contact_disposition": correction["decision"]["disposition"], "resolved_contact_identity": CONTACT_IDENTITY, "world_receipt_digest": followup["receipt_digest"], "next_pursuit": "replace-next-pursuit", "next_contact": base217.contact_template()}
    attachments = {"bound-contact.json": origin_binding, "unresolved-world-receipt.json": unresolved_world, "followup-world-receipt.json": followup, "bound-correction.json": correction["binding"]}
    seed = base217.seed_actor(root, corrected, completed, contract, template, "Assimilate the exact corrected maintenance consequence and end carrying a G5-valid contact on a different callable.", attachments)
    label = "post-correction-assimilator"
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision_value = json.loads((workspace / "continuation-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
        contact_check = base217.valid_contact(decision_value.get("next_contact"), completed)
        public = base217.execute_cases(workspace / "operations/system.py", workspace / "operations/reference.py", decision_value["next_contact"]["target_symbol"], decision_value["next_contact"]["cases"]) if contact_check["accepted"] else None
        valid = bool(contact_check["accepted"] and public["all_valid"] and decision_value.get("resolved_contact_disposition") == correction["decision"]["disposition"] and decision_value.get("resolved_contact_identity") == CONTACT_IDENTITY and decision_value.get("world_receipt_digest") == followup["receipt_digest"] and decision_value["next_contact"]["target_symbol"] != TARGET and isinstance(decision_value.get("next_pursuit"), str) and decision_value["next_pursuit"].strip())
    except (OSError, json.JSONDecodeError, KeyError):
        decision_value, immutable_ok, contact_check, public, valid = None, False, {"accepted": False}, None, False
    accepted = bool(valid and immutable_ok and output and output.get("action") == "assimilate-correction-and-reopen")
    audit = context.audit_actor(label, output, base_audit, accepted, ["continuation-decision.json"])
    binding = None
    if accepted and prior131.audit_accepted(audit):
        body = {"authority": "ot-0218-bound-post-correction-assimilation", "source_subject_digest": corrected["artifact_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision_value, "next_contact_identity": contact_check["contact_identity"], "next_new_input_count": contact_check["new_input_count"], "public_result": public}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-assimilation.json", binding)
    return {"output": output, "audit": audit, "decision": decision_value, "contact_check": contact_check, "public": public, "binding": binding, "accepted": binding is not None}


def compile_final(corrected: dict[str, Any], assimilation: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(corrected)
    child.pop("artifact_digest", None)
    package = assimilation["decision"]["next_contact"]
    pending = {"authority": "G5-pending-contact-bearing-continuation", "binding_digest": assimilation["binding"]["binding_digest"], "contact_identity": assimilation["binding"]["next_contact_identity"], "package": copy.deepcopy(package), "package_digest": p82.digest(package), "consequence_status": "unreceipted"}
    child["pending_contact_bearing_continuations"] = [*child.get("pending_contact_bearing_continuations", []), pending]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": assimilation["decision"]["next_pursuit"]}
    child["continuation_liveness"] = {"authority": "G5-contact-bearing-continuation-liveness", "status": "live", "contact_identity": pending["contact_identity"], "binding_digest": pending["binding_digest"], "transition_receipt_digest": base217.G5_RECEIPT}
    child["unresolved"] = "Expose the post-correction pending contact to independent consequence and continue from its receipt."
    return p82.seal(child)


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
    run = (args.evidence_root or store / "runs/OT-0218").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0217", "live-subject-before-unresolved-contact-assimilation.json")
    result217 = selector_base.load_artifact(p82, repo, store, "OT-0217", "two-handoff-contact-bearing-continuation-aggregate.json")
    origin_binding = result217["originator"]["binding"]
    unresolved_world = result217["hidden_world"]
    fixture_root = run.parent / "OT-0218-preflight"
    if fixture_root.exists():
        import shutil
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    baseline_root = fixture_root / "baseline"
    baseline_root.mkdir()
    write_environment(baseline_root, installed_source(parent))
    original_public = execute(baseline_root / "operations/system.py", baseline_root / "operations/reference.py", origin_binding["decision"]["next_contact"]["cases"])
    unchanged_followup = execute(baseline_root / "operations/system.py", baseline_root / "operations/reference.py", FOLLOWUP_CASES)
    corrected_root = fixture_root / "corrected"
    corrected_root.mkdir()
    corrected_source = corrected_fixture_source(parent)
    write_environment(corrected_root, installed_source(parent))
    (corrected_root / "operations/system.py").write_text(corrected_source)
    corrected_public = execute(corrected_root / "operations/system.py", corrected_root / "operations/reference.py", origin_binding["decision"]["next_contact"]["cases"])
    corrected_followup = execute(corrected_root / "operations/system.py", corrected_root / "operations/reference.py", FOLLOWUP_CASES)
    checker_seed = correction_seed(fixture_root / "correction-checker", parent, origin_binding, unresolved_world)
    (checker_seed / "operations/system.py").write_text(corrected_source)
    fixture_decision = correction_template()
    fixture_decision.update(rationale="The unresolved rows contradict criticality-only priority.", next_pursuit="Confirm expected maintenance risk under new sealed contact.")
    write_json(checker_seed / "correction-decision.json", fixture_decision)
    correction_checker = subprocess.run(["python3", "check_correction.py"], cwd=checker_seed, capture_output=True)
    fixture_correction = {"decision": fixture_decision, "binding": {"binding_digest": "a" * 64, "patched_source": corrected_source, "patched_source_digest": p82.digest(corrected_source)}}
    fixture_followup = {"receipt_digest": "b" * 64, "outcome": "success"}
    prospective_corrected = compile_corrected(parent, origin_binding, unresolved_world, fixture_correction, fixture_followup, p82)
    completed = base217.registry_for(prospective_corrected, origin_binding["decision"]["next_contact"])
    fixture_next = base217.representative_contact("schedule_recovery", "post-correction")
    fixture_next_check = base217.valid_contact(fixture_next, completed)
    fixture_assim_decision = {"resolved_contact_disposition": "revise", "resolved_contact_identity": CONTACT_IDENTITY, "world_receipt_digest": fixture_followup["receipt_digest"], "next_pursuit": "Open a different recovery contact.", "next_contact": fixture_next}
    fixture_contract = {"authority": "ot-0218-assimilator-contract", "mode": "assimilator", "required_decision_fields": list(fixture_assim_decision), "contact_fields": sorted(base216.CONTACT_CORE), "predicates": PREDICATES, "minimum_new_inputs": 2, "forbidden_target": TARGET, "allowed_dispositions": ["revise"], "resolved_contact_identity": CONTACT_IDENTITY, "world_receipt_digest": fixture_followup["receipt_digest"]}
    assimilation_seed = base217.seed_actor(fixture_root / "assimilation-checker", prospective_corrected, completed, fixture_contract, fixture_assim_decision, "Fixture", {"bound-contact.json": origin_binding, "unresolved-world-receipt.json": unresolved_world, "followup-world-receipt.json": fixture_followup, "bound-correction.json": fixture_correction["binding"]})
    assimilation_checker = subprocess.run(["python3", "check_continuation.py"], cwd=assimilation_seed, capture_output=True)
    fixture_assim = {"decision": fixture_assim_decision, "binding": {"binding_digest": "c" * 64, "next_contact_identity": fixture_next_check["contact_identity"]}}
    prospective_final = compile_final(prospective_corrected, fixture_assim, p82)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    schema_text = CORRECTOR_SCHEMA.read_text() + ASSIMILATOR_SCHEMA.read_text()
    checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_live": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation_liveness"]["status"] == "live" and runtime.identity_conforms(parent), "ot0217_exact_rejection": result217["observer_disposition"] == "rejected" and result217["final_subject_digest"] == PARENT_DIGEST, "receipt_exact_unresolved": unresolved_world["receipt_digest"] == WORLD_RECEIPT and unresolved_world["outcome"] == "unresolved" and unresolved_world["result"]["matches"] == 2, "contact_exact": origin_binding["binding_digest"] == CONTACT_BINDING and origin_binding["contact_identity"] == CONTACT_IDENTITY, "original_public_replay_1_of_4": original_public["all_valid"] and original_public["matches"] == 1, "unchanged_followup_2_of_6": unchanged_followup["all_valid"] and unchanged_followup["matches"] == 2, "corrected_public_4_of_4": corrected_public["all_valid"] and corrected_public["matches"] == 4, "corrected_followup_6_of_6": corrected_followup["all_valid"] and corrected_followup["matches"] == 6, "target_only_fixture_change": target_only_change(corrected_source, installed_source(parent)), "corrector_checker_passed": correction_checker.returncode == 0, "assimilator_checker_passed": assimilation_checker.returncode == 0 and fixture_next_check["accepted"], "prospective_corrected_conforms": runtime.identity_conforms(prospective_corrected), "prospective_final_conforms": runtime.identity_conforms(prospective_final) and prospective_final["continuation_liveness"]["status"] == "live", "schemas_supported": CORRECTOR_SCHEMA.is_file() and ASSIMILATOR_SCHEMA.is_file() and "uniqueItems" not in schema_text, "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0218-preflight", "source_subject_digest": parent["artifact_digest"], "original_public": original_public, "unchanged_followup": unchanged_followup, "corrected_public": corrected_public, "corrected_followup": corrected_followup, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0218 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    correction = run_corrector(context, prior131, p82, run / "correction", parent, origin_binding, unresolved_world)
    followup = corrected = assimilation = None
    if correction["accepted"]:
        if correction["decision"]["disposition"] == "revise":
            eval_root = run / "followup-evaluation"
            eval_root.mkdir()
            write_environment(eval_root, installed_source(parent))
            (eval_root / "operations/system.py").write_text(correction["binding"]["patched_source"])
            observed = execute(eval_root / "operations/system.py", eval_root / "operations/reference.py", FOLLOWUP_CASES)
            control = execute(eval_root / "operations/baseline.py", eval_root / "operations/reference.py", FOLLOWUP_CASES)
            outcome = "success" if observed["all_valid"] and observed["matches"] >= 6 else ("surrender" if observed["all_valid"] and observed["matches"] <= 0 else "unresolved")
            gate = outcome == "success" and control["matches"] <= 2
        else:
            observed, control, outcome, gate = None, None, "surrender", True
        body = {"authority": "ot-0218-sealed-correction-world", "source_subject_digest": parent["artifact_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_cases_digest": p82.digest(FOLLOWUP_CASES), "result": observed, "unchanged_control": control, "outcome": outcome, "world_promotion_gate": gate}
        followup = {**body, "receipt_digest": p82.digest(body)}
        write_json(run / "followup-world-receipt.json", followup)
    if followup and followup["world_promotion_gate"]:
        candidate = compile_corrected(parent, origin_binding, unresolved_world, correction, followup, p82)
        if runtime.identity_conforms(candidate):
            corrected = candidate
            write_json(run / "corrected-subject.json", corrected)
            assimilation = run_assimilator(context, prior131, p82, run / "assimilation", corrected, origin_binding, unresolved_world, correction, followup)
    final = corrected or parent
    final_ok = False
    if assimilation and assimilation["accepted"]:
        candidate = compile_final(corrected, assimilation, p82)
        final_ok = runtime.identity_conforms(candidate)
        if final_ok: final = candidate
    replay = bool(final_ok and base217.valid_contact(final["pending_contact_bearing_continuations"][-1]["package"], base217.registry_for(final, origin_binding["decision"]["next_contact"]))["accepted"])
    gates = {"preflight_passed": checks["passed"], "corrector_accepted": correction["accepted"], "correction_disposition_decisive": bool(correction["accepted"] and correction["decision"]["disposition"] in {"revise", "surrender"}), "followup_world_decisive": bool(followup and followup["world_promotion_gate"]), "corrected_subject_conforms": corrected is not None, "assimilator_accepted": bool(assimilation and assimilation["accepted"]), "different_target_g5_reopening": bool(assimilation and assimilation["accepted"] and assimilation["decision"]["next_contact"]["target_symbol"] != TARGET), "pending_contact_replay": replay, "final_subject_conforms": final_ok, "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    gates["passed"] = all(gates.values())
    result = {"authority": "ot-0218-unresolved-consequence-correction-handoff", "source_subject_digest": parent["artifact_digest"], "correction": p82.compact(correction), "followup_world": followup, "corrected_subject_digest": corrected["artifact_digest"] if corrected else None, "assimilation": p82.compact(assimilation) if assimilation else None, "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final.get("continuation_liveness"), "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 + (1 if assimilation else 0)}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
