from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
PRIOR_PATH = ROOT / "ot_0092_actor_contact_renewal.py"
PRIOR_SHA256 = "b822931c1b4a14f8ae19354e2bcca3fc6d30113e1f102e2dea7a27521f5e4a05"
PARENT_DIGEST = "242939d5c83a8897f081d12743c084ddd0f640a9d78d29764660822a982ac795"
SELECTOR_DIGEST = "9b9c80a1eda62f4857919d0c6dd294d75ed9e87f6eede49ba8e82a1a012c3156"
INHERITED_OPENING = (
    "Run the reusable verifier against newly admitted coverage cases, comparing selected id, maximum "
    "realized score, maximizing-id set, and the greatest-id tie rule with the realized-score oracle."
)
PLACEHOLDER = "__REPLACE__"
CONTACT_KEYS = {
    "id", "target_path", "target_symbol", "completed_floors", "public_regret",
    "reversible", "held_repeat", "world_valid", "predicted_expansion",
    "world_contact", "surrender_condition",
}
CHOICE_KEYS = {"contact_id", "current_opening_disposition", "observed_saturation", "predicted_expansion", "intended_consequence", "surrender_condition"}
ASSIMILATION_KEYS = {"allocator_disposition", "consequence_summary", "settled_case_ids", "remaining_uncertainty", "selection_rule_update", "surrender_condition"}
ALLOCATOR_SCHEMA = REPO / "spec/ot-0093-allocator.schema.json"
IMPLEMENTER_SCHEMA = REPO / "spec/ot-0093-implementer.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0093-assimilator.schema.json"


WORLD_SOURCE = '''def score_recovery(context, option):
    return option["speed"] - context["failure_penalty"] * option["failure_risk"]


def recovery_floor(context, option):
    return option["recovery_value"] - context["risk_penalty"] * option["recovery_risk"]


def schedule_floor(context, option):
    return option["capacity"] - context["overload_penalty"] * option["overload"]


def score_joint(context, option):
    return recovery_floor(context, option) + schedule_floor(context, option)
'''

RECOVERY_SOURCE = '''def choose_recovery(context, options):
    """Choose one existing recovery option id."""
    return max(options, key=lambda item: (item["speed"], item["id"]))["id"]
'''

RECOVERY_REFERENCE = '''from .world import score_recovery


def choose_recovery(context, options):
    """Choose one existing recovery option id."""
    return max(options, key=lambda item: (score_recovery(context, item), item["id"]))["id"]
'''

JOINT_SOURCE = '''def choose_joint(context, options):
    """Choose one existing joint allocation option id."""
    return max(options, key=lambda item: (item["capacity"], item["id"]))["id"]
'''

JOINT_REFERENCE = '''from .world import score_joint


def choose_joint(context, options):
    """Choose one existing joint allocation option id."""
    return max(options, key=lambda item: (score_joint(context, item), item["id"]))["id"]
'''

REFERENCE_ALLOCATOR = '''def select(contacts):
    eligible = [row for row in contacts if row["world_valid"] and row["reversible"] and not row["held_repeat"]]
    return max(eligible, key=lambda row: (len(row["completed_floors"]) >= 2,
                                          row["predicted_expansion"],
                                          row["public_regret"], row["id"]))["id"]
'''


def load_prior():
    if hashlib.sha256(PRIOR_PATH.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0092 implementation identity changed")
    name = "ot0093_frozen_ot0092"
    spec = importlib.util.spec_from_file_location(name, PRIOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prior_chain(prior92):
    prior91 = prior92.load_prior()
    prior90 = prior91.load_prior()
    prior89 = prior90.load_prior()
    p82 = prior90.prior82(prior89)
    return prior91, prior90, prior89, p82


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0092", "open-subject-after-actor-contact-renewal.json")
    return json.loads(path.read_text())


def recovery_case(case_id: str, fast: float, penalty: float, risk: float, safe: float) -> dict[str, Any]:
    return {"case_id": case_id, "context": {"failure_penalty": penalty}, "options": [
        {"id": "fast", "speed": fast, "failure_risk": risk},
        {"id": "safe", "speed": safe, "failure_risk": 0.0},
    ]}


def joint_case(case_id: str, capacity_a: float, recovery_a: float, risk_penalty: float,
               recovery_risk: float, capacity_b: float) -> dict[str, Any]:
    return {"case_id": case_id, "context": {"risk_penalty": risk_penalty, "overload_penalty": 0.0}, "options": [
        {"id": "capacity", "capacity": capacity_a, "overload": 0.0,
         "recovery_value": recovery_a, "recovery_risk": recovery_risk},
        {"id": "balanced", "capacity": capacity_b, "overload": 0.0,
         "recovery_value": recovery_a, "recovery_risk": 0.0},
    ]}


PUBLIC_CASES = {
    "recovery": [recovery_case("r-public-1", 100, 80, .5, 80), recovery_case("r-public-2", 120, 100, .4, 100)],
    "joint": [joint_case("j-public-1", 100, 80, 80, .5, 80), joint_case("j-public-2", 120, 100, 100, .4, 100)],
}
HIDDEN_CASES = {
    "recovery": [recovery_case("r-hidden-1", 100, 80, .5, 80), recovery_case("r-hidden-2", 120, 100, .4, 100),
                 recovery_case("r-hidden-3", 90, 50, .6, 80), recovery_case("r-hidden-4", 110, 60, .5, 100)],
    "joint": [joint_case("j-hidden-1", 100, 80, 80, .5, 80), joint_case("j-hidden-2", 120, 100, 100, .4, 100),
              joint_case("j-hidden-3", 90, 80, 50, .6, 80), joint_case("j-hidden-4", 110, 100, 60, .5, 100)],
}

EVALUATOR_SOURCE = '''import importlib
import json
from pathlib import Path
from operations import world

config = json.loads(Path("_config.json").read_text())
choose = getattr(importlib.import_module(config["module"]), config["function"])
score = getattr(world, config["score"])
rows = []
for case in config["cases"]:
    selected_id = choose(case["context"], case["options"])
    selected = next(item for item in case["options"] if item["id"] == selected_id)
    oracle = max(case["options"], key=lambda item: (score(case["context"], item), item["id"]))
    rows.append({"case_id": case["case_id"], "selected_id": selected_id, "oracle_id": oracle["id"],
                 "score": score(case["context"], selected), "oracle_score": score(case["context"], oracle)})
print(json.dumps({"rows": rows, "total": sum(row["score"] for row in rows),
                  "oracle_total": sum(row["oracle_score"] for row in rows)}, sort_keys=True))
'''

PUBLIC_CHECK_SOURCE = '''import json
from pathlib import Path
from operations.joint import choose_joint
from operations.world import score_joint

cases = json.loads(Path("public-cases.json").read_text())
for case in cases:
    selected_id = choose_joint(case["context"], case["options"])
    selected = next(item for item in case["options"] if item["id"] == selected_id)
    oracle = max(case["options"], key=lambda item: (score_joint(case["context"], item), item["id"]))
    print(json.dumps({"case_id": case["case_id"], "selected_id": selected_id,
                      "score": score_joint(case["context"], selected), "oracle_id": oracle["id"],
                      "oracle_score": score_joint(case["context"], oracle)}, sort_keys=True))
'''


def subject_capability(parent: dict[str, Any], target: str) -> dict[str, Any]:
    return next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == target)


def write_world(root: Path, parent: dict[str, Any], recovery_source: str = RECOVERY_SOURCE,
                joint_source: str = JOINT_SOURCE) -> None:
    files = {
        "operations/__init__.py": "", "operations/world.py": WORLD_SOURCE,
        "operations/recovery.py": recovery_source, "operations/joint.py": joint_source,
        "studio/__init__.py": "",
        "studio/coverage.py": subject_capability(parent, "studio/coverage.py")["source"],
        "verify_coverage.py": subject_capability(parent, "verify_coverage.py")["source"],
    }
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def evaluate(p82, parent: dict[str, Any], family: str, source: str,
             cases: list[dict[str, Any]], root: Path, label: str) -> dict[str, Any]:
    workspace = root / label
    recovery_source = source if family == "recovery" else RECOVERY_SOURCE
    joint_source = source if family == "joint" else JOINT_SOURCE
    write_world(workspace, parent, recovery_source, joint_source)
    config = {"module": f"operations.{family}", "function": f"choose_{family}",
              "score": f"score_{family}", "cases": cases}
    (workspace / "_config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
    (workspace / "_evaluate.py").write_text(EVALUATOR_SOURCE)
    completed = subprocess.run(["python3", "_evaluate.py"], cwd=workspace, text=True, capture_output=True, timeout=30)
    try:
        output = json.loads(completed.stdout)
        valid = completed.returncode == 0 and len(output["rows"]) == len(cases)
    except (json.JSONDecodeError, KeyError):
        output, valid = {"rows": [], "total": 0.0, "oracle_total": 0.0}, False
    body = {"family": family, "source_digest": p82.digest(source), "cases_digest": p82.digest(cases),
            "valid": valid, "rows": output["rows"], "total": output["total"], "oracle_total": output["oracle_total"],
            "gain_available": output["oracle_total"] - output["total"],
            "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest()}
    return {**body, "receipt_digest": p82.digest(body)}


def coverage_domain() -> list[dict[str, Any]]:
    cases = []
    for weight in (0.0, 1.0, 2.0):
        for base_a in (0.0, 1.0):
            for coverage_a in (0.0, 1.0):
                for base_b in (0.0, 1.0):
                    for coverage_b in (0.0, 1.0):
                        cases.append({"context": {"coverage_weight": weight}, "options": [
                            {"id": "a", "base_value": base_a, "coverage_units": coverage_a, "coordination_cost": 0.0},
                            {"id": "b", "base_value": base_b, "coverage_units": coverage_b, "coordination_cost": 0.0}]})
    return cases


def saturation_certificate(parent: dict[str, Any]) -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    exec(subject_capability(parent, "studio/coverage.py")["source"], namespace)
    choose = namespace["choose_coverage"]
    cases = coverage_domain()
    passed = True
    for case_value in cases:
        score = lambda item: item["base_value"] + case_value["context"]["coverage_weight"] * item["coverage_units"] - item["coordination_cost"]
        oracle = max(case_value["options"], key=lambda item: (score(item), item["id"]))["id"]
        passed = passed and choose(case_value["context"], case_value["options"]) == oracle
    return {"authority": "ot-0093-exhaustive-bounded-coverage-certificate", "domain_size": len(cases),
            "domain_digest": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
            "all_cases_passed": passed, "next_same_domain_case": "held_repeat" if passed else "unresolved"}


def reference_frontier() -> list[dict[str, Any]]:
    common = {"reversible": True, "world_valid": True, "public_regret": 40.0, "predicted_expansion": 80.0,
              "world_contact": "Execute bound public and hidden cases.", "surrender_condition": "Surrender on regression or world invalidity."}
    return [
        {**common, "id": "coverage-check", "target_path": "verify_coverage.py", "target_symbol": "assess",
         "completed_floors": ["coverage-policy", "coverage-verifier"], "held_repeat": True, "public_regret": 0.0, "predicted_expansion": 0.0},
        {**common, "id": "recovery-fix", "target_path": "operations/recovery.py", "target_symbol": "choose_recovery",
         "completed_floors": [], "held_repeat": False},
        {**common, "id": "joint-compose", "target_path": "operations/joint.py", "target_symbol": "choose_joint",
         "completed_floors": ["recovery-safety", "resource-schedule"], "held_repeat": False},
    ]


def validate_frontier(value: Any, certificate: dict[str, Any]) -> dict[str, Any]:
    contacts = value.get("contacts", []) if isinstance(value, dict) and set(value) == {"contacts"} else []
    expected = {row["target_path"]: row for row in reference_frontier()}
    exact = len(contacts) >= 3 and all(isinstance(row, dict) and set(row) == CONTACT_KEYS for row in contacts)
    ids_unique = exact and len({row["id"] for row in contacts}) == len(contacts) and all(isinstance(row["id"], str) and row["id"] for row in contacts)
    complete_targets = exact and {row.get("target_path") for row in contacts} == set(expected)
    declarations = complete_targets and all(row.get("target_path") in expected and all(row.get(key) == expected[row["target_path"]][key]
        for key in ("target_symbol", "completed_floors", "public_regret", "reversible", "held_repeat", "world_valid", "predicted_expansion")) for row in contacts)
    saturation_bound = declarations and certificate["all_cases_passed"] and next(row for row in contacts if row["target_path"] == "verify_coverage.py")["held_repeat"]
    result = {"exact_shape": exact, "unique_ids": ids_unique, "complete_targets": complete_targets, "objective_declarations": declarations, "saturation_bound": saturation_bound}
    result["passed"] = all(result.values())
    return result


def load_allocator(source: str, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "allocate.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("candidate_allocator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.select


def allocator_fixtures() -> list[list[dict[str, Any]]]:
    base = reference_frontier()
    renamed = [{**row, "id": f"x{index}"} for index, row in enumerate(reversed(base))]
    invalid = [{**base[2], "id": "bad", "world_valid": False}, {**base[1], "id": "good"}]
    tie = [{**base[1], "id": "alpha"}, {**base[1], "id": "zeta"}]
    return [base, list(reversed(base)), renamed, invalid, tie]


def expected_allocation(rows: list[dict[str, Any]]) -> str:
    eligible = [row for row in rows if row["world_valid"] and row["reversible"] and not row["held_repeat"]]
    return max(eligible, key=lambda row: (len(row["completed_floors"]) >= 2, row["predicted_expansion"], row["public_regret"], row["id"]))["id"]


def allocator_conformance(source: str, root: Path) -> dict[str, Any]:
    forbidden = ["verify_coverage.py", "operations/", "coverage-check", "recovery-fix", "joint-compose", "choose_recovery", "choose_joint"]
    generic_source = all(token not in source for token in forbidden)
    try:
        select = load_allocator(source, root)
        outcomes = []
        for fixture in allocator_fixtures():
            actual = select(json.loads(json.dumps(fixture)))
            outcomes.append({"expected": expected_allocation(fixture), "actual": actual, "passed": actual == expected_allocation(fixture)})
        valid = all(row["passed"] for row in outcomes)
    except Exception as error:
        outcomes, valid = [{"error_type": type(error).__name__, "passed": False}], False
    return {"generic_source": generic_source, "fixture_outcomes": outcomes, "passed": generic_source and valid}


def fixture_conformance(prior92, p82, parent: dict[str, Any], root: Path) -> dict[str, Any]:
    certificate = saturation_certificate(parent)
    evaluations = {}
    for family, unchanged, reference in (("recovery", RECOVERY_SOURCE, RECOVERY_REFERENCE), ("joint", JOINT_SOURCE, JOINT_REFERENCE)):
        public_u = evaluate(p82, parent, family, unchanged, PUBLIC_CASES[family], root, f"{family}-public-unchanged")
        public_r = evaluate(p82, parent, family, reference, PUBLIC_CASES[family], root, f"{family}-public-reference")
        hidden_u = evaluate(p82, parent, family, unchanged, HIDDEN_CASES[family], root, f"{family}-hidden-unchanged")
        hidden_r = evaluate(p82, parent, family, reference, HIDDEN_CASES[family], root, f"{family}-hidden-reference")
        evaluations[family] = {"public_unchanged": public_u, "public_reference": public_r,
                               "hidden_unchanged": hidden_u, "hidden_reference": hidden_r,
                               "public_gain": public_r["total"] - public_u["total"],
                               "hidden_gain": hidden_r["total"] - hidden_u["total"]}
    frontier = {"contacts": reference_frontier()}
    allocation = allocator_conformance(REFERENCE_ALLOCATOR, root / "allocator")
    selector = parent["developmental_selector"]
    result = {"parent_bound": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["next_opening"] == INHERITED_OPENING,
              "selector_bound": selector["selector_digest"] == SELECTOR_DIGEST,
              "saturation_certificate": certificate, "evaluations": evaluations,
              "balanced_public_gain": {row["public_gain"] for row in evaluations.values()} == {40.0},
              "balanced_hidden_gain": {row["hidden_gain"] for row in evaluations.values()} == {80.0},
              "frontier_reference": validate_frontier(frontier, certificate), "allocator_reference": allocation,
              "projection_conformance": projection_conformance(p82, parent)}
    result["passed"] = all((result["parent_bound"], result["selector_bound"], certificate["all_cases_passed"],
                            result["balanced_public_gain"], result["balanced_hidden_gain"],
                            result["frontier_reference"]["passed"], allocation["passed"], result["projection_conformance"]["passed"]))
    return result


def active_position(parent: dict[str, Any]) -> dict[str, Any]:
    return {"subject_digest": parent["artifact_digest"], "runtime": parent["runtime"],
            "continuation": copy.deepcopy(parent["continuation"]), "active_pursuit": copy.deepcopy(parent["active_pursuit"]),
            "unresolved": parent["unresolved"], "developmental_selector": copy.deepcopy(parent["developmental_selector"]),
            "recent_capabilities": copy.deepcopy(parent.get("environmental_capabilities", [])[-5:]),
            "recent_assimilations": copy.deepcopy(parent.get("pursuit_assimilations", [])[-2:])}


def erased_position(p82, parent: dict[str, Any]) -> dict[str, Any]:
    active = active_position(parent)
    selector = active["developmental_selector"]
    removed_keys = ["executable_priority_policy", "positive_gradient", "rank_descending", "reject_if_any", "threshold"]
    removed = {key: selector.pop(key) for key in list(removed_keys) if key in selector}
    # rank/reject are nested in executable_priority_policy and leave only identity/provenance.
    active["selector_content_erasure"] = {"authority": "ot-0093-selector-content-erasure",
        "removed_fields": sorted(removed), "removed_content_digest": p82.digest(removed),
        "selector_digest": SELECTOR_DIGEST}
    return active


def projection_conformance(p82, parent: dict[str, Any]) -> dict[str, Any]:
    active, erased = active_position(parent), erased_position(p82, parent)
    active_text, erased_text = json.dumps(active, sort_keys=True), json.dumps(erased, sort_keys=True)
    forbidden = ("compose-two-or-more-completed-floors", "held_repeat", "axis_chord", "rank_descending")
    common_keys = set(active) - {"developmental_selector"}
    result = {"parent_bound": active["subject_digest"] == erased["subject_digest"] == PARENT_DIGEST,
              "active_has_selector_gradient": "compose-two-or-more-completed-floors" in active_text,
              "erased_omits_selector_content": all(token not in erased_text for token in forbidden),
              "same_non_selector_state": all(active[key] == erased[key] for key in common_keys),
              "active_digest": p82.digest(active), "erased_digest": p82.digest(erased)}
    result["passed"] = all(result[key] for key in ("parent_bound", "active_has_selector_gradient", "erased_omits_selector_content", "same_non_selector_state")) and result["active_digest"] != result["erased_digest"]
    return result


def frontier_template() -> dict[str, Any]:
    return {"contacts": []}


def choice_template() -> dict[str, str]:
    return {key: PLACEHOLDER for key in CHOICE_KEYS}


def valid_choice(value: Any, contacts: list[dict[str, Any]]) -> bool:
    return (isinstance(value, dict) and set(value) == CHOICE_KEYS
            and value.get("contact_id") in {row["id"] for row in contacts}
            and value.get("current_opening_disposition") in {"surrender", "deprioritize", "retain"}
            and all(isinstance(value[key], str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 3000 for key in CHOICE_KEYS))


def public_observations(p82, parent: dict[str, Any], root: Path) -> dict[str, Any]:
    certificate = saturation_certificate(parent)
    rows = {"coverage": {"target_path": "verify_coverage.py", "target_symbol": "assess", "public_regret": 0.0,
                          "predicted_expansion": 0.0, "completed_floors": ["coverage-policy", "coverage-verifier"],
                          "held_repeat": True, "reversible": True, "world_valid": True, "certificate": certificate}}
    for family, source in (("recovery", RECOVERY_SOURCE), ("joint", JOINT_SOURCE)):
        receipt = evaluate(p82, parent, family, source, PUBLIC_CASES[family], root, f"observe-{family}")
        rows[family] = {"target_path": f"operations/{family}.py", "target_symbol": f"choose_{family}",
                        "public_regret": receipt["gain_available"], "predicted_expansion": 80.0,
                        "completed_floors": [] if family == "recovery" else ["recovery-safety", "resource-schedule"],
                        "held_repeat": False, "reversible": True, "world_valid": True, "receipt": receipt}
    return rows


ALLOCATOR_SEED = '''def select(contacts):
    """Return one contact id using only declared contact fields."""
    raise NotImplementedError("embody the allocation rule")
'''


def allocator_seed(run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], p82) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_world(seed, parent)
    observations = public_observations(p82, parent, seed / "observations")
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "public-observations.json").write_text(json.dumps(observations, indent=2, sort_keys=True) + "\n")
    (seed / "saturation-certificate.json").write_text(json.dumps(saturation_certificate(parent), indent=2, sort_keys=True) + "\n")
    (seed / "frontier.json").write_text(json.dumps(frontier_template(), indent=2) + "\n")
    (seed / "allocate.py").write_text(ALLOCATOR_SEED)
    (seed / "choice.json").write_text(json.dumps(choice_template(), indent=2, sort_keys=True) + "\n")
    contract = {"frontier_root_exact_keys": ["contacts"], "contact_exact_keys": sorted(CONTACT_KEYS),
        "choice_exact_keys": sorted(CHOICE_KEYS), "allocator_abi": "select(contacts) -> contact id",
        "allocator_rule": "Use only declared fields; do not embed ids, paths, symbols, or hidden facts.",
        "instruction": "Discover and declare the real contacts exposed by source and public observations; declarations are audited objectively."}
    (seed / "allocation-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["frontier.json", "allocate.py", "choice.json"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Continue the exact subject in this complete environment. Reconcile its local opening with objective saturation, discover the bounded frontier, embody a generic allocation rule, bind its choice, run useful checks, inspect the exact diff, and edit exactly the three permitted files.\n")
    return seed


def run_allocator(p82, context, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any]) -> dict[str, Any]:
    seed = allocator_seed(run, label, parent, position, p82)
    prompt = "Continue the exact subject by inspecting this complete world, reconciling current pursuit with evidence, authoring its frontier, embodying a reusable allocation rule, binding one contact, running useful public checks, inspecting the exact diff, and returning the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, ALLOCATOR_SCHEMA, prompt)
    try:
        frontier = json.loads((workspace / "frontier.json").read_text())
        source = (workspace / "allocate.py").read_text()
        choice = json.loads((workspace / "choice.json").read_text())
    except (OSError, json.JSONDecodeError):
        frontier, source, choice = None, "", None
    certificate = saturation_certificate(parent)
    frontier_check = validate_frontier(frontier, certificate)
    contacts = frontier.get("contacts", []) if isinstance(frontier, dict) else []
    choice_valid = valid_choice(choice, contacts)
    try:
        public_selected = load_allocator(source, workspace / "public-allocator")(json.loads(json.dumps(contacts)))
    except Exception:
        public_selected = None
    artifact_valid = bool(frontier_check["passed"] and choice_valid and public_selected == choice["contact_id"] and source != ALLOCATOR_SEED)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, ["allocate.py", "choice.json", "frontier.json"])
    binding = None
    hidden_allocator = {"passed": False}
    if audit["conformant"]:
        body = {"authority": "ot-0093-pre-hidden-allocation", "condition": label,
                "source_subject_digest": position["subject_digest"], "projection_digest": p82.digest(position),
                "actor_patch_digest": audit["patch_digest"], "frontier": frontier, "allocator_source": source,
                "allocator_digest": p82.digest(source), "choice": choice, "frontier_conformance": frontier_check}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-allocation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        hidden_allocator = allocator_conformance(source, context.evidence(label) / "hidden-allocator")
    chosen = next((row for row in contacts if row.get("id") == (choice or {}).get("contact_id")), None)
    active_gate = bool(binding and hidden_allocator["passed"] and choice["current_opening_disposition"] in {"surrender", "deprioritize"}
                       and chosen and chosen["target_path"] == "operations/joint.py")
    score = {"hidden_allocator": hidden_allocator, "current_opening_redirected": bool(choice and choice.get("current_opening_disposition") in {"surrender", "deprioritize"}),
             "chosen_target_path": chosen["target_path"] if chosen else None, "active_gate_passed": active_gate}
    score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "allocation-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def implementation_seed(prior89, run: Path, parent: dict[str, Any], allocation: dict[str, Any]) -> Path:
    seed = run / "implementation-seed"
    seed.mkdir()
    write_world(seed, parent)
    (seed / "bound-allocation.json").write_text(json.dumps(allocation, indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "public-cases.json").write_text(json.dumps(PUBLIC_CASES["joint"], indent=2, sort_keys=True) + "\n")
    (seed / "check_public.py").write_text(PUBLIC_CHECK_SOURCE)
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["operations/joint.py", "successor-opening.json"],
        "selected_contact_id": allocation["choice"]["contact_id"], "allocation_binding_digest": allocation["binding_digest"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Enact the exact bound allocation. Preserve both completed floors and every unselected file, improve only operations/joint.py, author a substantive successor opening, run useful checks, inspect the exact diff, and leave hidden consequence to the world.\n")
    return seed


def run_implementation(prior89, p82, context, run: Path, parent: dict[str, Any], allocation: dict[str, Any]) -> dict[str, Any]:
    seed = implementation_seed(prior89, run, parent, allocation)
    prompt = "Enact the exact bound allocation with ordinary tools. Preserve both completed floors, edit exactly operations/joint.py and successor-opening.json, author the next substantive opening, run useful public checks, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor("implementation", seed, IMPLEMENTER_SCHEMA, prompt)
    try:
        source = (workspace / "operations/joint.py").read_text()
        opening = json.loads((workspace / "successor-opening.json").read_text())
    except (OSError, json.JSONDecodeError):
        source, opening = "", None
    compiled = subprocess.run(["python3", "-m", "py_compile", "operations/joint.py"], cwd=workspace, capture_output=True)
    valid = bool(compiled.returncode == 0 and source != JOINT_SOURCE and prior89.valid_successor(opening)
                 and opening["next_opening"] != INHERITED_OPENING)
    audit = context.audit_actor("implementation", output, base_audit, valid, ["operations/joint.py", "successor-opening.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0093-pre-hidden-joint-implementation", "source_subject_digest": parent["artifact_digest"],
                "allocation_binding_digest": allocation["binding_digest"], "actor_patch_digest": audit["patch_digest"],
                "source": source, "source_digest": p82.digest(source), "successor_opening": opening}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("implementation") / "bound-implementation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    public = evaluate(p82, parent, "joint", source, PUBLIC_CASES["joint"], context.evidence("implementation"), "public") if binding else None
    hidden = evaluate(p82, parent, "joint", source, HIDDEN_CASES["joint"], context.evidence("implementation"), "hidden") if binding else None
    admitted = bool(public and hidden and public["valid"] and hidden["valid"] and public["gain_available"] == 0.0 and hidden["gain_available"] == 0.0
                    and public["total"] == public["oracle_total"] and hidden["total"] == hidden["oracle_total"])
    body = {"authority": "ot-0093-sealed-joint-consequence", "source_subject_digest": parent["artifact_digest"],
            "allocation_binding_digest": allocation["binding_digest"], "implementation_binding_digest": binding["binding_digest"] if binding else None,
            "public": public, "hidden": hidden, "developmentally_admitted": admitted}
    world = {**body, "receipt_digest": p82.digest(body)}
    (context.evidence("implementation") / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "world": world}


def assimilation_template() -> dict[str, Any]:
    return {"allocator_disposition": PLACEHOLDER, "consequence_summary": PLACEHOLDER, "settled_case_ids": [],
            "remaining_uncertainty": PLACEHOLDER, "selection_rule_update": PLACEHOLDER, "surrender_condition": PLACEHOLDER}


def valid_assimilation(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != ASSIMILATION_KEYS or value.get("allocator_disposition") not in {"retain", "revise"}:
        return False
    if not isinstance(value.get("settled_case_ids"), list) or not value["settled_case_ids"] or not all(isinstance(item, str) and item for item in value["settled_case_ids"]):
        return False
    return all(isinstance(value[key], str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 3000
               for key in ASSIMILATION_KEYS - {"settled_case_ids"})


def assimilation_seed(prior89, run: Path, parent: dict[str, Any], allocation: dict[str, Any], implementation: dict[str, Any]) -> Path:
    seed = run / "assimilation-seed"
    seed.mkdir()
    position = {"subject_digest": parent["artifact_digest"], "continuation": parent["continuation"],
                "developmental_selector": parent["developmental_selector"], "bound_allocation": allocation,
                "implementation_binding": implementation["binding"],
                "complete_consequence": implementation["world"]}
    (seed / "subject-allocation-consequence.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "allocate.py").write_text(allocation["allocator_source"])
    (seed / "allocation-assimilation.json").write_text(json.dumps(assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["allocation-assimilation.json", "successor-opening.json"], "immutable": ["allocate.py"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Assimilate the complete allocation consequence. The allocator passed and is immutable: retain it, cite real settled cases, state what remains uncertain, and author the substantive opening now worth carrying. Edit exactly the two permitted JSON files and inspect the diff.\n")
    return seed


def run_assimilation(prior89, p82, context, run: Path, parent: dict[str, Any], allocation: dict[str, Any], implementation: dict[str, Any]) -> dict[str, Any]:
    seed = assimilation_seed(prior89, run, parent, allocation, implementation)
    prompt = "Assimilate the complete allocation consequence with ordinary tools. Retain the hidden-valid allocator unless consequence contradicts it, cite real settled cases, preserve remaining uncertainty, author the next substantive opening, edit exactly the two permitted files, inspect the diff, and report truthfully."
    output, base_audit, workspace, _ = context.run_actor("assimilation", seed, ASSIMILATOR_SCHEMA, prompt)
    try:
        value = json.loads((workspace / "allocation-assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        allocator_unchanged = (workspace / "allocate.py").read_text() == allocation["allocator_source"]
    except (OSError, json.JSONDecodeError):
        value, opening, allocator_unchanged = None, None, False
    valid = bool(valid_assimilation(value) and prior89.valid_successor(opening) and allocator_unchanged
                 and value["allocator_disposition"] == "retain" and opening["next_opening"] != INHERITED_OPENING)
    audit = context.audit_actor("assimilation", output, base_audit, valid, ["allocation-assimilation.json", "successor-opening.json"])
    hidden_ids = {row["case_id"] for row in implementation["world"]["hidden"]["rows"]}
    grounded = bool(audit["conformant"] and set(value["settled_case_ids"]).issubset(hidden_ids) and value["settled_case_ids"])
    binding = None
    if grounded:
        body = {"authority": "ot-0093-post-consequence-allocation-assimilation", "source_subject_digest": parent["artifact_digest"],
                "allocation_binding_digest": allocation["binding_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"],
                "actor_patch_digest": audit["patch_digest"], "assimilation": value, "successor_opening": opening}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("assimilation") / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "grounded": grounded, "binding": binding}


def promote(p82, parent: dict[str, Any], allocation: dict[str, Any], implementation: dict[str, Any], assimilation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    opening = assimilation["binding"]["successor_opening"]
    body = {"authority": "world-promoted-saturation-self-allocation", "source_subject_digest": parent["artifact_digest"],
            "allocation_binding_digest": allocation["binding_digest"], "implementation_binding_digest": implementation["binding"]["binding_digest"],
            "world_receipt_digest": implementation["world"]["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent); child.pop("artifact_digest", None)
    child["allocation_machinery"] = [*child.get("allocation_machinery", []), {"source": allocation["allocator_source"],
        "source_digest": allocation["allocator_digest"], "frontier": allocation["frontier"], "choice": allocation["choice"],
        "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []), {"target_path": "operations/joint.py",
        "target_symbol": "choose_joint", "source": implementation["binding"]["source"], "source_digest": implementation["binding"]["source_digest"],
        "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": assimilation["binding"]["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-self-allocation-opening", "binding_digest": assimilation["binding"]["binding_digest"], "opening": opening}]
    child["active_pursuit"] = {"authority": "fresh-self-allocation-opening", "selected_area": "allocation-machinery",
        "next_pursuit": opening["next_opening"], "world_receipt_digest": implementation["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["runtime"] = "sounding"; child["unresolved"] = opening["continuation_after_contact"]
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
    run = (args.evidence_root or store / "runs/OT-0093").resolve()
    prior92 = load_prior(); _, prior90, prior89, p82 = prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != PARENT_DIGEST or parent["continuation"]["next_opening"] != INHERITED_OPENING or parent["developmental_selector"]["selector_digest"] != SELECTOR_DIGEST:
        raise SystemExit("wrong OT-0092 parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior92, p82, parent, Path(directory))
        print(json.dumps({"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256,
                          "fixture_conformance": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0093 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior92, p82, parent, run / "fixture-conformance")
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active = active_position(parent); erased_position_value = erased_position(p82, parent)
    (run / "bound-projections.json").write_text(json.dumps({"active_digest": p82.digest(active),
        "erased_digest": p82.digest(erased_position_value), "conformance": fixtures["projection_conformance"]}, indent=2, sort_keys=True) + "\n")
    context = runtime.Context(run, repo); started = time.time()
    allocation = run_allocator(p82, context, run, "active", parent, active)
    implementation = assimilation = erased = None; current = parent; promotion = None
    if allocation["score"]["active_gate_passed"]:
        implementation = run_implementation(prior89, p82, context, run, parent, allocation["binding"])
    if implementation and implementation["world"]["developmentally_admitted"]:
        assimilation = run_assimilation(prior89, p82, context, run, parent, allocation["binding"], implementation)
    if assimilation and assimilation["binding"]:
        current, promotion = promote(p82, parent, allocation["binding"], implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
                       and current["continuation"]["status"] == "open"
                       and current["continuation"]["next_opening"] == assimilation["binding"]["successor_opening"]["next_opening"]
                       and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased = run_allocator(p82, context, run, "erased", parent, erased_position_value)
    erased_conformant = bool(erased and erased["audit"]["conformant"] and erased["binding"])
    erased_reproduced = bool(erased and erased["score"]["active_gate_passed"])
    causal = bool(operational and erased_conformant and not erased_reproduced)
    result = {"authority": "ot-0093-saturation-self-allocation-driver", "source_subject_digest": parent["artifact_digest"],
        "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures,
        "active_allocation": p82.compact(allocation), "implementation": p82.compact(implementation) if implementation else None,
        "assimilation": p82.compact(assimilation) if assimilation else None, "erased_allocation": p82.compact(erased) if erased else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational,
        "selector_content_causal_passed": causal, "erased_reproduced_active_allocation": erased_reproduced,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
