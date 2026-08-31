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
PRIOR_SHA256 = "d08a19ce44f1628b5f1d67d9250eac77dbe3d6909bd38c3e6391fbc4e92853ae"
REPORT_ABI = '{"route_count": count_routes(...), "next_event": predict_next(events)}'


def load_prior(repo: Path = REPO):
    path = repo / "experiments/ot_0084_discovered_contact.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0084 implementation identity changed")
    name = "ot0085_frozen_ot0084"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def report_source(prior) -> str:
    old = '"""Return one report containing route count and predicted next score event."""'
    new = f'"""Return {REPORT_ABI}."""'
    if prior.REPORT_SOURCE.count(old) != 1:
        raise RuntimeError("unexpected OT-0084 report source")
    return prior.REPORT_SOURCE.replace(old, new)


def environment_files(prior) -> dict[str, str]:
    return {**prior.ENVIRONMENT_FILES, "workbench/report.py": report_source(prior)}


def write_environment(prior, root: Path) -> None:
    for relative, source in environment_files(prior).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def source_delta_conforms(prior) -> bool:
    before = prior.REPORT_SOURCE.splitlines()
    after = report_source(prior).splitlines()
    differences = [(left, right) for left, right in zip(before, after) if left != right]
    return len(before) == len(after) and differences == [
        ('    """Return one report containing route count and predicted next score event."""',
         f'    """Return {REPORT_ABI}."""')
    ]


def abi_conformance(prior) -> dict[str, Any]:
    visible = report_source(prior)
    hidden = prior.REPORT_HIDDEN
    result = {
        "report_only_source_delta": source_delta_conforms(prior),
        "visible_route_count_key": '"route_count"' in visible,
        "visible_next_event_key": '"next_event"' in visible,
        "hidden_route_count_key": '"route_count"' in hidden,
        "hidden_next_event_key": '"next_event"' in hidden,
        "prior_next_score_not_required": '"next_score"' not in hidden,
    }
    result["passed"] = all(result.values())
    return result


def load_parent(prior, prior83, prior82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = prior82.materialize(repo, store, "OT-0084", "reopened-parent-after-discovered-contact-rejection.json")
    return json.loads(path.read_text())


def opportunity(prior, target_path: str) -> dict[str, Any] | None:
    return prior.OPPORTUNITIES.get(target_path)


def test_intervention(prior, prior82, target_path: str, source: str, evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    write_environment(prior, root)
    (root / target_path).write_text(source)
    selected = opportunity(prior, target_path)
    (root / "tests/test_hidden.py").write_text(selected["hidden"] if selected else prior.UNKNOWN_HIDDEN)
    completed = subprocess.run(["python3", "-m", "unittest", "-q", "tests.test_floor", "tests.test_hidden"], cwd=root, text=True, capture_output=True, timeout=30)
    passed = completed.returncode == 0
    body = {"authority": "ot-0085-sealed-explicit-abi-world", "target_path": target_path, "source_digest": prior82.digest(source), "floor_and_hidden_passed": passed, "returncode": completed.returncode, "stdout_digest": prior82.digest(completed.stdout), "stderr_digest": prior82.digest(completed.stderr), "developmental_class": selected["developmental_class"] if passed and selected else "world-invalid"}
    return {**body, "receipt_digest": prior82.digest(body)}


def fixture_conformance(prior, prior82, evidence: Path) -> dict[str, Any]:
    files = environment_files(prior)
    rows = []
    for target_path, selected in prior.OPPORTUNITIES.items():
        initial = test_intervention(prior, prior82, target_path, files[target_path], evidence, f"{Path(target_path).stem}-initial")
        reference = test_intervention(prior, prior82, target_path, selected["reference"], evidence, f"{Path(target_path).stem}-reference")
        rows.append({"target_path": target_path, "initial_failed": not initial["floor_and_hidden_passed"], "reference_passed": reference["floor_and_hidden_passed"]})
    return {"rows": rows, "passed": all(row["initial_failed"] and row["reference_passed"] for row in rows)}


def discovery_seed(prior, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(prior, seed)
    projection = {"subject_digest": subject["artifact_digest"], "continuation": subject["continuation"], "developmental_selector": subject["developmental_selector"], "held_capability_areas": [row.get("selected_area") for row in subject.get("tool_world_capabilities", [])], "denied_target_paths": sorted(denied)}
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "frontier.json").write_text(json.dumps(prior.frontier_template(), indent=2, sort_keys=True) + "\n")
    (seed / "frontier-contract.json").write_text(json.dumps(prior.frontier_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("This small workbench is incomplete, but its development surfaces are not enumerated for you. Inspect subject-position.json, the package, its docstrings, and tests with ordinary tools. Edit exactly frontier.json to formulate three distinct coherent interventions. Replace every placeholder and preserve the complete machine-readable shape. Do not edit the package and do not directly select a candidate; the inherited selector runs only after audit and binding.\n")
    return seed


def run_discovery(prior, prior82, context, run: Path, label: str, subject: dict[str, Any], denied: set[str]) -> dict[str, Any]:
    seed = discovery_seed(prior, run, label, subject, denied)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Inspect the inherited subject position and this unenumerated repository. Discover and assess exactly three distinct development contacts by completing frontier.json. Follow frontier-contract.json exactly, edit no code, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, prior.DISCOVERY_SCHEMA, prompt)
    try:
        frontier = json.loads((workspace / "frontier.json").read_text())
    except (json.JSONDecodeError, OSError):
        frontier = None
    audit = context.audit_actor(label, output, base, prior.valid_frontier(frontier, workspace), ["frontier.json"])
    binding = None
    if audit["conformant"]:
        candidates = [{**copy.deepcopy(row), "candidate_id": prior.candidate_identity(prior82, row)} for row in frontier["candidates"]]
        body = {"authority": "ot-0085-pre-selection-actor-discovered-frontier", "source_subject_digest": subject["artifact_digest"], "denied_target_paths": sorted(denied), "actor_patch_digest": audit["patch_digest"], "frontier": {"candidates": candidates, "next_pursuit": frontier["next_pursuit"]}}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-frontier.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    selected = prior.active_select(subject, binding, denied) if binding else None
    return {"label": label, "output": output, "audit": audit, "binding": binding, "selected_candidate": selected}


def implementation_seed(prior, run: Path, label: str, route: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    write_environment(prior, seed)
    selected = route["selected_candidate"]
    projection = {"frontier_binding_digest": route["binding"]["binding_digest"], "source_subject_digest": route["binding"]["source_subject_digest"], "selected_candidate": selected, "editable": [selected["target_path"]]}
    (seed / "bound-contact.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(f"The inherited selector chose the bound actor-discovered contact in bound-contact.json. Edit exactly {selected['target_path']}. Treat its source and docstring as the public ABI. Preserve inherited floors, implement the opening, run useful tests, and inspect the exact diff. Hidden outcomes remain external.\n")
    return seed


def run_implementation(prior, prior82, context, run: Path, label: str, route: dict[str, Any]) -> dict[str, Any]:
    selected = route["selected_candidate"]
    seed = implementation_seed(prior, run, label, route)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Implement the exact bound contact. Edit only its target path, follow the actor-visible ABI exactly, preserve inherited behavior, run useful checks, inspect the exact diff, and return the required report."
    output, base, workspace, _ = context.run_actor(label, seed, prior.IMPLEMENTATION_SCHEMA, prompt)
    target = workspace / selected["target_path"]
    source = target.read_text()
    changed = source != environment_files(prior)[selected["target_path"]]
    compiled = subprocess.run(["python3", "-m", "compileall", "-q", "workbench"], cwd=workspace, capture_output=True)
    audit = context.audit_actor(label, output, base, changed and compiled.returncode == 0, [selected["target_path"]])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0085-pre-hidden-explicit-abi-intervention-binding", "source_subject_digest": route["binding"]["source_subject_digest"], "frontier_binding_digest": route["binding"]["binding_digest"], "candidate_id": selected["candidate_id"], "target_path": selected["target_path"], "target_symbol": selected["target_symbol"], "actor_patch_digest": audit["patch_digest"], "source": source, "source_digest": prior82.digest(source)}
        binding = {**body, "binding_digest": prior82.digest(body)}
        (context.evidence(label) / "bound-intervention.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = test_intervention(prior, prior82, selected["target_path"], source, context.evidence(label), "sealed-world") if binding else {"floor_and_hidden_passed": False, "developmental_class": "world-invalid"}
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
    run = (args.evidence_root or store / "runs/OT-0085").resolve()
    prior = load_prior(repo)
    prior83 = prior.load_prior(repo)
    prior82 = prior83.load_prior(repo)
    runtime = prior82.load_runtime(repo, store)
    parent = load_parent(prior, prior83, prior82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != "8ba78ade10b5f19f56a079c0de195a83c1309506e852ddff76659d284ec83896" or parent["continuation"]["next_opening"] != "inspect-and-select-environmental-intervention":
        raise SystemExit("wrong OT-0084 reopened parent")
    abi = abi_conformance(prior)
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / "environment"
            write_environment(prior, environment)
            contract = prior.contract_conformance(environment)
            fixtures = fixture_conformance(prior, prior82, root / "fixtures")
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "abi_conformance": abi, "contract_conformance": contract, "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if abi["passed"] and contract["passed"] and fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0085 evidence")
    run.mkdir(parents=True)
    environment = run / "contract-environment"
    write_environment(prior, environment)
    contract = prior.contract_conformance(environment)
    fixtures = fixture_conformance(prior, prior82, run / "fixture-conformance")
    if not abi["passed"] or not contract["passed"] or not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo)
    started = time.time()
    current = parent
    discoveries, implementations, denials = [], [], []
    promoted = None
    selected_route = None
    denied: set[str] = set()
    for attempt in range(1, prior.MAX_ATTEMPTS + 1):
        route = run_discovery(prior, prior82, context, run, f"discovery-{attempt:02d}", current, denied)
        discoveries.append(route)
        if not route["selected_candidate"]:
            break
        implementation = run_implementation(prior, prior82, context, run, f"implementation-{attempt:02d}", route)
        implementations.append(implementation)
        if not (implementation["audit"]["conformant"] and implementation["binding"] and implementation["world"]["floor_and_hidden_passed"]):
            break
        if implementation["world"]["developmental_class"] in {"world-valid-held-primitive-repetition", "world-valid-held-floor-modification"}:
            current, denial = prior.compile_denial(prior82, current, route, implementation)
            denials.append(denial)
            denied.add(route["selected_candidate"]["target_path"])
            continue
        current, promotion_receipt = prior.promote(prior82, current, route, implementation)
        promoted = promotion_receipt
        selected_route = route
        break
    operational_passed = bool(promoted and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open" and current["continuation"]["next_opening"] == "inspect-and-select-environmental-intervention" and len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1 and len(current.get("discovered_environmental_frontiers", [])) == len(parent.get("discovered_environmental_frontiers", [])) + 1)
    control = None
    selector_effect = False
    if operational_passed and selected_route:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control_candidate = prior.erased_select(selected_route["binding"])
        control_route = {**selected_route, "selected_candidate": control_candidate}
        control_impl = run_implementation(prior, prior82, context, run, "control-implementation", control_route) if control_candidate else None
        control_class = control_impl["world"]["developmental_class"] if control_impl else "world-invalid"
        control = {"authority": "ot-0085-post-seal-selector-erased-control", "source_frontier_binding_digest": selected_route["binding"]["binding_digest"], "selected_candidate": control_candidate, "implementation": prior82.compact(control_impl) if control_impl else None, "developmental_class": control_class, "developmentally_admitted": control_class in {"world-valid-novel-composition", "world-valid-novel-primitive"}}
        selector_effect = promoted["developmental_class"] in {"world-valid-novel-composition", "world-valid-novel-primitive"} and not control["developmentally_admitted"]
    observer = "promoted" if operational_passed and selector_effect else "conditional" if operational_passed else "rejected"
    result = {"authority": "ot-0085-fixed-explicit-abi-discovered-contact-driver", "source_subject_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "abi_conformance": abi, "contract_conformance": contract, "fixture_conformance": fixtures, "discoveries": [prior82.compact(row) for row in discoveries], "implementations": [prior82.compact(row) for row in implementations], "denial_receipts": denials, "promotion_receipt": promoted, "operational_transition_passed": operational_passed, "selector_effect_passed": selector_effect, "control": control, "observer_disposition": observer, "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = prior82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
