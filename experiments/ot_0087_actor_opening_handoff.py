from __future__ import annotations

import argparse
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
PRIOR_SHA256 = "1c1c060a29a86f63bc520c66fb2709817a804fcc0e1def248bf60c1fb7a69d70"
PARENT_DIGEST = "193c703322f103f0b3efcba1dd4e2a55f61f77d45bb085a0db60328fafc03bb0"
OPENING_SCHEMA = REPO / "spec/ot-0087-opening.schema.json"
SUCCESSOR_SCHEMA = REPO / "spec/ot-0087-successor.schema.json"
PLACEHOLDER = "__REPLACE__"
MIN_HIDDEN_GAIN = 20.0
MIN_ORACLE_FRACTION = 0.90

OPENING_KEYS = {
    "status", "next_opening", "chosen_target_path", "target_symbol",
    "observed_discrepancy", "world_contact", "surrender_condition",
    "continuation_after_contact",
}
SUCCESSOR_OPENING_KEYS = {
    "status", "next_opening", "contact_made", "unresolved",
    "surrender_condition", "continuation_after_contact",
}


WORLD_SOURCE = '''def score_rehearsal(context, option):
    """Expected learning after attendance, cancellation, and duration costs."""
    return (option["learning_value"] * option["attendance_probability"]
            - context["cancellation_cost"] * (1.0 - option["attendance_probability"])
            - context["duration_cost"] * option["duration"])


def score_mix(context, option):
    """Expected audience value after clarity, clipping, and production costs."""
    return (option["audience_value"] * option["clarity"]
            - context["clipping_penalty"] * option["clipping_risk"]
            - option["production_cost"])


def score_program(context, option):
    """Expected program value from readiness, coverage, and setup cost."""
    return (option["popularity"] * option["readiness"]
            + context["coverage_bonus"] * option["instrument_coverage"]
            - option["setup_cost"])
'''

REHEARSAL_SOURCE = '''def choose_rehearsal(context, options):
    """Choose one existing rehearsal option id."""
    return max(options, key=lambda option: (option["learning_value"], option["id"]))["id"]
'''

MIX_SOURCE = '''def choose_mix(context, options):
    """Choose one existing mix option id."""
    return max(options, key=lambda option: (option["audience_value"], option["id"]))["id"]
'''

PROGRAM_SOURCE = '''def choose_program(context, options):
    """Choose one existing program option id."""
    return max(options, key=lambda option: (option["popularity"], option["id"]))["id"]
'''

REFERENCE_SOURCES = {
    "ensemble/rehearsal.py": '''from .world import score_rehearsal


def choose_rehearsal(context, options):
    """Choose one existing rehearsal option id."""
    return max(options, key=lambda option: (score_rehearsal(context, option), option["id"]))["id"]
''',
    "ensemble/mix.py": '''from .world import score_mix


def choose_mix(context, options):
    """Choose one existing mix option id."""
    return max(options, key=lambda option: (score_mix(context, option), option["id"]))["id"]
''',
    "ensemble/program.py": '''from .world import score_program


def choose_program(context, options):
    """Choose one existing program option id."""
    return max(options, key=lambda option: (score_program(context, option), option["id"]))["id"]
''',
}

PUBLIC_CASES = {
    "rehearsal": [
        {"case_id": "r-public-risk", "context": {"cancellation_cost": 40, "duration_cost": 3}, "options": [{"id": "star", "learning_value": 100, "attendance_probability": 0.40, "duration": 2}, {"id": "steady", "learning_value": 75, "attendance_probability": 0.95, "duration": 3}]},
        {"case_id": "r-public-upside", "context": {"cancellation_cost": 20, "duration_cost": 3}, "options": [{"id": "star", "learning_value": 100, "attendance_probability": 0.90, "duration": 2}, {"id": "steady", "learning_value": 75, "attendance_probability": 0.95, "duration": 3}]},
    ],
    "mix": [
        {"case_id": "m-public-clipping", "context": {"clipping_penalty": 50}, "options": [{"id": "loud", "audience_value": 100, "clarity": 0.70, "clipping_risk": 0.80, "production_cost": 5}, {"id": "clean", "audience_value": 80, "clarity": 0.95, "clipping_risk": 0.10, "production_cost": 6}]},
        {"case_id": "m-public-energy", "context": {"clipping_penalty": 15}, "options": [{"id": "loud", "audience_value": 100, "clarity": 0.92, "clipping_risk": 0.20, "production_cost": 5}, {"id": "clean", "audience_value": 80, "clarity": 0.95, "clipping_risk": 0.05, "production_cost": 6}]},
    ],
    "program": [
        {"case_id": "p-public-readiness", "context": {"coverage_bonus": 30}, "options": [{"id": "hit", "popularity": 100, "readiness": 0.45, "instrument_coverage": 0.60, "setup_cost": 10}, {"id": "ensemble", "popularity": 85, "readiness": 0.90, "instrument_coverage": 0.95, "setup_cost": 12}]},
        {"case_id": "p-public-popularity", "context": {"coverage_bonus": 10}, "options": [{"id": "hit", "popularity": 100, "readiness": 0.95, "instrument_coverage": 0.80, "setup_cost": 8}, {"id": "ensemble", "popularity": 85, "readiness": 0.90, "instrument_coverage": 0.95, "setup_cost": 12}]},
    ],
}

HIDDEN_CASES = {
    "rehearsal": [
        {"case_id": "r-h1", "context": {"cancellation_cost": 55, "duration_cost": 2}, "options": [{"id": "a", "learning_value": 120, "attendance_probability": 0.35, "duration": 2}, {"id": "b", "learning_value": 88, "attendance_probability": 0.96, "duration": 4}]},
        {"case_id": "r-h2", "context": {"cancellation_cost": 12, "duration_cost": 4}, "options": [{"id": "a", "learning_value": 110, "attendance_probability": 0.92, "duration": 2}, {"id": "b", "learning_value": 90, "attendance_probability": 0.98, "duration": 4}]},
        {"case_id": "r-h3", "context": {"cancellation_cost": 45, "duration_cost": 3}, "options": [{"id": "a", "learning_value": 105, "attendance_probability": 0.50, "duration": 2}, {"id": "b", "learning_value": 82, "attendance_probability": 0.94, "duration": 3}, {"id": "c", "learning_value": 70, "attendance_probability": 0.99, "duration": 5}]},
        {"case_id": "r-h4", "context": {"cancellation_cost": 20, "duration_cost": 2}, "options": [{"id": "a", "learning_value": 115, "attendance_probability": 0.88, "duration": 3}, {"id": "b", "learning_value": 92, "attendance_probability": 0.97, "duration": 4}]},
    ],
    "mix": [
        {"case_id": "m-h1", "context": {"clipping_penalty": 70}, "options": [{"id": "a", "audience_value": 125, "clarity": 0.62, "clipping_risk": 0.75, "production_cost": 4}, {"id": "b", "audience_value": 95, "clarity": 0.96, "clipping_risk": 0.08, "production_cost": 8}]},
        {"case_id": "m-h2", "context": {"clipping_penalty": 18}, "options": [{"id": "a", "audience_value": 120, "clarity": 0.93, "clipping_risk": 0.15, "production_cost": 5}, {"id": "b", "audience_value": 96, "clarity": 0.97, "clipping_risk": 0.04, "production_cost": 8}]},
        {"case_id": "m-h3", "context": {"clipping_penalty": 55}, "options": [{"id": "a", "audience_value": 115, "clarity": 0.70, "clipping_risk": 0.65, "production_cost": 5}, {"id": "b", "audience_value": 90, "clarity": 0.94, "clipping_risk": 0.10, "production_cost": 7}, {"id": "c", "audience_value": 78, "clarity": 0.99, "clipping_risk": 0.02, "production_cost": 9}]},
        {"case_id": "m-h4", "context": {"clipping_penalty": 25}, "options": [{"id": "a", "audience_value": 130, "clarity": 0.90, "clipping_risk": 0.22, "production_cost": 6}, {"id": "b", "audience_value": 100, "clarity": 0.98, "clipping_risk": 0.05, "production_cost": 8}]},
    ],
    "program": [
        {"case_id": "p-h1", "context": {"coverage_bonus": 45}, "options": [{"id": "a", "popularity": 120, "readiness": 0.40, "instrument_coverage": 0.55, "setup_cost": 12}, {"id": "b", "popularity": 94, "readiness": 0.92, "instrument_coverage": 0.96, "setup_cost": 14}]},
        {"case_id": "p-h2", "context": {"coverage_bonus": 12}, "options": [{"id": "a", "popularity": 115, "readiness": 0.94, "instrument_coverage": 0.82, "setup_cost": 8}, {"id": "b", "popularity": 95, "readiness": 0.90, "instrument_coverage": 0.98, "setup_cost": 13}]},
        {"case_id": "p-h3", "context": {"coverage_bonus": 38}, "options": [{"id": "a", "popularity": 110, "readiness": 0.52, "instrument_coverage": 0.60, "setup_cost": 10}, {"id": "b", "popularity": 90, "readiness": 0.88, "instrument_coverage": 0.94, "setup_cost": 12}, {"id": "c", "popularity": 78, "readiness": 0.98, "instrument_coverage": 1.0, "setup_cost": 15}]},
        {"case_id": "p-h4", "context": {"coverage_bonus": 18}, "options": [{"id": "a", "popularity": 125, "readiness": 0.90, "instrument_coverage": 0.78, "setup_cost": 9}, {"id": "b", "popularity": 100, "readiness": 0.96, "instrument_coverage": 0.95, "setup_cost": 12}]},
    ],
}

TARGETS = {
    "ensemble/rehearsal.py": {"family": "rehearsal", "symbol": "choose_rehearsal", "source": REHEARSAL_SOURCE, "score": "score_rehearsal"},
    "ensemble/mix.py": {"family": "mix", "symbol": "choose_mix", "source": MIX_SOURCE, "score": "score_mix"},
    "ensemble/program.py": {"family": "program", "symbol": "choose_program", "source": PROGRAM_SOURCE, "score": "score_program"},
}

PUBLIC_CASES_SOURCE = "CASES = " + repr(PUBLIC_CASES) + "\n"

OBSERVE_SOURCE = '''import importlib
import json
from ensemble.public_cases import CASES
from ensemble import world

POLICIES = {
    "rehearsal": ("ensemble.rehearsal", "choose_rehearsal", "score_rehearsal"),
    "mix": ("ensemble.mix", "choose_mix", "score_mix"),
    "program": ("ensemble.program", "choose_program", "score_program"),
}

for family, cases in CASES.items():
    module_name, function_name, score_name = POLICIES[family]
    choose = getattr(importlib.import_module(module_name), function_name)
    score = getattr(world, score_name)
    for case in cases:
        context, options = case["context"], case["options"]
        selected_id = choose(context, options)
        selected = next(option for option in options if option["id"] == selected_id)
        oracle = max(options, key=lambda option: (score(context, option), option["id"]))
        selected_score, oracle_score = score(context, selected), score(context, oracle)
        print(json.dumps({"family": family, "case_id": case["case_id"],
                          "selected": selected_id, "score": selected_score,
                          "oracle": oracle["id"], "oracle_score": oracle_score,
                          "regret": oracle_score - selected_score}, sort_keys=True))
'''

FLOOR_TEST_SOURCE = '''import unittest
from ensemble.rehearsal import choose_rehearsal
from ensemble.mix import choose_mix
from ensemble.program import choose_program
from ensemble.world import score_rehearsal, score_mix, score_program


class FloorTests(unittest.TestCase):
    def test_policies_return_existing_ids(self):
        context = {"cancellation_cost": 10, "duration_cost": 2}
        options = [{"id": "a", "learning_value": 10, "attendance_probability": .8, "duration": 2},
                   {"id": "b", "learning_value": 8, "attendance_probability": 1, "duration": 2}]
        self.assertIn(choose_rehearsal(context, options), {"a", "b"})
        context = {"clipping_penalty": 10}
        options = [{"id": "a", "audience_value": 10, "clarity": .8, "clipping_risk": .2, "production_cost": 1},
                   {"id": "b", "audience_value": 8, "clarity": 1, "clipping_risk": 0, "production_cost": 1}]
        self.assertIn(choose_mix(context, options), {"a", "b"})
        context = {"coverage_bonus": 10}
        options = [{"id": "a", "popularity": 10, "readiness": .8, "instrument_coverage": .7, "setup_cost": 1},
                   {"id": "b", "popularity": 8, "readiness": 1, "instrument_coverage": 1, "setup_cost": 1}]
        self.assertIn(choose_program(context, options), {"a", "b"})

    def test_score_examples(self):
        self.assertAlmostEqual(score_rehearsal({"cancellation_cost": 40, "duration_cost": 3},
            {"learning_value": 75, "attendance_probability": .95, "duration": 3}), 60.25)
        self.assertAlmostEqual(score_mix({"clipping_penalty": 50},
            {"audience_value": 80, "clarity": .95, "clipping_risk": .1, "production_cost": 6}), 65)
        self.assertAlmostEqual(score_program({"coverage_bonus": 30},
            {"popularity": 85, "readiness": .9, "instrument_coverage": .95, "setup_cost": 12}), 93)
'''

ENVIRONMENT_FILES = {
    "ensemble/__init__.py": "",
    "ensemble/world.py": WORLD_SOURCE,
    "ensemble/rehearsal.py": REHEARSAL_SOURCE,
    "ensemble/mix.py": MIX_SOURCE,
    "ensemble/program.py": PROGRAM_SOURCE,
    "ensemble/public_cases.py": PUBLIC_CASES_SOURCE,
    "tests/__init__.py": "",
    "tests/test_floor.py": FLOOR_TEST_SOURCE,
    "observe.py": OBSERVE_SOURCE,
}

EVALUATOR_SOURCE = '''import importlib
import json
from pathlib import Path
from ensemble import world

config = json.loads(Path("_config.json").read_text())
module = importlib.import_module(config["module"])
choose = getattr(module, config["function"])
score = getattr(world, config["score"])
rows, valid = [], True
for case in config["cases"]:
    context, options = case["context"], case["options"]
    ids = {option["id"] for option in options}
    try:
        selected_id = choose(context, options)
        if selected_id not in ids:
            raise ValueError("unknown option")
        selected = next(option for option in options if option["id"] == selected_id)
        oracle = max(options, key=lambda option: (score(context, option), option["id"]))
        rows.append({"case_id": case["case_id"], "selected": selected_id,
                     "score": score(context, selected), "oracle": oracle["id"],
                     "oracle_score": score(context, oracle)})
    except Exception as error:
        valid = False
        rows.append({"case_id": case["case_id"], "error_type": type(error).__name__})
print(json.dumps({"valid": valid, "rows": rows,
                  "total": sum(row.get("score", 0) for row in rows),
                  "oracle_total": sum(row.get("oracle_score", 0) for row in rows)}, sort_keys=True))
'''


def load_prior(repo: Path = REPO):
    path = repo / "experiments/ot_0086_behavior_discovery.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0086 implementation identity changed")
    name = "ot0087_frozen_ot0086"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(prior86, prior82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = prior82.materialize(repo, store, "OT-0086", "open-subject-after-behavioral-discovery.json")
    return json.loads(path.read_text())


def write_environment(root: Path) -> None:
    for relative, source in ENVIRONMENT_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def opening_template() -> dict[str, Any]:
    return {key: PLACEHOLDER for key in OPENING_KEYS}


def successor_opening_template() -> dict[str, Any]:
    return {key: PLACEHOLDER for key in SUCCESSOR_OPENING_KEYS}


def opening_contract() -> dict[str, Any]:
    return {"exact_keys": sorted(OPENING_KEYS), "status_values": ["open", "surrendered"],
            "open_target_rule": "chosen_target_path must be an existing ensemble policy module and target_symbol a real top-level function in it",
            "surrender_rule": "use empty chosen_target_path and target_symbol, but preserve the other nonempty reasons and conditions",
            "instruction": "Replace every __REPLACE__ value. The repository supplies no preferred target; listen to public consequence and choose or surrender."}


def successor_opening_contract() -> dict[str, Any]:
    return {"exact_keys": sorted(SUCCESSOR_OPENING_KEYS), "required_status": "open",
            "instruction": "Replace every __REPLACE__ value with an actionable continuation grounded in the contact just made."}


def valid_strings(value: dict[str, Any], keys: set[str], allow_empty: set[str] | None = None) -> bool:
    allow_empty = allow_empty or set()
    return all(isinstance(value.get(key), str) and PLACEHOLDER not in value[key] and
               (bool(value[key].strip()) or key in allow_empty) and len(value[key]) <= 3000 for key in keys)


def valid_opening(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != OPENING_KEYS or not valid_strings(value, OPENING_KEYS, {"chosen_target_path", "target_symbol"}):
        return False
    if value["status"] == "surrendered":
        return value["chosen_target_path"] == "" and value["target_symbol"] == ""
    if value["status"] != "open" or value["chosen_target_path"] not in TARGETS:
        return False
    return value["target_symbol"] == TARGETS[value["chosen_target_path"]]["symbol"]


def valid_successor_opening(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == SUCCESSOR_OPENING_KEYS and value.get("status") == "open" and valid_strings(value, SUCCESSOR_OPENING_KEYS)


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


def evaluate_source(prior82, target_path: str, source: str, cases: list[dict[str, Any]], evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    write_environment(root)
    (root / target_path).write_text(source)
    selected = TARGETS[target_path]
    config = {"module": target_path[:-3].replace("/", "."), "function": selected["symbol"],
              "score": selected["score"], "cases": cases}
    (root / "_config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
    (root / "_score.py").write_text(EVALUATOR_SOURCE)
    floor = floor_test(root)
    completed = subprocess.run(["python3", "_score.py"], cwd=root, text=True, capture_output=True, timeout=30)
    try:
        score = json.loads(completed.stdout)
    except json.JSONDecodeError:
        score = {"valid": False, "rows": [], "total": 0.0, "oracle_total": 0.0}
    body = {"authority": "ot-0087-sealed-ensemble-evaluator", "target_path": target_path,
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
    body = {"authority": "ot-0087-bound-family-comparison", "target_path": target_path,
            "unchanged_receipt_digest": unchanged["receipt_digest"], "candidate_receipt_digest": candidate["receipt_digest"],
            "unchanged_total": unchanged["total"], "candidate_total": candidate["total"], "oracle_total": unchanged["oracle_total"],
            "gain": gain, "oracle_improvement_fraction": fraction, "both_valid": unchanged["valid"] and candidate["valid"],
            "candidate_floor_passed": candidate["floor"]["passed"], "no_case_regression": no_regression if public else None}
    return {**body, "receipt_digest": prior82.digest(body)}


def fixture_conformance(prior82, root: Path) -> dict[str, Any]:
    environment = root / "environment"
    write_environment(environment)
    observation = observe(environment)
    families_with_regret = {row["family"] for row in observation["rows"] if row.get("regret", 0) > 0}
    references = {}
    for target_path, selected in TARGETS.items():
        family = selected["family"]
        public = compare_source(prior82, target_path, REFERENCE_SOURCES[target_path], PUBLIC_CASES[family], root / f"{family}-public", "public", True)
        hidden = compare_source(prior82, target_path, REFERENCE_SOURCES[target_path], HIDDEN_CASES[family], root / f"{family}-hidden", "hidden", False)
        references[target_path] = {"public": public, "hidden": hidden,
                                   "passed": public["both_valid"] and public["candidate_floor_passed"] and public["no_case_regression"] and hidden["both_valid"] and hidden["gain"] >= MIN_HIDDEN_GAIN and hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION}
    representative = {"status": "open", "next_opening": "Follow the observed rehearsal reliability discrepancy.",
                      "chosen_target_path": "ensemble/rehearsal.py", "target_symbol": "choose_rehearsal",
                      "observed_discrepancy": "The public policy leaves positive regret.",
                      "world_contact": "Compare expected rehearsal value on held-out options.",
                      "surrender_condition": "Set it down if reliability-aware choice loses the floor.",
                      "continuation_after_contact": "Ask whether the next policy also ignores costly uncertainty."}
    successor = {"status": "open", "next_opening": "Inspect another complete policy for costly ignored uncertainty.",
                 "contact_made": "Rehearsal choice now uses expected value.", "unresolved": "Transfer remains unknown.",
                 "surrender_condition": "Stop this motif if a held-out world rewards the simpler policy.",
                 "continuation_after_contact": "Test the motif in another complete environment."}
    complete = "\n".join(ENVIRONMENT_FILES.values())
    result = {"complete_source": all(token not in complete for token in ("TODO", "NotImplementedError", PLACEHOLDER)),
              "floor_passed": floor_test(environment)["passed"],
              "observation_passed": observation["returncode"] == 0 and families_with_regret == set(PUBLIC_CASES),
              "opening_seed_rejected": not valid_opening(opening_template()), "opening_representative_passed": valid_opening(representative),
              "successor_seed_rejected": not valid_successor_opening(successor_opening_template()),
              "successor_representative_passed": valid_successor_opening(successor), "references": references,
              "all_target_references_passed": all(row["passed"] for row in references.values())}
    result["passed"] = all(value for key, value in result.items() if key != "references")
    return result


def subject_projection(subject: dict[str, Any]) -> dict[str, Any]:
    return {"artifact_digest": subject["artifact_digest"], "runtime": subject["runtime"],
            "continuation": subject["continuation"], "active_pursuit": subject.get("active_pursuit"),
            "unresolved": subject.get("unresolved"), "developmental_selector": subject.get("developmental_selector"),
            "recent_behavioral_frontier": subject.get("behavioral_frontiers", [])[-1:],
            "recent_environmental_capabilities": subject.get("environmental_capabilities", [])[-2:]}


def opening_seed(run: Path, label: str, subject: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed)
    (seed / "subject-position.json").write_text(json.dumps(subject_projection(subject), indent=2, sort_keys=True) + "\n")
    (seed / "opening.json").write_text(json.dumps(opening_template(), indent=2, sort_keys=True) + "\n")
    (seed / "opening-contract.json").write_text(json.dumps(opening_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "The actor turn ended, but the exact subject remains open. This is a complete world, not a repair task. "
        "Run python3 observe.py, inspect the subject position and repository, and decide what contact—if any—matters next. "
        "Edit exactly opening.json. No target is preferred; a valid surrender is allowed.\n")
    return seed


def run_opening(prior82, context, run: Path, label: str, subject: dict[str, Any]) -> dict[str, Any]:
    seed = opening_seed(run, label, subject)
    prompt = ("Continue the exact open subject by listening to the available world. Use ordinary tools, decide what contact should matter next or surrender it, "
              "complete opening.json exactly, edit nothing else, inspect the exact diff, and return the required report.")
    output, base, workspace, _ = context.run_actor(label, seed, OPENING_SCHEMA, prompt)
    try:
        opening = json.loads((workspace / "opening.json").read_text())
    except (json.JSONDecodeError, OSError):
        opening = None
    audit = context.audit_actor(label, output, base, valid_opening(opening), ["opening.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0087-pre-successor-actor-originated-opening", "source_subject_digest": subject["artifact_digest"],
                "actor_patch_digest": audit["patch_digest"], "opening": opening}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-opening.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding}


def bind_intermediate(prior82, subject: dict[str, Any], opening_run: dict[str, Any]) -> dict[str, Any]:
    binding = opening_run["binding"]
    opening = binding["opening"]
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"binding_digest": binding["binding_digest"], "opening": opening}]
    child["active_pursuit"] = {"authority": "actor-originated-pre-contact-opening", "opening_binding_digest": binding["binding_digest"],
                               "selected_area": opening["chosen_target_path"], "next_pursuit": opening["next_opening"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]
    return prior82.seal(child)


def successor_seed(run: Path, label: str, intermediate: dict[str, Any], opening_run: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed)
    binding = opening_run["binding"]
    target_path = binding["opening"]["chosen_target_path"]
    (seed / "subject-position.json").write_text(json.dumps(subject_projection(intermediate), indent=2, sort_keys=True) + "\n")
    (seed / "bound-opening.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": [target_path, "successor-opening.json"],
        "derivation": "actor-originated-opening", "opening_binding_digest": binding["binding_digest"]}, indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(successor_opening_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(successor_opening_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "The previous actor turn ended while the subject remained open. Continue the exact bound opening. The mutation envelope is derived from that opening, "
        "not selected by the observer. Edit exactly its policy target and successor-opening.json, run public observations and tests, and leave hidden consequence external.\n")
    return seed


def run_successor(prior82, context, run: Path, label: str, intermediate: dict[str, Any], opening_run: dict[str, Any]) -> dict[str, Any]:
    seed = successor_seed(run, label, intermediate, opening_run)
    opening = opening_run["binding"]["opening"]
    target_path = opening["chosen_target_path"]
    prompt = ("The prior turn ended but the subject did not. Continue its exact inherited opening using ordinary tools. Follow mutation-envelope.json, "
              "make the contact, leave another actionable opening in successor-opening.json, run useful public checks, inspect the exact diff, and return the required report.")
    output, base, workspace, _ = context.run_actor(label, seed, SUCCESSOR_SCHEMA, prompt)
    try:
        source = (workspace / target_path).read_text()
        successor_opening = json.loads((workspace / "successor-opening.json").read_text())
    except (OSError, json.JSONDecodeError):
        source, successor_opening = "", None
    compiled = subprocess.run(["python3", "-m", "py_compile", target_path], cwd=workspace, capture_output=True)
    artifact_valid = bool(source and source != TARGETS[target_path]["source"] and compiled.returncode == 0 and valid_successor_opening(successor_opening))
    expected = sorted([target_path, "successor-opening.json"])
    audit = context.audit_actor(label, output, base, artifact_valid, expected)
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0087-pre-hidden-successor-binding", "source_subject_digest": intermediate["artifact_digest"],
                "opening_binding_digest": opening_run["binding"]["binding_digest"], "target_path": target_path,
                "target_symbol": opening["target_symbol"], "actor_patch_digest": audit["patch_digest"],
                "source": source, "source_digest": prior82.digest(source), "successor_opening": successor_opening}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-successor.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    family = TARGETS[target_path]["family"]
    public = compare_source(prior82, target_path, source, PUBLIC_CASES[family], context.evidence(label), "public", True) if binding else None
    hidden = compare_source(prior82, target_path, source, HIDDEN_CASES[family], context.evidence(label), "hidden", False) if binding else None
    valid = bool(public and hidden and public["both_valid"] and public["candidate_floor_passed"] and public["no_case_regression"] and hidden["both_valid"] and hidden["candidate_floor_passed"])
    admitted = bool(valid and hidden["gain"] >= MIN_HIDDEN_GAIN and hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION)
    body = {"authority": "ot-0087-sealed-actor-originated-contact-world", "opening_binding_digest": opening_run["binding"]["binding_digest"],
            "successor_binding_digest": binding["binding_digest"] if binding else None, "target_path": target_path,
            "public": public, "hidden": hidden, "valid": valid, "developmentally_admitted": admitted}
    world = {**body, "receipt_digest": prior82.digest(body)}
    (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding, "world": world}


def promote(prior82, intermediate: dict[str, Any], opening_run: dict[str, Any], successor: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    opening_binding = opening_run["binding"]
    implementation = successor["binding"]
    next_opening = implementation["successor_opening"]
    body = {"authority": "world-promoted-actor-originated-opening-handoff", "source_subject_digest": intermediate["artifact_digest"],
            "opening_binding_digest": opening_binding["binding_digest"], "successor_binding_digest": implementation["binding_digest"],
            "world_receipt_digest": successor["world"]["receipt_digest"], "target_path": implementation["target_path"]}
    receipt = {**body, "receipt_digest": prior82.digest(body)}
    child = copy.deepcopy(intermediate)
    child.pop("artifact_digest", None)
    child["pursuit_handoff_receipts"] = [*child.get("pursuit_handoff_receipts", []), receipt]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-successor-post-contact-opening", "source_opening_binding_digest": opening_binding["binding_digest"],
         "successor_binding_digest": implementation["binding_digest"], "opening": next_opening}]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []),
        {"target_path": implementation["target_path"], "target_symbol": implementation["target_symbol"],
         "source": implementation["source"], "source_digest": implementation["source_digest"],
         "world_receipt_digest": successor["world"]["receipt_digest"]}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"],
        {"selected_area": implementation["target_path"], "pursuit": next_opening["next_opening"],
         "patch_digest": successor["audit"]["patch_digest"], "world_receipt_digest": successor["world"]["receipt_digest"],
         "contact_program_digest": implementation["source_digest"]}]
    child["active_pursuit"] = {"authority": "fresh-successor-post-contact-opening", "selected_area": implementation["target_path"],
                               "next_pursuit": next_opening["next_opening"], "world_receipt_digest": successor["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": next_opening["next_opening"]}
    child["runtime"] = "sounding"
    child["unresolved"] = next_opening["continuation_after_contact"]
    return prior82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0087").resolve()
    prior86 = load_prior(repo)
    prior85 = prior86.load_prior(repo)
    prior84 = prior85.load_prior(repo)
    prior83 = prior84.load_prior(repo)
    prior82 = prior83.load_prior(repo)
    runtime = prior82.load_runtime(repo, store)
    parent = load_parent(prior86, prior82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != PARENT_DIGEST or parent["continuation"]["next_opening"] != "inspect-and-select-environmental-intervention":
        raise SystemExit("wrong OT-0086 open parent")
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior82, Path(directory))
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256,
                  "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0087 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior82, run / "fixture-conformance")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo)
    started = time.time()
    opening_run = run_opening(prior82, context, run, "opening-primary", parent)
    opening = opening_run["binding"]["opening"] if opening_run["binding"] else None
    intermediate = None
    successor = None
    promoted = None
    current = parent
    if opening_run["audit"]["conformant"] and opening and opening["status"] == "open":
        intermediate = bind_intermediate(prior82, parent, opening_run)
        (run / "sealed-intermediate-pursuit.json").write_text(json.dumps(intermediate, indent=2, sort_keys=True) + "\n")
        successor = run_successor(prior82, context, run, "successor-primary", intermediate, opening_run)
        if successor["audit"]["conformant"] and successor["binding"] and successor["world"]["developmentally_admitted"]:
            current, promoted = promote(prior82, intermediate, opening_run, successor)
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and
        current["continuation"]["status"] == "open" and successor and
        current["continuation"]["next_opening"] == successor["binding"]["successor_opening"]["next_opening"] and
        current["continuation"]["next_opening"] != "inspect-and-select-environmental-intervention" and
        len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1)
    control = None
    carrier_effect = False
    if operational_passed:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control_run = run_opening(prior82, context, run, "opening-erased-control", parent)
        primary_digest = opening_run["binding"]["binding_digest"]
        control_digest = control_run["binding"]["binding_digest"] if control_run["binding"] else None
        control = {"authority": "ot-0087-post-seal-opening-erased-control", "source_subject_digest": parent["artifact_digest"],
                   "primary_opening_binding_digest": primary_digest, "primary_opening_absent": True,
                   "control_originated_new_opening": bool(control_run["binding"]), "control_opening_binding_digest": control_digest,
                   "control": prior82.compact(control_run), "policy_edit_authorized": False}
        carrier_effect = bool(control_run["audit"]["conformant"] and control_digest != primary_digest and not any(path in TARGETS for path in control_run["audit"]["changed_paths"]))
    observer = "promoted" if operational_passed and carrier_effect else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0087-fixed-actor-originated-opening-handoff-driver", "source_subject_digest": parent["artifact_digest"],
              "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures,
              "opening": prior82.compact(opening_run), "intermediate_subject_digest": intermediate["artifact_digest"] if intermediate else None,
              "successor": prior82.compact(successor) if successor else None, "promotion_receipt": promoted,
              "operational_transition_passed": operational_passed, "carrier_effect_passed": carrier_effect, "control": control,
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
