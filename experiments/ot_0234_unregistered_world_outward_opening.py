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
BASE_PATH = ROOT / "ot_0233_final_registry_correction_reuse.py"
BASE_SHA256 = "91264f0a780113a3c90727bd451ab1e8088179c10633e74b6160b86dee6a341a"
PARENT_DIGEST = "5ec3a3c63bb723f4468dcb6a9e3ef8351c79ec64f96de737f7ce35bf14c0547e"
OT233_RECEIPT = "fd3d0ab4dfc636ac3b2479d5adb4c1432a953b70012e508c8b75592fec64d8b5"
AUTHORITY = "ot-0234-unregistered-world-outward-opening"
SCHEMA = REPO / "spec/ot-0234-outward-opening.schema.json"
ABI = "case-object-to-ordered-identifier-list-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0233 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0234_frozen_ot0233", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base233 = load_base()
base232 = base233.base232
base231 = base232.base231
base229 = base233.base229
base228 = base229.base228
base226 = base228.base226
base225 = base233.base225
base224 = base225.base224
base213 = base233.base213
authority_base = base233.authority_base
PREDICATES = base224.PREDICATES


FIELD_SOURCE = '''def _greedy(items, capacity, magnitude):
    remaining = capacity
    chosen = []
    for item in sorted(items, key=lambda row: (-row[magnitude], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"])
            remaining -= item["effort"]
    return chosen


def dispatch_mobile_clinics(case):
    return _greedy(case["districts"], case["capacity"], "patients")


def restore_water_links(case):
    return _greedy(case["links"], case["capacity"], "households")


def stage_cooling_units(case):
    return _greedy(case["sites"], case["capacity"], "residents")
'''


REFERENCE_SOURCE = '''def _best(items, capacity, value):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > capacity:
            continue
        score = sum(value(item) for item in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])


def dispatch_mobile_clinics(case):
    return _best(case["districts"], case["capacity"], lambda row: row["patients"] * row["delay"] * row["access_risk"])


def restore_water_links(case):
    return _best(case["links"], case["capacity"], lambda row: row["households"] * row["downtime"] * row["failure_risk"])


def stage_cooling_units(case):
    return _best(case["sites"], case["capacity"], lambda row: row["residents"] * row["heat_hours"] * row["medical_risk"])
'''


SURFACES = {
    "dispatch_mobile_clinics": ("districts", "patients", "delay", "access_risk"),
    "restore_water_links": ("links", "households", "downtime", "failure_risk"),
    "stage_cooling_units": ("sites", "residents", "heat_hours", "medical_risk"),
}


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name + hashlib.sha256(path.read_bytes()).hexdigest()[:10], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_world(root: Path, include_reference: bool = False) -> None:
    path = root / "field/operations.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FIELD_SOURCE)
    (root / "field/__init__.py").write_text("")
    if include_reference:
        (root / "field/reference.py").write_text(REFERENCE_SOURCE)


def hidden_cases(target: str) -> list[dict[str, Any]]:
    collection, magnitude, duration, risk = SURFACES[target]
    values = [
        (3, [(10, 1, .2, 3), (6, 8, .9, 3)]),
        (4, [(10, 1, .2, 4), (7, 7, .8, 2), (6, 6, .9, 2)]),
        (5, [(10, 1, .2, 5), (8, 6, .8, 3), (7, 5, .9, 2)]),
        (2, [(8, 8, .8, 2), (10, 1, .2, 2)]),
        (4, [(9, 5, .9, 2), (5, 2, .5, 2)]),
        (4, [(8, 4, .8, 2), (7, 3, .7, 2)]),
    ]
    rows = []
    for index, (capacity, items) in enumerate(values, 1):
        encoded = []
        for offset, (size, span, probability, effort) in enumerate(items):
            encoded.append({"id": chr(103 + offset), magnitude: size, duration: span, risk: probability, "effort": effort})
        rows.append({"case_id": f"sealed-{target}-{index}", "input": {"capacity": capacity, collection: encoded}})
    return rows


HIDDEN_CASES = {target: hidden_cases(target) for target in SURFACES}


def execute_public(root: Path, decision: dict[str, Any]) -> dict[str, Any]:
    contact = decision["next_contact"]
    module = load_module(root / contact["target_path"], "public_")
    function = getattr(module, contact["target_symbol"])
    rows = []
    for case in contact["cases"]:
        try:
            observed = function(copy.deepcopy(case["input"]))
            json.dumps(observed)
            rows.append({"case_id": case["case_id"], "valid": True, "observed": observed})
        except Exception as error:
            rows.append({"case_id": case.get("case_id"), "valid": False, "error_type": type(error).__name__})
    return {"case_count": len(rows), "all_valid": len(rows) == 4 and all(row["valid"] for row in rows), "rows": rows}


def execute_hidden(root: Path, target: str) -> dict[str, Any]:
    installed = getattr(load_module(root / "field/operations.py", "installed_"), target)
    reference = getattr(load_module(root / "field/reference.py", "reference_"), target)
    rows = []
    for case in HIDDEN_CASES[target]:
        try:
            observed = installed(copy.deepcopy(case["input"]))
            expected = reference(copy.deepcopy(case["input"]))
            rows.append({"case_id": case["case_id"], "valid": True, "observed": observed, "expected": expected, "matches": observed == expected})
        except Exception as error:
            rows.append({"case_id": case["case_id"], "valid": False, "matches": False, "error_type": type(error).__name__})
    return {"case_count": len(rows), "all_valid": all(row["valid"] for row in rows), "matches": sum(row["matches"] for row in rows), "rows": rows}


def structural(decision: Any, root: Path, ledger: dict[str, Any]) -> bool:
    if not isinstance(decision, dict) or set(decision) != {"next_pursuit", "extension_rationale", "next_contact"}:
        return False
    if not all(isinstance(decision.get(key), str) and decision[key].strip() and not decision[key].startswith("replace-") for key in ("next_pursuit", "extension_rationale")):
        return False
    contact = decision["next_contact"]
    if not isinstance(contact, dict) or set(contact) != base224.base219.CONTACT_CORE:
        return False
    if not all(isinstance(contact.get(key), str) and contact[key].strip() and not contact[key].startswith("replace-") for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")):
        return False
    path = Path(contact["target_path"])
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py" or not path.parts or path.parts[0] != "field":
        return False
    if contact["target_symbol"] in ledger["targets"] or contact["predicates"] != PREDICATES:
        return False
    cases = contact.get("cases")
    if not isinstance(cases, list) or len(cases) != 4 or len({row.get("case_id") for row in cases if isinstance(row, dict)}) != 4:
        return False
    if not all(isinstance(row, dict) and set(row) == {"case_id", "input"} and isinstance(row["case_id"], str) and row["case_id"].strip() and isinstance(row["input"], dict) for row in cases):
        return False
    try:
        module = load_module(root / path, "structural_")
        function = getattr(module, contact["target_symbol"])
    except (OSError, AttributeError):
        return False
    return callable(function) and len(base224.base219.canonical(contact)) <= 32768


CHECKER = r'''import copy, hashlib, importlib.util, json
from pathlib import Path
root=Path(__file__).parent
d=json.loads((root/"outward-opening.json").read_text()); c=d.get("next_contact") if isinstance(d,dict) else None
contract=json.loads((root/"outward-contract.json").read_text()); ledger=json.loads((root/"local-frontier-ledger.json").read_text())
shape=isinstance(d,dict) and set(d)=={"next_pursuit","extension_rationale","next_contact"} and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("next_pursuit","extension_rationale")) and isinstance(c,dict) and set(c)==set(contract["contact_fields"])
if shape:
 p=Path(c.get("target_path","")); rows=c.get("cases"); shape=bool(not p.is_absolute() and ".." not in p.parts and p.suffix==".py" and p.parts and p.parts[0]=="field" and c.get("target_symbol") not in ledger["targets"] and all(isinstance(c.get(k),str) and c[k].strip() and not c[k].startswith("replace-") for k in ("contact_id","target_path","target_symbol","abi","stake")) and c.get("predicates")==contract["predicates"] and isinstance(rows,list) and len(rows)==4 and len({x.get("case_id") for x in rows if isinstance(x,dict)})==4 and all(isinstance(x,dict) and set(x)=={"case_id","input"} and isinstance(x.get("case_id"),str) and x["case_id"].strip() and isinstance(x.get("input"),dict) for x in rows))
if shape:
 try:
  spec=importlib.util.spec_from_file_location("chosen"+hashlib.sha256((root/p).read_bytes()).hexdigest()[:8],root/p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); fn=getattr(m,c["target_symbol"]); shape=callable(fn)
 except Exception: shape=False
results=[]
if shape:
 for row in c["cases"]:
  try: value=fn(copy.deepcopy(row["input"])); json.dumps(value); results.append({"case_id":row["case_id"],"valid":True})
  except Exception as e: results.append({"case_id":row.get("case_id"),"valid":False,"error_type":type(e).__name__})
passed=shape and len(results)==4 and all(row["valid"] for row in results)
print(json.dumps({"passed":bool(passed),"rows":results},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def template() -> dict[str, Any]:
    return {"next_pursuit": "replace-next-pursuit", "extension_rationale": "replace-rationale", "next_contact": {"contact_id": "replace-contact", "target_path": "replace-path", "target_symbol": "replace-target", "abi": ABI, "stake": "replace-stake", "cases": [], "predicates": copy.deepcopy(PREDICATES)}}


def fixture_decision(target: str) -> dict[str, Any]:
    collection, magnitude, duration, risk = SURFACES[target]
    cases = []
    for index in range(4):
        cases.append({"case_id": f"fixture-{index}", "input": {"capacity": 2 + index, collection: [{"id": "a", magnitude: 2 + index, duration: 1 + index, risk: .2 + index / 10, "effort": 1}, {"id": "b", magnitude: 1, duration: 3, risk: .8, "effort": 2}]}})
    return {"next_pursuit": "Test whether consequence-blind allocation survives outward contact.", "extension_rationale": "This callable is executable but absent from the completed local registry.", "next_contact": {"contact_id": f"fixture-{target}", "target_path": "field/operations.py", "target_symbol": target, "abi": ABI, "stake": "Determine whether magnitude-only allocation preserves the highest consequence-weighted feasible set.", "cases": cases, "predicates": copy.deepcopy(PREDICATES)}}


def seed_actor(root: Path, subject: dict[str, Any], decision: dict[str, Any]) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_world(seed)
    write_json(seed / "exact-subject.json", subject)
    write_json(seed / "subject-position.json", base224.base217.projection(subject))
    write_json(seed / "local-frontier-ledger.json", subject["local_frontier_ledger"])
    write_json(seed / "outward-contract.json", {"authority": AUTHORITY, "contact_fields": sorted(base224.base219.CONTACT_CORE), "predicates": PREDICATES})
    write_json(seed / "outward-opening.json", decision)
    (seed / "check_outward.py").write_text(CHECKER)
    immutable = ["exact-subject.json", "subject-position.json", "local-frontier-ledger.json", "outward-contract.json", "check_outward.py", "field/__init__.py", "field/operations.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["outward-opening.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue from the exact subject position. Inspect the surrounding executable world and, if a coherent outward continuation exists, bind one real contact with it. Do not manufacture another local contact merely to avoid stopping. Edit only outward-opening.json, run python3 check_outward.py, and inspect the exact diff. Hidden consequence is unavailable.\n")
    return seed


def output_valid(output: Any) -> bool:
    return isinstance(output, dict) and set(output) == {"action", "files_changed", "selected_target"} and output.get("action") == "open-outward-contact" and isinstance(output.get("files_changed"), list) and output["files_changed"] == ["outward-opening.json"] and isinstance(output.get("selected_target"), str) and bool(output["selected_target"].strip())


def claim_fidelity(output: Any, target: str, path: str) -> str:
    reported = output.get("selected_target") if isinstance(output, dict) else None
    if reported == target:
        return "exact"
    if reported == f"{path}::{target}":
        return "qualified-consistent"
    return "inconsistent"


def run_actor(context, p82, root: Path, subject: dict[str, Any]) -> dict[str, Any]:
    seed = seed_actor(root, subject, template())
    label = "outward-opening-actor"
    prompt = (seed / "README.md").read_text().strip()
    output, base_audit, workspace, _ = context.run_actor(label, seed, SCHEMA, prompt)
    try:
        decision = json.loads((workspace / "outward-opening.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        structural_ok = structural(decision, workspace, subject["local_frontier_ledger"])
        public = execute_public(workspace, decision) if structural_ok else None
        target = decision["next_contact"]["target_symbol"] if structural_ok else None
        semantic = bool(immutable_ok and structural_ok and target in SURFACES and public and public["all_valid"])
    except (OSError, json.JSONDecodeError, KeyError):
        decision, public, target, semantic = None, None, None, False
    transport = output_valid(output)
    audit = context.audit_actor(label, output, base_audit, semantic and transport, ["outward-opening.json"])
    effect = base226.g8(audit, semantic and transport)
    fidelity = claim_fidelity(output, target, decision["next_contact"]["target_path"]) if target and decision else "inconsistent"
    binding = None
    if effect["causal_effect_accepted"]:
        contact = decision["next_contact"]
        body = {"authority": AUTHORITY + "-actor-authored-binding", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision, "contact_identity": p82.digest({"target_path": contact["target_path"], "target_symbol": contact["target_symbol"], "abi": contact["abi"], "cases": contact["cases"], "predicates": contact["predicates"]}), "public_result": public, "report_fidelity": effect["report_fidelity"], "target_claim_fidelity": fidelity}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-outward-contact.json", binding)
    return {"accepted": binding is not None, "binding": binding, "decision": decision, "public": public, "effect_audit": effect, "output": output, "target_claim_fidelity": fidelity}


def compile_intermediate(subject: dict[str, Any], action: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    contact = copy.deepcopy(action["decision"]["next_contact"])
    target = contact["target_symbol"]
    extension = {"authority": AUTHORITY + "-actor-authored-environment-extension", "source_subject_digest": subject["artifact_digest"], "binding_digest": action["binding"]["binding_digest"], "target_path": contact["target_path"], "target_symbol": target, "abi": contact["abi"], "installed_source": FIELD_SOURCE, "installed_source_digest": p82.digest(FIELD_SOURCE), "status": "bound-outside-inherited-registry"}
    child["actor_authored_environment_extensions"] = [*child.get("actor_authored_environment_extensions", []), extension]
    child["subject_originated_world_stakes"] = [*child.get("subject_originated_world_stakes", []), action["binding"]]
    pending = {"authority": AUTHORITY + "-pending-outward-contact", "binding_digest": action["binding"]["binding_digest"], "contact_identity": action["binding"]["contact_identity"], "package": contact, "package_digest": p82.digest(contact), "consequence_status": "unreceipted"}
    child["pending_contact_bearing_continuations"] = [*child["pending_contact_bearing_continuations"], pending]
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    ledger["targets"][target] = {"status": "verification-due", "admitted_capability_receipts": [], "correction_receipts": [], "independent_success_receipts": [], "latest_world_receipt_digest": None, "latest_world_outcome": None, "origin": "actor-authored-outward-contact"}
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state.update(phase="contact", last_target=target, accepted_actors=state["accepted_actors"] + 1)
    child["fixed_g6_recurrence_driver"] = state
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": action["decision"]["next_pursuit"]}
    child["continuation_liveness"] = {"authority": AUTHORITY, "status": "live-outside-inherited-registry", "contact_identity": pending["contact_identity"], "binding_digest": pending["binding_digest"], "target_status": "verification-due"}
    child["unresolved"] = "Expose the actor-authored outward contact to independent consequence."
    return p82.seal(child)


def compile_world(subject: dict[str, Any], world: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    pending = copy.deepcopy(child["pending_contact_bearing_continuations"])
    pending[-1] = {**pending[-1], "consequence_status": world["outcome"], "world_receipt_digest": world["receipt_digest"]}
    child["pending_contact_bearing_continuations"] = pending
    child["outward_world_receipts"] = [*child.get("outward_world_receipts", []), world]
    target = world["target_symbol"]
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    ledger["targets"][target].update(status="unresolved" if world["outcome"] == "unresolved" else "verified-local", latest_world_receipt_digest=world["receipt_digest"], latest_world_outcome=world["outcome"], independent_success_receipts=[world["receipt_digest"]] if world["outcome"] == "success" else [])
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state["phase"] = "correct" if world["outcome"] == "unresolved" else "assimilate"
    state["encounters"] += 1
    state["history"] = [*state["history"], {"encounter": state["encounters"], "target": target, "outcome": world["outcome"], "receipt_digest": world["receipt_digest"]}]
    child["fixed_g6_recurrence_driver"] = state
    child["continuation_liveness"] = {"authority": AUTHORITY, "status": "unresolved-outward-contact" if world["outcome"] == "unresolved" else "awaiting-outward-reopening", "contact_identity": world["contact_identity"], "world_receipt_digest": world["receipt_digest"], "target_status": ledger["targets"][target]["status"]}
    return p82.seal(child)


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0234").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0233", "open-subject-at-all-target-verification.json")
    result233 = selector_base.load_artifact(p82, repo, store, "OT-0233", "final-registry-correction-reuse-aggregate.json")

    fixture_root = run.parent / "OT-0234-preflight"
    import shutil
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    decisions = {}
    hidden = {}
    prospective = {}
    checker_passes = {}
    for target in sorted(SURFACES):
        seed = seed_actor(fixture_root / target, parent, fixture_decision(target))
        checker = subprocess.run(["python3", "check_outward.py"], cwd=seed, capture_output=True)
        decision = fixture_decision(target)
        structural_ok = structural(decision, seed, parent["local_frontier_ledger"])
        public = execute_public(seed, decision) if structural_ok else None
        binding = {"binding_digest": "a" * 64, "contact_identity": "b" * 64}
        intermediate = compile_intermediate(parent, {"decision": decision, "binding": binding}, p82)
        world_root = fixture_root / f"world-{target}"
        write_world(world_root, include_reference=True)
        observed = execute_hidden(world_root, target)
        outcome = "success" if observed["matches"] >= 4 else ("surrender" if observed["matches"] == 0 else "unresolved")
        body = {"authority": AUTHORITY + "-sealed-world", "source_subject_digest": intermediate["artifact_digest"], "contact_binding_digest": binding["binding_digest"], "contact_identity": binding["contact_identity"], "target_symbol": target, "hidden_cases_digest": p82.digest(HIDDEN_CASES[target]), "reference_source_digest": p82.digest(REFERENCE_SOURCE), "result": observed, "outcome": outcome}
        world = {**body, "receipt_digest": p82.digest(body)}
        final = compile_world(intermediate, world, p82)
        decisions[target] = {"structural": structural_ok, "public": public}
        hidden[target] = observed
        prospective[target] = runtime.identity_conforms(intermediate) and runtime.identity_conforms(final)
        checker_passes[target] = checker.returncode == 0

    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    prompt = (seed_actor(fixture_root / "prompt", parent, template()) / "README.md").read_text()
    inherited = set(parent["expanded_semantic_environment"]["registry"])
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_all_verified_assimilate": parent["artifact_digest"] == PARENT_DIGEST and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate" and all(row["status"] == "verified-local" for row in parent["local_frontier_ledger"]["targets"].values()) and runtime.identity_conforms(parent),
        "ot0233_exact_promotion": result233["observer_disposition"] == "promoted" and result233["receipt_digest"] == OT233_RECEIPT and result233["final_subject_digest"] == PARENT_DIGEST,
        "world_has_no_registry_or_reference": not (fixture_root / sorted(SURFACES)[0] / "seed/environment-registry.json").exists() and not (fixture_root / sorted(SURFACES)[0] / "seed/field/reference.py").exists(),
        "prompt_names_no_surface": not any(target in prompt for target in SURFACES),
        "prompt_names_no_registry_entry": "registry entry" not in prompt.lower(),
        "all_surfaces_outside_inherited_registry": not (set(SURFACES) & inherited),
        "all_dynamic_checkers_pass": all(checker_passes.values()),
        "all_public_contacts_executable": all(row["structural"] and row["public"] and row["public"]["all_valid"] for row in decisions.values()),
        "all_hidden_worlds_2_of_6": all(row["all_valid"] and row["matches"] == 2 for row in hidden.values()),
        "template_rejected": not structural(template(), fixture_root / sorted(SURFACES)[0] / "seed", parent["local_frontier_ledger"]),
        "all_prospective_states_conform": all(prospective.values()),
        "schema_present": SCHEMA.is_file(),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "surface_count": len(SURFACES), "decisions": decisions, "hidden": hidden, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0234 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    action = run_actor(context, p82, run / "assimilation", parent)
    intermediate = compile_intermediate(parent, action, p82) if action["accepted"] else parent
    world = None
    final = intermediate
    if action["accepted"] and runtime.identity_conforms(intermediate):
        target = action["decision"]["next_contact"]["target_symbol"]
        world_root = run / "world"
        write_world(world_root, include_reference=True)
        observed = execute_hidden(world_root, target)
        outcome = "success" if observed["matches"] >= 4 else ("surrender" if observed["matches"] == 0 else "unresolved")
        body = {"authority": AUTHORITY + "-sealed-world", "source_subject_digest": intermediate["artifact_digest"], "contact_binding_digest": action["binding"]["binding_digest"], "contact_identity": action["binding"]["contact_identity"], "target_symbol": target, "hidden_cases_digest": p82.digest(HIDDEN_CASES[target]), "reference_source_digest": p82.digest(REFERENCE_SOURCE), "result": observed, "outcome": outcome}
        world = {**body, "receipt_digest": p82.digest(body)}
        write_json(run / "hidden-world-receipt.json", world)
        final = compile_world(intermediate, world, p82)
    target = action["decision"]["next_contact"]["target_symbol"] if action["accepted"] else None
    gates = {
        "preflight_passed": checks["passed"],
        "fresh_actor_accepted": action["accepted"],
        "selected_outside_inherited_registry": bool(target and target in SURFACES and target not in inherited),
        "g8_effect_accepted": action["effect_audit"]["causal_effect_accepted"],
        "public_contact_executable": bool(action["public"] and action["public"]["all_valid"]),
        "actor_authored_extension_retained": bool(action["accepted"] and intermediate["actor_authored_environment_extensions"][-1]["target_symbol"] == target),
        "inherited_registry_unchanged": intermediate["expanded_semantic_environment"]["registry"] == parent["expanded_semantic_environment"]["registry"] if action["accepted"] else False,
        "intermediate_open_conformant": action["accepted"] and intermediate["continuation"]["status"] == "open" and runtime.identity_conforms(intermediate),
        "independent_world_valid": bool(world and world["result"]["all_valid"]),
        "world_2_of_6": bool(world and world["result"]["matches"] == 2),
        "outward_target_unresolved": bool(world and final["local_frontier_ledger"]["targets"][target]["status"] == "unresolved"),
        "final_open_correct": final["continuation"]["status"] == "open" and final["fixed_g6_recurrence_driver"]["phase"] == "correct" and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "outward_opening": action, "intermediate_subject_digest": intermediate["artifact_digest"], "world": world, "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1}
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
