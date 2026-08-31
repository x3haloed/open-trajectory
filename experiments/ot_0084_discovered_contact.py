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
PRIOR_PATH = ROOT / "ot_0083_explicit_routing.py"
PRIOR_SHA256 = "9371a7bfaf1587472e61c89c158229ec21f63f7b977cbb8e97a634168f4137b4"
DISCOVERY_SCHEMA = REPO / "spec/ot-0084-discovery.schema.json"
IMPLEMENTATION_SCHEMA = REPO / "spec/ot-0084-implementation.schema.json"
PLACEHOLDER = "__REPLACE__"
MAX_ATTEMPTS = 3
INTEGER_FIELDS = ("axis_chord", "reversibility", "immediate_gain", "axis_lumen")
BOOLEAN_FIELDS = ("collision", "held_repeat", "irreversible_closure", "world_invalid")
CANDIDATE_KEYS = {
    "target_path", "target_symbol", *INTEGER_FIELDS, *BOOLEAN_FIELDS,
    "rationale", "implementation_opening",
}


ROUTES_SOURCE = '''def count_routes(graph, start, end):
    """Count simple directed routes from start to end."""
    def visit(node, seen):
        if node == end:
            return 1
        return sum(visit(child, seen | {child}) for child in graph.get(node, []) if child not in seen)
    return visit(start, {start})
'''

SCORE_SOURCE = '''def predict_next(events):
    """Continue arithmetic tick/span fields and the shortest repeating tone cycle."""
    if len(events) < 2:
        raise ValueError("at least two events are required")
    tick_step = events[-1]["tick"] - events[-2]["tick"]
    span_step = events[-1]["span"] - events[-2]["span"]
    tones = [row["tone"] for row in events]
    period = next((p for p in range(1, len(tones) + 1)
                   if all(tones[i] == tones[i % p] for i in range(len(tones)))), len(tones))
    return {"tick": events[-1]["tick"] + tick_step,
            "span": events[-1]["span"] + span_step,
            "tone": tones[len(tones) % period]}
'''

CADENCE_SOURCE = '''def next_tone(events):
    """Return the next tone from the shortest repeating categorical cycle."""
    raise NotImplementedError("cadence continuation is not implemented")
'''

REPORT_SOURCE = '''from .routes import count_routes
from .score import predict_next

def analyze_route_score(graph, start, end, events):
    """Return one report containing route count and predicted next score event."""
    raise NotImplementedError("joint route/score analysis is not implemented")
'''

REGISTRY_SOURCE = '''class Registry:
    def __init__(self):
        self._values = {}

    def register(self, name, value):
        self._values[name] = value

    def resolve(self, name):
        return self._values[name]

    def resolve_many(self, names):
        """Resolve names in order while preserving later registration changes."""
        raise NotImplementedError("batch resolution is not implemented")
'''

FLOOR_TEST = '''import unittest
from workbench.registry import Registry
from workbench.routes import count_routes
from workbench.score import predict_next

class FloorTests(unittest.TestCase):
    def test_route_floor(self):
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        self.assertEqual(count_routes(graph, "a", "d"), 2)

    def test_score_floor(self):
        events = [{"tick": 0, "span": 2, "tone": "x"},
                  {"tick": 3, "span": 3, "tone": "y"},
                  {"tick": 6, "span": 4, "tone": "x"}]
        self.assertEqual(predict_next(events), {"tick": 9, "span": 5, "tone": "y"})

    def test_registry_floor(self):
        registry = Registry()
        registry.register("a", 1)
        self.assertEqual(registry.resolve("a"), 1)

if __name__ == "__main__":
    unittest.main()
'''

CADENCE_HIDDEN = '''import unittest
from workbench.cadence import next_tone

class HiddenTests(unittest.TestCase):
    def test_unseen_cycles(self):
        self.assertEqual(next_tone(["x", "x", "x"]), "x")
        self.assertEqual(next_tone(["q", "r", "s", "q", "r", "s", "q"]), "r")
        self.assertEqual(next_tone(["one", "two", "one"]), "two")
        self.assertEqual(next_tone(["a", "b", "c", "d", "a", "b"]), "c")
'''

REPORT_HIDDEN = '''import unittest
from workbench.report import analyze_route_score

class HiddenTests(unittest.TestCase):
    def test_cross_products(self):
        cases = [
            ({"s": ["a", "b"], "a": ["t"], "b": ["c", "t"], "c": ["t"], "t": []},
             [{"tick": 10, "span": 8, "tone": "a"}, {"tick": 8, "span": 10, "tone": "b"},
              {"tick": 6, "span": 12, "tone": "c"}, {"tick": 4, "span": 14, "tone": "a"}],
             {"route_count": 3, "next_event": {"tick": 2, "span": 16, "tone": "b"}}),
            ({"s": ["t"], "t": []},
             [{"tick": -1, "span": 5, "tone": "z"}, {"tick": 4, "span": 4, "tone": "z"}],
             {"route_count": 1, "next_event": {"tick": 9, "span": 3, "tone": "z"}}),
        ]
        for graph, events, expected in cases:
            self.assertEqual(analyze_route_score(graph, "s", "t", events), expected)
'''

REGISTRY_HIDDEN = '''import unittest
from workbench.registry import Registry

class HiddenTests(unittest.TestCase):
    def test_registration_after_warm_batch(self):
        registry = Registry()
        registry.register("a", 1)
        self.assertEqual(registry.resolve_many(["a"]), [1])
        registry.register("a", 3)
        registry.register("b", 2)
        self.assertEqual(registry.resolve_many(["a", "b"]), [3, 2])

    def test_missing_name_remains_visible(self):
        registry = Registry()
        with self.assertRaises(KeyError):
            registry.resolve_many(["missing"])
'''

UNKNOWN_HIDDEN = '''import unittest

class HiddenTests(unittest.TestCase):
    def test_no_frozen_new_capability(self):
        self.fail("the bound target has no prospectively frozen hidden opportunity")
'''

ENVIRONMENT_FILES = {
    "workbench/__init__.py": "",
    "workbench/routes.py": ROUTES_SOURCE,
    "workbench/score.py": SCORE_SOURCE,
    "workbench/cadence.py": CADENCE_SOURCE,
    "workbench/report.py": REPORT_SOURCE,
    "workbench/registry.py": REGISTRY_SOURCE,
    "tests/__init__.py": "",
    "tests/test_floor.py": FLOOR_TEST,
}

OPPORTUNITIES = {
    "workbench/cadence.py": {
        "symbol": "next_tone",
        "hidden": CADENCE_HIDDEN,
        "developmental_class": "world-valid-held-primitive-repetition",
        "reference": CADENCE_SOURCE.replace('raise NotImplementedError("cadence continuation is not implemented")', 'return next((events[len(events) % p] for p in range(1, len(events) + 1) if all(events[i] == events[i % p] for i in range(len(events)))), events[0])'),
    },
    "workbench/report.py": {
        "symbol": "analyze_route_score",
        "hidden": REPORT_HIDDEN,
        "developmental_class": "world-valid-novel-composition",
        "reference": REPORT_SOURCE.replace('raise NotImplementedError("joint route/score analysis is not implemented")', 'return {"route_count": count_routes(graph, start, end), "next_event": predict_next(events)}'),
    },
    "workbench/registry.py": {
        "symbol": "Registry.resolve_many",
        "hidden": REGISTRY_HIDDEN,
        "developmental_class": "world-valid-novel-primitive",
        "reference": REGISTRY_SOURCE.replace('raise NotImplementedError("batch resolution is not implemented")', 'return [self.resolve(name) for name in names]'),
    },
}


def load_prior(repo: Path = REPO):
    path = repo / "experiments/ot_0083_explicit_routing.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0083 implementation identity changed")
    name = "ot0084_frozen_ot0083"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(prior83, prior82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = prior82.materialize(repo, store, "OT-0083", "open-subject-after-world-routing.json")
    return json.loads(path.read_text())


def write_environment(root: Path) -> None:
    for relative, source in ENVIRONMENT_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def target_symbols(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    result = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result.add(f"{node.name}.{child.name}")
    return result


def candidate_template() -> dict[str, Any]:
    row = {"target_path": PLACEHOLDER, "target_symbol": PLACEHOLDER}
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
        "target_path_rule": "existing workbench/*.py file; three distinct paths",
        "target_symbol_rule": "existing top-level function or Class.method in target_path",
        "integer_fields": {key: {"minimum": 0, "maximum": 4} for key in INTEGER_FIELDS},
        "boolean_fields": list(BOOLEAN_FIELDS),
        "string_fields": ["rationale", "implementation_opening", "next_pursuit"],
        "instruction": "Replace every __REPLACE__ string. Preserve all keys and JSON types. Inspect the repository to author the candidates; do not directly select one.",
    }


def valid_candidate(value: Any, environment: Path) -> bool:
    if not isinstance(value, dict) or set(value) != CANDIDATE_KEYS:
        return False
    if not all(isinstance(value[key], int) and not isinstance(value[key], bool) and 0 <= value[key] <= 4 for key in INTEGER_FIELDS):
        return False
    if not all(isinstance(value[key], bool) for key in BOOLEAN_FIELDS):
        return False
    if not all(isinstance(value[key], str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 2000 for key in ("target_path", "target_symbol", "rationale", "implementation_opening")):
        return False
    path = Path(value["target_path"])
    if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "workbench" or path.suffix != ".py":
        return False
    source_path = environment / path
    return source_path.is_file() and value["target_symbol"] in target_symbols(source_path.read_text())


def valid_frontier(value: Any, environment: Path) -> bool:
    if not isinstance(value, dict) or set(value) != {"candidates", "next_pursuit"} or not isinstance(value["candidates"], list) or len(value["candidates"]) != 3:
        return False
    if not isinstance(value["next_pursuit"], str) or not value["next_pursuit"].strip() or PLACEHOLDER in value["next_pursuit"]:
        return False
    if not all(valid_candidate(row, environment) for row in value["candidates"]):
        return False
    targets = [(row["target_path"], row["target_symbol"]) for row in value["candidates"]]
    return len(set(targets)) == 3 and len({row["target_path"] for row in value["candidates"]}) == 3


def candidate_identity(prior82, value: dict[str, Any]) -> str:
    return prior82.digest({key: value[key] for key in ("target_path", "target_symbol", "implementation_opening")})


def bind_frontier(prior82, subject: dict[str, Any], value: dict[str, Any], audit: dict[str, Any], denied: set[str]) -> dict[str, Any]:
    candidates = [{**copy.deepcopy(row), "candidate_id": candidate_identity(prior82, row)} for row in value["candidates"]]
    body = {"authority": "ot-0084-pre-selection-actor-discovered-frontier", "source_subject_digest": subject["artifact_digest"], "denied_target_paths": sorted(denied), "actor_patch_digest": audit["patch_digest"], "frontier": {"candidates": candidates, "next_pursuit": value["next_pursuit"]}}
    return {**body, "binding_digest": prior82.digest(body)}


def active_select(subject: dict[str, Any], binding: dict[str, Any], denied: set[str]) -> dict[str, Any] | None:
    policy = subject["developmental_selector"]["executable_priority_policy"]
    threshold = subject["developmental_selector"]["threshold"]
    eligible = []
    for row in binding["frontier"]["candidates"]:
        if row["target_path"] in denied or any(row[key] for key in policy["reject_if_any"]):
            continue
        if row["axis_chord"] < threshold:
            continue
        eligible.append(row)
    eligible.sort(key=lambda row: tuple([-row[key] for key in policy["rank_descending"]] + [row["candidate_id"]]))
    return eligible[0] if eligible else None


def erased_select(binding: dict[str, Any]) -> dict[str, Any] | None:
    eligible = [row for row in binding["frontier"]["candidates"] if not row["world_invalid"]]
    eligible.sort(key=lambda row: (row["target_path"], row["target_symbol"], row["candidate_id"]))
    return eligible[0] if eligible else None


def representative_frontier() -> dict[str, Any]:
    rows = []
    definitions = [
        ("workbench/cadence.py", "next_tone", 1, True, "Complete the held cadence operation."),
        ("workbench/report.py", "analyze_route_score", 4, False, "Compose route and score floors."),
        ("workbench/registry.py", "Registry.resolve_many", 2, False, "Add extension-preserving batch resolution."),
    ]
    for path, symbol, chord, held, opening in definitions:
        row = candidate_template()
        row.update({"target_path": path, "target_symbol": symbol, "axis_chord": chord, "reversibility": 4, "immediate_gain": 3, "axis_lumen": 3, "held_repeat": held, "rationale": "Representative repository-derived candidate.", "implementation_opening": opening})
        rows.append(row)
    return {"candidates": rows, "next_pursuit": "Apply the inherited selector to the bound discovered frontier."}


def contract_conformance(environment: Path) -> dict[str, Any]:
    seeded = frontier_template()
    representative = representative_frontier()
    duplicate = copy.deepcopy(representative)
    duplicate["candidates"][2]["target_path"] = duplicate["candidates"][1]["target_path"]
    duplicate["candidates"][2]["target_symbol"] = duplicate["candidates"][1]["target_symbol"]
    missing = copy.deepcopy(representative)
    missing["candidates"][1]["target_symbol"] = "missing_symbol"
    result = {
        "seed_exact_keys": set(seeded) == {"candidates", "next_pursuit"} and all(set(row) == CANDIDATE_KEYS for row in seeded["candidates"]),
        "seed_rejected_with_placeholders": not valid_frontier(seeded, environment),
        "representative_passed": valid_frontier(representative, environment),
        "duplicate_rejected": not valid_frontier(duplicate, environment),
        "missing_symbol_rejected": not valid_frontier(missing, environment),
    }
    result["passed"] = all(result.values())
    return result


def test_intervention(prior82, target_path: str, source: str, evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    write_environment(root)
    target = root / target_path
    target.write_text(source)
    opportunity = OPPORTUNITIES.get(target_path)
    (root / "tests/test_hidden.py").write_text(opportunity["hidden"] if opportunity else UNKNOWN_HIDDEN)
    completed = subprocess.run(["python3", "-m", "unittest", "-q", "tests.test_floor", "tests.test_hidden"], cwd=root, text=True, capture_output=True, timeout=30)
    passed = completed.returncode == 0
    body = {
        "authority": "ot-0084-sealed-discovered-contact-world",
        "target_path": target_path,
        "source_digest": prior82.digest(source),
        "floor_and_hidden_passed": passed,
        "returncode": completed.returncode,
        "stdout_digest": prior82.digest(completed.stdout),
        "stderr_digest": prior82.digest(completed.stderr),
        "developmental_class": opportunity["developmental_class"] if passed and opportunity else "world-invalid",
    }
    return {**body, "receipt_digest": prior82.digest(body)}


def fixture_conformance(prior82, evidence: Path) -> dict[str, Any]:
    rows = []
    for target_path, opportunity in OPPORTUNITIES.items():
        initial = test_intervention(prior82, target_path, ENVIRONMENT_FILES[target_path], evidence, f"{Path(target_path).stem}-initial")
        reference = test_intervention(prior82, target_path, opportunity["reference"], evidence, f"{Path(target_path).stem}-reference")
        rows.append({"target_path": target_path, "initial_failed": not initial["floor_and_hidden_passed"], "reference_passed": reference["floor_and_hidden_passed"]})
    return {"rows": rows, "passed": all(row["initial_failed"] and row["reference_passed"] for row in rows)}


def discovery_seed(run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed)
    projection = {"subject_digest": subject["artifact_digest"], "continuation": subject["continuation"], "developmental_selector": subject["developmental_selector"], "held_capability_areas": [row.get("selected_area") for row in subject.get("tool_world_capabilities", [])], "denied_target_paths": sorted(denied)}
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "frontier.json").write_text(json.dumps(frontier_template(), indent=2, sort_keys=True) + "\n")
    (seed / "frontier-contract.json").write_text(json.dumps(frontier_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("This small workbench is incomplete, but its development surfaces are not enumerated for you. Inspect subject-position.json, the package, and its tests with ordinary tools. Edit exactly frontier.json to formulate three distinct coherent interventions from what you find. Replace every placeholder and preserve the complete machine-readable shape. Do not edit the package and do not directly select a candidate; the inherited selector runs only after your frontier is audited and bound.\n")
    return seed


def run_discovery(prior82, context, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> dict[str, Any]:
    seed = discovery_seed(run, label, subject, denied)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Inspect the inherited subject position and this unenumerated repository. Discover and assess exactly three distinct development contacts by completing frontier.json. Follow frontier-contract.json exactly, edit no code, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, DISCOVERY_SCHEMA, prompt)
    try:
        frontier = json.loads((workspace / "frontier.json").read_text())
    except (json.JSONDecodeError, OSError):
        frontier = None
    audit = context.audit_actor(label, output, base, valid_frontier(frontier, workspace), ["frontier.json"])
    binding = bind_frontier(prior82, subject, frontier, audit, denied) if audit["conformant"] else None
    if binding:
        (context.evidence(label) / "bound-frontier.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    selected = active_select(subject, binding, denied) if binding else None
    return {"label": label, "output": output, "audit": audit, "binding": binding, "selected_candidate": selected}


def implementation_seed(run: Path, label: str, route: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(seed)
    selected = route["selected_candidate"]
    projection = {"frontier_binding_digest": route["binding"]["binding_digest"], "source_subject_digest": route["binding"]["source_subject_digest"], "selected_candidate": selected, "editable": [selected["target_path"]]}
    (seed / "bound-contact.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(f"The inherited selector chose the bound actor-discovered contact in bound-contact.json. Edit exactly {selected['target_path']}. Preserve all inherited floors, implement the stated opening, run useful tests, and inspect the exact diff. Hidden outcome and admission remain external.\n")
    return seed


def run_implementation(prior82, context, run: Path, label: str, route: dict[str, Any]) -> dict[str, Any]:
    selected = route["selected_candidate"]
    seed = implementation_seed(run, label, route)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Implement the exact bound contact in the repository. Edit only its declared target path, preserve inherited behavior, run useful checks, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, IMPLEMENTATION_SCHEMA, prompt)
    target = workspace / selected["target_path"]
    source = target.read_text()
    changed = source != ENVIRONMENT_FILES[selected["target_path"]]
    compiled = subprocess.run(["python3", "-m", "compileall", "-q", "workbench"], cwd=workspace, capture_output=True)
    audit = context.audit_actor(label, output, base, changed and compiled.returncode == 0, [selected["target_path"]])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0084-pre-hidden-discovered-intervention-binding", "source_subject_digest": route["binding"]["source_subject_digest"], "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"], "target_path": selected["target_path"], "target_symbol": selected["target_symbol"], "actor_patch_digest": audit["patch_digest"], "source": source, "source_digest": prior82.digest(source)}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-intervention.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = test_intervention(prior82, selected["target_path"], source, context.evidence(label), "sealed-world") if binding else {"floor_and_hidden_passed": False, "developmental_class": "world-invalid"}
    (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding, "world": world}


def compile_denial(prior82, subject: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = route["selected_candidate"]
    body = {"authority": "subject-discovered-contact-developmental-denial", "source_subject_digest": subject["artifact_digest"], "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"], "target_path": selected["target_path"], "world_receipt_digest": implementation["world"]["receipt_digest"], "developmental_class": implementation["world"]["developmental_class"], "developmentally_admitted": False}
    receipt = {**body, "receipt_digest": prior82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["discovered_contact_denial_receipts"] = [*child.get("discovered_contact_denial_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["unresolved"] = "Discover a non-repeating environmental contact using the retained denial."
    return prior82.seal(child), receipt


def promote(prior82, subject: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = route["selected_candidate"]
    body = {"authority": "world-promoted-actor-discovered-environmental-contact", "source_subject_digest": subject["artifact_digest"], "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"], "target_path": selected["target_path"], "intervention_binding_digest": implementation["binding"]["binding_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"], "developmental_class": implementation["world"]["developmental_class"]}
    receipt = {**body, "receipt_digest": prior82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["discovered_environmental_frontiers"] = [*child.get("discovered_environmental_frontiers", []), {"binding_digest": route["binding"]["binding_digest"], "candidate_ids": [row["candidate_id"] for row in route["binding"]["frontier"]["candidates"]], "selected_candidate_id": selected["candidate_id"]}]
    child["world_contact_routing_receipts"] = [*child.get("world_contact_routing_receipts", []), receipt]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []), {"candidate_id": selected["candidate_id"], "target_path": selected["target_path"], "target_symbol": selected["target_symbol"], "source": implementation["binding"]["source"], "source_digest": implementation["binding"]["source_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"], {"selected_area": selected["target_path"], "pursuit": implementation["output"]["next_pursuit"], "patch_digest": implementation["audit"]["patch_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"], "contact_program_digest": implementation["binding"]["source_digest"]}]
    child["active_pursuit"] = {"authority": "world-promoted-actor-discovered-contact", "selected_area": selected["target_path"], "next_pursuit": implementation["output"]["next_pursuit"], "world_receipt_digest": implementation["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["runtime"] = "sounding"
    child["unresolved"] = "Inspect another environment and continue from the actor-discovered capability."
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
    run = (args.evidence_root or store / "runs/OT-0084").resolve()
    prior83 = load_prior(repo)
    prior82 = prior83.load_prior(repo)
    runtime = prior82.load_runtime(repo, store)
    parent = load_parent(prior83, prior82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != "8ba78ade10b5f19f56a079c0de195a83c1309506e852ddff76659d284ec83896" or parent["continuation"]["next_opening"] != "inspect-and-select-environmental-intervention":
        raise SystemExit("wrong OT-0083 open parent")
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / "environment"
            write_environment(environment)
            contract = contract_conformance(environment)
            fixtures = fixture_conformance(prior82, root / "fixtures")
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "contract_conformance": contract, "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if contract["passed"] and fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0084 evidence")
    run.mkdir(parents=True)
    conformance_environment = run / "contract-environment"
    write_environment(conformance_environment)
    contract = contract_conformance(conformance_environment)
    fixtures = fixture_conformance(prior82, run / "fixture-conformance")
    if not contract["passed"] or not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo)
    started = time.time()
    current = parent
    discoveries, implementations, denials = [], [], []
    promoted = None
    selected_route = None
    denied: set[str] = set()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        route = run_discovery(prior82, context, run, f"discovery-{attempt:02d}", current, denied)
        discoveries.append(route)
        if not route["selected_candidate"]:
            break
        implementation = run_implementation(prior82, context, run, f"implementation-{attempt:02d}", route)
        implementations.append(implementation)
        if not (implementation["audit"]["conformant"] and implementation["binding"] and implementation["world"]["floor_and_hidden_passed"]):
            break
        if implementation["world"]["developmental_class"] in {"world-valid-held-primitive-repetition", "world-valid-held-floor-modification"}:
            current, denial = compile_denial(prior82, current, route, implementation)
            denials.append(denial)
            denied.add(route["selected_candidate"]["target_path"])
            continue
        current, promotion_receipt = promote(prior82, current, route, implementation)
        promoted = promotion_receipt
        selected_route = route
        break
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open" and current["continuation"]["next_opening"] == "inspect-and-select-environmental-intervention" and len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1 and len(current.get("discovered_environmental_frontiers", [])) == len(parent.get("discovered_environmental_frontiers", [])) + 1)
    control = None
    selector_effect = False
    if operational_passed and selected_route:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control_candidate = erased_select(selected_route["binding"])
        control_route = {**selected_route, "selected_candidate": control_candidate}
        control_impl = run_implementation(prior82, context, run, "control-implementation", control_route) if control_candidate else None
        control_class = control_impl["world"]["developmental_class"] if control_impl else "world-invalid"
        control = {"authority": "ot-0084-post-seal-selector-erased-control", "source_frontier_binding_digest": selected_route["binding"]["binding_digest"], "selected_candidate": control_candidate, "implementation": prior82.compact(control_impl) if control_impl else None, "developmental_class": control_class, "developmentally_admitted": control_class in {"world-valid-novel-composition", "world-valid-novel-primitive"}}
        selector_effect = promoted["developmental_class"] in {"world-valid-novel-composition", "world-valid-novel-primitive"} and not control["developmentally_admitted"]
    observer = "promoted" if operational_passed and selector_effect else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0084-fixed-actor-discovered-contact-driver", "source_subject_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "contract_conformance": contract, "fixture_conformance": fixtures, "discoveries": [prior82.compact(row) for row in discoveries], "implementations": [prior82.compact(row) for row in implementations], "denial_receipts": denials, "promotion_receipt": promoted, "operational_transition_passed": operational_passed, "selector_effect_passed": selector_effect, "control": control, "observer_disposition": observer, "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = prior82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
