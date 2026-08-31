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
PRIOR_PATH = ROOT / "ot_0082_world_routing.py"
PRIOR_SHA256 = "aa8acbc8749a4f3f994af2dac01123ac1e63d8802e602ae61a46d7073c556f92"
PLACEHOLDER = "__REPLACE__"


def load_prior(repo: Path = REPO):
    path = repo / "experiments/ot_0082_world_routing.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0082 implementation identity changed")
    name = "ot0083_frozen_ot0082"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(prior, repo: Path, store: Path) -> dict[str, Any]:
    _, path = prior.materialize(repo, store, "OT-0082", "open-subject-after-routing-rejection.json")
    return json.loads(path.read_text())


def assessment_template(surface_id: str) -> dict[str, Any]:
    return {
        "surface_id": surface_id,
        "axis_chord": 0,
        "reversibility": 0,
        "immediate_gain": 0,
        "axis_lumen": 0,
        "collision": False,
        "held_repeat": False,
        "irreversible_closure": False,
        "world_invalid": False,
        "rationale": PLACEHOLDER,
        "implementation_opening": PLACEHOLDER,
    }


def route_template(prior) -> dict[str, Any]:
    return {"assessments": [assessment_template(surface_id) for surface_id in prior.SURFACE_ORDER], "next_pursuit": PLACEHOLDER}


def route_contract(prior) -> dict[str, Any]:
    return {
        "exact_top_level_keys": ["assessments", "next_pursuit"],
        "surface_ids": list(prior.SURFACE_ORDER),
        "assessment_exact_keys": sorted(prior.ASSESSMENT_KEYS),
        "integer_fields": {key: {"minimum": 0, "maximum": 4} for key in ("axis_chord", "reversibility", "immediate_gain", "axis_lumen")},
        "boolean_fields": ["collision", "held_repeat", "irreversible_closure", "world_invalid"],
        "string_fields": ["rationale", "implementation_opening"],
        "top_level_string_fields": ["next_pursuit"],
        "instruction": "Replace every __REPLACE__ string; preserve every key, JSON type, surface identifier, and row count.",
    }


def valid_completed_route(prior, value: Any) -> bool:
    return prior.valid_route(value) and PLACEHOLDER not in json.dumps(value, sort_keys=True)


def representative_route(prior) -> dict[str, Any]:
    rows = []
    chord = {"surface-17": 1, "surface-42": 4, "surface-68": 2}
    for surface_id in prior.SURFACE_ORDER:
        row = assessment_template(surface_id)
        row.update({"axis_chord": chord[surface_id], "reversibility": 3, "immediate_gain": 2, "axis_lumen": 3, "held_repeat": surface_id == "surface-17", "rationale": "Representative bounded assessment.", "implementation_opening": "Implement the bound surface and test it."})
        rows.append(row)
    return {"assessments": rows, "next_pursuit": "Apply the inherited selector to the bound assessment."}


def contract_conformance(prior) -> dict[str, Any]:
    seeded = route_template(prior)
    completed = representative_route(prior)
    exact_seed_keys = set(seeded) == {"assessments", "next_pursuit"} and all(set(row) == prior.ASSESSMENT_KEYS for row in seeded["assessments"])
    result = {"seed_exact_keys": exact_seed_keys, "seed_rejected_with_placeholders": not valid_completed_route(prior, seeded), "representative_value_only_completion_passed": valid_completed_route(prior, completed), "representative_preserved_keys": [set(row) for row in seeded["assessments"]] == [set(row) for row in completed["assessments"]]}
    result["passed"] = all(result.values())
    return result


def routing_seed(prior, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    for surface_id in prior.SURFACE_ORDER:
        prior.materialize_surface(seed / "surfaces" / surface_id, surface_id)
    projection = {"subject_digest": subject["artifact_digest"], "continuation": subject["continuation"], "developmental_selector": subject["developmental_selector"], "held_capability_areas": [row.get("selected_area") for row in subject.get("tool_world_capabilities", [])], "denied_surface_ids": sorted(denied)}
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "route.json").write_text(json.dumps(route_template(prior), indent=2, sort_keys=True) + "\n")
    (seed / "route-contract.json").write_text(json.dumps(route_contract(prior), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Inspect subject-position.json, route-contract.json, and every surface under surfaces/. Do not implement one yet. Edit exactly route.json by replacing every placeholder and assigning all typed assessment fields. Preserve its complete shape. The fixed inherited selector will choose only after your file is audited and bound. Do not edit a surface.\n")
    return seed


def run_router(prior, context, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> dict[str, Any]:
    seed = routing_seed(prior, run, label, subject, denied)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Inspect the exact subject position, complete machine-readable route contract, populated route template, and all three real surfaces. Edit only route.json. Replace every placeholder, preserve the exact shape and types, inspect the diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, prior.ROUTING_SCHEMA, prompt)
    try:
        route = json.loads((workspace / "route.json").read_text())
    except (json.JSONDecodeError, OSError):
        route = None
    audit = context.audit_actor(label, output, base, valid_completed_route(prior, route), ["route.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0083-pre-selection-environment-assessment", "source_subject_digest": subject["artifact_digest"], "denied_surface_ids": sorted(denied), "actor_patch_digest": audit["patch_digest"], "route": route}
        binding = {**body, "binding_digest": prior.digest(body)}
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    selected = prior.active_select(subject, route, denied) if binding else None
    return {"label": label, "output": output, "audit": audit, "binding": binding, "selected_surface": selected}


def run_implementation(prior, context, run: Path, label: str, subject: dict[str, Any], route: dict[str, Any], surface_id: str) -> dict[str, Any]:
    seed = prior.implementation_seed(run, label, subject, route, surface_id)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Implement the exact bound environmental intervention. Edit only implementation.py, preserve the public contract and future extension, run useful tests, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, prior.IMPLEMENTATION_SCHEMA, prompt)
    source = (workspace / "implementation.py").read_text()
    changed = source != prior.SURFACES[surface_id]["source"]
    compiled = subprocess.run(["python3", "-m", "py_compile", "implementation.py"], cwd=workspace, capture_output=True)
    audit = context.audit_actor(label, output, base, changed and compiled.returncode == 0, ["implementation.py"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0083-pre-hidden-intervention-binding", "source_subject_digest": route["binding"]["source_subject_digest"], "route_binding_digest": route["binding"]["binding_digest"], "surface_id": surface_id, "actor_patch_digest": audit["patch_digest"], "source": source, "source_digest": prior.digest(source)}
        binding = {**body, "binding_digest": prior.digest(body)}
        (context.evidence(label) / "bound-intervention.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = prior.test_surface(source, surface_id, context.evidence(label), "sealed-world") if binding else {"public_hidden_passed": False, "developmental_class": "world-invalid"}
    (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding, "world": world}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0083").resolve()
    prior = load_prior(repo)
    runtime = prior.load_runtime(repo, store)
    parent = load_parent(prior, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != "1c04f340012e69dbd7a3783ab85d2d0e37667d5beb552f879b2ac20ab5dd7b73" or parent["continuation"]["next_opening"] != "inspect-and-select-environmental-intervention":
        raise SystemExit("wrong OT-0082 open parent")
    contract = contract_conformance(prior)
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            fixtures = prior.fixture_conformance(Path(directory))
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "contract_conformance": contract, "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True, default=list))
        return 0 if contract["passed"] and fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0083 evidence")
    run.mkdir(parents=True)
    started = time.time()
    fixtures = prior.fixture_conformance(run / "fixture-conformance")
    if not contract["passed"] or not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo)
    current = parent
    routes, implementations, denials = [], [], []
    promoted = None
    selected_route = None
    denied: set[str] = set()
    for attempt in range(1, prior.MAX_ROUTES + 1):
        route = run_router(prior, context, run, f"route-{attempt:02d}", current, denied)
        routes.append(route)
        if not route["selected_surface"]:
            break
        implementation = run_implementation(prior, context, run, f"implementation-{attempt:02d}", current, route, route["selected_surface"])
        implementations.append(implementation)
        if not (implementation["audit"]["conformant"] and implementation["binding"] and implementation["world"]["public_hidden_passed"]):
            break
        if implementation["world"]["developmental_class"] == "world-valid-held-primitive-repetition":
            current, denial = prior.compile_denial(current, route, implementation)
            denials.append(denial)
            denied.add(route["selected_surface"])
            continue
        current, promotion_receipt = prior.promote(current, route, implementation)
        promoted = promotion_receipt
        selected_route = route
        break
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open" and current["continuation"]["next_opening"] == "inspect-and-select-environmental-intervention" and len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1)
    control = None
    selector_effect = False
    if operational_passed and selected_route:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control_surface = prior.erased_select(selected_route["binding"]["route"])
        control_route = {**selected_route, "selected_surface": control_surface}
        control_impl = run_implementation(prior, context, run, "control-implementation", parent, control_route, control_surface) if control_surface else None
        control_class = control_impl["world"]["developmental_class"] if control_impl else "world-invalid"
        control = {"authority": "ot-0083-post-seal-selector-erased-control", "source_route_binding_digest": selected_route["binding"]["binding_digest"], "selected_surface": control_surface, "implementation": prior.compact(control_impl) if control_impl else None, "developmental_class": control_class, "developmentally_admitted": control_class in {"world-valid-novel-composition", "world-valid-novel-primitive"}}
        selector_effect = promoted["developmental_class"] in {"world-valid-novel-composition", "world-valid-novel-primitive"} and not control["developmentally_admitted"]
    observer = "promoted" if operational_passed and selector_effect else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0083-fixed-explicit-contract-world-routing-driver", "source_subject_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "contract_conformance": contract, "fixture_conformance": fixtures, "routes": [prior.compact(row) for row in routes], "implementations": [prior.compact(row) for row in implementations], "denial_receipts": denials, "promotion_receipt": promoted, "operational_transition_passed": operational_passed, "selector_effect_passed": selector_effect, "control": control, "observer_disposition": observer, "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = prior.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=list) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True, default=list))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
