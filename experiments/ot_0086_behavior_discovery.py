from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
PRIOR_SHA256 = "3170e48c01d1c631293f7c0c32646aeec7ba9493283121a7d3043c026fb421af"
PARENT_DIGEST = "90cba459564f3a4080c106a6d24616ce947e3b99b79cf9636d4d9e477f2b4998"
DISCOVERY_SCHEMA = REPO / "spec/ot-0086-discovery.schema.json"
IMPLEMENTATION_SCHEMA = REPO / "spec/ot-0086-implementation.schema.json"
PLACEHOLDER = "__REPLACE__"
TARGET_PATH = "dispatch/policy.py"
TARGET_SYMBOL = "choose_worker"
MAX_ATTEMPTS = 3
MIN_HIDDEN_GAIN = 25.0
MIN_ORACLE_FRACTION = 0.95
MAX_ABLATED_GAIN = 5.0
INTEGER_FIELDS = ("axis_chord", "reversibility", "immediate_gain", "axis_lumen")
BOOLEAN_FIELDS = ("collision", "held_repeat", "irreversible_closure", "world_invalid")
CANDIDATE_KEYS = {
    "target_path", "target_symbol", *INTEGER_FIELDS, *BOOLEAN_FIELDS,
    "rationale", "implementation_opening",
}


WORLD_SOURCE = '''def completion_time(job, worker):
    """Return deterministic completion time for one worker and job."""
    return job["cost"] / worker["speed"]


def expected_score(job, worker):
    """Value reliable completion and subtract the visible lateness cost."""
    lateness = max(0.0, completion_time(job, worker) - job["deadline"])
    return job["value"] * worker["reliability"] - job["late_penalty"] * lateness
'''

SIGNALS_SOURCE = '''from .world import completion_time


def timeliness(job, worker):
    """Positive margin means completion is before the deadline."""
    return job["deadline"] - completion_time(job, worker)


def reliability(worker):
    """Return the worker's observed completion reliability."""
    return worker["reliability"]
'''

POLICY_SOURCE = '''def choose_worker(job, workers):
    """Choose one existing worker id for the supplied job."""
    return max(workers, key=lambda worker: (worker["speed"], worker["id"]))["id"]
'''

REFERENCE_POLICY_SOURCE = '''from .world import expected_score


def choose_worker(job, workers):
    """Choose one existing worker id for the supplied job."""
    return max(workers, key=lambda worker: (
        expected_score(job, worker), worker["speed"], worker["id"]
    ))["id"]
'''

PUBLIC_CASES = [
    {"case_id": "loose-reliability", "job": {"cost": 30, "deadline": 6, "value": 100, "late_penalty": 30}, "workers": [{"id": "fast", "speed": 10, "reliability": 0.45}, {"id": "safe", "speed": 6, "reliability": 0.95}]},
    {"case_id": "tight-speed", "job": {"cost": 30, "deadline": 3, "value": 100, "late_penalty": 35}, "workers": [{"id": "fast", "speed": 10, "reliability": 0.45}, {"id": "safe", "speed": 6, "reliability": 0.95}]},
    {"case_id": "three-way-reliability", "job": {"cost": 24, "deadline": 4, "value": 120, "late_penalty": 25}, "workers": [{"id": "fast", "speed": 12, "reliability": 0.50}, {"id": "balanced", "speed": 8, "reliability": 0.85}, {"id": "safe", "speed": 6, "reliability": 0.96}]},
    {"case_id": "lateness-switch", "job": {"cost": 40, "deadline": 4, "value": 90, "late_penalty": 40}, "workers": [{"id": "fast", "speed": 10, "reliability": 0.62}, {"id": "safe", "speed": 5, "reliability": 0.98}]},
]

HIDDEN_CASES = [
    {"case_id": "h01", "job": {"cost": 36, "deadline": 7, "value": 140, "late_penalty": 22}, "workers": [{"id": "f", "speed": 12, "reliability": 0.48}, {"id": "s", "speed": 6, "reliability": 0.97}]},
    {"case_id": "h02", "job": {"cost": 36, "deadline": 3, "value": 140, "late_penalty": 55}, "workers": [{"id": "f", "speed": 12, "reliability": 0.58}, {"id": "s", "speed": 6, "reliability": 0.98}]},
    {"case_id": "h03", "job": {"cost": 25, "deadline": 5, "value": 80, "late_penalty": 18}, "workers": [{"id": "f", "speed": 10, "reliability": 0.52}, {"id": "m", "speed": 7, "reliability": 0.86}, {"id": "s", "speed": 5, "reliability": 0.99}]},
    {"case_id": "h04", "job": {"cost": 48, "deadline": 4, "value": 110, "late_penalty": 60}, "workers": [{"id": "f", "speed": 12, "reliability": 0.61}, {"id": "m", "speed": 8, "reliability": 0.88}, {"id": "s", "speed": 6, "reliability": 0.98}]},
    {"case_id": "h05", "job": {"cost": 18, "deadline": 4, "value": 160, "late_penalty": 12}, "workers": [{"id": "f", "speed": 9, "reliability": 0.44}, {"id": "s", "speed": 5, "reliability": 0.96}]},
    {"case_id": "h06", "job": {"cost": 60, "deadline": 6, "value": 125, "late_penalty": 42}, "workers": [{"id": "f", "speed": 15, "reliability": 0.55}, {"id": "m", "speed": 10, "reliability": 0.82}, {"id": "s", "speed": 7, "reliability": 0.97}]},
    {"case_id": "h07", "job": {"cost": 42, "deadline": 8, "value": 95, "late_penalty": 20}, "workers": [{"id": "f", "speed": 14, "reliability": 0.50}, {"id": "s", "speed": 6, "reliability": 0.94}]},
    {"case_id": "h08", "job": {"cost": 54, "deadline": 4, "value": 150, "late_penalty": 75}, "workers": [{"id": "f", "speed": 18, "reliability": 0.63}, {"id": "m", "speed": 12, "reliability": 0.91}, {"id": "s", "speed": 8, "reliability": 0.99}]},
]

PUBLIC_CASES_SOURCE = "CASES = " + repr(PUBLIC_CASES) + "\n"

OBSERVE_SOURCE = '''import json
from dispatch.policy import choose_worker
from dispatch.public_cases import CASES
from dispatch.world import completion_time, expected_score


for case in CASES:
    job, workers = case["job"], case["workers"]
    selected_id = choose_worker(job, workers)
    selected = next(worker for worker in workers if worker["id"] == selected_id)
    best = max(workers, key=lambda worker: (
        expected_score(job, worker), worker["speed"], worker["id"]
    ))
    selected_score = expected_score(job, selected)
    best_score = expected_score(job, best)
    print(json.dumps({
        "case_id": case["case_id"],
        "selected_worker": selected_id,
        "completion_time": completion_time(job, selected),
        "reliability": selected["reliability"],
        "expected_score": selected_score,
        "best_worker": best["id"],
        "best_score": best_score,
        "regret": best_score - selected_score,
    }, sort_keys=True))
'''

FLOOR_TEST_SOURCE = '''import unittest
from dispatch.policy import choose_worker
from dispatch.world import completion_time, expected_score


class FloorTests(unittest.TestCase):
    def test_world_semantics(self):
        job = {"cost": 20, "deadline": 3, "value": 100, "late_penalty": 10}
        worker = {"id": "w", "speed": 5, "reliability": 0.9}
        self.assertEqual(completion_time(job, worker), 4)
        self.assertEqual(expected_score(job, worker), 80)

    def test_policy_returns_existing_id(self):
        job = {"cost": 8, "deadline": 2, "value": 10, "late_penalty": 2}
        workers = [{"id": "a", "speed": 2, "reliability": 1.0},
                   {"id": "b", "speed": 4, "reliability": 0.5}]
        self.assertIn(choose_worker(job, workers), {"a", "b"})
'''

ENVIRONMENT_FILES = {
    "dispatch/__init__.py": "",
    "dispatch/world.py": WORLD_SOURCE,
    "dispatch/signals.py": SIGNALS_SOURCE,
    "dispatch/policy.py": POLICY_SOURCE,
    "dispatch/public_cases.py": PUBLIC_CASES_SOURCE,
    "tests/__init__.py": "",
    "tests/test_floor.py": FLOOR_TEST_SOURCE,
    "observe.py": OBSERVE_SOURCE,
}

EVALUATOR_SOURCE = '''import json
from pathlib import Path
from dispatch.policy import choose_worker
from dispatch.world import expected_score

cases = json.loads(Path("_cases.json").read_text())
rows = []
valid = True
for case in cases:
    job, workers = case["job"], case["workers"]
    ids = {worker["id"] for worker in workers}
    try:
        selected_id = choose_worker(job, workers)
        if selected_id not in ids:
            raise ValueError("policy returned an unknown worker")
        selected = next(worker for worker in workers if worker["id"] == selected_id)
        oracle = max(workers, key=lambda worker: (
            expected_score(job, worker), worker["speed"], worker["id"]
        ))
        rows.append({"case_id": case["case_id"], "selected_worker": selected_id,
                     "score": expected_score(job, selected),
                     "oracle_worker": oracle["id"], "oracle_score": expected_score(job, oracle)})
    except Exception as error:
        valid = False
        rows.append({"case_id": case["case_id"], "error_type": type(error).__name__})
print(json.dumps({"valid": valid, "rows": rows,
                  "total": sum(row.get("score", 0.0) for row in rows),
                  "oracle_total": sum(row.get("oracle_score", 0.0) for row in rows)}, sort_keys=True))
'''


def load_prior(repo: Path = REPO):
    path = repo / "experiments/ot_0085_explicit_contact_abi.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0085 implementation identity changed")
    name = "ot0086_frozen_ot0085"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(prior, prior82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = prior82.materialize(repo, store, "OT-0085", "open-subject-after-discovered-contact.json")
    return json.loads(path.read_text())


def write_environment(root: Path) -> None:
    for relative, source in ENVIRONMENT_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def candidate_template() -> dict[str, Any]:
    row = {"target_path": TARGET_PATH, "target_symbol": TARGET_SYMBOL}
    row.update({key: 0 for key in INTEGER_FIELDS})
    row.update({key: False for key in BOOLEAN_FIELDS})
    row.update({"rationale": PLACEHOLDER, "implementation_opening": PLACEHOLDER})
    return row


def frontier_template() -> dict[str, Any]:
    return {"candidates": [candidate_template() for _ in range(3)], "next_pursuit": PLACEHOLDER}


def frontier_contract() -> dict[str, Any]:
    return {
        "exact_top_level_keys": ["candidates", "next_pursuit"],
        "candidate_count": 3,
        "candidate_exact_keys": sorted(CANDIDATE_KEYS),
        "target_rule": {"target_path": TARGET_PATH, "target_symbol": TARGET_SYMBOL},
        "identity_rule": "three distinct identities derived from target path, symbol, and implementation opening",
        "integer_fields": {key: {"minimum": 0, "maximum": 4} for key in INTEGER_FIELDS},
        "boolean_fields": list(BOOLEAN_FIELDS),
        "instruction": "Replace every __REPLACE__ string. Propose three distinct behavioral interventions from observed outcomes; do not select one directly.",
    }


def target_has_symbol(environment: Path) -> bool:
    try:
        tree = ast.parse((environment / TARGET_PATH).read_text())
    except (OSError, SyntaxError):
        return False
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET_SYMBOL for node in tree.body)


def candidate_identity(prior82, row: dict[str, Any]) -> str:
    return prior82.digest({key: row[key] for key in ("target_path", "target_symbol", "implementation_opening")})


def valid_candidate(value: Any, environment: Path) -> bool:
    if not isinstance(value, dict) or set(value) != CANDIDATE_KEYS:
        return False
    if value.get("target_path") != TARGET_PATH or value.get("target_symbol") != TARGET_SYMBOL or not target_has_symbol(environment):
        return False
    if not all(isinstance(value[key], int) and not isinstance(value[key], bool) and 0 <= value[key] <= 4 for key in INTEGER_FIELDS):
        return False
    if not all(isinstance(value[key], bool) for key in BOOLEAN_FIELDS):
        return False
    return all(isinstance(value[key], str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 2000 for key in ("rationale", "implementation_opening"))


def valid_frontier(value: Any, environment: Path, prior82) -> bool:
    if not isinstance(value, dict) or set(value) != {"candidates", "next_pursuit"}:
        return False
    if not isinstance(value["candidates"], list) or len(value["candidates"]) != 3:
        return False
    if not isinstance(value["next_pursuit"], str) or not value["next_pursuit"].strip() or PLACEHOLDER in value["next_pursuit"]:
        return False
    if not all(valid_candidate(row, environment) for row in value["candidates"]):
        return False
    identities = [candidate_identity(prior82, row) for row in value["candidates"]]
    return len(set(identities)) == 3


def representative_frontier() -> dict[str, Any]:
    rows = []
    openings = [
        ("Choose by visible expected score, composing reliability and lateness.", 4),
        ("Prefer on-time workers, then use reliability as a tie-break.", 3),
        ("Use a weighted reliability and speed utility for each job.", 2),
    ]
    for opening, chord in openings:
        row = candidate_template()
        row.update({"axis_chord": chord, "reversibility": 4, "immediate_gain": 3,
                    "axis_lumen": 3, "rationale": "Public regret motivates this bounded policy change.",
                    "implementation_opening": opening})
        rows.append(row)
    return {"candidates": rows, "next_pursuit": "Select and test one behavioral intervention."}


def observe(root: Path) -> dict[str, Any]:
    completed = subprocess.run(["python3", "observe.py"], cwd=root, text=True, capture_output=True, timeout=30)
    try:
        rows = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError:
        rows = []
    return {"returncode": completed.returncode, "rows": rows,
            "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest()}


def floor_test(root: Path) -> dict[str, Any]:
    completed = subprocess.run(["python3", "-m", "unittest", "-q", "tests.test_floor"], cwd=root, text=True, capture_output=True, timeout=30)
    return {"passed": completed.returncode == 0, "returncode": completed.returncode,
            "stdout_digest": hashlib.sha256(completed.stdout.encode()).hexdigest(),
            "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest()}


def evaluate_source(prior82, source: str, cases: list[dict[str, Any]], evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    write_environment(root)
    (root / TARGET_PATH).write_text(source)
    (root / "_cases.json").write_text(json.dumps(cases, sort_keys=True) + "\n")
    (root / "_score.py").write_text(EVALUATOR_SOURCE)
    floor = floor_test(root)
    completed = subprocess.run(["python3", "_score.py"], cwd=root, text=True, capture_output=True, timeout=30)
    try:
        score = json.loads(completed.stdout)
    except json.JSONDecodeError:
        score = {"valid": False, "rows": [], "total": 0.0, "oracle_total": 0.0}
    body = {"authority": "ot-0086-sealed-dispatch-evaluator", "label": label,
            "source_digest": prior82.digest(source), "cases_digest": prior82.digest(cases),
            "floor": floor, "execution_returncode": completed.returncode,
            "execution_stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            "valid": completed.returncode == 0 and bool(score.get("valid")),
            "rows": score.get("rows", []), "total": score.get("total", 0.0),
            "oracle_total": score.get("oracle_total", 0.0)}
    return {**body, "receipt_digest": prior82.digest(body)}


def compare_sources(prior82, candidate: str, evidence: Path, label: str,
                    cases: list[dict[str, Any]], require_public: bool) -> dict[str, Any]:
    unchanged = evaluate_source(prior82, POLICY_SOURCE, cases, evidence, f"{label}-unchanged")
    proposed = evaluate_source(prior82, candidate, cases, evidence, f"{label}-candidate")
    baseline_by_case = {row["case_id"]: row.get("score") for row in unchanged["rows"]}
    no_regression = all(row.get("score", float("-inf")) + 1e-9 >= baseline_by_case.get(row["case_id"], float("inf")) for row in proposed["rows"])
    gain = proposed["total"] - unchanged["total"]
    oracle_gain = unchanged["oracle_total"] - unchanged["total"]
    oracle_fraction = gain / oracle_gain if oracle_gain > 1e-9 else 1.0
    body = {"authority": "ot-0086-bound-policy-comparison", "cases_digest": prior82.digest(cases),
            "unchanged_receipt_digest": unchanged["receipt_digest"],
            "candidate_receipt_digest": proposed["receipt_digest"],
            "unchanged_total": unchanged["total"], "candidate_total": proposed["total"],
            "oracle_total": unchanged["oracle_total"], "gain": gain,
            "oracle_improvement_fraction": oracle_fraction,
            "both_valid": unchanged["valid"] and proposed["valid"],
            "candidate_floor_passed": proposed["floor"]["passed"],
            "no_case_regression": no_regression if require_public else None}
    return {**body, "receipt_digest": prior82.digest(body)}


def fixture_conformance(prior82, root: Path) -> dict[str, Any]:
    environment = root / "environment"
    write_environment(environment)
    seeded = frontier_template()
    representative = representative_frontier()
    duplicate = copy.deepcopy(representative)
    duplicate["candidates"][2]["implementation_opening"] = duplicate["candidates"][1]["implementation_opening"]
    public = compare_sources(prior82, REFERENCE_POLICY_SOURCE, root / "public", "public", PUBLIC_CASES, True)
    hidden = compare_sources(prior82, REFERENCE_POLICY_SOURCE, root / "hidden", "hidden", HIDDEN_CASES, False)
    ablated_cases = copy.deepcopy(HIDDEN_CASES)
    for case in ablated_cases:
        for worker in case["workers"]:
            worker["reliability"] = 1.0
    ablated = compare_sources(prior82, REFERENCE_POLICY_SOURCE, root / "ablated", "ablated", ablated_cases, False)
    observation = observe(environment)
    source_text = "\n".join(ENVIRONMENT_FILES.values())
    result = {
        "complete_source": all(token not in source_text for token in ("TODO", "NotImplementedError", "__REPLACE__")),
        "target_symbol_exists": target_has_symbol(environment),
        "floor_passed": floor_test(environment)["passed"],
        "observation_passed": observation["returncode"] == 0 and len(observation["rows"]) == len(PUBLIC_CASES) and any(row["regret"] > 0 for row in observation["rows"]),
        "seed_rejected": not valid_frontier(seeded, environment, prior82),
        "representative_passed": valid_frontier(representative, environment, prior82),
        "duplicate_rejected": not valid_frontier(duplicate, environment, prior82),
        "reference_public_passed": public["both_valid"] and public["candidate_floor_passed"] and public["no_case_regression"],
        "reference_hidden_passed": hidden["gain"] >= MIN_HIDDEN_GAIN and hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION,
        "reference_ablation_passed": ablated["gain"] < MAX_ABLATED_GAIN,
        "reference_receipts": {"public": public, "hidden": hidden, "ablated": ablated},
    }
    result["passed"] = all(value for key, value in result.items() if key != "reference_receipts")
    return result


def active_select(subject: dict[str, Any], binding: dict[str, Any], denied: set[str]) -> dict[str, Any] | None:
    policy = subject["developmental_selector"]["executable_priority_policy"]
    threshold = subject["developmental_selector"]["threshold"]
    eligible = []
    for row in binding["frontier"]["candidates"]:
        if row["candidate_id"] in denied or any(row[key] for key in policy["reject_if_any"]):
            continue
        if row["axis_chord"] >= threshold:
            eligible.append(row)
    eligible.sort(key=lambda row: tuple([-row[key] for key in policy["rank_descending"]] + [row["candidate_id"]]))
    return eligible[0] if eligible else None


def discovery_seed(run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed)
    projection = {"subject_digest": subject["artifact_digest"], "continuation": subject["continuation"],
                  "developmental_selector": subject["developmental_selector"],
                  "denied_candidate_ids": sorted(denied)}
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "frontier.json").write_text(json.dumps(frontier_template(), indent=2, sort_keys=True) + "\n")
    (seed / "frontier-contract.json").write_text(json.dumps(frontier_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "This is a complete dispatch repository, not a repair task. Run python3 observe.py and inspect the code and tests. "
        "Infer three distinct behavioral interventions from observed regret. Edit exactly frontier.json, preserve its exact shape, "
        "replace every placeholder, and do not edit code or directly choose a proposal.\n")
    return seed


def run_discovery(prior82, context, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> dict[str, Any]:
    seed = discovery_seed(run, label, subject, denied)
    prompt = ("You are a fresh continuation actor with ordinary broad tools. Inspect the inherited position and complete repository, "
              "run its declared observation command, and author exactly three distinct behavioral interventions in frontier.json. "
              "Follow frontier-contract.json, edit no code, inspect the exact diff, and return the required report.")
    output, base, workspace, _ = context.run_actor(label, seed, DISCOVERY_SCHEMA, prompt)
    try:
        frontier = json.loads((workspace / "frontier.json").read_text())
    except (json.JSONDecodeError, OSError):
        frontier = None
    audit = context.audit_actor(label, output, base, valid_frontier(frontier, workspace, prior82), ["frontier.json"])
    binding = None
    if audit["conformant"]:
        candidates = [{**copy.deepcopy(row), "candidate_id": candidate_identity(prior82, row)} for row in frontier["candidates"]]
        body = {"authority": "ot-0086-pre-selection-behavioral-frontier", "source_subject_digest": subject["artifact_digest"],
                "denied_candidate_ids": sorted(denied), "actor_patch_digest": audit["patch_digest"],
                "frontier": {"candidates": candidates, "next_pursuit": frontier["next_pursuit"]}}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-frontier.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    selected = active_select(subject, binding, denied) if binding else None
    return {"label": label, "output": output, "audit": audit, "binding": binding, "selected_candidate": selected}


def implementation_seed(run: Path, label: str, route: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed)
    selected = route["selected_candidate"]
    projection = {"frontier_binding_digest": route["binding"]["binding_digest"],
                  "source_subject_digest": route["binding"]["source_subject_digest"],
                  "selected_candidate": selected, "editable": [TARGET_PATH]}
    (seed / "bound-contact.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "The inherited selector chose the behavioral intervention in bound-contact.json. Edit exactly dispatch/policy.py. "
        "Its ABI is choose_worker(job, workers) -> one existing worker id. Run public observations and tests, inspect the exact diff, "
        "and leave hidden outcomes to the world.\n")
    return seed


def run_implementation(prior82, context, run: Path, label: str, route: dict[str, Any]) -> dict[str, Any]:
    seed = implementation_seed(run, label, route)
    prompt = ("You are a fresh continuation actor with ordinary broad tools. Implement the exact bound behavioral intervention. "
              "Edit only dispatch/policy.py, preserve its public ABI, run useful checks, inspect the exact diff, and return the required report.")
    output, base, workspace, _ = context.run_actor(label, seed, IMPLEMENTATION_SCHEMA, prompt)
    try:
        source = (workspace / TARGET_PATH).read_text()
    except OSError:
        source = ""
    compiled = subprocess.run(["python3", "-m", "py_compile", TARGET_PATH], cwd=workspace, capture_output=True)
    changed = bool(source) and source != POLICY_SOURCE
    audit = context.audit_actor(label, output, base, changed and compiled.returncode == 0, [TARGET_PATH])
    binding = None
    if audit["conformant"]:
        selected = route["selected_candidate"]
        body = {"authority": "ot-0086-pre-hidden-policy-binding", "source_subject_digest": route["binding"]["source_subject_digest"],
                "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"],
                "target_path": TARGET_PATH, "target_symbol": TARGET_SYMBOL, "actor_patch_digest": audit["patch_digest"],
                "source": source, "source_digest": prior82.digest(source)}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-intervention.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    public = compare_sources(prior82, source, context.evidence(label), "public", PUBLIC_CASES, True) if binding else None
    hidden = compare_sources(prior82, source, context.evidence(label), "hidden", HIDDEN_CASES, False) if binding else None
    valid = bool(public and hidden and public["both_valid"] and public["candidate_floor_passed"] and public["no_case_regression"] and hidden["both_valid"] and hidden["candidate_floor_passed"])
    admitted = bool(valid and hidden["gain"] >= MIN_HIDDEN_GAIN and hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION)
    body = {"authority": "ot-0086-sealed-behavioral-world", "candidate_id": route["selected_candidate"]["candidate_id"],
            "intervention_binding_digest": binding["binding_digest"] if binding else None,
            "public": public, "hidden": hidden, "valid": valid, "developmentally_admitted": admitted,
            "developmental_class": "world-valid-behavioral-composition" if admitted else "world-valid-non-improving" if valid else "world-invalid"}
    world = {**body, "receipt_digest": prior82.digest(body)}
    (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding, "world": world}


def compile_denial(prior82, subject: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = route["selected_candidate"]
    body = {"authority": "subject-behavioral-policy-denial", "source_subject_digest": subject["artifact_digest"],
            "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"],
            "world_receipt_digest": implementation["world"]["receipt_digest"], "developmentally_admitted": False}
    receipt = {**body, "receipt_digest": prior82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["behavioral_policy_denial_receipts"] = [*child.get("behavioral_policy_denial_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["unresolved"] = "Use retained behavioral consequence to discover a different intervention."
    return prior82.seal(child), receipt


def promote(prior82, subject: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = route["selected_candidate"]
    body = {"authority": "world-promoted-behaviorally-discovered-policy", "source_subject_digest": subject["artifact_digest"],
            "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"],
            "intervention_binding_digest": implementation["binding"]["binding_digest"],
            "world_receipt_digest": implementation["world"]["receipt_digest"],
            "developmental_class": implementation["world"]["developmental_class"]}
    receipt = {**body, "receipt_digest": prior82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["behavioral_frontiers"] = [*child.get("behavioral_frontiers", []),
        {"binding_digest": route["binding"]["binding_digest"],
         "candidate_ids": [row["candidate_id"] for row in route["binding"]["frontier"]["candidates"]],
         "selected_candidate_id": selected["candidate_id"]}]
    child["behavioral_policy_receipts"] = [*child.get("behavioral_policy_receipts", []), receipt]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []),
        {"candidate_id": selected["candidate_id"], "target_path": TARGET_PATH, "target_symbol": TARGET_SYMBOL,
         "source": implementation["binding"]["source"], "source_digest": implementation["binding"]["source_digest"],
         "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"],
        {"selected_area": TARGET_PATH, "pursuit": implementation["output"]["next_pursuit"],
         "patch_digest": implementation["audit"]["patch_digest"],
         "world_receipt_digest": implementation["world"]["receipt_digest"],
         "contact_program_digest": implementation["binding"]["source_digest"]}]
    child["active_pursuit"] = {"authority": "world-promoted-behavioral-policy", "selected_area": TARGET_PATH,
                               "next_pursuit": implementation["output"]["next_pursuit"],
                               "world_receipt_digest": implementation["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["runtime"] = "sounding"
    child["unresolved"] = "Inspect another environment and continue from consequence-grounded behavioral discovery."
    return prior82.seal(child), receipt


def run_ablation(prior82, source: str, evidence: Path) -> dict[str, Any]:
    cases = copy.deepcopy(HIDDEN_CASES)
    for case in cases:
        for worker in case["workers"]:
            worker["reliability"] = 1.0
    comparison = compare_sources(prior82, source, evidence, "reliability-neutralized", cases, False)
    body = {"authority": "ot-0086-post-seal-reliability-neutralization", "comparison": comparison,
            "composition_effect_passed": comparison["both_valid"] and comparison["gain"] < MAX_ABLATED_GAIN}
    return {**body, "receipt_digest": prior82.digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0086").resolve()
    prior = load_prior(repo)
    prior84 = prior.load_prior(repo)
    prior83 = prior84.load_prior(repo)
    prior82 = prior83.load_prior(repo)
    runtime = prior82.load_runtime(repo, store)
    parent = load_parent(prior, prior82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != PARENT_DIGEST or parent["continuation"]["next_opening"] != "inspect-and-select-environmental-intervention":
        raise SystemExit("wrong OT-0085 open parent")
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior82, Path(directory))
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256,
                  "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0086 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior82, run / "fixture-conformance")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo)
    started = time.time()
    current = parent
    discoveries, implementations, denials = [], [], []
    promoted = None
    selected_route = None
    selected_implementation = None
    denied: set[str] = set()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        route = run_discovery(prior82, context, run, f"discovery-{attempt:02d}", current, denied)
        discoveries.append(route)
        if not route["selected_candidate"]:
            break
        implementation = run_implementation(prior82, context, run, f"implementation-{attempt:02d}", route)
        implementations.append(implementation)
        if not (implementation["audit"]["conformant"] and implementation["binding"] and implementation["world"]["valid"]):
            break
        if not implementation["world"]["developmentally_admitted"]:
            current, denial = compile_denial(prior82, current, route, implementation)
            denials.append(denial)
            denied.add(route["selected_candidate"]["candidate_id"])
            continue
        current, promoted = promote(prior82, current, route, implementation)
        selected_route, selected_implementation = route, implementation
        break
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and
        current["continuation"]["status"] == "open" and current["continuation"]["next_opening"] == "inspect-and-select-environmental-intervention" and
        len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1 and
        len(current.get("behavioral_frontiers", [])) == len(parent.get("behavioral_frontiers", [])) + 1)
    ablation = None
    composition_effect = False
    if operational_passed and selected_route and selected_implementation:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        ablation = run_ablation(prior82, selected_implementation["binding"]["source"], run / "post-seal-ablation")
        composition_effect = ablation["composition_effect_passed"]
    observer = "promoted" if operational_passed and composition_effect else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0086-fixed-behavioral-discovery-driver", "source_subject_digest": parent["artifact_digest"],
              "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures,
              "discoveries": [prior82.compact(row) for row in discoveries],
              "implementations": [prior82.compact(row) for row in implementations], "denial_receipts": denials,
              "promotion_receipt": promoted, "operational_transition_passed": operational_passed,
              "composition_effect_passed": composition_effect, "post_seal_ablation": ablation,
              "observer_disposition": observer, "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
              "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
              "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = prior82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
