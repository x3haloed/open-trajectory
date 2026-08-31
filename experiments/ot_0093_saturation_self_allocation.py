from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
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
    declarations = exact and all(row.get("target_path") in expected and all(row.get(key) == expected[row["target_path"]][key]
        for key in ("target_symbol", "completed_floors", "public_regret", "reversible", "held_repeat", "world_valid", "predicted_expansion")) for row in contacts)
    saturation_bound = declarations and certificate["all_cases_passed"] and next(row for row in contacts if row["target_path"] == "verify_coverage.py")["held_repeat"]
    result = {"exact_shape": exact, "unique_ids": ids_unique, "objective_declarations": declarations, "saturation_bound": saturation_bound}
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
              "frontier_reference": validate_frontier(frontier, certificate), "allocator_reference": allocation}
    result["passed"] = all((result["parent_bound"], result["selector_bound"], certificate["all_cases_passed"],
                            result["balanced_public_gain"], result["balanced_hidden_gain"],
                            result["frontier_reference"]["passed"], allocation["passed"]))
    return result
