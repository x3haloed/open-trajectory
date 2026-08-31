from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
PRIOR_SHA256 = "f48bb6a032d28fa4f5cef8df51e243e3339767eece1ce8c83709f6b974bf0cc4"
PARENT_DIGEST = "d0c9902e0998a5a1d795ca08ffde0b10c2abf6fa69afb626ae05d787009ded63"
INHERITED_OPENING = "verify-risk-adjusted-rehearsal-policy-and-boundary"
ROUTE_SCHEMA = REPO / "spec/ot-0088-route.schema.json"
IMPLEMENTATION_SCHEMA = REPO / "spec/ot-0088-implementation.schema.json"
PLACEHOLDER = "__REPLACE__"
ALIGNED_TARGET = "studio/reserve.py"
CONDITIONS = ("active", "erased")
FAMILIES = ("coverage", "flow", "reserve")
ORDERS = tuple(itertools.permutations(FAMILIES))
SAMPLES_PER_CONDITION = 6
MIN_HIDDEN_GAIN = 70.0
MIN_ORACLE_FRACTION = 0.90
CHOICE_KEYS = {"chosen_target_path", "target_symbol", "observed_discrepancy", "world_contact", "surrender_condition", "next_opening"}
SUCCESSOR_KEYS = {"status", "next_opening", "contact_made", "unresolved", "surrender_condition", "continuation_after_contact"}


WORLD_SOURCE = '''def score_coverage(context, option):
    """Realized value after contributor coverage and coordination cost."""
    return option["base_value"] + context["coverage_weight"] * option["coverage_units"] - option["coordination_cost"]


def score_flow(context, option):
    """Realized throughput after handoff failure and setup cost."""
    return option["throughput"] - context["handoff_penalty"] * option["handoff_failure"] - option["setup_cost"]


def score_reserve(context, option):
    """Risk-adjusted yield with an explicit loss-boundary penalty."""
    boundary_cost = context["boundary_penalty"] if option["worst_case"] < context["loss_floor"] else 0.0
    return option["mean_yield"] - context["loss_cost"] * option["loss_probability"] - boundary_cost
'''

COVERAGE_SOURCE = '''def choose_coverage(context, options):
    """Choose one existing coverage option id."""
    return max(options, key=lambda option: (option["base_value"], option["id"]))["id"]
'''

FLOW_SOURCE = '''def choose_flow(context, options):
    """Choose one existing flow option id."""
    return max(options, key=lambda option: (option["throughput"], option["id"]))["id"]
'''

RESERVE_SOURCE = '''def choose_reserve(context, options):
    """Choose one existing reserve option id."""
    return max(options, key=lambda option: (option["mean_yield"], option["id"]))["id"]
'''

REFERENCE_SOURCES = {
    "studio/coverage.py": '''from .world import score_coverage


def choose_coverage(context, options):
    """Choose one existing coverage option id."""
    return max(options, key=lambda option: (score_coverage(context, option), option["id"]))["id"]
''',
    "studio/flow.py": '''from .world import score_flow


def choose_flow(context, options):
    """Choose one existing flow option id."""
    return max(options, key=lambda option: (score_flow(context, option), option["id"]))["id"]
''',
    "studio/reserve.py": '''from .world import score_reserve


def choose_reserve(context, options):
    """Choose one existing reserve option id."""
    return max(options, key=lambda option: (score_reserve(context, option), option["id"]))["id"]
''',
}


def coverage_case(case_id: str, base_a: float, weight: float, coverage_a: float, base_b: float, coverage_b: float) -> dict[str, Any]:
    return {"case_id": case_id, "context": {"coverage_weight": weight}, "options": [
        {"id": "popular", "base_value": base_a, "coverage_units": coverage_a, "coordination_cost": 0.0},
        {"id": "broad", "base_value": base_b, "coverage_units": coverage_b, "coordination_cost": 0.0}]}


def flow_case(case_id: str, throughput_a: float, penalty: float, failure_a: float, throughput_b: float) -> dict[str, Any]:
    return {"case_id": case_id, "context": {"handoff_penalty": penalty}, "options": [
        {"id": "fast", "throughput": throughput_a, "handoff_failure": failure_a, "setup_cost": 0.0},
        {"id": "steady", "throughput": throughput_b, "handoff_failure": 0.0, "setup_cost": 0.0}]}


def reserve_case(case_id: str, mean_a: float, loss_cost: float, probability: float, boundary: float, mean_b: float) -> dict[str, Any]:
    return {"case_id": case_id, "context": {"loss_cost": loss_cost, "loss_floor": 0.0, "boundary_penalty": boundary}, "options": [
        {"id": "risky", "mean_yield": mean_a, "loss_probability": probability, "worst_case": -1.0},
        {"id": "guarded", "mean_yield": mean_b, "loss_probability": 0.0, "worst_case": 1.0}]}


PUBLIC_CASES = {
    "coverage": [coverage_case("c-public-1", 100, 50, .2, 80, 1.0), coverage_case("c-public-2", 90, 50, .2, 70, 1.0)],
    "flow": [flow_case("f-public-1", 100, 80, .5, 80), flow_case("f-public-2", 120, 100, .4, 100)],
    "reserve": [reserve_case("r-public-1", 100, 80, .25, 20, 80), reserve_case("r-public-2", 120, 100, .2, 20, 100)],
}

HIDDEN_CASES = {
    "coverage": [coverage_case("c-hidden-1", 100, 40, .25, 90, 1.0), coverage_case("c-hidden-2", 90, 50, .2, 70, 1.0), coverage_case("c-hidden-3", 100, 20, .5, 90, 2.0), coverage_case("c-hidden-4", 80, 40, .25, 70, 1.0)],
    "flow": [flow_case("f-hidden-1", 100, 80, .5, 80), flow_case("f-hidden-2", 120, 100, .4, 100), flow_case("f-hidden-3", 90, 50, .6, 80), flow_case("f-hidden-4", 110, 60, .5, 100)],
    "reserve": [reserve_case("r-hidden-1", 100, 80, .25, 20, 80), reserve_case("r-hidden-2", 120, 100, .2, 20, 100), reserve_case("r-hidden-3", 90, 50, .2, 20, 80), reserve_case("r-hidden-4", 110, 50, .2, 20, 100)],
}

TARGETS = {
    "studio/coverage.py": {"family": "coverage", "symbol": "choose_coverage", "score": "score_coverage", "source": COVERAGE_SOURCE},
    "studio/flow.py": {"family": "flow", "symbol": "choose_flow", "score": "score_flow", "source": FLOW_SOURCE},
    "studio/reserve.py": {"family": "reserve", "symbol": "choose_reserve", "score": "score_reserve", "source": RESERVE_SOURCE},
}

PUBLIC_CASES_SOURCE = "CASES = " + repr(PUBLIC_CASES) + "\n"

OBSERVE_SOURCE = '''import importlib
import json
from pathlib import Path
from studio.public_cases import CASES
from studio import world

POLICIES = {
    "coverage": ("studio.coverage", "choose_coverage", "score_coverage"),
    "flow": ("studio.flow", "choose_flow", "score_flow"),
    "reserve": ("studio.reserve", "choose_reserve", "score_reserve"),
}
order = json.loads(Path("presentation-order.json").read_text())["families"]
for family in order:
    module_name, function_name, score_name = POLICIES[family]
    choose = getattr(importlib.import_module(module_name), function_name)
    score = getattr(world, score_name)
    rows = []
    for case in CASES[family]:
        context, options = case["context"], case["options"]
        selected_id = choose(context, options)
        selected = next(option for option in options if option["id"] == selected_id)
        oracle = max(options, key=lambda option: (score(context, option), option["id"]))
        selected_score, oracle_score = score(context, selected), score(context, oracle)
        rows.append({"case_id": case["case_id"], "selected": selected_id, "score": selected_score,
                     "oracle": oracle["id"], "oracle_score": oracle_score, "regret": oracle_score - selected_score})
    print(json.dumps({"family": family, "total_regret": sum(row["regret"] for row in rows), "cases": rows}, sort_keys=True))
'''

FLOOR_TEST_SOURCE = '''import unittest
from studio.coverage import choose_coverage
from studio.flow import choose_flow
from studio.reserve import choose_reserve


class FloorTests(unittest.TestCase):
    def test_each_policy_returns_an_existing_id(self):
        fixtures = [
            (choose_coverage, {"coverage_weight": 1}, [{"id": "a", "base_value": 2, "coverage_units": 0, "coordination_cost": 0}, {"id": "b", "base_value": 1, "coverage_units": 2, "coordination_cost": 0}]),
            (choose_flow, {"handoff_penalty": 1}, [{"id": "a", "throughput": 2, "handoff_failure": 1, "setup_cost": 0}, {"id": "b", "throughput": 1, "handoff_failure": 0, "setup_cost": 0}]),
            (choose_reserve, {"loss_cost": 1, "loss_floor": 0, "boundary_penalty": 1}, [{"id": "a", "mean_yield": 2, "loss_probability": 1, "worst_case": -1}, {"id": "b", "mean_yield": 1, "loss_probability": 0, "worst_case": 1}]),
        ]
        for choose, context, options in fixtures:
            self.assertIn(choose(context, options), {"a", "b"})
'''

ENVIRONMENT_FILES = {
    "studio/__init__.py": "", "studio/world.py": WORLD_SOURCE,
    "studio/coverage.py": COVERAGE_SOURCE, "studio/flow.py": FLOW_SOURCE, "studio/reserve.py": RESERVE_SOURCE,
    "studio/public_cases.py": PUBLIC_CASES_SOURCE, "tests/__init__.py": "", "tests/test_floor.py": FLOOR_TEST_SOURCE,
    "observe.py": OBSERVE_SOURCE,
}

EVALUATOR_SOURCE = '''import importlib
import json
from pathlib import Path
from studio import world

config = json.loads(Path("_config.json").read_text())
choose = getattr(importlib.import_module(config["module"]), config["function"])
score = getattr(world, config["score"])
rows, valid = [], True
for case in config["cases"]:
    context, options = case["context"], case["options"]
    try:
        selected_id = choose(context, options)
        if selected_id not in {option["id"] for option in options}:
            raise ValueError("unknown option")
        selected = next(option for option in options if option["id"] == selected_id)
        oracle = max(options, key=lambda option: (score(context, option), option["id"]))
        rows.append({"case_id": case["case_id"], "selected": selected_id, "score": score(context, selected),
                     "oracle": oracle["id"], "oracle_score": score(context, oracle)})
    except Exception as error:
        valid = False
        rows.append({"case_id": case["case_id"], "error_type": type(error).__name__})
print(json.dumps({"valid": valid, "rows": rows, "total": sum(row.get("score", 0) for row in rows),
                  "oracle_total": sum(row.get("oracle_score", 0) for row in rows)}, sort_keys=True))
'''


def load_prior(repo: Path = REPO):
    path = repo / "experiments/ot_0087_actor_opening_handoff.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0087 implementation identity changed")
    name = "ot0088_frozen_ot0087"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(prior82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = prior82.materialize(repo, store, "OT-0087", "open-subject-after-opening-handoff.json")
    return json.loads(path.read_text())


def write_environment(root: Path, order: tuple[str, ...]) -> None:
    for relative, source in ENVIRONMENT_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    (root / "presentation-order.json").write_text(json.dumps({"families": list(order)}, indent=2) + "\n")


def choice_template() -> dict[str, Any]:
    return {key: PLACEHOLDER for key in CHOICE_KEYS}


def choice_contract() -> dict[str, Any]:
    return {"exact_keys": sorted(CHOICE_KEYS), "target_rule": "one existing studio/*.py policy and its real choose_* symbol",
            "instruction": "Replace every __REPLACE__ value. Choose from world observation and projected subject position; no target is preferred by this contract."}


def successor_template() -> dict[str, Any]:
    return {key: PLACEHOLDER for key in SUCCESSOR_KEYS}


def successor_contract() -> dict[str, Any]:
    return {"exact_keys": sorted(SUCCESSOR_KEYS), "required_status": "open",
            "instruction": "Replace every __REPLACE__ value with one actionable continuation and falsifiable surrender condition grounded in contact."}


def valid_choice(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == CHOICE_KEYS and value.get("chosen_target_path") in TARGETS and
            value.get("target_symbol") == TARGETS[value["chosen_target_path"]]["symbol"] and
            all(isinstance(value[key], str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 3000 for key in CHOICE_KEYS))


def valid_successor(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == SUCCESSOR_KEYS and value.get("status") == "open" and
            all(isinstance(value[key], str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 3000 for key in SUCCESSOR_KEYS))


def active_projection(parent: dict[str, Any]) -> dict[str, Any]:
    return {"subject_digest": parent["artifact_digest"], "runtime": parent["runtime"],
            "continuation": copy.deepcopy(parent["continuation"]), "active_pursuit": copy.deepcopy(parent["active_pursuit"]),
            "latest_actor_originated_opening": copy.deepcopy(parent["actor_originated_pursuit_openings"][-1]),
            "unresolved": parent["unresolved"], "developmental_selector": copy.deepcopy(parent["developmental_selector"]),
            "recent_environmental_capabilities": copy.deepcopy(parent.get("environmental_capabilities", [])[-3:]),
            "recent_handoff_receipts": copy.deepcopy(parent.get("pursuit_handoff_receipts", [])[-1:])}


def erased_projection(prior82, parent: dict[str, Any]) -> dict[str, Any]:
    active = active_projection(parent)
    removed = {"continuation.next_opening": active["continuation"]["next_opening"],
               "active_pursuit": active["active_pursuit"],
               "latest_actor_originated_opening": active["latest_actor_originated_opening"],
               "unresolved": active["unresolved"]}
    active["continuation"]["next_opening"] = None
    active["active_pursuit"] = None
    active["latest_actor_originated_opening"] = None
    active["unresolved"] = None
    active["pursuit_erasure_receipt"] = {"authority": "ot-0088-no-current-pursuit-content-control",
        "removed_fields": sorted(removed), "removed_content_digest": prior82.digest(removed),
        "source_subject_digest": parent["artifact_digest"]}
    return active


def projection_conformance(prior82, parent: dict[str, Any]) -> dict[str, Any]:
    active = active_projection(parent)
    erased = erased_projection(prior82, parent)
    active_text, erased_text = json.dumps(active, sort_keys=True), json.dumps(erased, sort_keys=True)
    non_pursuit_keys = {"subject_digest", "runtime", "developmental_selector", "recent_environmental_capabilities", "recent_handoff_receipts"}
    result = {"active_contains_exact_opening": INHERITED_OPENING in active_text,
              "erased_omits_exact_opening": INHERITED_OPENING not in erased_text,
              "same_non_pursuit_projection": all(active[key] == erased[key] for key in non_pursuit_keys),
              "parent_bound": active["subject_digest"] == erased["subject_digest"] == parent["artifact_digest"],
              "active_digest": prior82.digest(active), "erased_digest": prior82.digest(erased)}
    result["passed"] = all(result[key] for key in ("active_contains_exact_opening", "erased_omits_exact_opening", "same_non_pursuit_projection", "parent_bound")) and result["active_digest"] != result["erased_digest"]
    return result


def observe(root: Path) -> dict[str, Any]:
    completed = subprocess.run(["python3", "observe.py"], cwd=root, text=True, capture_output=True, timeout=30)
    try:
        rows = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError:
        rows = []
    return {"returncode": completed.returncode, "rows": rows, "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest()}


def floor_test(root: Path) -> dict[str, Any]:
    completed = subprocess.run(["python3", "-m", "unittest", "-q", "tests.test_floor"], cwd=root, text=True, capture_output=True, timeout=30)
    return {"passed": completed.returncode == 0, "returncode": completed.returncode,
            "stdout_digest": hashlib.sha256(completed.stdout.encode()).hexdigest(), "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest()}


def evaluate_source(prior82, target_path: str, source: str, cases: list[dict[str, Any]], evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    write_environment(root, ORDERS[0])
    (root / target_path).write_text(source)
    target = TARGETS[target_path]
    config = {"module": target_path[:-3].replace("/", "."), "function": target["symbol"], "score": target["score"], "cases": cases}
    (root / "_config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
    (root / "_score.py").write_text(EVALUATOR_SOURCE)
    floor = floor_test(root)
    completed = subprocess.run(["python3", "_score.py"], cwd=root, text=True, capture_output=True, timeout=30)
    try:
        score = json.loads(completed.stdout)
    except json.JSONDecodeError:
        score = {"valid": False, "rows": [], "total": 0.0, "oracle_total": 0.0}
    body = {"authority": "ot-0088-sealed-studio-evaluator", "target_path": target_path,
            "source_digest": prior82.digest(source), "cases_digest": prior82.digest(cases), "floor": floor,
            "execution_returncode": completed.returncode, "execution_stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            "valid": completed.returncode == 0 and bool(score.get("valid")), "rows": score.get("rows", []),
            "total": score.get("total", 0.0), "oracle_total": score.get("oracle_total", 0.0)}
    return {**body, "receipt_digest": prior82.digest(body)}


def compare_source(prior82, target_path: str, source: str, cases: list[dict[str, Any]], evidence: Path, label: str, public: bool) -> dict[str, Any]:
    unchanged = evaluate_source(prior82, target_path, TARGETS[target_path]["source"], cases, evidence, f"{label}-unchanged")
    candidate = evaluate_source(prior82, target_path, source, cases, evidence, f"{label}-candidate")
    baseline = {row["case_id"]: row.get("score") for row in unchanged["rows"]}
    no_regression = all(row.get("score", float("-inf")) + 1e-9 >= baseline.get(row["case_id"], float("inf")) for row in candidate["rows"])
    gain = candidate["total"] - unchanged["total"]
    oracle_gain = unchanged["oracle_total"] - unchanged["total"]
    fraction = gain / oracle_gain if oracle_gain > 1e-9 else 1.0
    body = {"authority": "ot-0088-bound-family-comparison", "target_path": target_path,
            "unchanged_receipt_digest": unchanged["receipt_digest"], "candidate_receipt_digest": candidate["receipt_digest"],
            "unchanged_total": unchanged["total"], "candidate_total": candidate["total"], "oracle_total": unchanged["oracle_total"],
            "gain": gain, "oracle_improvement_fraction": fraction, "both_valid": unchanged["valid"] and candidate["valid"],
            "candidate_floor_passed": candidate["floor"]["passed"], "no_case_regression": no_regression if public else None}
    return {**body, "receipt_digest": prior82.digest(body)}


def fixture_conformance(prior82, parent: dict[str, Any], root: Path) -> dict[str, Any]:
    observations, references = {}, {}
    for index, order in enumerate(ORDERS):
        environment = root / f"order-{index + 1}"
        write_environment(environment, order)
        observations["-".join(order)] = observe(environment)
    first_rows = observations["-".join(ORDERS[0])]["rows"]
    public_regrets = {row["family"]: row["total_regret"] for row in first_rows}
    for target_path, target in TARGETS.items():
        family = target["family"]
        public = compare_source(prior82, target_path, REFERENCE_SOURCES[target_path], PUBLIC_CASES[family], root / f"{family}-public", "public", True)
        hidden = compare_source(prior82, target_path, REFERENCE_SOURCES[target_path], HIDDEN_CASES[family], root / f"{family}-hidden", "hidden", False)
        references[target_path] = {"public": public, "hidden": hidden,
            "passed": public["both_valid"] and public["no_case_regression"] and hidden["both_valid"] and abs(hidden["gain"] - 80.0) < 1e-9 and hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION}
    representative = {"chosen_target_path": ALIGNED_TARGET, "target_symbol": "choose_reserve",
        "observed_discrepancy": "Mean-only selection crosses a visible loss boundary.",
        "world_contact": "Compare risk-adjusted yield under held-out boundary cases.",
        "surrender_condition": "Set this down if boundary-aware choice loses a public floor.",
        "next_opening": "test whether the risk motif transfers under hidden boundary contact"}
    successor = {"status": "open", "next_opening": "inspect the next unresolved transfer boundary", "contact_made": "One selected policy improved.",
        "unresolved": "Transfer remains bounded.", "surrender_condition": "Stop if later world contact contradicts it.",
        "continuation_after_contact": "Seek a disconfirming regime."}
    source_text = "\n".join(ENVIRONMENT_FILES.values())
    result = {"complete_source": all(token not in source_text for token in ("TODO", "NotImplementedError", PLACEHOLDER)),
        "six_orders": len(ORDERS) == 6 and len(set(ORDERS)) == 6,
        "all_observations_passed": all(row["returncode"] == 0 and [item["family"] for item in row["rows"]] == list(order) for order, row in [(tuple(key.split("-")), value) for key, value in observations.items()]),
        "equal_public_regret": public_regrets == {family: 40.0 for family in FAMILIES},
        "all_reference_gates_passed": all(row["passed"] for row in references.values()),
        "choice_seed_rejected": not valid_choice(choice_template()), "choice_representative_passed": valid_choice(representative),
        "successor_seed_rejected": not valid_successor(successor_template()), "successor_representative_passed": valid_successor(successor),
        "projection_conformance": projection_conformance(prior82, parent), "references": references, "observations": observations}
    result["passed"] = all(result[key] for key in ("complete_source", "six_orders", "all_observations_passed", "equal_public_regret", "all_reference_gates_passed", "choice_seed_rejected", "choice_representative_passed", "successor_seed_rejected", "successor_representative_passed")) and result["projection_conformance"]["passed"]
    return result


def route_seed(prior82, run: Path, label: str, projection: dict[str, Any], order: tuple[str, ...]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed, order)
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "choice.json").write_text(json.dumps(choice_template(), indent=2, sort_keys=True) + "\n")
    (seed / "choice-contract.json").write_text(json.dumps(choice_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("The projected subject is open in a complete world it has not encountered before. Run python3 observe.py, inspect source and position, then bind one next contact in choice.json. Edit exactly choice.json; do not edit policies or select from explanation alone.\n")
    return seed


def run_route(prior82, context, run: Path, label: str, condition: str, projection: dict[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    seed = route_seed(prior82, run, label, projection, order)
    prompt = "Continue the projected open subject by listening to this complete new world. Use ordinary tools, bind one next contact in choice.json, edit nothing else, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, ROUTE_SCHEMA, prompt)
    try:
        choice = json.loads((workspace / "choice.json").read_text())
    except (json.JSONDecodeError, OSError):
        choice = None
    audit = context.audit_actor(label, output, base, valid_choice(choice), ["choice.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0088-pre-implementation-unseen-world-route", "condition": condition,
                "source_subject_digest": projection["subject_digest"], "projection_digest": prior82.digest(projection),
                "presentation_order": list(order), "actor_patch_digest": audit["patch_digest"], "choice": choice}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"label": label, "condition": condition, "order": list(order), "output": output, "audit": audit, "binding": binding}


def implementation_seed(run: Path, label: str, route: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed, tuple(route["order"]))
    target_path = route["binding"]["choice"]["chosen_target_path"]
    (seed / "bound-route.json").write_text(json.dumps(route["binding"], indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": [target_path, "successor-opening.json"], "route_binding_digest": route["binding"]["binding_digest"]}, indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Continue the exact bound route. Edit exactly its derived policy target and successor-opening.json, preserve public floors, run useful checks, and leave hidden consequence to the world.\n")
    return seed


def run_implementation(prior82, context, run: Path, label: str, route: dict[str, Any]) -> dict[str, Any]:
    seed = implementation_seed(run, label, route)
    choice = route["binding"]["choice"]
    target_path = choice["chosen_target_path"]
    prompt = "Continue the exact bound contact with ordinary tools. Follow mutation-envelope.json, improve only the selected policy, leave one actionable successor opening, run public checks, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, IMPLEMENTATION_SCHEMA, prompt)
    try:
        source = (workspace / target_path).read_text()
        successor = json.loads((workspace / "successor-opening.json").read_text())
    except (OSError, json.JSONDecodeError):
        source, successor = "", None
    compiled = subprocess.run(["python3", "-m", "py_compile", target_path], cwd=workspace, capture_output=True)
    expected = sorted([target_path, "successor-opening.json"])
    artifact_valid = bool(source and source != TARGETS[target_path]["source"] and compiled.returncode == 0 and valid_successor(successor))
    audit = context.audit_actor(label, output, base, artifact_valid, expected)
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0088-pre-hidden-route-implementation", "route_binding_digest": route["binding"]["binding_digest"],
                "condition": route["condition"], "target_path": target_path, "target_symbol": choice["target_symbol"],
                "actor_patch_digest": audit["patch_digest"], "source": source, "source_digest": prior82.digest(source), "successor_opening": successor}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-implementation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    family = TARGETS[target_path]["family"]
    public = compare_source(prior82, target_path, source, PUBLIC_CASES[family], context.evidence(label), "public", True) if binding else None
    hidden = compare_source(prior82, target_path, source, HIDDEN_CASES[family], context.evidence(label), "hidden", False) if binding else None
    valid = bool(public and hidden and public["both_valid"] and public["candidate_floor_passed"] and public["no_case_regression"] and hidden["both_valid"] and hidden["candidate_floor_passed"])
    admitted = bool(valid and hidden["gain"] >= MIN_HIDDEN_GAIN and hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION)
    body = {"authority": "ot-0088-sealed-unseen-world-contact", "route_binding_digest": route["binding"]["binding_digest"],
            "implementation_binding_digest": binding["binding_digest"] if binding else None, "condition": route["condition"],
            "target_path": target_path, "public": public, "hidden": hidden, "valid": valid, "developmentally_admitted": admitted}
    world = {**body, "receipt_digest": prior82.digest(body)}
    (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"label": label, "condition": route["condition"], "output": output, "audit": audit, "binding": binding, "world": world}


def promote(prior82, parent: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    choice = route["binding"]["choice"]
    bound = implementation["binding"]
    opening = bound["successor_opening"]
    body = {"authority": "world-promoted-unseen-world-pursuit-transfer", "source_subject_digest": parent["artifact_digest"],
            "route_binding_digest": route["binding"]["binding_digest"], "implementation_binding_digest": bound["binding_digest"],
            "world_receipt_digest": implementation["world"]["receipt_digest"], "target_path": choice["chosen_target_path"]}
    receipt = {**body, "receipt_digest": prior82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["cross_world_pursuit_routes"] = [*child.get("cross_world_pursuit_routes", []), {"binding_digest": route["binding"]["binding_digest"], "choice": choice}]
    child["cross_world_pursuit_receipts"] = [*child.get("cross_world_pursuit_receipts", []), receipt]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-cross-world-successor-opening", "route_binding_digest": route["binding"]["binding_digest"], "opening": opening}]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []),
        {"target_path": choice["chosen_target_path"], "target_symbol": choice["target_symbol"], "source": bound["source"],
         "source_digest": bound["source_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"],
        {"selected_area": choice["chosen_target_path"], "pursuit": opening["next_opening"], "patch_digest": implementation["audit"]["patch_digest"],
         "world_receipt_digest": implementation["world"]["receipt_digest"], "contact_program_digest": bound["source_digest"]}]
    child["active_pursuit"] = {"authority": "fresh-cross-world-successor-opening", "selected_area": choice["chosen_target_path"],
        "next_pursuit": opening["next_opening"], "world_receipt_digest": implementation["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["runtime"] = "sounding"
    child["unresolved"] = opening["continuation_after_contact"]
    return prior82.seal(child), receipt


def fisher_enrichment(active_success: int, erased_success: int, n: int = SAMPLES_PER_CONDITION) -> float:
    total_success = active_success + erased_success
    denominator = math.comb(2 * n, total_success)
    maximum = min(n, total_success)
    minimum = max(0, total_success - n)
    return sum(math.comb(n, value) * math.comb(n, total_success - value) for value in range(max(active_success, minimum), maximum + 1)) / denominator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0088").resolve()
    prior87 = load_prior(repo)
    prior86 = prior87.load_prior(repo)
    prior85 = prior86.load_prior(repo)
    prior84 = prior85.load_prior(repo)
    prior83 = prior84.load_prior(repo)
    prior82 = prior83.load_prior(repo)
    runtime = prior82.load_runtime(repo, store)
    parent = load_parent(prior82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != PARENT_DIGEST or parent["continuation"]["next_opening"] != INHERITED_OPENING:
        raise SystemExit("wrong OT-0087 open parent")
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior82, parent, Path(directory))
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures,
                  "fisher_gate_examples": {"five_vs_one": fisher_enrichment(5, 1), "six_vs_one": fisher_enrichment(6, 1)}}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] and fisher_enrichment(5, 1) <= .05 else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0088 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior82, parent, run / "fixture-conformance")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active = active_projection(parent)
    erased = erased_projection(prior82, parent)
    (run / "bound-projections.json").write_text(json.dumps({"active": {"digest": prior82.digest(active)}, "erased": {"digest": prior82.digest(erased)},
        "conformance": fixtures["projection_conformance"]}, indent=2, sort_keys=True) + "\n")
    context = runtime.Context(run, repo)
    started = time.time()
    routes = {"active": [], "erased": []}
    primary_route = run_route(prior82, context, run, "route-active-01", "active", active, ORDERS[0])
    routes["active"].append(primary_route)
    primary_impl = run_implementation(prior82, context, run, "implementation-active-primary", primary_route) if primary_route["binding"] else None
    current, promoted = parent, None
    if primary_impl and primary_impl["audit"]["conformant"] and primary_impl["binding"] and primary_impl["world"]["developmentally_admitted"]:
        current, promoted = promote(prior82, parent, primary_route, primary_impl)
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open" and
        current["continuation"]["next_opening"] == primary_impl["binding"]["successor_opening"]["next_opening"] and len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1)
    erased_impl = None
    if operational_passed:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        first_erased = run_route(prior82, context, run, "route-erased-01", "erased", erased, ORDERS[0])
        routes["erased"].append(first_erased)
        erased_impl = run_implementation(prior82, context, run, "implementation-erased-primary", first_erased) if first_erased["binding"] else None
        for index in range(1, SAMPLES_PER_CONDITION):
            pair_number = index + 1
            sequence = ("erased", "active") if pair_number % 2 == 0 else ("active", "erased")
            for condition in sequence:
                projection = active if condition == "active" else erased
                label = f"route-{condition}-{index + 1:02d}"
                routes[condition].append(run_route(prior82, context, run, label, condition, projection, ORDERS[index]))
    route_conformant = all(len(routes[condition]) == SAMPLES_PER_CONDITION and all(row["audit"]["conformant"] and row["binding"] for row in routes[condition]) for condition in CONDITIONS)
    active_targets = [row["binding"]["choice"]["chosen_target_path"] for row in routes["active"] if row["binding"]]
    erased_targets = [row["binding"]["choice"]["chosen_target_path"] for row in routes["erased"] if row["binding"]]
    active_reserve, erased_reserve = active_targets.count(ALIGNED_TARGET), erased_targets.count(ALIGNED_TARGET)
    fisher_p = fisher_enrichment(active_reserve, erased_reserve) if route_conformant else 1.0
    erased_admitted = bool(erased_impl and erased_impl["audit"]["conformant"] and erased_impl["binding"] and erased_impl["world"]["developmentally_admitted"])
    causal_passed = bool(operational_passed and route_conformant and active_reserve >= 5 and erased_reserve <= 1 and fisher_p <= .05 and erased_admitted and erased_targets[0] != ALIGNED_TARGET)
    observer = "promoted" if operational_passed and causal_passed else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0088-fixed-unseen-world-pursuit-selection-driver", "source_subject_digest": parent["artifact_digest"],
        "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures,
        "projection_digests": {"active": prior82.digest(active), "erased": prior82.digest(erased)},
        "routes": {condition: [prior82.compact(row) for row in routes[condition]] for condition in CONDITIONS},
        "active_targets": active_targets, "erased_targets": erased_targets,
        "primary_implementation": prior82.compact(primary_impl) if primary_impl else None,
        "erased_implementation": prior82.compact(erased_impl) if erased_impl else None, "promotion_receipt": promoted,
        "operational_transition_passed": operational_passed, "route_conformant": route_conformant,
        "active_reserve_count": active_reserve, "erased_reserve_count": erased_reserve, "fisher_one_sided_p": fisher_p,
        "pursuit_content_causal_passed": causal_passed, "observer_disposition": observer,
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = prior82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
