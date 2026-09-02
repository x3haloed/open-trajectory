from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0267_standing_world_feed.py"
BASE_SHA256 = "85a9e18ae02bed83238fcfa83ca275918cfd0ed99a97e04902412daf8b6a327a"
PARENT_DIGEST = "f02cf7cdcd68237b3327dacb2c733f3b67dba26caceb83d7ed83240ff1e4991c"
OT267_RECEIPT = "d75632a371d90de625e58b7499789ce20df0ccde4e0365baf6b255ee04016f4a"
AUTHORITY = "ot-0268-independent-world-package"
SCHEMA = REPO / "spec/ot-0268-world-author.schema.json"
ALLOWED_CALLS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0267 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0268_frozen_ot0267", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base267 = load_base()
base266 = base267.base266
base265 = base267.base265
base261 = base267.base261
base260 = base267.base260
base236 = base266.base258.base236
authority_base = base267.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def valid_world_id(value):
    return (
        isinstance(value, str)
        and 3 <= len(value) <= 64
        and value[0].isalnum()
        and value[-1].isalnum()
        and all(character.isalnum() or character in "-_" for character in value)
    )


def safe_module(source):
    if not isinstance(source, str) or not source or len(source.encode()) > 10000:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    forbidden = (
        ast.Import,
        ast.ImportFrom,
        ast.Attribute,
        ast.ClassDef,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Raise,
        ast.Global,
        ast.Nonlocal,
    )
    if any(isinstance(node, forbidden) for node in ast.walk(tree)):
        return None
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    public = sorted(name for name in defined if not name.startswith("_"))
    if len(public) != 1:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return None
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS | defined:
                return None
    safe_builtins = {
        name: getattr(__builtins__, name)
        for name in ALLOWED_CALLS
        if hasattr(__builtins__, name)
    }
    namespace = {"__builtins__": safe_builtins}
    try:
        exec(compile(tree, "<world-package>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get(public[0])
    return (public[0], function) if callable(function) else None


def evaluate_package(package, digest):
    required = {
        "world_id",
        "visible_sources",
        "sealed_reference_sources",
        "sealed_cases",
    }
    if not isinstance(package, dict) or set(package) != required:
        return {"valid": False, "reason": "shape"}
    if not valid_world_id(package.get("world_id")):
        return {"valid": False, "reason": "world-id"}
    visible = package.get("visible_sources")
    reference = package.get("sealed_reference_sources")
    cases = package.get("sealed_cases")
    if (
        not isinstance(visible, dict)
        or len(visible) != 3
        or not isinstance(reference, dict)
        or set(reference) != set(visible)
        or not isinstance(cases, dict)
        or len(json.dumps(package, sort_keys=True).encode()) > 60000
    ):
        return {"valid": False, "reason": "collections"}
    targets = {}
    loaded = {}
    for path_text in sorted(visible):
        path = Path(path_text)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 2 or path.suffix != ".py":
            return {"valid": False, "reason": "path"}
        visible_module = safe_module(visible[path_text])
        reference_module = safe_module(reference[path_text])
        if not visible_module or not reference_module or visible_module[0] != reference_module[0]:
            return {"valid": False, "reason": "source"}
        target = visible_module[0]
        if target in targets:
            return {"valid": False, "reason": "duplicate-target"}
        targets[target] = path_text
        loaded[target] = (visible_module[1], reference_module[1])
    if set(cases) != set(targets):
        return {"valid": False, "reason": "case-targets"}
    rows = {}
    for target in sorted(targets):
        target_cases = cases[target]
        if (
            not isinstance(target_cases, list)
            or len(target_cases) != 6
            or len(
                {
                    row.get("case_id")
                    for row in target_cases
                    if isinstance(row, dict)
                }
            )
            != 6
        ):
            return {"valid": False, "reason": "case-count"}
        results = []
        for row in target_cases:
            if (
                not isinstance(row, dict)
                or set(row) != {"case_id", "input"}
                or not isinstance(row["case_id"], str)
                or not isinstance(row["input"], dict)
            ):
                return {"valid": False, "reason": "case-shape"}
            original = copy.deepcopy(row["input"])
            try:
                observed = loaded[target][0](copy.deepcopy(original))
                expected = loaded[target][1](copy.deepcopy(original))
                json.dumps(observed)
                json.dumps(expected)
            except Exception:
                return {"valid": False, "reason": "execution"}
            results.append(
                {
                    "case_id": row["case_id"],
                    "matches": observed == expected,
                    "observed": observed,
                    "expected": expected,
                }
            )
        if sum(result["matches"] for result in results) != 2:
            return {"valid": False, "reason": "not-2-of-6"}
        rows[target] = results
    public = {"world_id": package["world_id"], "visible_sources": visible}
    return {
        "valid": True,
        "world_id": package["world_id"],
        "targets": targets,
        "rows": rows,
        "public_package": public,
        "public_package_digest": digest(public),
        "full_package_digest": digest(package),
    }


CHECKER_SOURCE = (
    "import ast, copy, hashlib, json\nfrom pathlib import Path\n"
    + "ALLOWED_CALLS = "
    + repr(ALLOWED_CALLS)
    + "\n"
    + inspect.getsource(valid_world_id)
    + inspect.getsource(safe_module)
    + inspect.getsource(evaluate_package)
    + '''
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

package = json.loads(Path("world-package.json").read_text())
result = evaluate_package(package, digest)
print(json.dumps(result, sort_keys=True))
raise SystemExit(0 if result.get("valid") else 2)
'''
)


def example_package(world_id="example-world-v1"):
    visible = {}
    reference = {}
    cases = {}
    definitions = (
        ("example/alpha.py", "choose_alpha"),
        ("example/beta.py", "choose_beta"),
        ("example/gamma.py", "choose_gamma"),
    )
    for path, target in definitions:
        visible[path] = f'def {target}(case):\n    return case["value"]\n'
        reference[path] = f'def {target}(case):\n    return case["value"] + case["shift"]\n'
        cases[target] = [
            {"case_id": f"{target}-{index}", "input": {"value": index, "shift": 0 if index < 2 else index}}
            for index in range(6)
        ]
    return {
        "world_id": world_id,
        "visible_sources": visible,
        "sealed_reference_sources": reference,
        "sealed_cases": cases,
    }


EXAMPLE = example_package()
TEMPLATE = example_package("draft-replace-this-world-v1")


def seed_actor(root, package):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "world-package.json", package)
    write_json(seed / "example-world-package.json", EXAMPLE)
    write_json(
        seed / "world-package-contract.json",
        {
            "authority": AUTHORITY,
            "editable": ["world-package.json"],
            "exact_top_level_fields": [
                "world_id",
                "visible_sources",
                "sealed_reference_sources",
                "sealed_cases",
            ],
            "source_count": 3,
            "source_path": "relative-two-component-python",
            "one_public_callable_per_source": True,
            "matching_reference_path_and_callable": True,
            "cases_per_callable": 6,
            "required_visible_reference_matches": 2,
            "maximum_source_bytes": 10000,
            "maximum_package_bytes": 60000,
            "forbidden_source_authority": [
                "imports",
                "attributes",
                "dynamic-execution",
                "io",
                "ambient-state",
            ],
        },
    )
    (seed / "check_package.py").write_text(CHECKER_SOURCE)
    immutable = [
        "example-world-package.json",
        "world-package-contract.json",
        "check_package.py",
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(
        seed / "mutation-envelope.json",
        {"editable": ["world-package.json"], "immutable": immutable},
    )
    (seed / "README.md").write_text(
        "You are authoring an external world for an unknown continuing subject. "
        "No subject state, pursuit, target catalog, or prior world ids are available. "
        "Invent a coherent world with three distinct executable surfaces. The visible "
        "functions should encode plausible but incomplete local policies; the sealed "
        "references and six cases per callable must make each visible policy agree on "
        "exactly two cases. Use only the pure restricted Python described by the contract. "
        "Edit only world-package.json, run python3 check_package.py, and inspect the exact diff.\n"
    )
    return seed


def output_valid(output, package):
    return (
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "world_id"}
        and output.get("action") == "author-world-package"
        and output.get("files_changed") == ["world-package.json"]
        and isinstance(package, dict)
        and output.get("world_id") == package.get("world_id")
    )


def negative_controls(digest):
    negatives = []
    imported = copy.deepcopy(EXAMPLE)
    imported["visible_sources"]["example/alpha.py"] = "import os\ndef choose_alpha(case):\n    return []\n"
    negatives.append(imported)
    attribute = copy.deepcopy(EXAMPLE)
    attribute["visible_sources"]["example/alpha.py"] = 'def choose_alpha(case):\n    return case.get("value")\n'
    negatives.append(attribute)
    matching = copy.deepcopy(EXAMPLE)
    matching["sealed_reference_sources"] = copy.deepcopy(matching["visible_sources"])
    negatives.append(matching)
    two_sources = copy.deepcopy(EXAMPLE)
    two_sources["visible_sources"].pop("example/gamma.py")
    two_sources["sealed_reference_sources"].pop("example/gamma.py")
    two_sources["sealed_cases"].pop("choose_gamma")
    negatives.append(two_sources)
    wrong_cases = copy.deepcopy(EXAMPLE)
    wrong_cases["sealed_cases"]["choose_alpha"] = wrong_cases["sealed_cases"]["choose_alpha"][:5]
    negatives.append(wrong_cases)
    path = copy.deepcopy(EXAMPLE)
    path["visible_sources"]["../alpha.py"] = path["visible_sources"].pop("example/alpha.py")
    path["sealed_reference_sources"]["../alpha.py"] = path["sealed_reference_sources"].pop("example/alpha.py")
    negatives.append(path)
    extra = copy.deepcopy(EXAMPLE)
    extra["extra"] = True
    negatives.append(extra)
    return [evaluate_package(package, digest) for package in negatives]


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0268").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0267", "open-subject-with-standing-world-feed.json"
    )
    result267 = selector_base.load_artifact(
        p82, repo, store, "OT-0267", "standing-world-feed-aggregate.json"
    )
    fixture_root = run.parent / "OT-0268-preflight"
    if fixture_root.exists():
        import shutil

        shutil.rmtree(fixture_root)
    fixture_seed = seed_actor(fixture_root, EXAMPLE)
    fixture_checker = subprocess.run(
        ["python3", "check_package.py"], cwd=fixture_seed, capture_output=True
    )
    fixture_evaluation = evaluate_package(EXAMPLE, p82.digest)
    fixture_scan = base267.scan_feed(
        parent, [fixture_evaluation["public_package"]], p82.digest
    )
    route, identity = base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open_correction": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and base260.needs_refresh(parent, p82)
        and base261.challenger(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0267_exact_promotion": result267["observer_disposition"] == "promoted"
        and result267["receipt_digest"] == OT267_RECEIPT
        and result267["final_subject_digest"] == PARENT_DIGEST,
        "standing_scanner_exact": parent["active_standing_world_provider"]["scanner_source_digest"]
        == p82.digest(base267.SCANNER_SOURCE),
        "actual_seed_interface_conforms": fixture_checker.returncode == 0
        and fixture_evaluation["valid"]
        and fixture_scan["status"] == "world-available",
        "seven_negative_controls_reject": all(
            not row["valid"] for row in negative_controls(p82.digest)
        ),
        "template_requires_authorship": p82.digest(TEMPLATE) != p82.digest(EXAMPLE),
        "subject_receives_no_package": "world-package" not in json.dumps(parent),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0268 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run / "runtime", repo)
    )
    seed = seed_actor(run / "actor", TEMPLATE)
    label = "independent-world-author"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        package = json.loads((workspace / "world-package.json").read_text())
        evaluation = evaluate_package(package, p82.digest)
        checker = subprocess.run(
            ["python3", "check_package.py"], cwd=workspace, capture_output=True
        )
        public = evaluation.get("public_package") if evaluation["valid"] else None
        scan = base267.scan_feed(parent, [public], p82.digest) if public else None
        semantic = bool(
            checker.returncode == 0
            and evaluation["valid"]
            and p82.digest(package) not in {p82.digest(TEMPLATE), p82.digest(EXAMPLE)}
            and scan
            and scan["status"] == "world-available"
            and scan["available_world"]["world_id"] == package["world_id"]
        )
    except (OSError, json.JSONDecodeError, KeyError):
        package, evaluation, checker, scan, semantic = None, {"valid": False}, None, None, False
    transport = output_valid(output, package)
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        semantic and transport,
        ["world-package.json"],
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and base236.g10(normalized))
    if package is not None:
        write_json(run / "world-package.json", package)
    actor = {
        "accepted": accepted,
        "output": output,
        "audit": audit,
        "g10_disposition": base236.g10(normalized),
        "evaluation": evaluation,
        "scanner_observation": scan,
    }
    gates = {
        "preflight_passed": checks["passed"],
        "one_fresh_world_actor": True,
        "world_actor_accepted": accepted,
        "exact_one_file_effect": audit["exact_changes"]
        and audit["changed_paths"] == ["world-package.json"],
        "truthful_clean_g10": audit["truthful"]
        and normalized["accepted"]
        and normalized["outside_file_changes"] == [],
        "three_distinct_targets": bool(
            evaluation["valid"] and len(evaluation["targets"]) == 3
        ),
        "all_three_exact_2_of_6": bool(
            evaluation["valid"]
            and all(
                sum(row["matches"] for row in rows) == 2
                for rows in evaluation["rows"].values()
            )
        ),
        "standing_scanner_admits": bool(
            scan
            and scan["status"] == "world-available"
            and not any(
                scan[key]
                for key in (
                    "selection_authority",
                    "scoring_authority",
                    "admission_authority",
                    "outcome_authority",
                    "actor_authority",
                )
            )
        ),
        "subject_exactly_unchanged": parent["artifact_digest"] == PARENT_DIGEST
        and runtime.identity_conforms(parent),
        "subject_still_open_correction": parent["continuation"]["status"] == "open"
        and base261.challenger(parent, p82) == "outward-correct",
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "actor": actor,
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": parent["continuation"]["status"],
        "final_subject_digest": parent["artifact_digest"],
        "world_id": package.get("world_id") if package else None,
        "public_package_digest": evaluation.get("public_package_digest"),
        "full_package_digest": evaluation.get("full_package_digest"),
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", parent)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
