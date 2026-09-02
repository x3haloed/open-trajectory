from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0284_tideglass_second_renewal_cycle.py"
BASE_SHA256 = "5f87495285a12eb7dd60edb4e6122d195aa32e28981b5139288cd6ac056a0792"
OT284_PREFLIGHT_RECEIPT = "ce7b935616a91a6b17e83eed48069e16592a76ef35b5013f7607868b4046f839"
AUTHORITY = "ot-0285-current-package-isolation-second-cycle"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0284 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0285_frozen_ot0284", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base284 = load_base()
base284.AUTHORITY = AUTHORITY
base284.b.AUTHORITY = AUTHORITY
base284.b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base284.write_json(path, value)


def current_package_public_only(seed, package, evaluation):
    files = [path for path in seed.rglob("*") if path.is_file()]
    corpus = "\n".join(path.read_text(errors="replace") for path in files)
    hidden_rows = [row for rows in package["sealed_cases"].values() for row in rows[4:]]
    forbidden = [
        *package["sealed_reference_sources"].values(),
        *(json.dumps(row, sort_keys=True) for row in hidden_rows),
        json.dumps(package["sealed_cases"], sort_keys=True),
        evaluation["full_package_digest"],
    ]
    return all(value not in corpus for value in forbidden) and not any(
        "sealed" in path.name.lower() for path in files
    )


def corrected_selected_fixture(
    root, offered, target, package, evaluation, result280, p82, runtime
):
    final, checks = original_selected_fixture(
        root, offered, target, package, evaluation, result280, p82, runtime
    )
    checks["public_only"] = current_package_public_only(
        root / "actor" / "seed", package, evaluation
    )
    return final, checks


original_selected_fixture = base284.selected_fixture
base284.selected_fixture = corrected_selected_fixture


def setup(args):
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    forwarded = copy.copy(args)
    forwarded.evidence_root = (
        args.evidence_root or store / "runs/OT-0285"
    ).resolve()
    values = base284.setup(forwarded)
    _, _, p82, _, _, _, _, _, _, _ = values
    lineage = base284.b.authority_base.guide_base.load_base()
    rejected284 = lineage.selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0284",
        "rejected-tideglass-second-cycle-preflight.json",
    )
    return (*values, rejected284)


def preflight(root, p82, runtime, parent, package, result283, result280, rejected284):
    result = base284.preflight(
        root, p82, runtime, parent, package, result283, result280
    )
    evaluation = base284.b.base268.evaluate_package(package, p82.digest)
    _, offered, _ = base284.b.base281.wake(parent, package, p82)
    fixture_root = root / "isolation-controls"
    target = sorted(evaluation["targets"])[0]
    base284.selected_fixture(
        fixture_root, offered, target, package, evaluation, result280, p82, runtime
    )
    seed = fixture_root / "actor" / "seed"
    controls = {}
    forbidden = {
        "reference_source": next(iter(package["sealed_reference_sources"].values())),
        "hidden_case": json.dumps(next(iter(package["sealed_cases"].values()))[4], sort_keys=True),
        "full_case_collection": json.dumps(package["sealed_cases"], sort_keys=True),
        "full_package_digest": evaluation["full_package_digest"],
    }
    marker = seed / "current-package-leak-control.txt"
    for name, value in forbidden.items():
        marker.write_text(value)
        controls[name] = not current_package_public_only(seed, package, evaluation)
    marker.unlink()
    result["checks"]["base_hash_exact"] = (
        hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    )
    result["checks"]["ot0284_rejection_preserved"] = (
        rejected284["receipt_digest"] == OT284_PREFLIGHT_RECEIPT
        and rejected284["checks"]["passed"] is False
        and rejected284["checks"]["all_complete_branches_pass"] is False
    )
    result["checks"]["current_package_leaks_rejected"] = all(controls.values())
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected284["receipt_digest"]
    result["isolation_controls"] = controls
    result.pop("receipt_digest", None)
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result283,
        result280,
        core,
        base130,
        rejected284,
    ) = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight",
            p82,
            runtime,
            parent,
            package,
            result283,
            result280,
            rejected284,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return base284.advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result280,
        fixtures,
        core,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
