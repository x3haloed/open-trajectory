from __future__ import annotations

import argparse
import ast
import builtins
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
BASE_PATH = ROOT / "ot_0279_standing_world_renewal.py"
BASE_SHA256 = "6e6dee3c502090f6c2b59c934ecd59fd034f72c6bca881b2c03311eb1c57db4a"
PARENT_DIGEST = "645c525e317d885ae7f622b35a400bd37b2fd2d7162c29082f6de389f6b20c55"
INSTALLED_DIGEST = "cfab2a5071046cced4e48e732c4735461ebc7a2149c82e25331ca3d608127e51"
OT279_RECEIPT = "26b97e289b6ee602c71913205a199cb7d0521596003073aeb14456d9287e3e90"
AUTHORITY = "ot-0280-import-stable-world-evaluator"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0279 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0280_frozen_ot0279", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base279 = load_base()
base268 = base279.base268
base267 = base279.base267
base272 = base279.base272
authority_base = base279.authority_base
ALLOWED_CALLS = frozenset(base268.ALLOWED_CALLS)


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


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
    safe_builtins = {name: getattr(builtins, name) for name in ALLOWED_CALLS}
    namespace = {"__builtins__": safe_builtins}
    try:
        exec(compile(tree, "<world-package>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get(public[0])
    return (public[0], function) if callable(function) else None


PROBES = {
    "abs": "abs(-3)",
    "all": "all([True, True])",
    "any": "any([False, True])",
    "bool": "bool(1)",
    "dict": "dict([('a', 1)])",
    "enumerate": "list(enumerate(['a', 'b']))",
    "float": "float('1.5')",
    "int": "int('3')",
    "len": "len([1, 2])",
    "list": "list((1, 2))",
    "max": "max(2, 5)",
    "min": "min(2, 5)",
    "range": "list(range(3))",
    "reversed": "list(reversed([1, 2]))",
    "round": "round(1.6)",
    "set": "sorted(set([2, 1, 2]))",
    "sorted": "sorted([2, 1])",
    "str": "str(7)",
    "sum": "sum([1, 2])",
    "tuple": "list(tuple([1, 2]))",
    "zip": "list(zip([1, 2], [3, 4]))",
}


def run_probes():
    results = {}
    for name, expression in sorted(PROBES.items()):
        loaded = safe_module(f"def probe(case):\n    return {expression}\n")
        if not loaded:
            raise RuntimeError(f"probe failed to load: {name}")
        results[name] = loaded[1]({})
    return results


def standalone_probes():
    source = "\n".join(
        [
            "import ast, builtins, json",
            f"ALLOWED_CALLS = frozenset({sorted(ALLOWED_CALLS)!r})",
            f"PROBES = {PROBES!r}",
            inspect.getsource(safe_module),
            inspect.getsource(run_probes),
            "print(json.dumps(run_probes(), sort_keys=True))",
        ]
    )
    process = subprocess.run(
        ["python3", "-c", source], capture_output=True, text=True
    )
    return process, json.loads(process.stdout) if process.returncode == 0 else None


def with_corrected_evaluator(function, *args):
    original = base268.safe_module
    base268.safe_module = safe_module
    try:
        return function(*args)
    finally:
        base268.safe_module = original


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector, core = lineage.selector_base, lineage.base
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0280").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0278", "open-subject-at-fifth-standing-feed-wait.json"
    )
    rejected = selector.load_artifact(
        p82, repo, store, "OT-0279", "standing-world-renewal-rejected-result.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0279", "retained-morrowglass-world-candidate.json"
    )
    return repo, run, p82, runtime, parent, rejected, package


def evaluate(run, p82, runtime, parent, rejected, package):
    installed = base279.install(parent, p82)
    legacy = base268.evaluate_package(package, p82.digest)
    corrected = with_corrected_evaluator(base268.evaluate_package, package, p82.digest)
    corrected_negatives = with_corrected_evaluator(
        base268.negative_controls, p82.digest
    )
    checker_root = base268.seed_actor(run / "checker-v2", package)
    checker_process = subprocess.run(
        ["python3", "check_package.py"],
        cwd=checker_root,
        capture_output=True,
        text=True,
    )
    checker_result = (
        json.loads(checker_process.stdout) if checker_process.returncode == 0 else None
    )
    imported_probes = json.loads(json.dumps(run_probes(), sort_keys=True))
    standalone_process, standalone = standalone_probes()
    scan = (
        base267.scan_feed(installed, [corrected["public_package"]], p82.digest)
        if corrected.get("valid")
        else None
    )
    route, identity = base272.base265.floors(installed)
    target_collision = bool(
        corrected.get("valid")
        and set(corrected["targets"])
        & set(parent["local_frontier_ledger"]["targets"])
    )
    retained_actor = rejected["actor"]
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST
        and runtime.identity_conforms(parent),
        "installed_exact": installed["artifact_digest"] == INSTALLED_DIGEST
        and base279.derive(installed, [], p82) == "renew-world-feed"
        and runtime.identity_conforms(installed),
        "ot0279_exact_rejection": rejected["receipt_digest"] == OT279_RECEIPT
        and rejected["observer_disposition"] == "rejected"
        and rejected["final_subject_digest"] == INSTALLED_DIGEST,
        "legacy_reproduces_execution_failure": legacy
        == {"valid": False, "reason": "execution"},
        "allowed_set_unchanged": ALLOWED_CALLS == frozenset(base268.ALLOWED_CALLS)
        and set(PROBES) == set(ALLOWED_CALLS),
        "all_allowed_calls_import_stable": standalone_process.returncode == 0
        and standalone == imported_probes
        and len(imported_probes) == len(ALLOWED_CALLS),
        "negative_controls_preserved": all(
            not row["valid"] for row in corrected_negatives
        ),
        "published_checker_parity": checker_process.returncode == 0
        and checker_result == corrected,
        "retained_package_three_exact_2_of_6": bool(
            corrected.get("valid")
            and len(corrected["targets"]) == 3
            and all(
                sum(row["matches"] for row in rows) == 2
                for rows in corrected["rows"].values()
            )
        ),
        "targets_novel": corrected.get("valid") and not target_collision,
        "retained_actor_eligible_not_rescored": retained_actor["accepted"] is False
        and retained_actor["g10_disposition"] is True
        and retained_actor["audit"]["exact_changes"] is True
        and retained_actor["audit"]["truthful"] is True
        and retained_actor["audit"]["trace_regime"]["accepted"] is True,
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
        "subject_open_fifth_wait": installed["continuation"]["status"] == "open"
        and installed["active_world_stream_wait"]["status"] == "waiting"
        and len(installed["world_stream_wait_receipts"]) == 5,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "historical_ot0279_disposition": rejected["observer_disposition"],
        "legacy_evaluation": legacy,
        "corrected_evaluation": corrected,
        "allowed_call_probe_results": imported_probes,
        "scanner_observation": scan,
        "target_collision": target_collision,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": installed["continuation"]["status"],
        "final_subject_digest": installed["artifact_digest"],
        "world_id": corrected.get("world_id"),
        "public_package_digest": corrected.get("public_package_digest"),
        "full_package_digest": corrected.get("full_package_digest"),
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    return result, installed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, rejected, package = setup(args)
    if run.exists() and (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0280 evidence")
    run.mkdir(parents=True, exist_ok=True)
    result, installed = evaluate(run, p82, runtime, parent, rejected, package)
    write_json(run / "fixture-conformance.json", result)
    if args.preflight_only:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["checks"]["passed"] else 2
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", installed)
    write_json(run / "world-package.json", package)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["checks"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
