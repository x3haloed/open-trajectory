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
BASE_PATH = ROOT / "ot_0218_unresolved_consequence_correction_handoff.py"
BASE_SHA256 = "21b666df413e19e6383a1a8edd395abcaaa415ba3236178116525b3e345ec8bd"
PARENT_DIGEST = "2d5a0cf4f158c4e5ab63e75697e3e04c0bda6ae7ad217acd660da73a043184b7"
OT218_RECEIPT = "d2e1f112d5cd6ae885d3eb043e8ee52701debb00ed62d430d40d543c112f1c16"
PENDING_IDENTITY_G5 = "5d7b7319291fed31478501be035a27ce8b1714845638e8d27bb049a93058ef77"
GENERATOR_SEED = 219_604_127


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0218 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0219_frozen_ot0218", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base218 = load_base()
base217 = base218.base217
base216 = base218.base216
base215 = base218.base215
base213 = base218.base213
authority_base = base218.authority_base
ABI = base217.ABI
PREDICATES = base217.PREDICATES
CONTACT_CORE = base216.CONTACT_CORE
DECISION_CORE = {"next_pursuit", "next_contact"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outcome(function, value: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"status": "ok", "value": function(copy.deepcopy(value))}
    except Exception as error:
        return {"status": "error", "error_type": type(error).__name__}


def mapping_paths(value: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    paths = []
    if isinstance(value, dict):
        for key in sorted(value):
            path = (*prefix, key)
            paths.append(path)
            paths.extend(mapping_paths(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(mapping_paths(item, (*prefix, index)))
    return paths


def remove_path(value: Any, path: tuple[Any, ...]) -> Any:
    candidate = copy.deepcopy(value)
    cursor = candidate
    for segment in path[:-1]:
        cursor = cursor[segment]
    del cursor[path[-1]]
    return candidate


def behavioral_projection(case_input: dict[str, Any], installed, reference) -> dict[str, Any]:
    projected = copy.deepcopy(case_input)
    while True:
        baseline = (outcome(installed, projected), outcome(reference, projected))
        removed = False
        paths = sorted(mapping_paths(projected), key=lambda path: (-len(path), tuple(str(part) for part in path)))
        for path in paths:
            candidate = remove_path(projected, path)
            if (outcome(installed, candidate), outcome(reference, candidate)) == baseline:
                projected = candidate
                removed = True
                break
        if not removed:
            return projected


def functions(system_path: Path, reference_path: Path) -> dict[str, tuple[Any, Any]]:
    system = load_module(system_path, "ot0219_system_" + hashlib.sha256(system_path.read_bytes()).hexdigest()[:10])
    reference = load_module(reference_path, "ot0219_reference_" + hashlib.sha256(reference_path.read_bytes()).hexdigest()[:10])
    return {target: (getattr(system, target), getattr(reference, target)) for target in sorted(base217.TARGETS)}


def project_contact(contact: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    installed, reference = available[contact["target_symbol"]]
    return {"target_symbol": contact["target_symbol"], "target_path": contact["target_path"], "abi": contact["abi"], "case_inputs": sorted(digest(behavioral_projection(case["input"], installed, reference)) for case in contact["cases"]), "predicates": contact["predicates"]}


def projected_identity(contact: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> str:
    return digest(project_contact(contact, available))


def structural_contact(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != CONTACT_CORE:
        return False
    if not all(isinstance(value.get(key), str) and value[key].strip() for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")):
        return False
    interface = base217.environment_registry().get(value["target_symbol"])
    if not interface or value["target_path"] != interface["target_path"] or value["abi"] != interface["abi"]:
        return False
    cases = value.get("cases")
    return bool(isinstance(cases, list) and len(cases) == 4 and len({case.get("case_id") for case in cases if isinstance(case, dict)}) == 4 and all(isinstance(case, dict) and set(case) == {"case_id", "input"} and isinstance(case.get("case_id"), str) and case["case_id"].strip() and isinstance(case.get("input"), dict) for case in cases) and value.get("predicates") == PREDICATES and len(canonical(value)) <= 32768)


def completed_registry(parent: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    packages = []
    packages.extend(capability["package"] for capability in parent.get("semantic_contact_program_capabilities", []))
    packages.extend(capability["package"] for capability in parent.get("semantic_move_capabilities", []))
    identities = set()
    inputs: dict[str, set[str]] = {}
    for package in packages:
        contact = {"contact_id": package.get("contact_id", package.get("move_id", "historical")), "target_path": package["target_path"], "target_symbol": package["target_symbol"], "abi": ABI, "stake": package["stake"], "cases": package["cases"], "predicates": PREDICATES}
        if contact["target_symbol"] not in available:
            continue
        identities.add(projected_identity(contact, available))
        installed, reference = available[contact["target_symbol"]]
        inputs.setdefault(contact["target_symbol"], set()).update(digest(behavioral_projection(case["input"], installed, reference)) for case in contact["cases"])
    return {"identities": identities, "inputs": inputs}


def g6(value: Any, registry: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    if not isinstance(value, dict) or not DECISION_CORE.issubset(value) or not isinstance(value.get("next_pursuit"), str) or not value["next_pursuit"].strip():
        return {"accepted": False, "reason": "invalid-decision-core"}
    extras = {key: item for key, item in value.items() if key not in DECISION_CORE}
    if len(extras) > 8 or not all(base213.EXTENSION_KEY.fullmatch(key) and base213.safe_extension(item) for key, item in extras.items()):
        return {"accepted": False, "reason": "invalid-extension"}
    contact = value.get("next_contact")
    if not structural_contact(contact):
        return {"accepted": False, "reason": "invalid-contact"}
    identity = projected_identity(contact, available)
    if identity in registry["identities"]:
        return {"accepted": False, "reason": "already-receipted-projected-contact", "projected_identity": identity}
    installed, reference = available[contact["target_symbol"]]
    prior = registry["inputs"].get(contact["target_symbol"], set())
    projected = [behavioral_projection(case["input"], installed, reference) for case in contact["cases"]]
    new_count = sum(digest(item) not in prior for item in projected)
    return {"accepted": new_count >= 2, "reason": "behaviorally-new-contact" if new_count >= 2 else "insufficient-new-projected-inputs", "projected_identity": identity, "new_input_count": new_count, "projected_inputs": projected}


def decision(description: str, contact: Any, **extras: Any) -> dict[str, Any]:
    return {"next_pursuit": description, "next_contact": contact, **extras}


def decorated(contact: dict[str, Any], top: bool = True, nested: bool = False, reverse: bool = False) -> dict[str, Any]:
    value = copy.deepcopy(contact)
    for index, case in enumerate(value["cases"]):
        if top: case["input"]["world"] = f"ignored-{index}"
        if nested:
            collection = next(key for key in ("incidents", "requests", "tasks") if key in case["input"])
            for row in case["input"][collection]: row["annotation"] = "ignored"
        case["case_id"] = f"renamed-{index}"
    if reverse: value["cases"].reverse()
    value["contact_id"] = "decorated-duplicate"
    value["stake"] = "Novel words cannot make old behavior new."
    return value


def historical_contact(package: dict[str, Any]) -> dict[str, Any]:
    return {"contact_id": package.get("contact_id", package.get("move_id", "historical-contact")), "target_path": package["target_path"], "target_symbol": package["target_symbol"], "abi": ABI, "stake": package["stake"], "cases": copy.deepcopy(package["cases"]), "predicates": copy.deepcopy(PREDICATES)}


def heldout_bundle(parent: dict[str, Any]) -> list[dict[str, Any]]:
    completed_schedule = historical_contact(next(capability["package"] for capability in parent["semantic_move_capabilities"] if capability["target_symbol"] == "schedule_recovery"))
    actual_pending = copy.deepcopy(parent["pending_contact_bearing_continuations"][-1]["package"])
    genuine = base217.representative_contact("schedule_recovery", "genuine-projected")
    one_new_cases = copy.deepcopy(completed_schedule["cases"][:3]) + [copy.deepcopy(genuine["cases"][0])]
    one_new = copy.deepcopy(completed_schedule)
    one_new.update(contact_id="one-new-projected", cases=one_new_cases)
    invalid_target = copy.deepcopy(genuine); invalid_target["target_symbol"] = "invented_target"
    invalid_abi = copy.deepcopy(genuine); invalid_abi["abi"] = "free-form"
    wrong_count = copy.deepcopy(genuine); wrong_count["cases"] = wrong_count["cases"][:3]
    wrong_predicates = copy.deepcopy(genuine); wrong_predicates["predicates"] = {"success": True}
    missing = {key: copy.deepcopy(item) for key, item in genuine.items() if key != "abi"}
    fixtures = [
        {"id": "actual-top-decoration", "expected": False, "decision": decision("Decorated actual package.", actual_pending)},
        {"id": "nested-decoration", "expected": False, "decision": decision("Nested decoration.", decorated(completed_schedule, top=False, nested=True))},
        {"id": "multiple-decoration-reordered", "expected": False, "decision": decision("Many decorations.", decorated(completed_schedule, top=True, nested=True, reverse=True))},
        {"id": "genuine-new", "expected": True, "decision": decision("Poor prose.", genuine)},
        {"id": "genuine-new-extension", "expected": True, "decision": decision("Continue.", copy.deepcopy(genuine), causal_thread={"origin": "subject"})},
        {"id": "one-new-three-decorated", "expected": False, "decision": decision("Almost new.", decorated(one_new, top=True))},
        {"id": "exact-completed", "expected": False, "decision": decision("Exact old contact.", completed_schedule)},
        {"id": "invalid-target", "expected": False, "decision": decision("Bad target.", invalid_target)},
        {"id": "invalid-abi", "expected": False, "decision": decision("Bad ABI.", invalid_abi)},
        {"id": "wrong-case-count", "expected": False, "decision": decision("Wrong count.", wrong_count)},
        {"id": "wrong-predicates", "expected": False, "decision": decision("Wrong predicates.", wrong_predicates)},
        {"id": "missing-field", "expected": False, "decision": decision("Missing field.", missing)},
        {"id": "prose-only", "expected": False, "decision": {"next_pursuit": "Only words.", "next_contact": None}},
        {"id": "excessive-extensions", "expected": False, "decision": decision("Too many.", copy.deepcopy(genuine), **{f"extra_{index}": index for index in range(9)})},
        {"id": "deep-extension", "expected": False, "decision": decision("Too deep.", copy.deepcopy(genuine), causal_thread={"a": {"b": {"c": {"d": {"e": 1}}}}})},
        {"id": "invalid-extension-key", "expected": False, "decision": decision("Bad key.", copy.deepcopy(genuine), **{"Invalid Key": True})},
    ]
    random.Random(GENERATOR_SEED).shuffle(fixtures)
    return fixtures


def evaluate_bundle(bundle: list[dict[str, Any]], parent: dict[str, Any], registry: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    raw_registry = base216.completed_registry(parent)
    rows = []
    for fixture in bundle:
        g5_result = base216.challenger_g5(fixture["decision"], raw_registry)
        g6_result = g6(fixture["decision"], registry, available)
        rows.append({"id": fixture["id"], "expected": fixture["expected"], "g5_accepted": g5_result["accepted"], "g6": g6_result, "g6_correct": g6_result["accepted"] == fixture["expected"]})
    return {"case_count": len(rows), "g5_correct_count": sum(row["g5_accepted"] == row["expected"] for row in rows), "g6_correct_count": sum(row["g6_correct"] for row in rows), "passed": all(row["g6_correct"] for row in rows), "rows": rows}


def compile_candidate(parent: dict[str, Any], p82, bundle: dict[str, Any], construction: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    body = {"authority": "ot-0219-evaluation-regime-transition", "from_regime": "G5-raw-input-contact-identity", "to_regime": "G6-behavioral-ABI-projected-contact-identity", "source_subject_digest": parent["artifact_digest"], "algorithm_digest": digest({"field_removal": "deterministic-fixed-point", "comparison": "installed-and-reference-validity-and-exact-output", "generator_seed": GENERATOR_SEED}), "construction_receipt_digest": digest(construction), "heldout_receipt_digest": digest(bundle), "historical_rescoring": False}
    transition = {**body, "receipt_digest": p82.digest(body)}
    child["evaluation_regime_transitions"] = [*child.get("evaluation_regime_transitions", []), transition]
    child["continuation_liveness"] = {"authority": "G6-behavioral-ABI-projected-contact-identity", "status": "unresolved", "reason": "pending recovery inputs collapse to completed contact after ignored-field projection", "raw_pending_contact_identity": parent["continuation_liveness"]["contact_identity"], "transition_receipt_digest": transition["receipt_digest"]}
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
    run = (args.evidence_root or store / "runs/OT-0219").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0218", "live-subject-after-unresolved-consequence-correction.json")
    result218 = selector_base.load_artifact(p82, repo, store, "OT-0218", "unresolved-consequence-correction-aggregate.json")
    fixture_root = run.parent / "OT-0219-preflight"
    if fixture_root.exists():
        import shutil
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    base218.write_environment(fixture_root, base218.installed_source(parent))
    available = functions(fixture_root / "operations/system.py", fixture_root / "operations/reference.py")
    registry = completed_registry(parent, available)
    actual = parent["pending_contact_bearing_continuations"][-1]["package"]
    actual_g5 = base216.challenger_g5(decision(parent["continuation"]["next_opening"], actual), base216.completed_registry(parent))
    actual_g6 = g6(decision(parent["continuation"]["next_opening"], actual), registry, available)
    completed_schedule = historical_contact(next(capability["package"] for capability in parent["semantic_move_capabilities"] if capability["target_symbol"] == "schedule_recovery"))
    construction = {"authority": "ot-0219-construction", "g5_accepts_actual": actual_g5["accepted"], "g6_rejects_actual": not actual_g6["accepted"], "g6_reason": actual_g6["reason"], "actual_projected_identity": actual_g6.get("projected_identity"), "completed_projected_identity": projected_identity(completed_schedule, available)}
    bundle = evaluate_bundle(heldout_bundle(parent), parent, registry, available)
    installed_recovery, reference_recovery = available["schedule_recovery"]
    base_input = completed_schedule["cases"][0]["input"]
    decorated_input = copy.deepcopy(base_input); decorated_input["world"] = "ignored"; decorated_input["incidents"][0]["annotation"] = "ignored"
    projection_checks = {"ignored_decoration_collapses": behavioral_projection(decorated_input, installed_recovery, reference_recovery) == behavioral_projection(base_input, installed_recovery, reference_recovery), "key_order_deterministic": digest(behavioral_projection(dict(reversed(list(decorated_input.items()))), installed_recovery, reference_recovery)) == digest(behavioral_projection(decorated_input, installed_recovery, reference_recovery))}
    for field, replacement in (("capacity", base_input["capacity"] + 1),):
        changed = copy.deepcopy(base_input); changed[field] = replacement; projection_checks[f"relevant_{field}_retained"] = behavioral_projection(changed, installed_recovery, reference_recovery) != behavioral_projection(base_input, installed_recovery, reference_recovery)
    changed = copy.deepcopy(base_input); changed["incidents"][0]["probability"] += .01; projection_checks["reference_probability_retained"] = behavioral_projection(changed, installed_recovery, reference_recovery) != behavioral_projection(base_input, installed_recovery, reference_recovery)
    relief_input = copy.deepcopy(base217.HIDDEN_CASES["allocate_relief"][0]["input"])
    installed_relief, reference_relief = available["allocate_relief"]
    relief_projection = behavioral_projection(relief_input, installed_relief, reference_relief)
    projection_checks["reference_only_probability_retained"] = all("probability" in row for row in relief_projection["requests"])
    projection_checks["validity_required_capacity_retained"] = "capacity" in behavioral_projection(base_input, installed_recovery, reference_recovery)
    reversed_contact = copy.deepcopy(completed_schedule); reversed_contact["cases"].reverse()
    projection_checks["case_order_deterministic"] = projected_identity(reversed_contact, available) == projected_identity(completed_schedule, available)
    prospective, transition = compile_candidate(parent, p82, bundle, construction)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_operational": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent), "ot0218_exact_promotion": result218["observer_disposition"] == "promoted" and result218["final_subject_digest"] == PARENT_DIGEST and result218["receipt_digest"] == OT218_RECEIPT, "pending_g5_identity_exact": parent["continuation_liveness"]["contact_identity"] == PENDING_IDENTITY_G5, "construction_discriminates": construction["g5_accepts_actual"] and construction["g6_rejects_actual"] and construction["actual_projected_identity"] == construction["completed_projected_identity"], "heldout_16_of_16": bundle["passed"] and bundle["case_count"] == 16 and bundle["g6_correct_count"] == 16, "g6_improves_over_g5": bundle["g6_correct_count"] > bundle["g5_correct_count"], "projection_checks_pass": all(projection_checks.values()), "prospective_identity_conforms": runtime.identity_conforms(prospective), "operational_state_exact": all(prospective.get(key) == value for key, value in parent.items() if key not in {"artifact_digest", "evaluation_regime_transitions", "continuation_liveness"}), "pending_bytes_exact": prospective["pending_contact_bearing_continuations"] == parent["pending_contact_bearing_continuations"], "transition_append_exact": prospective["evaluation_regime_transitions"] == [*parent.get("evaluation_regime_transitions", []), transition], "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0219-g6-transition", "generator_seed": GENERATOR_SEED, "source_subject_digest": parent["artifact_digest"], "construction": construction, "projection_checks": projection_checks, "heldout": bundle, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0219 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "transition-fixtures.json", fixtures)
    if not checks["passed"]: raise SystemExit("transition failed")
    candidate, transition = compile_candidate(parent, p82, bundle, construction)
    successor_ok = runtime.identity_conforms(candidate)
    checks["successor_identity_conforms"] = successor_ok
    checks["passed"] = checks["passed"] and successor_ok
    final = candidate if successor_ok else parent
    result = {"authority": "ot-0219-behavioral-abi-projected-contact-identity", "source_subject_digest": parent["artifact_digest"], "transition": transition if successor_ok else None, "fixtures": fixtures, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final.get("continuation_liveness"), "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"]}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
