from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import load_manifest, object_path, verify_artifact


ROOT = Path(__file__).parent
REPO = ROOT.parent
ROUTING_SCHEMA = REPO / "spec/ot-0082-routing.schema.json"
IMPLEMENTATION_SCHEMA = REPO / "spec/ot-0082-implementation.schema.json"
SATURATION_CASES = [(3109, 8), (3203, 10), (3301, 12)]
SURFACE_ORDER = ("surface-17", "surface-42", "surface-68")
MAX_ROUTES = 3
ASSESSMENT_KEYS = {
    "surface_id", "axis_chord", "reversibility", "immediate_gain", "axis_lumen",
    "collision", "held_repeat", "irreversible_closure", "world_invalid",
    "rationale", "implementation_opening",
}


CADENCE_SOURCE = '''def next_tone(events):
    """Return the next categorical tone from a repeating cycle."""
    raise NotImplementedError("continue the cadence")
'''

CADENCE_PUBLIC = '''import unittest
from implementation import next_tone

class PublicTests(unittest.TestCase):
    def test_two_cycles(self):
        self.assertEqual(next_tone(["a", "b", "a", "b"]), "a")
        self.assertEqual(next_tone(["red", "blue", "gold", "red", "blue"]), "gold")

if __name__ == "__main__":
    unittest.main()
'''

CADENCE_HIDDEN = '''import unittest
from implementation import next_tone

class HiddenTests(unittest.TestCase):
    def test_unseen_cycles(self):
        self.assertEqual(next_tone(["x", "x", "x"]), "x")
        self.assertEqual(next_tone(["q", "r", "s", "q", "r", "s", "q"]), "r")
        self.assertEqual(next_tone(["one", "two", "one"]), "two")
        self.assertEqual(next_tone(["a", "b", "c", "d", "a", "b"]), "c")

if __name__ == "__main__":
    unittest.main()
'''

BRIDGE_SOURCE = '''from __future__ import annotations

def count_routes(graph, start, end):
    """Count simple directed routes from start to end."""
    def visit(node, seen):
        if node == end:
            return 1
        return sum(visit(child, seen | {child}) for child in graph.get(node, []) if child not in seen)
    return visit(start, {start})

def predict_next(events):
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

def analyze_route_score(graph, start, end, events):
    """Return both the route count and predicted next score event."""
    raise NotImplementedError("compose the two completed operations")
'''

BRIDGE_PUBLIC = '''import unittest
from implementation import analyze_route_score

class PublicTests(unittest.TestCase):
    def test_joint_result(self):
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        events = [{"tick": 0, "span": 2, "tone": "x"},
                  {"tick": 3, "span": 3, "tone": "y"},
                  {"tick": 6, "span": 4, "tone": "x"}]
        self.assertEqual(analyze_route_score(graph, "a", "d", events),
                         {"route_count": 2, "next_event": {"tick": 9, "span": 5, "tone": "y"}})

if __name__ == "__main__":
    unittest.main()
'''

BRIDGE_HIDDEN = '''import unittest
from implementation import analyze_route_score

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

    def test_cycle_is_not_last_value(self):
        graph = {"s": ["a", "t"], "a": ["t"], "t": []}
        events = [{"tick": i * 2, "span": 20 - i, "tone": ("p", "q", "r")[i % 3]} for i in range(5)]
        self.assertEqual(analyze_route_score(graph, "s", "t", events)["next_event"]["tone"], "r")

if __name__ == "__main__":
    unittest.main()
'''

REGISTRY_SOURCE = '''class Registry:
    def __init__(self):
        self._values = {}

    def register(self, name, value):
        self._values[name] = value

    def resolve(self, name):
        return self._values[name]

    def resolve_many(self, names):
        """Resolve names efficiently without making later registration stale."""
        raise NotImplementedError("add a safe batch path")
'''

REGISTRY_PUBLIC = '''import unittest
from implementation import Registry

class PublicTests(unittest.TestCase):
    def test_batch(self):
        registry = Registry()
        registry.register("a", 1)
        registry.register("b", 2)
        self.assertEqual(registry.resolve_many(["b", "a", "b"]), [2, 1, 2])

if __name__ == "__main__":
    unittest.main()
'''

REGISTRY_HIDDEN = '''import unittest
from implementation import Registry

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

if __name__ == "__main__":
    unittest.main()
'''


SURFACES = {
    "surface-17": {
        "description": "Complete a categorical cadence continuation operation.",
        "source": CADENCE_SOURCE, "public": CADENCE_PUBLIC, "hidden": CADENCE_HIDDEN,
        "developmental_class": "world-valid-held-primitive-repetition",
    },
    "surface-42": {
        "description": "Compose ordered-route counting and score continuation behind one operation.",
        "source": BRIDGE_SOURCE, "public": BRIDGE_PUBLIC, "hidden": BRIDGE_HIDDEN,
        "developmental_class": "world-valid-novel-composition",
    },
    "surface-68": {
        "description": "Add mutable-registry batch resolution while preserving extension after warm use.",
        "source": REGISTRY_SOURCE, "public": REGISTRY_PUBLIC, "hidden": REGISTRY_HIDDEN,
        "developmental_class": "world-valid-novel-primitive",
    },
}


def digest(value: Any) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(value)
    child.pop("artifact_digest", None)
    child["artifact_digest"] = digest(child)
    return child


def materialize(repo: Path, store: Path, experiment: str, manifest_name: str) -> tuple[dict[str, Any], Path]:
    path = repo / "evidence/manifests" / experiment / manifest_name
    manifest = load_manifest(path)
    valid, message = verify_artifact(repo=repo, manifest_path=path, store=store)
    if not valid:
        raise RuntimeError(message)
    return manifest, object_path(store, manifest["sha256"])


def load_runtime(repo: Path, store: Path):
    _, path = materialize(repo, store, "OT-0080", "continuing-subject-harness.json")
    name = "ot0082_adopted_harness"
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(repo: Path, store: Path) -> dict[str, Any]:
    _, path = materialize(repo, store, "OT-0081", "open-subject-v3.json")
    return json.loads(path.read_text())


def load_ot0081(repo: Path):
    path = repo / "experiments/ot_0081_recurrence.py"
    name = "ot0082_ot0081_runtime"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def valid_assessment(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != ASSESSMENT_KEYS:
        return False
    integer_keys = ("axis_chord", "reversibility", "immediate_gain", "axis_lumen")
    boolean_keys = ("collision", "held_repeat", "irreversible_closure", "world_invalid")
    return all(isinstance(value[key], int) and not isinstance(value[key], bool) and 0 <= value[key] <= 4 for key in integer_keys) and all(isinstance(value[key], bool) for key in boolean_keys) and value["surface_id"] in SURFACE_ORDER and all(isinstance(value[key], str) and 0 < len(value[key].strip()) <= 2000 for key in ("rationale", "implementation_opening"))


def valid_route(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"assessments", "next_pursuit"} and isinstance(value["assessments"], list) and len(value["assessments"]) == 3 and all(valid_assessment(row) for row in value["assessments"]) and {row["surface_id"] for row in value["assessments"]} == set(SURFACE_ORDER) and isinstance(value["next_pursuit"], str) and bool(value["next_pursuit"].strip())


def active_select(subject: dict[str, Any], route: dict[str, Any], denied: set[str]) -> str | None:
    policy = subject["developmental_selector"]["executable_priority_policy"]
    threshold = subject["developmental_selector"]["threshold"]
    eligible = []
    for row in route["assessments"]:
        if row["surface_id"] in denied or any(row[key] for key in policy["reject_if_any"]):
            continue
        if row["axis_chord"] < threshold:
            continue
        eligible.append(row)
    if not eligible:
        return None
    eligible.sort(key=lambda row: tuple([-row[key] for key in policy["rank_descending"]] + [row["surface_id"]]))
    return eligible[0]["surface_id"]


def erased_select(route: dict[str, Any]) -> str | None:
    eligible = sorted(row["surface_id"] for row in route["assessments"] if not row["world_invalid"])
    return eligible[0] if eligible else None


def materialize_surface(root: Path, surface_id: str) -> None:
    surface = SURFACES[surface_id]
    root.mkdir(parents=True)
    (root / "implementation.py").write_text(surface["source"])
    (root / "test_public.py").write_text(surface["public"])
    metadata = {"surface_id": surface_id, "description": surface["description"], "editable": ["implementation.py"]}
    (root / "surface.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def test_surface(source: str, surface_id: str, evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    root.mkdir(parents=True)
    surface = SURFACES[surface_id]
    (root / "implementation.py").write_text(source)
    (root / "test_public.py").write_text(surface["public"])
    (root / "test_hidden.py").write_text(surface["hidden"])
    completed = subprocess.run(["python3", "-m", "unittest", "-q", "test_public.py", "test_hidden.py"], cwd=root, text=True, capture_output=True, timeout=30)
    body = {
        "authority": "ot-0082-sealed-tool-world",
        "surface_id": surface_id,
        "source_digest": digest(source),
        "public_hidden_passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout_digest": digest(completed.stdout),
        "stderr_digest": digest(completed.stderr),
        "developmental_class": surface["developmental_class"] if completed.returncode == 0 else "world-invalid",
    }
    return {**body, "receipt_digest": digest(body)}


def fixture_conformance(evidence: Path) -> dict[str, Any]:
    references = {
        "surface-17": CADENCE_SOURCE.replace('raise NotImplementedError("continue the cadence")', 'return next((events[len(events) % p] for p in range(1, len(events) + 1) if all(events[i] == events[i % p] for i in range(len(events)))), events[0])'),
        "surface-42": BRIDGE_SOURCE.replace('raise NotImplementedError("compose the two completed operations")', 'return {"route_count": count_routes(graph, start, end), "next_event": predict_next(events)}'),
        "surface-68": REGISTRY_SOURCE.replace('raise NotImplementedError("add a safe batch path")', 'return [self.resolve(name) for name in names]'),
    }
    rows = []
    for surface_id in SURFACE_ORDER:
        initial = test_surface(SURFACES[surface_id]["source"], surface_id, evidence, f"fixture-{surface_id}-initial")
        reference = test_surface(references[surface_id], surface_id, evidence, f"fixture-{surface_id}-reference")
        rows.append({"surface_id": surface_id, "initial_failed": not initial["public_hidden_passed"], "reference_passed": reference["public_hidden_passed"]})
    return {"rows": rows, "passed": all(row["initial_failed"] and row["reference_passed"] for row in rows)}


def compile_saturation(subject: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["challenge_machinery_saturation_receipts"] = [*child.get("challenge_machinery_saturation_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["unresolved"] = "Inspect the available environment and route through the inherited developmental selector."
    return seal(child)


def routing_seed(run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    for surface_id in SURFACE_ORDER:
        materialize_surface(seed / "surfaces" / surface_id, surface_id)
    projection = {
        "subject_digest": subject["artifact_digest"],
        "continuation": subject["continuation"],
        "developmental_selector": subject["developmental_selector"],
        "held_capability_areas": [row.get("selected_area") for row in subject.get("tool_world_capabilities", [])],
        "denied_surface_ids": sorted(denied),
    }
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "route.json").write_text(json.dumps({"assessments": [], "next_pursuit": ""}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Inspect subject-position.json and every surface under surfaces/. Do not implement one yet. "
        "Edit exactly route.json. Assess all three surfaces with the inherited selector axes and flags; "
        "the fixed scheduler, not you, will apply the executable ranking after your assessment is bound. "
        "Use ordinary tools to inspect source and public tests. Do not edit a surface.\n"
    )
    return seed


def run_router(context, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> dict[str, Any]:
    seed = routing_seed(run, label, subject, denied)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Inspect the inherited subject position and the three real tool-world surfaces. Make only the environmental assessment requested in README.md; do not pick by prose or modify an implementation. Exercise your inspection and return the required report after checking the exact diff."
    output, base, workspace, _ = context.run_actor(label, seed, ROUTING_SCHEMA, prompt)
    try:
        route = json.loads((workspace / "route.json").read_text())
    except (json.JSONDecodeError, OSError):
        route = None
    audit = context.audit_actor(label, output, base, valid_route(route), ["route.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0082-pre-selection-environment-assessment", "source_subject_digest": subject["artifact_digest"], "denied_surface_ids": sorted(denied), "actor_patch_digest": audit["patch_digest"], "route": route}
        binding = {**body, "binding_digest": digest(body)}
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    selected = active_select(subject, route, denied) if binding else None
    return {"label": label, "output": output, "audit": audit, "binding": binding, "selected_surface": selected}


def implementation_seed(run: Path, label: str, subject: dict[str, Any], route: dict[str, Any], surface_id: str) -> Path:
    seed = run / f"{label}-seed"
    materialize_surface(seed, surface_id)
    (seed / "route-binding.json").write_text(json.dumps({"subject_digest": route["binding"]["source_subject_digest"], "route_binding_digest": route["binding"]["binding_digest"], "selected_surface": surface_id}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("The inherited selector bound this surface before world outcome. Inspect the code, public tests, surface contract, and route binding. Edit exactly implementation.py. Preserve the interface, run useful tests, and inspect the exact diff. Hidden outcomes and admission are external.\n")
    return seed


def run_implementation(context, run: Path, label: str, subject: dict[str, Any], route: dict[str, Any], surface_id: str) -> dict[str, Any]:
    seed = implementation_seed(run, label, subject, route, surface_id)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Implement the exact bound environmental intervention. Make a real patch to implementation.py, preserve the public contract and future extension, run useful tests, and return the required report only after inspecting the exact diff."
    output, base, workspace, _ = context.run_actor(label, seed, IMPLEMENTATION_SCHEMA, prompt)
    source = (workspace / "implementation.py").read_text()
    changed = source != SURFACES[surface_id]["source"]
    compiled = subprocess.run(["python3", "-m", "py_compile", "implementation.py"], cwd=workspace, capture_output=True)
    audit = context.audit_actor(label, output, base, changed and compiled.returncode == 0, ["implementation.py"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0082-pre-hidden-intervention-binding", "source_subject_digest": route["binding"]["source_subject_digest"], "route_binding_digest": route["binding"]["binding_digest"], "surface_id": surface_id, "actor_patch_digest": audit["patch_digest"], "source": source, "source_digest": digest(source)}
        binding = {**body, "binding_digest": digest(body)}
        (context.evidence(label) / "bound-intervention.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = test_surface(source, surface_id, context.evidence(label), "sealed-world") if binding else {"public_hidden_passed": False, "developmental_class": "world-invalid"}
    (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding, "world": world}


def compile_denial(subject: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "subject-developmental-world-routing-denial", "source_subject_digest": subject["artifact_digest"], "route_binding_digest": route["binding"]["binding_digest"], "surface_id": route["selected_surface"], "world_receipt_digest": implementation["world"]["receipt_digest"], "developmental_class": implementation["world"]["developmental_class"], "developmentally_admitted": False}
    receipt = {**body, "receipt_digest": digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["world_routing_denial_receipts"] = [*child.get("world_routing_denial_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["unresolved"] = "Select a non-repeating environmental intervention using the retained denial."
    return seal(child), receipt


def promote(subject: dict[str, Any], route: dict[str, Any], implementation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "world-promoted-subject-owned-environmental-route", "source_subject_digest": subject["artifact_digest"], "route_binding_digest": route["binding"]["binding_digest"], "surface_id": route["selected_surface"], "intervention_binding_digest": implementation["binding"]["binding_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"], "developmental_class": implementation["world"]["developmental_class"]}
    receipt = {**body, "receipt_digest": digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["world_contact_routing_receipts"] = [*child.get("world_contact_routing_receipts", []), receipt]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []), {"surface_id": route["selected_surface"], "source": implementation["binding"]["source"], "source_digest": implementation["binding"]["source_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"], {"selected_area": route["selected_surface"], "pursuit": implementation["output"]["next_pursuit"], "patch_digest": implementation["audit"]["patch_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"], "contact_program_digest": implementation["binding"]["source_digest"]}]
    child["active_pursuit"] = {"authority": "world-promoted-environmental-route", "selected_area": route["selected_surface"], "next_pursuit": implementation["output"]["next_pursuit"], "world_receipt_digest": implementation["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "inspect-and-select-environmental-intervention"}
    child["runtime"] = "sounding"
    child["unresolved"] = "Inspect the environment again and continue from the expanded capability ledger."
    return seal(child), receipt


def compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: child for key, child in value.items() if key not in {"workspace"}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0082").resolve()
    runtime = load_runtime(repo, store)
    ot0081 = load_ot0081(repo)
    parent = load_parent(repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent):
        raise SystemExit("invalid OT-0081 parent")
    if parent["artifact_digest"] != "c55166a1805e3ef96f059832d7199f39e53a778bad301a600d2df1c8927ec128" or parent["challenge_machinery"][-1].get("version") != 3 or parent["executable_capabilities"][-1]["version"] != 5 or parent["continuation"]["next_opening"] != "execute-subject-owned-challenge-machinery":
        raise SystemExit("wrong OT-0081 parent position")
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = fixture_conformance(root)
            context = runtime.Context(root / "subject", repo)
            saturation = ot0081.evaluate_generator(context, parent["challenge_machinery"][-1]["generator_source"], parent["executable_capabilities"][-1]["program"], SATURATION_CASES, "saturation", "ot-0082-preflight-saturation")
        result = {"parent_digest": parent["artifact_digest"], "fixture_conformance": fixtures, "saturation_passed": saturation["saturated"]}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] and saturation["saturated"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0082 evidence")
    run.mkdir(parents=True)
    started = time.time()
    fixtures = fixture_conformance(run / "fixture-conformance")
    if not fixtures["passed"]:
        raise SystemExit("fixture conformance failed")
    context = runtime.Context(run, repo)
    saturation = ot0081.evaluate_generator(context, parent["challenge_machinery"][-1]["generator_source"], parent["executable_capabilities"][-1]["program"], SATURATION_CASES, "saturation", "ot-0082-sealed-subject-machinery-saturation")
    current = compile_saturation(parent, saturation) if saturation["saturated"] else parent
    routes, implementations, denials = [], [], []
    promoted = None
    selected_route = None
    denied: set[str] = set()
    if saturation["saturated"]:
        for attempt in range(1, MAX_ROUTES + 1):
            route = run_router(context, run, f"route-{attempt:02d}", current, denied)
            routes.append(route)
            if not route["selected_surface"]:
                break
            implementation = run_implementation(context, run, f"implementation-{attempt:02d}", current, route, route["selected_surface"])
            implementations.append(implementation)
            if not (implementation["audit"]["conformant"] and implementation["binding"] and implementation["world"]["public_hidden_passed"]):
                break
            if implementation["world"]["developmental_class"] == "world-valid-held-primitive-repetition":
                current, denial = compile_denial(current, route, implementation)
                denials.append(denial)
                denied.add(route["selected_surface"])
                continue
            current, promotion_receipt = promote(current, route, implementation)
            promoted = promotion_receipt
            selected_route = route
            break
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open" and current["continuation"]["next_opening"] == "inspect-and-select-environmental-intervention" and len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1)
    control = None
    selector_effect = False
    if operational_passed and selected_route:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control_surface = erased_select(selected_route["binding"]["route"])
        control_route = {**selected_route, "selected_surface": control_surface}
        control_impl = run_implementation(context, run, "control-implementation", parent, control_route, control_surface) if control_surface else None
        control_class = control_impl["world"]["developmental_class"] if control_impl else "world-invalid"
        control = {"authority": "ot-0082-post-seal-selector-erased-control", "source_route_binding_digest": selected_route["binding"]["binding_digest"], "selected_surface": control_surface, "implementation": compact(control_impl) if control_impl else None, "developmental_class": control_class, "developmentally_admitted": control_class in {"world-valid-novel-composition", "world-valid-novel-primitive"}}
        selector_effect = promoted["developmental_class"] in {"world-valid-novel-composition", "world-valid-novel-primitive"} and not control["developmentally_admitted"]
    observer = "promoted" if operational_passed and selector_effect else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0082-fixed-subject-world-routing-driver", "source_subject_digest": parent["artifact_digest"], "fixture_conformance": fixtures, "saturation_receipt": saturation, "saturation_passed": saturation["saturated"], "routes": [compact(row) for row in routes], "implementations": [compact(row) for row in implementations], "denial_receipts": denials, "promotion_receipt": promoted, "operational_transition_passed": operational_passed, "selector_effect_passed": selector_effect, "control": control, "observer_disposition": observer, "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
