from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0291_recovered_world_wake_and_selection.py"
BASE_SHA256 = "852856a65fb90d466bea1b07a97756aed56e1cb20e8fd43ca32a2af9d3b08e84"
OT291_REJECTED_RECEIPT = "2b5587ede2b1f9cba81bbd0a0a4b53546f4cd8ff48a75bbd170728afa9b7b42a"
AUTHORITY = "ot-0292-recovered-package-content-isolation"
ACTIVE_REPO = REPO
ACTIVE_STORE = REPO / ".evidence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0291 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0292_frozen_ot0291", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base291 = load_base()
b = base291.b
base291.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def current_package_public_only(seed, package):
    files = [path for path in seed.rglob("*") if path.is_file()]
    corpus = "\n".join(path.read_text(errors="replace") for path in files)
    hidden_rows = [
        row for rows in package["sealed_cases"].values() for row in rows[4:]
    ]
    forbidden = [
        *package["sealed_reference_sources"].values(),
        *(json.dumps(row, sort_keys=True) for row in hidden_rows),
        json.dumps(package["sealed_cases"], sort_keys=True),
    ]
    return all(value not in corpus for value in forbidden) and not any(
        "sealed" in path.name.lower() for path in files
    )


original_selected_fixture = base291.selected_fixture


def corrected_selected_fixture(
    root, offered, target, package, evaluation, result280, p82, runtime
):
    result = original_selected_fixture(
        root, offered, target, package, evaluation, result280, p82, runtime
    )
    result["public_only"] = current_package_public_only(
        root / "actor" / "seed", package
    )
    return result


base291.selected_fixture = corrected_selected_fixture
original_preflight = base291.preflight


def corrected_preflight(root, p82, runtime, parent, package, result290, result280):
    result = original_preflight(
        root, p82, runtime, parent, package, result290, result280
    )
    lineage = b.authority_base.guide_base.load_base()
    rejected291 = lineage.selector_base.load_artifact(
        p82,
        ACTIVE_REPO,
        ACTIVE_STORE,
        "OT-0291",
        "rejected-recovered-world-wake-preflight.json",
    )
    evaluation, _, offered, _ = base291.wake(parent, package, p82)
    target = sorted(evaluation["targets"])[0]
    fixture_root = root / "isolation-controls"
    corrected_selected_fixture(
        fixture_root,
        offered,
        target,
        package,
        evaluation,
        result280,
        p82,
        runtime,
    )
    seed = fixture_root / "actor" / "seed"
    corpus = "\n".join(
        path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file()
    )
    controls = {
        "reference_source": next(iter(package["sealed_reference_sources"].values())),
        "hidden_case": json.dumps(
            next(iter(package["sealed_cases"].values()))[4], sort_keys=True
        ),
        "full_case_collection": json.dumps(package["sealed_cases"], sort_keys=True),
        "sealed_filename": "filename-only control",
    }
    outcomes = {}
    for name, value in controls.items():
        marker = seed / (
            "sealed-control.txt" if name == "sealed_filename" else "content-control.txt"
        )
        marker.write_text(value)
        outcomes[name] = not current_package_public_only(seed, package)
        marker.unlink()
    result["checks"]["base_hash_exact"] = (
        hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    )
    result["checks"]["ot0291_rejection_preserved"] = (
        rejected291["receipt_digest"] == OT291_REJECTED_RECEIPT
        and rejected291["checks"]["passed"] is False
        and rejected291["checks"]["three_complete_choice_branches"] is False
    )
    result["checks"]["legitimate_digest_retained"] = (
        evaluation["full_package_digest"] in corpus
    )
    result["checks"]["current_package_leaks_rejected"] = all(outcomes.values())
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected291["receipt_digest"]
    result["isolation_controls"] = outcomes
    result.pop("receipt_digest", None)
    result["receipt_digest"] = p82.digest(result)
    base291.write_json(root / "fixture-conformance.json", result)
    return result


base291.preflight = corrected_preflight


def main():
    global ACTIVE_REPO, ACTIVE_STORE
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    known, _ = parser.parse_known_args()
    ACTIVE_REPO = known.repo.resolve()
    ACTIVE_STORE = (known.store or ACTIVE_REPO / ".evidence").resolve()
    added_root = known.evidence_root is None
    if added_root:
        sys.argv.extend(
            ["--evidence-root", str(ACTIVE_STORE / "runs" / "OT-0292")]
        )
    try:
        return base291.main()
    finally:
        if added_root:
            del sys.argv[-2:]


if __name__ == "__main__":
    raise SystemExit(main())
