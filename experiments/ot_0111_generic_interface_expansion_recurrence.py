from __future__ import annotations

import argparse
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
BASE_PATH = ROOT / "ot_0110_retained_package_conformance_correction.py"
BASE_SHA256 = "fc8e568e6cb7346901758f6f5cab0eff3c9bc05f42af30ec6478f45db9b25298"
PARENT_OBJECT_SHA256 = "ebb5c52f4fdc46a9e6fe7c83377d5fb731d160b7c566a64f16a0a18dde706503"
PARENT_DIGEST = "331b301de6308c1867ae3abeef09db4d29c70e1b0a49ea881ab9d11047ae6f65"
AGGREGATE_SHA256 = "92a3d952463880a465620620f6a418bab498cee8c18fc7f5b7443ded9f669874"
INITIAL_PACKAGE_DIGEST = "76517b3c8c87a495fc8bceeb97028c7882ac0a41f5d2b9ed3b53ea7889474897"
AUTHOR_SCHEMA = REPO / "spec/ot-0111-package-author.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0111-assimilator.schema.json"
CORRECTOR_SCHEMA = REPO / "spec/ot-0110-corrector.schema.json"
PACKAGE_FILES = ["interface.json", "operation.py", "conformance.py", "contact.json"]
SPEC_KEYS = {"interface_id", "parent_interface_id", "new_context_field", "new_option_field", "minimum", "maximum", "score_composition", "reversible_projection"}
BASE_CONTEXT = {"risk_penalty", "overload_penalty"}
BASE_OPTION = {"id", "recovery_value", "recovery_risk", "capacity", "overload"}
COMPOSITION = "parent_score - context_penalty * option_burden"
FIELD_RE = re.compile(r"[a-z][a-z0-9_]{2,47}")
TARGET_RE = re.compile(r"[a-z][a-z0-9-]{2,63}")
ACTION_KEYS = {"action_kind", "action_target", "rationale", "expected_information", "surrender_condition"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0110 implementation identity changed")
    name = "ot0111_frozen_ot0110"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base = prior.base
foundation = prior.prior


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0110", "open-subject-after-interface-admission.json")
    if manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0110 subject object identity")
    return json.loads(path.read_text())


def load_initial_tip(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0110", "retained-package-correction-aggregate.json")
    if manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0110 aggregate identity")
    package = json.loads(path.read_text())["correction"]["binding"]
    if package["binding_digest"] != INITIAL_PACKAGE_DIGEST:
        raise RuntimeError("wrong initial package binding")
    interface = package["interface"]
    return {
        "interface_id": interface["interface_id"],
        "terms": [{
            "context_field": interface["new_context_field"], "option_field": interface["new_option_field"],
            "minimum": interface["minimum"], "maximum": interface["maximum"],
        }],
        "operation_source": package["operation_source"], "operation_symbol": "choose_frontier",
        "conformance_source": package["conformance_source"], "binding_digest": package["binding_digest"],
        "package": package,
    }


def extract_action(p82, subject: dict[str, Any]) -> dict[str, Any] | None:
    openings = subject.get("actor_originated_pursuit_openings", [])
    retained = openings[-1] if openings else {}
    action = retained.get("continuation_action")
    if not isinstance(action, dict) or set(action) != ACTION_KEYS:
        return None
    if subject.get("active_pursuit", {}).get("selected_area") != action.get("action_target"):
        return None
    if subject.get("continuation", {}).get("next_opening") != retained.get("opening", {}).get("next_opening"):
        return None
    body = {"authority": "ot-0111-subject-continuation", "source_subject_digest": subject["artifact_digest"], "opening_binding_digest": retained["binding_digest"], "continuation_action": action}
    return {**body, "binding_digest": p82.digest(body)}


def finite_number(value: Any, low: float, high: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def declaration_valid(value: Any) -> bool:
    return value is True or (isinstance(value, str) and 0 < len(value.strip()) <= 500)


def used_fields(tip: dict[str, Any]) -> set[str]:
    return BASE_CONTEXT | BASE_OPTION | {row[key] for row in tip["terms"] for key in ("context_field", "option_field")}


def valid_spec(value: Any, tip: dict[str, Any], target: str) -> bool:
    if not isinstance(value, dict) or set(value) != SPEC_KEYS:
        return False
    context_field, option_field = value.get("new_context_field"), value.get("new_option_field")
    return bool(
        value.get("interface_id") == target and value.get("parent_interface_id") == tip["interface_id"]
        and isinstance(context_field, str) and FIELD_RE.fullmatch(context_field)
        and isinstance(option_field, str) and FIELD_RE.fullmatch(option_field)
        and context_field != option_field and context_field not in used_fields(tip) and option_field not in used_fields(tip)
        and finite_number(value.get("minimum"), 0, 100) and finite_number(value.get("maximum"), 0, 100)
        and value["minimum"] < value["maximum"] and value.get("score_composition") == COMPOSITION
        and declaration_valid(value.get("reversible_projection"))
    )


def valid_id(value: Any) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (isinstance(value, int) and not isinstance(value, bool))


def score_terms(terms: list[dict[str, Any]], context: dict[str, Any], option: dict[str, Any]) -> float:
    score = base.joint_score(context, option)
    for term in terms:
        score -= context[term["context_field"]] * option[term["option_field"]]
    return score


def extended_terms(tip: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [*tip["terms"], {"context_field": spec["new_context_field"], "option_field": spec["new_option_field"], "minimum": spec["minimum"], "maximum": spec["maximum"]}]


def validate_contact(spec: dict[str, Any], tip: dict[str, Any], value: Any, require_coverage: bool = True) -> tuple[bool, dict[str, bool]]:
    cases = value.get("cases", []) if isinstance(value, dict) else []
    terms = extended_terms(tip, spec) if valid_spec(spec, tip, spec.get("interface_id", "")) else []
    context_keys = BASE_CONTEXT | {row["context_field"] for row in terms}
    option_keys = BASE_OPTION | {row["option_field"] for row in terms}
    shapes = bool(terms and isinstance(value, dict) and set(value) == {"interface_id", "cases"} and value.get("interface_id") == spec["interface_id"] and len(cases) == 3 and all(
        isinstance(case, dict) and set(case) == {"case_id", "context", "options"}
        and isinstance(case.get("case_id"), str) and bool(case["case_id"].strip())
        and isinstance(case.get("context"), dict) and set(case["context"]) == context_keys
        and all(finite_number(case["context"].get(key), 0, 100) for key in BASE_CONTEXT)
        and all(finite_number(case["context"].get(row["context_field"]), row["minimum"], row["maximum"]) for row in terms)
        and isinstance(case.get("options"), list) and len(case["options"]) == 2
        and all(isinstance(option, dict) and set(option) == option_keys and valid_id(option.get("id"))
            and all(finite_number(option.get(key), 0, 200) for key in BASE_OPTION - {"id"})
            and all(finite_number(option.get(row["option_field"]), row["minimum"], row["maximum"]) for row in terms)
            for option in case["options"])
        and type(case["options"][0]["id"]) is type(case["options"][1]["id"])
        and case["options"][0]["id"] != case["options"][1]["id"] for case in cases
    ))
    unique = bool(shapes and len({case["case_id"] for case in cases}) == 3 and len({base.digest(case) for case in cases}) == 3)
    new_term = terms[-1] if terms else {}
    nonzero = bool(shapes and any(case["context"][new_term["context_field"]] > 0 and option[new_term["option_field"]] > 0 for case in cases for option in case["options"]))
    flip = near = False
    if shapes:
        for case in cases:
            parent = max(case["options"], key=lambda row: (score_terms(tip["terms"], case["context"], row), row["id"]))
            child = max(case["options"], key=lambda row: (score_terms(terms, case["context"], row), row["id"]))
            scores = sorted((score_terms(terms, case["context"], row) for row in case["options"]), reverse=True)
            flip = flip or parent["id"] != child["id"]
            near = near or 0 < scores[0] - scores[1] <= base.BOUNDARY_WIDTH
    checks = {"exact_shape": shapes, "unique_cases": unique, "nonzero_new_term": nonzero, "new_term_changes_winner": flip, "near_extended_boundary": near}
    checks["passed"] = all(checks.values()) if require_coverage else shapes and unique
    return checks["passed"], checks


def load_named(source: str, symbol: str) -> Callable[..., Any] | None:
    return foundation.load_function(source, symbol)


def contact_mutations(spec: dict[str, Any], tip: dict[str, Any], contact: dict[str, Any]):
    rows = [("authored-valid", copy.deepcopy(contact), True)]
    missing = copy.deepcopy(contact); missing.pop("cases")
    rows.append(("missing-cases", missing, False))
    mixed = copy.deepcopy(contact)
    original = mixed["cases"][0]["options"][0]["id"]
    mixed["cases"][0]["options"][0]["id"] = 1 if isinstance(original, str) else "mixed"
    rows.append(("mixed-id-types", mixed, False))
    out = copy.deepcopy(contact); out["cases"][0]["context"][spec["new_context_field"]] = spec["maximum"] + 1
    rows.append(("new-field-out-of-bounds", out, False))
    inherited = copy.deepcopy(contact)
    inherited_term = tip["terms"][-1]
    inherited["cases"][0]["options"][0][inherited_term["option_field"]] = inherited_term["maximum"] + 1
    rows.append(("inherited-field-out-of-bounds", inherited, False))
    duplicate = copy.deepcopy(contact); duplicate["cases"][0]["options"][1]["id"] = duplicate["cases"][0]["options"][0]["id"]
    rows.append(("duplicate-option-id", duplicate, False))
    extra = copy.deepcopy(contact); extra["unexpected"] = True
    rows.append(("extra-root-key", extra, False))
    return rows


def public_agreement(spec: dict[str, Any], tip: dict[str, Any], contact: dict[str, Any], validator: Callable[..., Any] | None):
    rows = []
    for label, value, expected in contact_mutations(spec, tip, contact):
        try:
            observed = validator(copy.deepcopy(value)) if validator else None
        except Exception:
            observed = None
        rows.append({"fixture": label, "expected": expected, "observed": observed, "passed": type(observed) is bool and observed is expected})
    return {"rows": rows, "passed": bool(rows and all(row["passed"] for row in rows))}


def score_cases(spec: dict[str, Any], tip: dict[str, Any], cases: list[dict[str, Any]], chooser: Callable[..., Any] | None):
    terms = extended_terms(tip, spec)
    rows = []
    for case in cases:
        original = copy.deepcopy(case)
        try:
            selected_id = chooser(copy.deepcopy(case["context"]), copy.deepcopy(case["options"])) if chooser else None
        except Exception:
            selected_id = None
        oracle = max(case["options"], key=lambda row: (score_terms(terms, case["context"], row), row["id"]))
        selected = next((row for row in case["options"] if row["id"] == selected_id), None)
        rows.append({"case_id": case["case_id"], "selected_id": selected_id, "oracle_id": oracle["id"], "selected_score": score_terms(terms, case["context"], selected) if selected else None, "oracle_score": score_terms(terms, case["context"], oracle), "input_unchanged": original == case, "passed": selected_id == oracle["id"] and original == case})
    return {"rows": rows, "passed": bool(rows and all(row["passed"] for row in rows))}


def reversibility(spec: dict[str, Any], tip: dict[str, Any], cases: list[dict[str, Any]], chooser: Callable[..., Any] | None):
    parent = load_named(tip["operation_source"], tip["operation_symbol"])
    context_field, option_field = spec["new_context_field"], spec["new_option_field"]
    rows = []
    for case in cases:
        parent_context = {key: value for key, value in case["context"].items() if key != context_field}
        parent_options = [{key: value for key, value in option.items() if key != option_field} for option in case["options"]]
        zero_context = copy.deepcopy(case["context"]); zero_context[context_field] = 0
        zero_options = copy.deepcopy(case["options"])
        zero_burden = copy.deepcopy(case["options"])
        for option in zero_burden: option[option_field] = 0
        try:
            expected = parent(copy.deepcopy(parent_context), copy.deepcopy(parent_options)) if parent else None
            observed_context = chooser(zero_context, zero_options) if chooser else None
            observed_burden = chooser(copy.deepcopy(case["context"]), zero_burden) if chooser else None
        except Exception:
            expected = observed_context = observed_burden = None
        shape = set(parent_context) == BASE_CONTEXT | {row["context_field"] for row in tip["terms"]} and all(set(option) == BASE_OPTION | {row["option_field"] for row in tip["terms"]} for option in parent_options)
        rows.append({"case_id": case["case_id"], "parent_id": expected, "zero_context_id": observed_context, "zero_burden_id": observed_burden, "parent_shape_valid": shape, "passed": shape and expected == observed_context == observed_burden})
    return {"rows": rows, "passed": bool(rows and all(row["passed"] for row in rows))}


def assess(spec: dict[str, Any], tip: dict[str, Any], contact: dict[str, Any], operation_source: str, conformance_source: str, hidden_cases: list[dict[str, Any]]):
    contact_valid, checks = validate_contact(spec, tip, contact)
    chooser = load_named(operation_source, "choose_extension")
    validator = load_named(conformance_source, "validate_contact")
    public = public_agreement(spec, tip, contact, validator) if contact_valid else {"rows": [], "passed": False}
    authored = score_cases(spec, tip, contact.get("cases", []), chooser) if contact_valid else {"rows": [], "passed": False}
    hidden = score_cases(spec, tip, hidden_cases, chooser) if hidden_cases and valid_spec(spec, tip, spec.get("interface_id", "")) else {"rows": [], "passed": False}
    reversible = reversibility(spec, tip, contact.get("cases", []), chooser) if contact_valid else {"rows": [], "passed": False}
    result = {"spec_valid": valid_spec(spec, tip, spec.get("interface_id", "")), "contact_conformance": checks, "sources_load": bool(chooser and validator), "public_contract": public, "authored_oracle": authored, "hidden_oracle": hidden, "reversibility": reversible}
    result["passed"] = bool(result["spec_valid"] and contact_valid and result["sources_load"] and public["passed"] and authored["passed"] and hidden["passed"] and reversible["passed"])
    return result


def derive_hidden(spec: dict[str, Any], tip: dict[str, Any], seed: bytes, count: int = 8):
    generator = random.Random(int.from_bytes(seed, "big"))
    terms = extended_terms(tip, spec)
    cases = []
    for index in range(count):
        context = {"risk_penalty": generator.randint(0, 10), "overload_penalty": generator.randint(0, 10)}
        for term in terms: context[term["context_field"]] = generator.randint(int(term["minimum"]), int(term["maximum"]))
        options = []
        for suffix in ("a", "b"):
            option = {"id": f"hidden-{index}-{suffix}", "recovery_value": generator.randint(20, 150), "recovery_risk": generator.randint(0, 15), "capacity": generator.randint(10, 120), "overload": generator.randint(0, 15)}
            for term in terms: option[term["option_field"]] = generator.randint(int(term["minimum"]), int(term["maximum"]))
            options.append(option)
        cases.append({"case_id": f"hidden-expansion-{index:02d}", "context": context, "options": options})
    return cases


def package_seed(run: Path, label: str, subject: dict[str, Any], tip: dict[str, Any], selection: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"; seed.mkdir()
    target = selection["continuation_action"]["action_target"]
    visible = {"subject_position": base.active_position(subject), "developmental_history": foundation.active_history(subject), "bound_continuation": selection, "current_package_tip": {key: value for key, value in tip.items() if key != "package"}}
    (seed / "subject-opening.json").write_text(json.dumps(visible, indent=2, sort_keys=True) + "\n")
    (seed / "parent-operation.py").write_text(tip["operation_source"])
    (seed / "parent-conformance.py").write_text(tip["conformance_source"])
    terms = tip["terms"]
    contract = {
        "interface_exact_keys": sorted(SPEC_KEYS), "interface_id": target, "parent_interface_id": tip["interface_id"],
        "used_fields": sorted(used_fields(tip)), "new_field_pattern": FIELD_RE.pattern,
        "inherited_terms": terms, "base_context_fields": sorted(BASE_CONTEXT), "base_option_fields": sorted(BASE_OPTION),
        "new_bounds": "0 <= minimum < maximum <= 100", "score_composition": COMPOSITION,
        "contact": {"root_keys": ["interface_id", "cases"], "case_keys": ["case_id", "context", "options"], "case_count": 3, "options_per_case": 2},
        "operation_export": "choose_extension(context, options)", "conformance_export": "validate_contact(value) -> bool",
        "ids": "nonempty string or integer excluding bool; same type and distinct within each case",
        "coverage": "nonzero new term, one new-term parent-winner flip, one nonzero child margin <= 10",
        "reversibility": "zero new context penalty or all new option burdens must recover parent-operation.py; removing new fields must recover parent shapes",
        "source_constraints": "no imports, classes, globals, nonlocals, with statements, or double-underscore names",
        "available_builtins": sorted(foundation.SAFE_BUILTINS),
    }
    (seed / "public-meta-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Continue the exact registry-extension pursuit by authoring a reversible extension of the current package. Choose new boundary field names. Edit exactly the four empty package files, satisfy every public contract and coverage rule, inspect the diff, and report truthfully.\n")
    for name in PACKAGE_FILES: (seed / name).write_text("")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": PACKAGE_FILES, "immutable": ["subject-opening.json", "parent-operation.py", "parent-conformance.py", "public-meta-contract.json"]}, indent=2, sort_keys=True) + "\n")
    return seed


def read_package(workspace: Path):
    try:
        return {
            "interface": json.loads((workspace / "interface.json").read_text()),
            "contact": json.loads((workspace / "contact.json").read_text()),
            "operation_source": (workspace / "operation.py").read_text(),
            "conformance_source": (workspace / "conformance.py").read_text(),
        }
    except (OSError, json.JSONDecodeError):
        return None


def run_author(p82, context, run: Path, cycle: int, subject: dict[str, Any], tip: dict[str, Any], selection: dict[str, Any]):
    label = f"cycle-{cycle}-package-author"
    seed = package_seed(run, label, subject, tip, selection)
    prompt = "Author the complete extension package from the exact subject opening and dynamic public contract. Edit exactly interface.json, operation.py, conformance.py, and contact.json; inspect the diff and report truthfully."
    output, base_audit, workspace, _ = context.run_actor(label, seed, AUTHOR_SCHEMA, prompt)
    package = read_package(workspace)
    target = selection["continuation_action"]["action_target"]
    valid = bool(package and valid_spec(package["interface"], tip, target) and validate_contact(package["interface"], tip, package["contact"])[0] and load_named(package["operation_source"], "choose_extension") and load_named(package["conformance_source"], "validate_contact") and output.get("interface_id") == target and output.get("case_count") == 3)
    audit = context.audit_actor(label, output, base_audit, valid, PACKAGE_FILES)
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0111-subject-authored-extension-package", "cycle": cycle, "source_subject_digest": subject["artifact_digest"], "continuation_binding_digest": selection["binding_digest"], "parent_package_binding_digest": tip["binding_digest"], "actor_patch_digest": audit["patch_digest"], **package}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-package.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding}


def correction_seed(run: Path, label: str, package: dict[str, Any], disagreement: dict[str, Any], tip: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"; seed.mkdir()
    for name, value in (("interface.json", package["interface"]), ("contact.json", package["contact"])):
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "operation.py").write_text(package["operation_source"]); (seed / "conformance.py").write_text(package["conformance_source"])
    (seed / "public-contract-disagreement.json").write_text(json.dumps(disagreement, indent=2, sort_keys=True) + "\n")
    contract = {"base_context_bounds": [0, 100], "base_option_bounds": [0, 200], "terms": extended_terms(tip, package["interface"]), "exact_shapes_required": True, "ids": "nonempty string or integer excluding bool; consistent and distinct per case"}
    (seed / "public-meta-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["conformance.py"], "immutable": ["interface.json", "contact.json", "operation.py"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Correct the exact public validator from the complete independent disagreement. Edit only conformance.py, preserve all other package bytes, inspect the diff, and report truthfully.\n")
    return seed


def maybe_correct(p82, context, run: Path, cycle: int, subject: dict[str, Any], tip: dict[str, Any], package: dict[str, Any]):
    spec, contact = package["interface"], package["contact"]
    validator = load_named(package["conformance_source"], "validate_contact")
    disagreement = public_agreement(spec, tip, contact, validator)
    if disagreement["passed"]:
        return {"needed": False, "disagreement": disagreement, "binding": package, "actor": None}
    label = f"cycle-{cycle}-contract-corrector"; seed = correction_seed(run, label, package, disagreement, tip)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, "Correct conformance.py to agree with every independent fixture. Change no other package file, inspect the diff, and report truthfully.")
    try:
        source = (workspace / "conformance.py").read_text()
        immutable = json.loads((workspace / "interface.json").read_text()) == spec and json.loads((workspace / "contact.json").read_text()) == contact and (workspace / "operation.py").read_text() == package["operation_source"]
    except (OSError, json.JSONDecodeError):
        source = ""; immutable = False
    agreement = public_agreement(spec, tip, contact, load_named(source, "validate_contact"))
    valid = bool(immutable and source != package["conformance_source"] and agreement["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["conformance.py"])
    binding = None
    if audit["conformant"]:
        body = {**{key: value for key, value in package.items() if key != "binding_digest"}, "authority": "ot-0111-corrected-extension-package", "parent_package_binding_digest": package["binding_digest"], "actor_patch_digest": audit["patch_digest"], "conformance_source": source, "public_contract": agreement}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-corrected-package.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"needed": True, "disagreement": disagreement, "binding": binding, "actor": {"output": output, "audit": audit, "public_contract": agreement, "immutable": immutable}}


def admit(p82, run: Path, cycle: int, subject: dict[str, Any], tip: dict[str, Any], package: dict[str, Any]):
    seed = secrets.token_bytes(32); (run / f"cycle-{cycle}-hidden-seed.bin").write_bytes(seed)
    hidden = derive_hidden(package["interface"], tip, seed); (run / f"cycle-{cycle}-hidden-cases.json").write_text(json.dumps(hidden, indent=2, sort_keys=True) + "\n")
    assessment = assess(package["interface"], tip, package["contact"], package["operation_source"], package["conformance_source"], hidden)
    body = {"authority": "ot-0111-independent-generic-extension-admission", "cycle": cycle, "source_subject_digest": subject["artifact_digest"], "package_binding_digest": package["binding_digest"], "private_seed_digest": hashlib.sha256(seed).hexdigest(), "derivation_attempt": 1, "hidden_cases_digest": p82.digest(hidden), "assessment": assessment, "admitted": assessment["passed"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}; (run / f"cycle-{cycle}-admission-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def world_contact(p82, cycle: int, package: dict[str, Any], admission: dict[str, Any]):
    rows = admission["assessment"]["authored_oracle"]["rows"] if admission["admitted"] else []
    body = {"authority": "ot-0111-independent-extension-world", "cycle": cycle, "interface_id": package["interface"]["interface_id"], "package_binding_digest": package["binding_digest"], "admission_receipt_digest": admission["receipt_digest"], "rows": rows, "all_cases_passed": bool(rows and all(row["passed"] for row in rows))}
    return {**body, "receipt_digest": p82.digest(body)}


def advance_tip(tip: dict[str, Any], package: dict[str, Any]):
    return {"interface_id": package["interface"]["interface_id"], "terms": extended_terms(tip, package["interface"]), "operation_source": package["operation_source"], "operation_symbol": "choose_extension", "conformance_source": package["conformance_source"], "binding_digest": package["binding_digest"], "package": package}


def registered(subject: dict[str, Any]) -> set[str]:
    return set(foundation.prior.prior.REGISTERED) | {row["interface_id"] for row in subject.get("interface_registry_extensions", [])}


def valid_action(value: Any, subject: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or set(value) != ACTION_KEYS or value.get("action_kind") not in {"registered-contact", "registry-extension", "surrender"}:
        return False
    if not all(isinstance(value.get(key), str) and value[key].strip() and len(value[key]) <= 3000 for key in ACTION_KEYS - {"action_kind"}):
        return False
    if value["action_kind"] == "registered-contact": return value["action_target"] in registered(subject)
    if value["action_kind"] == "surrender": return value["action_target"] == "none"
    return value["action_target"] not in registered(subject) and bool(TARGET_RE.fullmatch(value["action_target"]))


def assimilation_seed(prior89, run: Path, label: str, subject: dict[str, Any], tip: dict[str, Any], package: dict[str, Any], admission: dict[str, Any], world: dict[str, Any]):
    seed = run / f"{label}-seed"; seed.mkdir()
    consequence = {"subject_position": base.active_position(subject), "developmental_history": foundation.active_history(subject), "package_chain_tip": tip, "bound_package": package, "admission_receipt": admission, "world_receipt": world, "registered_interfaces": sorted(registered(subject) | {package["interface"]["interface_id"]})}
    (seed / "subject-contact-consequence.json").write_text(json.dumps(consequence, indent=2, sort_keys=True) + "\n")
    (seed / "assimilation.json").write_text(json.dumps(base.assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action.json").write_text(json.dumps(foundation.prior.prior.action_template(), indent=2, sort_keys=True) + "\n")
    contract = {"exact_keys": sorted(ACTION_KEYS), "action_kinds": ["registered-contact", "registry-extension", "surrender"], "registered_targets": sorted(registered(subject) | {package["interface"]["interface_id"]}), "registry-extension": "new lowercase hyphenated target", "surrender": "target exactly none; use only when continued pursuit is no longer warranted"}
    (seed / "continuation-action-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "retained-parent-operation.py").write_text(tip["operation_source"]); (seed / "admitted-operation.py").write_text(package["operation_source"]); (seed / "admitted-conformance.py").write_text(package["conformance_source"])
    editable = ["assimilation.json", "successor-opening.json", "continuation-action.json"]
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": editable, "immutable": ["retained-parent-operation.py", "admitted-operation.py", "admitted-conformance.py"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the admitted extension consequence and choose what is worth carrying. You may use an admitted interface, open a genuinely new registry extension, or substantively surrender. Preserve package bytes, edit exactly the three permitted JSON files, inspect the diff, and report truthfully.\n")
    return seed


def run_assimilation(prior89, p82, context, run: Path, cycle: int, subject: dict[str, Any], tip: dict[str, Any], package: dict[str, Any], admission: dict[str, Any], world: dict[str, Any]):
    label = f"cycle-{cycle}-assimilation"; seed = assimilation_seed(prior89, run, label, subject, tip, package, admission, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, "Assimilate the completed admitted extension and bind the next continuation. Preserve immutable package bytes, edit exactly the three permitted JSON files, inspect the diff, and report truthfully.")
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text()); opening = json.loads((workspace / "successor-opening.json").read_text()); action = json.loads((workspace / "continuation-action.json").read_text())
        retained = (workspace / "retained-parent-operation.py").read_text() == tip["operation_source"] and (workspace / "admitted-operation.py").read_text() == package["operation_source"] and (workspace / "admitted-conformance.py").read_text() == package["conformance_source"]
    except (OSError, json.JSONDecodeError):
        assimilation = opening = action = None; retained = False
    valid = bool(base.valid_assimilation(assimilation) and prior89.valid_successor(opening) and valid_action(action, {**subject, "interface_registry_extensions": [*subject.get("interface_registry_extensions", []), {"interface_id": package["interface"]["interface_id"]}]}) and retained and (action["action_kind"] == "surrender" or opening["next_opening"] != base.active_position(subject)["continuation"]["next_opening"]))
    audit = context.audit_actor(label, output, base_audit, valid, ["assimilation.json", "successor-opening.json", "continuation-action.json"])
    passed = {row["case_id"] for row in world["rows"] if row["passed"]}; cited = set(assimilation["settled_case_ids"]) if isinstance(assimilation, dict) and isinstance(assimilation.get("settled_case_ids"), list) else set()
    grounded = bool(audit["conformant"] and cited and cited.issubset(passed)); binding = None
    if grounded:
        body = {"authority": "ot-0111-generic-expansion-assimilation", "cycle": cycle, "source_subject_digest": subject["artifact_digest"], "package_binding_digest": package["binding_digest"], "admission_receipt_digest": admission["receipt_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "package_retention_derived": retained, "assimilation": assimilation, "successor_opening": opening, "continuation_action": action}
        binding = {**body, "binding_digest": p82.digest(body)}; (context.evidence(label) / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "grounded": grounded, "package_retention_derived": retained, "binding": binding}


def promote(p82, subject: dict[str, Any], selection: dict[str, Any], package: dict[str, Any], admission: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]):
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); action = assimilation["continuation_action"]; opening = assimilation["successor_opening"]
    body = {"authority": "world-promoted-generic-interface-expansion", "source_subject_digest": subject["artifact_digest"], "continuation_binding_digest": selection["binding_digest"], "package_binding_digest": package["binding_digest"], "admission_receipt_digest": admission["receipt_digest"], "world_receipt_digest": world["receipt_digest"], "assimilation_binding_digest": assimilation["binding_digest"], "continuation_action": action}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["subject_recurrence_receipts"] = [*child.get("subject_recurrence_receipts", []), receipt]
    child["interface_registry_extensions"] = [*child.get("interface_registry_extensions", []), {"interface_id": package["interface"]["interface_id"], "package_binding_digest": package["binding_digest"], "admission_receipt_digest": admission["receipt_digest"]}]
    child["interface_package_chain"] = [*child.get("interface_package_chain", []), package]
    slug = package["interface"]["interface_id"]
    child["environmental_capabilities"] = [*child["environmental_capabilities"], {"target_path": f"operations/{slug}.py", "target_symbol": "choose_extension", "source": package["operation_source"], "source_digest": hashlib.sha256(package["operation_source"].encode()).hexdigest(), "world_receipt_digest": world["receipt_digest"], "binding_digest": package["binding_digest"]}, {"target_path": f"contracts/{slug}.py", "target_symbol": "validate_contact", "source": package["conformance_source"], "source_digest": hashlib.sha256(package["conformance_source"].encode()).hexdigest(), "world_receipt_digest": world["receipt_digest"], "binding_digest": package["binding_digest"]}]
    child["actor_authored_contacts"] = [*child.get("actor_authored_contacts", []), {"interface_id": slug, "binding_digest": package["binding_digest"], "world_receipt_digest": world["receipt_digest"]}]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": assimilation["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []), {"authority": "ot-0111-generic-expansion-opening", "binding_digest": assimilation["binding_digest"], "opening": opening, "continuation_action": action}]
    child["active_pursuit"] = {"authority": "ot-0111-generic-expansion-opening", "selected_area": action["action_target"], "next_pursuit": opening["next_opening"], "world_receipt_digest": world["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "closed" if action["action_kind"] == "surrender" else "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]; child["runtime"] = "sounding"
    return p82.seal(child), receipt


def fixture_sources(terms: list[dict[str, Any]]):
    score_lines = ["        score = option['recovery_value'] - context['risk_penalty'] * option['recovery_risk'] + option['capacity'] - context['overload_penalty'] * option['overload']"]
    score_lines += [f"        score -= context[{row['context_field']!r}] * option[{row['option_field']!r}]" for row in terms]
    operation = "def choose_extension(context, options):\n    def realized(option):\n" + "\n".join(score_lines) + "\n        return score\n    return max(options, key=lambda option: (realized(option), option['id']))['id']\n"
    context_bounds = {"risk_penalty": 100, "overload_penalty": 100, **{row["context_field"]: row["maximum"] for row in terms}}
    option_bounds = {"recovery_value": 200, "recovery_risk": 200, "capacity": 200, "overload": 200, **{row["option_field"]: row["maximum"] for row in terms}}
    validator = f"""def validate_contact(value):
    if not isinstance(value, dict) or set(value) != {{'interface_id', 'cases'}} or not isinstance(value.get('interface_id'), str): return False
    cases = value.get('cases')
    if not isinstance(cases, list) or len(cases) != 3: return False
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {{'case_id', 'context', 'options'}} or not isinstance(case.get('case_id'), str) or not case['case_id'] or case['case_id'] in seen: return False
        seen.add(case['case_id']); context = case.get('context'); options = case.get('options')
        if not isinstance(context, dict) or set(context) != set({context_bounds!r}): return False
        for key, high in {context_bounds!r}.items():
            if not isinstance(context.get(key), (int, float)) or isinstance(context[key], bool) or not 0 <= context[key] <= high: return False
        if not isinstance(options, list) or len(options) != 2: return False
        ids = []
        for option in options:
            if not isinstance(option, dict) or set(option) != set({option_bounds!r}) | {{'id'}}: return False
            identifier = option.get('id')
            if not ((isinstance(identifier, str) and bool(identifier)) or (isinstance(identifier, int) and not isinstance(identifier, bool))): return False
            ids.append(identifier)
            for key, high in {option_bounds!r}.items():
                if not isinstance(option.get(key), (int, float)) or isinstance(option[key], bool) or not 0 <= option[key] <= high: return False
        if type(ids[0]) is not type(ids[1]) or ids[0] == ids[1]: return False
    return True
"""
    return operation, validator


def fixture_package(tip: dict[str, Any], target: str, context_field: str, option_field: str):
    spec = {"interface_id": target, "parent_interface_id": tip["interface_id"], "new_context_field": context_field, "new_option_field": option_field, "minimum": 0, "maximum": 10, "score_composition": COMPOSITION, "reversible_projection": True}
    terms = extended_terms(tip, spec); base_context = {"risk_penalty": 0, "overload_penalty": 0, **{row["context_field"]: 0 for row in tip["terms"]}, context_field: 5}
    def option(identifier, recovery, burden): return {"id": identifier, "recovery_value": recovery, "recovery_risk": 0, "capacity": 40, "overload": 0, **{row["option_field"]: 0 for row in tip["terms"]}, option_field: burden}
    cases = [
        {"case_id": f"{target}-flip", "context": base_context, "options": [option("a", 100, 2), option("b", 95, 0)]},
        {"case_id": f"{target}-retain", "context": {**base_context, context_field: 2}, "options": [option("c", 100, 1), option("d", 90, 0)]},
        {"case_id": f"{target}-margin", "context": {**base_context, context_field: 3}, "options": [option("e", 98, 1), option("f", 94, 0)]},
    ]
    operation, conformance = fixture_sources(terms)
    return spec, {"interface_id": target, "cases": cases}, operation, conformance


def fixture_conformance(initial_tip: dict[str, Any]):
    spec1, contact1, operation1, contract1 = fixture_package(initial_tip, "fixture-extension-one", "delay_penalty", "delay_burden")
    hidden1 = derive_hidden(spec1, initial_tip, b"ot-0111-depth-one")
    good1 = assess(spec1, initial_tip, contact1, operation1, contract1, hidden1)
    package1 = {"interface": spec1, "contact": contact1, "operation_source": operation1, "conformance_source": contract1, "binding_digest": "fixture-one"}
    tip2 = advance_tip(initial_tip, package1)
    spec2, contact2, operation2, contract2 = fixture_package(tip2, "fixture-extension-two", "coordination_penalty", "coordination_burden")
    hidden2 = derive_hidden(spec2, tip2, b"ot-0111-depth-two")
    good2 = assess(spec2, tip2, contact2, operation2, contract2, hidden2)
    reused = {**spec2, "new_context_field": initial_tip["terms"][0]["context_field"]}
    wrong_parent = {**spec2, "parent_interface_id": "wrong-parent"}
    no_flip = copy.deepcopy(contact2)
    for case in no_flip["cases"]:
        for option in case["options"]: option[spec2["new_option_field"]] = 0
    vacuous = "def validate_contact(value):\n    return True\n"
    nonreversible = "def choose_extension(context, options):\n    return max(options, key=lambda option: (option['recovery_value'] + option['capacity'], option['id']))['id']\n"
    result = {"depth_one_admitted": good1["passed"], "depth_two_admitted": good2["passed"], "field_reuse_rejected": not valid_spec(reused, tip2, spec2["interface_id"]), "parent_mismatch_rejected": not valid_spec(wrong_parent, tip2, spec2["interface_id"]), "vacuous_validator_rejected": not assess(spec2, tip2, contact2, operation2, vacuous, hidden2)["passed"], "nonreversible_operation_rejected": not assess(spec2, tip2, contact2, nonreversible, contract2, hidden2)["passed"], "nonconsequential_boundary_rejected": not validate_contact(spec2, tip2, no_flip)[0]}
    result["passed"] = all(result.values()); return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); parser.add_argument("--reconstruct-stopped", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0111").resolve()
    prior92 = base.mechanism.load_prior(); _, _, prior89, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    subject = load_parent(p82, repo, store); tip = load_initial_tip(p82, repo, store); fixtures = fixture_conformance(tip); selection = extract_action(p82, subject)
    valid_parent = subject["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(subject) and selection and selection["continuation_action"]["action_kind"] == "registry-extension"
    if args.preflight_only:
        result = {"parent_digest": subject["artifact_digest"], "parent_object_sha256": PARENT_OBJECT_SHA256, "base_implementation_sha256": BASE_SHA256, "initial_package_digest": tip["binding_digest"], "fixture_conformance": fixtures, "initial_action": selection}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if valid_parent and fixtures["passed"] else 2
    if args.reconstruct_stopped:
        package = json.loads((run / "cycle-1-package-author" / "bound-package.json").read_text()); admission = json.loads((run / "cycle-1-admission-receipt.json").read_text()); audit = json.loads((run / "cycle-1-package-author" / "actor-audit.json").read_text()); output = json.loads((run / "cycle-1-package-author" / "output.json").read_text()); world = world_contact(p82, 1, package, admission)
        body = {"authority": "ot-0111-stopped-observation-reconstruction", "source_subject_digest": subject["artifact_digest"], "cycle_one_package_author": {"output": output, "audit": audit, "binding": package}, "cycle_one_admission": admission, "reconstructed_world_receipt": world, "promoted_cycle_count": 0, "two_cycle_target_passed": False, "observer_disposition": "rejected", "subject_disposition": "open", "final_subject_digest": subject["artifact_digest"], "continuation_action": subject["actor_originated_pursuit_openings"][-1].get("continuation_action"), "next_opening": subject["continuation"]["next_opening"], "stopping_error": "post-package implementation error resolving the inherited registered-interface constant before assimilation seed creation", "scientific_actor_count": 1}
        body["receipt_digest"] = p82.digest(body); (run / "reconstructed-world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n"); (run / "aggregate.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n"); (run / "final-full-subject.json").write_text(json.dumps(subject, indent=2, sort_keys=True) + "\n"); print(json.dumps(body, indent=2, sort_keys=True)); return 0
    if run.exists(): raise SystemExit("preserve existing OT-0111 evidence")
    run.mkdir(parents=True); (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not valid_parent or not fixtures["passed"]: raise SystemExit("pre-actor conformance failed")
    context = prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); started = time.time(); cycles = []
    current = subject; current_tip = tip; current_selection = selection
    for cycle in (1, 2):
        if current_selection["continuation_action"]["action_kind"] != "registry-extension": break
        authored = run_author(p82, context, run, cycle, current, current_tip, current_selection); raw = authored["binding"]
        corrected = maybe_correct(p82, context, run, cycle, current, current_tip, raw) if raw else None; package = corrected["binding"] if corrected else None
        admission = admit(p82, run, cycle, current, current_tip, package) if package else None; world = world_contact(p82, cycle, package, admission) if admission and admission["admitted"] else None
        assimilation = run_assimilation(prior89, p82, context, run, cycle, current, current_tip, package, admission, world) if world and world["all_cases_passed"] else None
        promotion = None
        if assimilation and assimilation["binding"]: current, promotion = promote(p82, current, current_selection, package, admission, world, assimilation["binding"])
        passed = bool(promotion and runtime.identity_conforms(current)); cycles.append({"cycle": cycle, "package_author": p82.compact(authored), "correction": p82.compact(corrected) if corrected else None, "admission": p82.compact(admission) if admission else None, "world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "promotion": promotion, "passed": passed, "successor_digest": current["artifact_digest"]})
        if not passed: break
        (run / f"sealed-cycle-{cycle}-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n"); current_tip = advance_tip(current_tip, package); current_selection = extract_action(p82, current)
        if not current_selection: break
    operational = len(cycles) == 2 and all(row["passed"] for row in cycles)
    result = {"authority": "ot-0111-generic-interface-expansion-recurrence-driver", "source_subject_digest": subject["artifact_digest"], "cycles": cycles, "promoted_cycle_count": sum(row["passed"] for row in cycles), "two_cycle_target_passed": operational, "observer_disposition": "promoted" if operational else "rejected", "subject_disposition": "open" if current["continuation"]["status"] == "open" else "closed", "final_subject_digest": current["artifact_digest"], "continuation_action": current["actor_originated_pursuit_openings"][-1].get("continuation_action"), "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time()-started,3)}
    result["receipt_digest"] = p82.digest(result); (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n"); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
