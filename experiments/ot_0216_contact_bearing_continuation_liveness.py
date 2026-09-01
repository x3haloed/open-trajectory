from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0215_artifact_conditioned_semantic_continuation.py"
BASE_SHA256 = "812f13991c7ae8cd166c8cb524c6b97f8cf5d1a13ed94ac175af6fedef39a7c8"
PARENT_DIGEST = "f0e044c284e7dd42fbd1811b0cd37d49201c4d883abd36affe98c1fb9d0f449c"
INHERITED_OPENING = "Test whether recovery ordering remains correct when recovery jobs compete for limited capacity and losses can be jointly recovered."
GENERATOR_SEED = 216_503_911
ABI = "case-object-to-ordered-identifier-list-v1"
PREDICATES = {"success": {"minimum_confirmations": 3}, "surrender": {"maximum_confirmations": 0}, "unresolved": {"otherwise": True}}
CONTACT_CORE = {"contact_id", "target_path", "target_symbol", "abi", "stake", "cases", "predicates"}
DECISION_CORE = {"next_pursuit", "next_contact"}
AVAILABLE_INTERFACES = {
    "schedule_recovery": {"target_path": "operations/system.py", "abi": ABI},
    "order_recovery": {"target_path": "operations/system.py", "abi": ABI},
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0215 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0216_frozen_ot0215", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base215 = load_base()
base213 = base215.base213
authority_base = base215.authority_base


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def input_key(target: str, target_path: str, abi: str, case_input: dict[str, Any]) -> str:
    return digest({"target_symbol": target, "target_path": target_path, "abi": abi, "input": case_input})


def contact_identity(value: dict[str, Any]) -> str:
    return digest({"target_symbol": value["target_symbol"], "target_path": value["target_path"], "abi": value["abi"], "case_inputs": sorted(digest(case["input"]) for case in value["cases"]), "predicates": value["predicates"]})


def completed_registry(parent: dict[str, Any]) -> dict[str, Any]:
    packages = []
    for capability in parent.get("semantic_contact_program_capabilities", []):
        package = capability["package"]
        packages.append({"target_symbol": package["target_symbol"], "target_path": package["target_path"], "abi": ABI, "cases": copy.deepcopy(package["cases"]), "predicates": PREDICATES})
    for capability in parent.get("semantic_move_capabilities", []):
        package = capability["package"]
        packages.append({"target_symbol": package["target_symbol"], "target_path": package["target_path"], "abi": ABI, "cases": copy.deepcopy(package["cases"]), "predicates": PREDICATES})
    identities = {contact_identity(package) for package in packages}
    inputs: dict[str, set[str]] = {}
    for package in packages:
        target = package["target_symbol"]
        inputs.setdefault(target, set()).update(input_key(target, package["target_path"], package["abi"], case["input"]) for case in package["cases"])
    return {"packages": packages, "identities": identities, "inputs": inputs}


def incumbent_g4_accepts(value: Any) -> bool:
    if not isinstance(value, dict) or not DECISION_CORE.issubset(value):
        return False
    if not isinstance(value.get("next_pursuit"), str) or not value["next_pursuit"].strip() or value["next_pursuit"] == INHERITED_OPENING:
        return False
    extras = {key: item for key, item in value.items() if key not in DECISION_CORE}
    return len(extras) <= 8 and all(base213.EXTENSION_KEY.fullmatch(key) and base213.safe_extension(item) for key, item in extras.items())


def valid_contact(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != CONTACT_CORE:
        return False
    if not all(isinstance(value.get(key), str) and value[key].strip() for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")):
        return False
    interface = AVAILABLE_INTERFACES.get(value["target_symbol"])
    if not interface or value["target_path"] != interface["target_path"] or value["abi"] != interface["abi"]:
        return False
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 4 or len({case.get("case_id") for case in cases if isinstance(case, dict)}) != 4:
        return False
    if not all(isinstance(case, dict) and set(case) == {"case_id", "input"} and isinstance(case["case_id"], str) and case["case_id"].strip() and isinstance(case["input"], dict) for case in cases):
        return False
    return value.get("predicates") == PREDICATES and len(canonical(value)) <= 32768


def challenger_g5(value: Any, registry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or not DECISION_CORE.issubset(value):
        return {"accepted": False, "reason": "missing-core"}
    if not isinstance(value.get("next_pursuit"), str) or not value["next_pursuit"].strip():
        return {"accepted": False, "reason": "missing-description"}
    extras = {key: item for key, item in value.items() if key not in DECISION_CORE}
    if len(extras) > 8 or not all(base213.EXTENSION_KEY.fullmatch(key) and base213.safe_extension(item) for key, item in extras.items()):
        return {"accepted": False, "reason": "invalid-extension"}
    contact = value.get("next_contact")
    if not valid_contact(contact):
        return {"accepted": False, "reason": "invalid-contact"}
    identity = contact_identity(contact)
    if identity in registry["identities"]:
        return {"accepted": False, "reason": "already-receipted-contact", "contact_identity": identity}
    prior_inputs = registry["inputs"].get(contact["target_symbol"], set())
    new_inputs = sum(input_key(contact["target_symbol"], contact["target_path"], contact["abi"], case["input"]) not in prior_inputs for case in contact["cases"])
    if new_inputs < 2:
        return {"accepted": False, "reason": "insufficient-unreceipted-inputs", "new_input_count": new_inputs}
    return {"accepted": True, "reason": "executable-unreceipted-contact", "contact_identity": identity, "new_input_count": new_inputs}


def incident(identity: str, severity: int, duration: int, probability: float, effort: int) -> dict[str, Any]:
    return {"id": identity, "severity": severity, "duration": duration, "probability": probability, "effort": effort}


def new_cases(prefix: str) -> list[dict[str, Any]]:
    return [
        {"case_id": f"{prefix}-1", "input": {"capacity": 3, "incidents": [incident("delta", 8, 7, .7, 3), incident("echo", 10, 1, .2, 3)]}},
        {"case_id": f"{prefix}-2", "input": {"capacity": 4, "incidents": [incident("delta", 7, 6, .8, 2), incident("echo", 9, 1, .3, 4), incident("foxtrot", 6, 5, .7, 2)]}},
        {"case_id": f"{prefix}-3", "input": {"capacity": 6, "incidents": [incident("delta", 9, 3, .8, 3), incident("echo", 8, 4, .7, 3), incident("foxtrot", 10, 1, .2, 6)]}},
        {"case_id": f"{prefix}-4", "input": {"capacity": 5, "incidents": [incident("delta", 8, 2, .9, 2), incident("echo", 7, 3, .8, 3)]}},
    ]


def package(contact_id: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"contact_id": contact_id, "target_path": "operations/system.py", "target_symbol": "schedule_recovery", "abi": ABI, "stake": "Test a still-unreceipted recovery-capacity boundary.", "cases": copy.deepcopy(cases), "predicates": copy.deepcopy(PREDICATES)}


def decision(name: str, contact: Any, **extras: Any) -> dict[str, Any]:
    return {"next_pursuit": name, "next_contact": contact, **extras}


def construction_bundle(parent: dict[str, Any]) -> list[dict[str, Any]]:
    registry = completed_registry(parent)
    completed = next(item for item in registry["packages"] if item["target_symbol"] == "schedule_recovery")
    completed_contact = {"contact_id": "renamed-completed", **{key: copy.deepcopy(completed[key]) for key in ("target_path", "target_symbol", "abi", "cases", "predicates")}, "stake": "Different words for completed contact."}
    return [
        {"id": "construction-live", "expected": True, "decision": decision("Open executable contact.", package("construction-live", new_cases("construction")))},
        {"id": "construction-paraphrase", "expected": False, "decision": {"next_pursuit": "Paraphrase the completed capacity contact.", "next_contact": None}},
        {"id": "construction-renamed-completed", "expected": False, "decision": decision("Rename completed contact.", completed_contact)},
    ]


def heldout_bundle(parent: dict[str, Any]) -> list[dict[str, Any]]:
    registry = completed_registry(parent)
    completed = next(item for item in registry["packages"] if item["target_symbol"] == "schedule_recovery")
    completed_cases = copy.deepcopy(completed["cases"])
    renamed = []
    for index, case in enumerate(reversed(completed_cases), 1):
        renamed.append({"case_id": f"renamed-{index}", "input": copy.deepcopy(case["input"])})
    live = package("heldout-live", new_cases("heldout"))
    one_new = copy.deepcopy(renamed[:3]) + [new_cases("one-new")[0]]
    fixtures = [
        {"id": "live-basic", "expected": True, "decision": decision("Poor prose is allowed.", live)},
        {"id": "live-extension", "expected": True, "decision": decision("Continue.", copy.deepcopy(live), causal_thread={"origin": "subject"})},
        {"id": "renamed-reordered-duplicate", "expected": False, "decision": decision("Novel wording.", package("renamed-duplicate", renamed))},
        {"id": "already-receipted", "expected": False, "decision": decision("Repeat exact contact.", package("exact-repeat", completed_cases))},
        {"id": "prose-only", "expected": False, "decision": {"next_pursuit": "A wholly new sentence.", "next_contact": None}},
        {"id": "one-new-input", "expected": False, "decision": decision("Almost new.", package("one-new", one_new))},
    ]
    malformed = {
        "missing-contact-field": {key: copy.deepcopy(item) for key, item in live.items() if key != "abi"},
        "invalid-target": {**copy.deepcopy(live), "target_symbol": "invented_target"},
        "invalid-abi": {**copy.deepcopy(live), "abi": "free-form"},
        "wrong-case-count": {**copy.deepcopy(live), "cases": copy.deepcopy(live["cases"][:3])},
        "wrong-predicates": {**copy.deepcopy(live), "predicates": {"success": True}},
    }
    fixtures.extend({"id": name, "expected": False, "decision": decision(name, contact)} for name, contact in malformed.items())
    fixtures.extend([
        {"id": "excessive-extensions", "expected": False, "decision": decision("Too many.", copy.deepcopy(live), **{f"extra_{index}": index for index in range(9)})},
        {"id": "deep-extension", "expected": False, "decision": decision("Too deep.", copy.deepcopy(live), causal_thread={"a": {"b": {"c": {"d": {"e": 1}}}}})},
        {"id": "broad-extension", "expected": False, "decision": decision("Too broad.", copy.deepcopy(live), causal_thread=list(range(17)))},
        {"id": "invalid-extension-key", "expected": False, "decision": decision("Bad key.", copy.deepcopy(live), **{"Invalid Key": True})},
        {"id": "oversized-extension", "expected": False, "decision": decision("Too large.", copy.deepcopy(live), causal_thread="x" * 3000)},
    ])
    random.Random(GENERATOR_SEED).shuffle(fixtures)
    return fixtures


def evaluate_bundle(bundle: list[dict[str, Any]], registry: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for fixture in bundle:
        g4 = incumbent_g4_accepts(fixture["decision"])
        g5 = challenger_g5(fixture["decision"], registry)
        rows.append({"id": fixture["id"], "expected": fixture["expected"], "g4_accepted": g4, "g5": g5, "g5_correct": g5["accepted"] == fixture["expected"]})
    return {"case_count": len(rows), "g5_correct_count": sum(row["g5_correct"] for row in rows), "g4_live_stale_discrimination": sum(row["g4_accepted"] == row["expected"] for row in rows), "passed": all(row["g5_correct"] for row in rows), "rows": rows}


def compile_candidate(parent: dict[str, Any], p82, construction: dict[str, Any], heldout: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    transition_body = {"authority": "ot-0216-evaluation-regime-transition", "from_regime": "G4-core-plus-bounded-nonauthoritative-extension", "to_regime": "G5-contact-bearing-continuation-liveness", "source_subject_digest": parent["artifact_digest"], "compiler_rules_digest": digest({"contact_core": sorted(CONTACT_CORE), "decision_core": sorted(DECISION_CORE), "predicates": PREDICATES, "minimum_new_inputs": 2, "generator_seed": GENERATOR_SEED}), "construction_receipt_digest": digest(construction), "heldout_receipt_digest": digest(heldout), "historical_rescoring": False}
    transition = {**transition_body, "receipt_digest": p82.digest(transition_body)}
    child["evaluation_regime_transitions"] = [*child.get("evaluation_regime_transitions", []), transition]
    child["continuation_liveness"] = {"authority": "G5-contact-bearing-continuation-liveness", "status": "unresolved", "reason": "current opening has no bound executable unreceipted contact", "source_opening": parent["continuation"]["next_opening"], "transition_receipt_digest": transition["receipt_digest"]}
    return p82.seal(child), transition


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0216").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0215", "open-subject-after-artifact-conditioned-continuation.json")
    result215 = selector_base.load_artifact(p82, repo, store, "OT-0215", "artifact-conditioned-semantic-continuation-aggregate.json")
    registry = completed_registry(parent)
    construction = evaluate_bundle(construction_bundle(parent), registry)
    heldout = evaluate_bundle(heldout_bundle(parent), registry)
    prospective, prospective_transition = compile_candidate(parent, p82, construction, heldout)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_operational_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "ot0215_exact_promotion": result215["observer_disposition"] == "promoted" and result215["final_subject_digest"] == PARENT_DIGEST,
        "ot0215_causal_interpretation_supported": result215["causal_interpretation"] == "supported",
        "construction_passed": construction["passed"],
        "heldout_all_correct": heldout["passed"],
        "heldout_complete": heldout["case_count"] == 16 and heldout["g5_correct_count"] == 16,
        "g5_improves_discrimination": heldout["g5_correct_count"] > heldout["g4_live_stale_discrimination"],
        "current_prose_not_live_under_g5": not challenger_g5({"next_pursuit": parent["continuation"]["next_opening"], "next_contact": None}, registry)["accepted"],
        "prospective_successor_identity_conforms": runtime.identity_conforms(prospective),
        "operational_state_exact": all(prospective.get(key) == value for key, value in parent.items() if key not in {"artifact_digest", "evaluation_regime_transitions"}) and prospective["continuation"] == parent["continuation"],
        "transition_append_exact": prospective["evaluation_regime_transitions"] == [*parent.get("evaluation_regime_transitions", []), prospective_transition],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0216-g5-transition", "generator_seed": GENERATOR_SEED, "source_subject_digest": parent["artifact_digest"], "completed_contact_identities": sorted(registry["identities"]), "construction": construction, "heldout": heldout, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0216 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "transition-fixtures.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("transition failed")
    candidate, transition = compile_candidate(parent, p82, construction, heldout)
    successor_ok = runtime.identity_conforms(candidate)
    checks["successor_identity_conforms"] = successor_ok
    checks["passed"] = checks["passed"] and successor_ok
    final = candidate if successor_ok else parent
    result = {"authority": "ot-0216-contact-bearing-continuation-liveness", "source_subject_digest": parent["artifact_digest"], "transition": transition if successor_ok else None, "fixtures": fixtures, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final.get("continuation_liveness"), "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"]}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
