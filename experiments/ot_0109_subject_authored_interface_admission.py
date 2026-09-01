from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import random
import re
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0108_semantic_id_registry_exit.py"
BASE_SHA256 = "b589ca059254d5bd1c28e202d72f7156ddf48f12015d6fe752a2de6f9204106f"
PARENT_OBJECT_SHA256 = "ed088039df81c86fca24bd707766090f74e99e0f75010c0da780f6ecfb974bfb"
PARENT_DIGEST = "ba13ac49759491fd105f52d51cda4236ab5f5bd84a6d483f35d37ecfe5dfb94f"
PACKAGE_SCHEMA = REPO / "spec/ot-0109-package-author.schema.json"
INTERFACE_ID = "joint-capability-frontier"
PACKAGE_FILES = ["interface.json", "operation.py", "conformance.py", "contact.json"]
SPEC_KEYS = {
    "interface_id", "new_context_field", "new_option_field", "minimum",
    "maximum", "score_composition", "reversible_projection",
}
CONTACT_KEYS = {"interface_id", "cases"}
CASE_KEYS = {"case_id", "context", "options"}
BASE_CONTEXT = {"risk_penalty", "overload_penalty"}
BASE_OPTION = {"id", "recovery_value", "recovery_risk", "capacity", "overload"}
COMPOSITION = "joint_score - context_penalty * option_burden"
FIELD_RE = re.compile(r"[a-z][a-z0-9_]{2,47}")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0108 implementation identity changed")
    name = "ot0109_frozen_ot0108"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base = prior.base


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0108", "open-subject-after-registry-exit.json")
    if manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0108 subject object identity")
    return json.loads(path.read_text())


def extract_extension(p82, subject: dict[str, Any]) -> dict[str, Any] | None:
    retained = subject.get("actor_originated_pursuit_openings", [])[-1]
    action = retained.get("continuation_action", {})
    if action.get("action_kind") != "registry-extension" or action.get("action_target") != INTERFACE_ID:
        return None
    if subject.get("active_pursuit", {}).get("selected_area") != INTERFACE_ID:
        return None
    if subject.get("continuation", {}).get("next_opening") != retained.get("opening", {}).get("next_opening"):
        return None
    body = {
        "authority": "ot-0109-subject-bound-registry-extension",
        "source_subject_digest": subject["artifact_digest"],
        "opening_binding_digest": retained["binding_digest"],
        "continuation_action": action,
    }
    return {**body, "binding_digest": p82.digest(body)}


def finite_number(value: Any, low: float, high: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def valid_spec(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != SPEC_KEYS:
        return False
    context_field = value.get("new_context_field")
    option_field = value.get("new_option_field")
    return bool(
        value.get("interface_id") == INTERFACE_ID
        and isinstance(context_field, str) and FIELD_RE.fullmatch(context_field)
        and isinstance(option_field, str) and FIELD_RE.fullmatch(option_field)
        and context_field != option_field
        and context_field not in BASE_CONTEXT | BASE_OPTION
        and option_field not in BASE_CONTEXT | BASE_OPTION
        and finite_number(value.get("minimum"), 0, 100)
        and finite_number(value.get("maximum"), 0, 100)
        and value["minimum"] < value["maximum"]
        and value.get("score_composition") == COMPOSITION
        and value.get("reversible_projection") is True
    )


def valid_id(value: Any) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (
        isinstance(value, int) and not isinstance(value, bool)
    )


def composed_score(spec: dict[str, Any], context: dict[str, Any], option: dict[str, Any]) -> float:
    return base.joint_score(context, option) - context[spec["new_context_field"]] * option[spec["new_option_field"]]


def validate_contact(spec: dict[str, Any], value: Any, require_coverage: bool = True) -> tuple[bool, dict[str, bool]]:
    cases = value.get("cases", []) if isinstance(value, dict) else []
    context_keys = BASE_CONTEXT | {spec.get("new_context_field")}
    option_keys = BASE_OPTION | {spec.get("new_option_field")}
    exact = isinstance(value, dict) and set(value) == CONTACT_KEYS and value.get("interface_id") == INTERFACE_ID
    shapes = bool(valid_spec(spec) and exact and len(cases) == 3 and all(
        isinstance(case, dict) and set(case) == CASE_KEYS
        and isinstance(case.get("case_id"), str) and bool(case["case_id"].strip())
        and isinstance(case.get("context"), dict) and set(case["context"]) == context_keys
        and all(finite_number(case["context"].get(key), 0, 100) for key in BASE_CONTEXT)
        and finite_number(case["context"].get(spec["new_context_field"]), spec["minimum"], spec["maximum"])
        and isinstance(case.get("options"), list) and len(case["options"]) == 2
        and all(
            isinstance(option, dict) and set(option) == option_keys and valid_id(option.get("id"))
            and all(finite_number(option.get(key), 0, 200) for key in BASE_OPTION - {"id"})
            and finite_number(option.get(spec["new_option_field"]), spec["minimum"], spec["maximum"])
            for option in case["options"]
        )
        and type(case["options"][0]["id"]) is type(case["options"][1]["id"])
        and case["options"][0]["id"] != case["options"][1]["id"]
        for case in cases
    ))
    case_ids_unique = bool(shapes and len({case["case_id"] for case in cases}) == 3)
    cases_unique = bool(shapes and len({base.digest(case) for case in cases}) == 3)
    nonzero = bool(shapes and any(
        case["context"][spec["new_context_field"]] > 0
        and option[spec["new_option_field"]] > 0
        for case in cases for option in case["options"]
    ))
    winner_flip = near_boundary = False
    if shapes:
        for case in cases:
            extended = max(case["options"], key=lambda row: (composed_score(spec, case["context"], row), row["id"]))
            joint = max(case["options"], key=lambda row: (base.joint_score(case["context"], row), row["id"]))
            scores = sorted((composed_score(spec, case["context"], row) for row in case["options"]), reverse=True)
            winner_flip = winner_flip or extended["id"] != joint["id"]
            near_boundary = near_boundary or 0 < scores[0] - scores[1] <= base.BOUNDARY_WIDTH
    checks = {
        "exact_shape": shapes,
        "case_ids_unique": case_ids_unique,
        "cases_unique": cases_unique,
        "nonzero_new_boundary": nonzero,
        "new_boundary_changes_winner": winner_flip,
        "near_extended_boundary": near_boundary,
    }
    required = checks.values() if require_coverage else [shapes, case_ids_unique, cases_unique]
    checks["passed"] = all(required)
    return checks["passed"], checks


SAFE_BUILTINS = {
    "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
    "float": float, "int": int, "isinstance": isinstance, "len": len, "list": list,
    "max": max, "min": min, "set": set, "sorted": sorted, "str": str,
    "sum": sum, "tuple": tuple, "type": type, "zip": zip,
}


def load_function(source: str, name: str) -> Callable[..., Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    forbidden_nodes = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith)
    if any(isinstance(node, forbidden_nodes) for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Name) and node.id.startswith("__") for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Attribute) and node.attr.startswith("__") for node in ast.walk(tree)):
        return None
    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(compile(tree, "<actor-package>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get(name)
    return function if callable(function) else None


def source_functions(operation_source: str, conformance_source: str):
    return load_function(operation_source, "choose_frontier"), load_function(conformance_source, "validate_contact")


def contact_mutations(spec: dict[str, Any], contact: dict[str, Any]) -> list[tuple[str, dict[str, Any], bool]]:
    mutations: list[tuple[str, dict[str, Any], bool]] = [("authored-valid", copy.deepcopy(contact), True)]
    missing = copy.deepcopy(contact); missing.pop("cases")
    mutations.append(("missing-cases", missing, False))
    mixed = copy.deepcopy(contact)
    original_id = mixed["cases"][0]["options"][0]["id"]
    mixed["cases"][0]["options"][0]["id"] = 1 if isinstance(original_id, str) else "mixed"
    mutations.append(("mixed-id-types", mixed, False))
    out_of_bounds = copy.deepcopy(contact)
    out_of_bounds["cases"][0]["context"][spec["new_context_field"]] = spec["maximum"] + 1
    mutations.append(("new-field-out-of-bounds", out_of_bounds, False))
    duplicate = copy.deepcopy(contact)
    duplicate["cases"][0]["options"][1]["id"] = duplicate["cases"][0]["options"][0]["id"]
    mutations.append(("duplicate-option-id", duplicate, False))
    extra = copy.deepcopy(contact); extra["unexpected"] = True
    mutations.append(("extra-root-key", extra, False))
    return mutations


def public_contract_agreement(spec: dict[str, Any], contact: dict[str, Any], validator: Callable[..., Any] | None) -> dict[str, Any]:
    rows = []
    for label, value, expected in contact_mutations(spec, contact):
        try:
            observed = validator(copy.deepcopy(value)) if validator else None
        except Exception:
            observed = None
        rows.append({"fixture": label, "expected": expected, "observed": observed, "passed": type(observed) is bool and observed is expected})
    return {"rows": rows, "passed": bool(rows and all(row["passed"] for row in rows))}


def score_cases(spec: dict[str, Any], cases: list[dict[str, Any]], chooser: Callable[..., Any] | None) -> dict[str, Any]:
    rows = []
    for case in cases:
        before = copy.deepcopy(case)
        try:
            selected_id = chooser(copy.deepcopy(case["context"]), copy.deepcopy(case["options"])) if chooser else None
        except Exception:
            selected_id = None
        oracle = max(case["options"], key=lambda row: (composed_score(spec, case["context"], row), row["id"]))
        selected = next((row for row in case["options"] if row["id"] == selected_id), None)
        rows.append({
            "case_id": case["case_id"], "selected_id": selected_id, "oracle_id": oracle["id"],
            "selected_score": composed_score(spec, case["context"], selected) if selected else None,
            "oracle_score": composed_score(spec, case["context"], oracle),
            "input_unchanged": before == case, "passed": selected_id == oracle["id"] and before == case,
        })
    return {"rows": rows, "passed": bool(rows and all(row["passed"] for row in rows))}


def retained_joint(parent: dict[str, Any]) -> tuple[str, Callable[..., Any]]:
    capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
    namespace: dict[str, Any] = {}
    exec(capability["source"], namespace)
    return capability["source"], namespace["choose_joint"]


def reversibility(spec: dict[str, Any], cases: list[dict[str, Any]], chooser: Callable[..., Any] | None, joint: Callable[..., Any]) -> dict[str, Any]:
    rows = []
    context_field, option_field = spec["new_context_field"], spec["new_option_field"]
    for case in cases:
        projected_context = {key: value for key, value in case["context"].items() if key != context_field}
        projected_options = [{key: value for key, value in row.items() if key != option_field} for row in case["options"]]
        zero_context = copy.deepcopy(case["context"]); zero_context[context_field] = 0
        zero_options = copy.deepcopy(case["options"])
        try:
            expected = joint(copy.deepcopy(projected_context), copy.deepcopy(projected_options))
            context_observed = chooser(zero_context, copy.deepcopy(zero_options)) if chooser else None
            burden_zero = copy.deepcopy(case["options"])
            for option in burden_zero: option[option_field] = 0
            burden_observed = chooser(copy.deepcopy(case["context"]), burden_zero) if chooser else None
        except Exception:
            expected = context_observed = burden_observed = None
        projected_shape = bool(
            set(projected_context) == BASE_CONTEXT
            and all(set(option) == BASE_OPTION for option in projected_options)
        )
        rows.append({
            "case_id": case["case_id"], "joint_id": expected,
            "zero_context_id": context_observed, "zero_burden_id": burden_observed,
            "projection_shape_valid": projected_shape,
            "passed": projected_shape and expected == context_observed == burden_observed,
        })
    return {"rows": rows, "passed": bool(rows and all(row["passed"] for row in rows))}


def assess_package(parent: dict[str, Any], spec: dict[str, Any], contact: dict[str, Any], operation_source: str, conformance_source: str, hidden_cases: list[dict[str, Any]]) -> dict[str, Any]:
    contact_valid, contact_checks = validate_contact(spec, contact)
    chooser, validator = source_functions(operation_source, conformance_source)
    _, joint = retained_joint(parent)
    public = public_contract_agreement(spec, contact, validator) if valid_spec(spec) and isinstance(contact, dict) else {"rows": [], "passed": False}
    authored = score_cases(spec, contact.get("cases", []), chooser) if contact_valid else {"rows": [], "passed": False}
    hidden = score_cases(spec, hidden_cases, chooser) if valid_spec(spec) and hidden_cases else {"rows": [], "passed": False}
    reversible = reversibility(spec, contact.get("cases", []), chooser, joint) if contact_valid else {"rows": [], "passed": False}
    result = {
        "spec_valid": valid_spec(spec), "contact_conformance": contact_checks,
        "sources_load": bool(chooser and validator), "public_contract": public,
        "authored_oracle": authored, "hidden_oracle": hidden, "reversibility": reversible,
    }
    result["passed"] = bool(
        result["spec_valid"] and contact_valid and result["sources_load"]
        and public["passed"] and authored["passed"] and hidden["passed"] and reversible["passed"]
    )
    return result


def package_seed(run: Path, parent: dict[str, Any], selection: dict[str, Any]) -> Path:
    seed = run / "package-author-seed"
    seed.mkdir()
    position = base.active_position(parent)
    visible = {
        "subject_position": position,
        "developmental_history": prior.prior.active_history(parent),
        "bound_registry_extension": selection,
        "registered_interfaces": sorted(prior.prior.REGISTERED),
    }
    (seed / "subject-opening.json").write_text(json.dumps(visible, indent=2, sort_keys=True) + "\n")
    joint_source, _ = retained_joint(parent)
    (seed / "retained-joint.py").write_text(joint_source)
    contract = {
        "interface_exact_keys": sorted(SPEC_KEYS), "interface_id": INTERFACE_ID,
        "new_field_pattern": FIELD_RE.pattern,
        "forbidden_field_collisions": sorted(BASE_CONTEXT | BASE_OPTION),
        "bounds": "minimum and maximum numeric, 0 <= minimum < maximum <= 100",
        "score_composition": COMPOSITION,
        "contact_root_keys": sorted(CONTACT_KEYS), "case_keys": sorted(CASE_KEYS),
        "base_context_keys": sorted(BASE_CONTEXT), "base_option_keys": sorted(BASE_OPTION),
        "ids": "nonempty string or integer, excluding bool; same type and distinct within a case",
        "required_cases": 3, "options_per_case": 2, "boundary_width": base.BOUNDARY_WIDTH,
        "operation_export": "choose_frontier(context, options)",
        "conformance_export": "validate_contact(value) -> bool",
        "available_builtins": sorted(SAFE_BUILTINS),
        "source_constraints": "no imports, classes, globals, nonlocals, with statements, or double-underscore names",
        "reversibility": "zero new context penalty or all new option burdens must recover retained choose_joint; field removal must recover base joint shapes",
    }
    (seed / "public-meta-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "Continue the subject's exact registry-extension opening. Invent the new numeric boundary and author the complete interface package. "
        "Edit exactly interface.json, operation.py, conformance.py, and contact.json. The new score is retained joint score minus the new context penalty times the new option burden. "
        "Make the public validator strict, make the operation reversible at zero, create exactly three novel cases including a new-boundary winner flip and a margin within the published boundary width, inspect the diff, and report truthfully.\n"
    )
    for name in PACKAGE_FILES:
        (seed / name).write_text("")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": PACKAGE_FILES,
        "immutable": ["subject-opening.json", "retained-joint.py", "public-meta-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    return seed


def read_package(workspace: Path):
    try:
        spec = json.loads((workspace / "interface.json").read_text())
        contact = json.loads((workspace / "contact.json").read_text())
        operation_source = (workspace / "operation.py").read_text()
        conformance_source = (workspace / "conformance.py").read_text()
    except (OSError, json.JSONDecodeError):
        return None, None, "", ""
    return spec, contact, operation_source, conformance_source


def run_package_author(p82, context, run: Path, parent: dict[str, Any], selection: dict[str, Any]):
    seed = package_seed(run, parent, selection)
    prompt = (
        "Follow the exact subject opening and public meta-contract. Author the complete reversible joint-capability-frontier package, edit exactly the four permitted files, inspect the diff, and return the required report."
    )
    output, base_audit, workspace, _ = context.run_actor("package-author", seed, PACKAGE_SCHEMA, prompt)
    spec, contact, operation_source, conformance_source = read_package(workspace)
    preliminary_valid = bool(
        valid_spec(spec) and validate_contact(spec, contact)[0]
        and all(source_functions(operation_source, conformance_source))
        and output.get("interface_id") == INTERFACE_ID and output.get("case_count") == 3
    )
    audit = context.audit_actor("package-author", output, base_audit, preliminary_valid, PACKAGE_FILES)
    binding = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0109-subject-authored-interface-package",
            "source_subject_digest": parent["artifact_digest"],
            "extension_binding_digest": selection["binding_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "interface": spec, "operation_source": operation_source,
            "conformance_source": conformance_source, "contact": contact,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("package-author") / "bound-package.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {
        "output": output, "audit": audit, "preliminary_valid": preliminary_valid,
        "binding": binding, "workspace": workspace,
    }


def derive_hidden_cases(spec: dict[str, Any], seed: bytes, count: int = 8) -> list[dict[str, Any]]:
    generator = random.Random(int.from_bytes(seed, "big"))
    cases = []
    for index in range(count):
        context = {
            "risk_penalty": generator.randint(0, 10),
            "overload_penalty": generator.randint(0, 10),
            spec["new_context_field"]: generator.randint(int(spec["minimum"]), int(spec["maximum"])),
        }
        options = []
        for suffix in ("a", "b"):
            options.append({
                "id": f"hidden-{index}-{suffix}",
                "recovery_value": generator.randint(20, 150),
                "recovery_risk": generator.randint(0, 15),
                "capacity": generator.randint(10, 120),
                "overload": generator.randint(0, 15),
                spec["new_option_field"]: generator.randint(int(spec["minimum"]), int(spec["maximum"])),
            })
        cases.append({"case_id": f"hidden-frontier-{index:02d}", "context": context, "options": options})
    return cases


def admit_package(p82, run: Path, parent: dict[str, Any], package: dict[str, Any]):
    seed = secrets.token_bytes(32)
    (run / "hidden-seed.bin").write_bytes(seed)
    spec, contact = package["interface"], package["contact"]
    hidden_cases = derive_hidden_cases(spec, seed)
    (run / "hidden-cases.json").write_text(json.dumps(hidden_cases, indent=2, sort_keys=True) + "\n")
    assessment = assess_package(parent, spec, contact, package["operation_source"], package["conformance_source"], hidden_cases)
    body = {
        "authority": "ot-0109-independent-interface-admission",
        "source_subject_digest": parent["artifact_digest"],
        "package_binding_digest": package["binding_digest"],
        "private_seed_digest": hashlib.sha256(seed).hexdigest(),
        "derivation_attempt": 1, "hidden_cases_digest": p82.digest(hidden_cases),
        "assessment": assessment, "admitted": assessment["passed"],
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (run / "admission-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def world_contact(p82, package: dict[str, Any], admission: dict[str, Any]) -> dict[str, Any]:
    rows = admission["assessment"]["authored_oracle"]["rows"] if admission["admitted"] else []
    body = {
        "authority": "ot-0109-independent-frontier-world",
        "interface_id": INTERFACE_ID, "package_binding_digest": package["binding_digest"],
        "admission_receipt_digest": admission["receipt_digest"], "rows": rows,
        "all_cases_passed": bool(rows and all(row["passed"] for row in rows)),
    }
    return {**body, "receipt_digest": p82.digest(body)}


def fixture_package():
    spec = {
        "interface_id": INTERFACE_ID, "new_context_field": "latency_penalty",
        "new_option_field": "latency_burden", "minimum": 0, "maximum": 10,
        "score_composition": COMPOSITION, "reversible_projection": True,
    }
    contact = {
        "interface_id": INTERFACE_ID,
        "cases": [
            {"case_id": "fixture-flip", "context": {"risk_penalty": 1, "overload_penalty": 1, "latency_penalty": 5}, "options": [
                {"id": "a", "recovery_value": 100, "recovery_risk": 0, "capacity": 40, "overload": 0, "latency_burden": 2},
                {"id": "b", "recovery_value": 95, "recovery_risk": 0, "capacity": 40, "overload": 0, "latency_burden": 0},
            ]},
            {"case_id": "fixture-risk", "context": {"risk_penalty": 4, "overload_penalty": 1, "latency_penalty": 2}, "options": [
                {"id": "c", "recovery_value": 110, "recovery_risk": 2, "capacity": 45, "overload": 1, "latency_burden": 1},
                {"id": "d", "recovery_value": 100, "recovery_risk": 0, "capacity": 40, "overload": 0, "latency_burden": 1},
            ]},
            {"case_id": "fixture-overload", "context": {"risk_penalty": 1, "overload_penalty": 4, "latency_penalty": 3}, "options": [
                {"id": "e", "recovery_value": 95, "recovery_risk": 1, "capacity": 55, "overload": 2, "latency_burden": 1},
                {"id": "f", "recovery_value": 92, "recovery_risk": 0, "capacity": 50, "overload": 0, "latency_burden": 0},
            ]},
        ],
    }
    operation = """def choose_frontier(context, options):
    def score(option):
        joint = option[\"recovery_value\"] - context[\"risk_penalty\"] * option[\"recovery_risk\"] + option[\"capacity\"] - context[\"overload_penalty\"] * option[\"overload\"]
        return joint - context[\"latency_penalty\"] * option[\"latency_burden\"]
    return max(options, key=lambda option: (score(option), option[\"id\"]))[\"id\"]
"""
    conformance = """def validate_contact(value):
    if not isinstance(value, dict) or set(value) != {\"interface_id\", \"cases\"} or value.get(\"interface_id\") != \"joint-capability-frontier\":
        return False
    cases = value.get(\"cases\")
    if not isinstance(cases, list) or len(cases) != 3:
        return False
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {\"case_id\", \"context\", \"options\"} or not isinstance(case.get(\"case_id\"), str) or not case[\"case_id\"] or case[\"case_id\"] in seen:
            return False
        seen.add(case[\"case_id\"])
        context = case.get(\"context\")
        if not isinstance(context, dict) or set(context) != {\"risk_penalty\", \"overload_penalty\", \"latency_penalty\"}:
            return False
        if not all(isinstance(context[key], (int, float)) and not isinstance(context[key], bool) and 0 <= context[key] <= (10 if key == \"latency_penalty\" else 100) for key in context):
            return False
        options = case.get(\"options\")
        if not isinstance(options, list) or len(options) != 2:
            return False
        ids = []
        for option in options:
            if not isinstance(option, dict) or set(option) != {\"id\", \"recovery_value\", \"recovery_risk\", \"capacity\", \"overload\", \"latency_burden\"}:
                return False
            identifier = option.get(\"id\")
            if not ((isinstance(identifier, str) and bool(identifier)) or (isinstance(identifier, int) and not isinstance(identifier, bool))):
                return False
            ids.append(identifier)
            for key in {\"recovery_value\", \"recovery_risk\", \"capacity\", \"overload\", \"latency_burden\"}:
                high = 10 if key == \"latency_burden\" else 200
                if not isinstance(option.get(key), (int, float)) or isinstance(option[key], bool) or not 0 <= option[key] <= high:
                    return False
        if type(ids[0]) is not type(ids[1]) or ids[0] == ids[1]:
            return False
    return True
"""
    return spec, contact, operation, conformance


def fixture_conformance(parent: dict[str, Any]) -> dict[str, Any]:
    spec, contact, operation, conformance = fixture_package()
    hidden = derive_hidden_cases(spec, b"ot-0109-frozen-fixture-seed")
    good = assess_package(parent, spec, contact, operation, conformance, hidden)
    collision = {**spec, "new_context_field": "risk_penalty"}
    mixed = copy.deepcopy(contact); mixed["cases"][0]["options"][0]["id"] = 1
    no_flip = copy.deepcopy(contact)
    for case in no_flip["cases"]:
        for option in case["options"]: option[spec["new_option_field"]] = 0
    vacuous = "def validate_contact(value):\n    return True\n"
    nonreversible = """def choose_frontier(context, options):
    return max(options, key=lambda option: (option[\"recovery_value\"] + option[\"capacity\"], option[\"id\"]))[\"id\"]
"""
    result = {
        "known_good_admitted": good["passed"],
        "old_field_collision_rejected": not valid_spec(collision),
        "mixed_ids_rejected": not validate_contact(spec, mixed)[0],
        "vacuous_public_validator_rejected": not assess_package(parent, spec, contact, operation, vacuous, hidden)["passed"],
        "nonreversible_operation_rejected": not assess_package(parent, spec, contact, nonreversible, conformance, hidden)["passed"],
        "nonconsequential_boundary_rejected": not validate_contact(spec, no_flip)[0],
    }
    result["passed"] = all(result.values())
    return result


def valid_extended_action(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != prior.prior.ACTION_KEYS or value.get("action_kind") not in prior.prior.ACTION_KINDS:
        return False
    if not all(isinstance(value.get(key), str) and value[key].strip() and prior.prior.PLACEHOLDER not in value[key] and len(value[key]) <= 3000 for key in prior.prior.ACTION_KEYS - {"action_kind"}):
        return False
    registered = prior.prior.REGISTERED | {INTERFACE_ID}
    if value["action_kind"] == "registered-contact":
        return value["action_target"] in registered
    return value["action_target"] not in registered and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["action_target"]))


def assimilation_seed(prior89, run: Path, parent: dict[str, Any], package: dict[str, Any], admission: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = run / "assimilation-seed"
    seed.mkdir()
    consequence = {
        "subject_position": base.active_position(parent),
        "developmental_history": prior.prior.active_history(parent),
        "bound_interface_package": package,
        "independent_admission_receipt": admission,
        "world_receipt": world,
        "registered_interfaces_after_admission": sorted(prior.prior.REGISTERED | {INTERFACE_ID}),
    }
    (seed / "subject-contact-consequence.json").write_text(json.dumps(consequence, indent=2, sort_keys=True) + "\n")
    (seed / "assimilation.json").write_text(json.dumps(base.assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action.json").write_text(json.dumps(prior.prior.action_template(), indent=2, sort_keys=True) + "\n")
    action_contract = {
        "exact_keys": sorted(prior.prior.ACTION_KEYS), "action_kinds": sorted(prior.prior.ACTION_KINDS),
        "registered_targets": sorted(prior.prior.REGISTERED | {INTERFACE_ID}),
        "registered-contact": "target must be an admitted registered id",
        "registry-extension": "target must be a new lowercase hyphenated id",
        "instruction": "Choose what remains worth carrying after this admitted consequence; make the opening and action consistent.",
    }
    (seed / "continuation-action-contract.json").write_text(json.dumps(action_contract, indent=2, sort_keys=True) + "\n")
    (seed / "retained-allocator.py").write_text(parent["allocation_machinery"][-1]["source"])
    joint_source, _ = retained_joint(parent)
    (seed / "retained-joint.py").write_text(joint_source)
    (seed / "admitted-interface.json").write_text(json.dumps(package["interface"], indent=2, sort_keys=True) + "\n")
    (seed / "admitted-operation.py").write_text(package["operation_source"])
    (seed / "admitted-conformance.py").write_text(package["conformance_source"])
    editable = ["assimilation.json", "successor-opening.json", "continuation-action.json"]
    immutable = ["retained-allocator.py", "retained-joint.py", "admitted-interface.json", "admitted-operation.py", "admitted-conformance.py"]
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": editable, "immutable": immutable}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "Assimilate the independently admitted interface and completed contact. Preserve all machinery and the package, edit exactly the three permitted JSON files, bind the next continuation from the published action space, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_assimilation(prior89, p82, context, run: Path, parent: dict[str, Any], package: dict[str, Any], admission: dict[str, Any], world: dict[str, Any]):
    seed = assimilation_seed(prior89, run, parent, package, admission, world)
    prompt = "Assimilate this admitted interface consequence and bind what is worth continuing. Preserve immutable machinery and package bytes, edit exactly the three permitted JSON files, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor("assimilation", seed, prior.prior.ASSIMILATOR_SCHEMA, prompt)
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        action = json.loads((workspace / "continuation-action.json").read_text())
        allocator_retained = (workspace / "retained-allocator.py").read_text() == parent["allocation_machinery"][-1]["source"]
        joint_source, _ = retained_joint(parent)
        joint_retained = (workspace / "retained-joint.py").read_text() == joint_source
        package_retained = bool(
            json.loads((workspace / "admitted-interface.json").read_text()) == package["interface"]
            and (workspace / "admitted-operation.py").read_text() == package["operation_source"]
            and (workspace / "admitted-conformance.py").read_text() == package["conformance_source"]
        )
    except (OSError, json.JSONDecodeError):
        assimilation = opening = action = None
        allocator_retained = joint_retained = package_retained = False
    position = base.active_position(parent)
    valid = bool(
        base.valid_assimilation(assimilation) and prior89.valid_successor(opening)
        and valid_extended_action(action) and allocator_retained and joint_retained and package_retained
        and opening["next_opening"] != position["continuation"]["next_opening"]
    )
    allowed = ["assimilation.json", "successor-opening.json", "continuation-action.json"]
    audit = context.audit_actor("assimilation", output, base_audit, valid, allowed)
    passed_ids = {row["case_id"] for row in world["rows"] if row["passed"]}
    cited = set(assimilation["settled_case_ids"]) if isinstance(assimilation, dict) and isinstance(assimilation.get("settled_case_ids"), list) else set()
    grounded = bool(audit["conformant"] and cited and cited.issubset(passed_ids))
    binding = None
    if grounded:
        body = {
            "authority": "ot-0109-admitted-interface-assimilation",
            "source_subject_digest": parent["artifact_digest"],
            "package_binding_digest": package["binding_digest"],
            "admission_receipt_digest": admission["receipt_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "history_projection_digest": p82.digest(prior.prior.active_history(parent)),
            "actor_patch_digest": audit["patch_digest"],
            "allocator_retention_derived": allocator_retained,
            "joint_retention_derived": joint_retained,
            "package_retention_derived": package_retained,
            "assimilation": assimilation, "successor_opening": opening,
            "continuation_action": action,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("assimilation") / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {
        "output": output, "audit": audit, "grounded": grounded,
        "allocator_retention_derived": allocator_retained,
        "joint_retention_derived": joint_retained,
        "package_retention_derived": package_retained, "binding": binding,
    }


def promote(p82, parent: dict[str, Any], selection: dict[str, Any], package: dict[str, Any], admission: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    action = assimilation["continuation_action"]
    opening = assimilation["successor_opening"]
    body = {
        "authority": "world-promoted-subject-authored-interface",
        "source_subject_digest": parent["artifact_digest"],
        "extension_binding_digest": selection["binding_digest"],
        "package_binding_digest": package["binding_digest"],
        "admission_receipt_digest": admission["receipt_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "assimilation_binding_digest": assimilation["binding_digest"],
        "continuation_action": action,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["subject_recurrence_receipts"] = [*child.get("subject_recurrence_receipts", []), receipt]
    child["interface_registry_extensions"] = [*child.get("interface_registry_extensions", []), {
        "interface_id": INTERFACE_ID, "package_binding_digest": package["binding_digest"],
        "admission_receipt_digest": admission["receipt_digest"],
    }]
    child["environmental_capabilities"] = [*child["environmental_capabilities"], {
        "target_path": "operations/joint-capability-frontier.py", "target_symbol": "choose_frontier",
        "source": package["operation_source"], "source_digest": hashlib.sha256(package["operation_source"].encode()).hexdigest(),
        "world_receipt_digest": world["receipt_digest"], "binding_digest": package["binding_digest"],
    }, {
        "target_path": "contracts/joint-capability-frontier.py", "target_symbol": "validate_contact",
        "source": package["conformance_source"], "source_digest": hashlib.sha256(package["conformance_source"].encode()).hexdigest(),
        "world_receipt_digest": world["receipt_digest"], "binding_digest": package["binding_digest"],
    }]
    child["actor_authored_contacts"] = [*child.get("actor_authored_contacts", []), {
        "interface_id": INTERFACE_ID, "binding_digest": package["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
    }]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": assimilation["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []), {
        "authority": "ot-0109-admitted-interface-opening", "binding_digest": assimilation["binding_digest"],
        "opening": opening, "continuation_action": action,
    }]
    child["active_pursuit"] = {
        "authority": "ot-0109-admitted-interface-opening", "selected_area": action["action_target"],
        "next_pursuit": opening["next_opening"], "world_receipt_digest": world["receipt_digest"],
    }
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]
    child["runtime"] = "sounding"
    return p82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0109").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    if parent["artifact_digest"] != PARENT_DIGEST or not runtime.identity_conforms(parent) or parent["continuation"]["status"] != "open":
        raise SystemExit("wrong OT-0108 parent")
    selection = extract_extension(p82, parent)
    fixtures = fixture_conformance(parent)
    if args.preflight_only:
        result = {
            "parent_digest": parent["artifact_digest"],
            "parent_object_sha256": PARENT_OBJECT_SHA256,
            "base_implementation_sha256": BASE_SHA256,
            "extension_binding_digest": selection["binding_digest"] if selection else None,
            "fixture_conformance": fixtures,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if selection and fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0109 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not selection or not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    authored = run_package_author(p82, context, run, parent, selection)
    package = authored["binding"]
    admission = admit_package(p82, run, parent, package) if package else None
    world = world_contact(p82, package, admission) if package and admission and admission["admitted"] else None
    if world:
        (run / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation = run_assimilation(prior89, p82, context, run, parent, package, admission, world) if world and world["all_cases_passed"] else None
    current = parent
    promotion = None
    if assimilation and assimilation["binding"]:
        current, promotion = promote(p82, parent, selection, package, admission, world, assimilation["binding"])
    extension_rows = current.get("interface_registry_extensions", [])
    installed = bool(
        extension_rows and extension_rows[-1].get("package_binding_digest") == (package or {}).get("binding_digest")
        and any(row.get("target_path") == "operations/joint-capability-frontier.py" and row.get("source") == (package or {}).get("operation_source") for row in current.get("environmental_capabilities", []))
    )
    operational = bool(
        promotion and installed and runtime.identity_conforms(current)
        and current["runtime"] == "sounding" and current["continuation"]["status"] == "open"
    )
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    package_summary = {
        "output": authored["output"], "audit": authored["audit"],
        "preliminary_valid": authored["preliminary_valid"], "binding": package,
    }
    result = {
        "authority": "ot-0109-subject-authored-interface-admission-driver",
        "source_subject_digest": parent["artifact_digest"],
        "extension_selection": selection,
        "package_author": p82.compact(package_summary),
        "admission_receipt": p82.compact(admission) if admission else None,
        "world_receipt": world,
        "assimilation": p82.compact(assimilation) if assimilation else None,
        "promotion_receipt": promotion,
        "package_admitted": bool(admission and admission["admitted"]),
        "authored_contact_passed": bool(world and world["all_cases_passed"]),
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"],
        "continuation_action": current["actor_originated_pursuit_openings"][-1].get("continuation_action"),
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
