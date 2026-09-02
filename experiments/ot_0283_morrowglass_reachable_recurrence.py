from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0282_morrowglass_recurrence_and_renewal.py"
BASE_SHA256 = "6237aeb1b739c1a4de2b30f2df8eb9894c74c80e55f862b2d2a39d9e52bea30b"
PARENT_DIGEST = "7c78dedafa62091b689414cf448da6baff130ade2a470de44b2b9520c8539174"
OT281_RECEIPT = "f20e5a583bb4555e7b2ca95045014df08d1d0a36204cec04ef9c94556780e5ac"
OT280_RECEIPT = "15d39db31b2031e2dd3e0c1f1917e4b4125ce2924cc3fcffc3f62710980d847c"
OT282_PREFLIGHT_RECEIPT = "7a500c1e9d450f32c26e1ebd67f71081fc2db9541b6d57848e2cd85387735ebb"
AUTHORITY = "ot-0283-morrowglass-reachable-recurrence"
MAX_CALLS = 18


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0282 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0283_frozen_ot0282", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base282 = load_base()
base282.AUTHORITY = AUTHORITY
base282.MAX_CALLS = MAX_CALLS
base282.base274.AUTHORITY = AUTHORITY
base282.base274.MAX_CALLS = MAX_CALLS


def write_json(path, value):
    base282.write_json(path, value)


def setup(args):
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    forwarded = copy.copy(args)
    forwarded.evidence_root = (
        args.evidence_root or store / "runs/OT-0283"
    ).resolve()
    values = base282.setup(forwarded)
    _, run, p82, _, _, _, _, _, _, _ = values
    lineage = base282.authority_base.guide_base.load_base()
    rejected282 = lineage.selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0282",
        "rejected-morrowglass-recurrence-preflight.json",
    )
    return (*values, rejected282)


def input_classes(cases, p82):
    classes = {}
    for row in cases:
        classes.setdefault(p82.digest(row["input"]), []).append(row)
    return classes


def consistent_input_outcomes(package, evaluation, p82):
    for target, cases in package["sealed_cases"].items():
        rows = evaluation["rows"][target]
        if len(cases) != len(rows):
            return False
        outcomes = {}
        for case, row in zip(cases, rows, strict=True):
            outcomes.setdefault(p82.digest(case["input"]), set()).add(
                p82.digest(row["expected"])
            )
        if any(len(values) != 1 for values in outcomes.values()):
            return False
    return True


def feedback_capacity(package, target, p82):
    cases = package["sealed_cases"][target]
    visible = {p82.digest(row["input"]) for row in cases[:4]}
    hidden = {p82.digest(row["input"]) for row in cases[4:]}
    return len(hidden - visible)


def reachable_depths(parent, order, package, p82):
    initial = base282.base274.selected(parent)[4]
    capacities = [
        feedback_capacity(package, target, p82)
        for target in (initial, *order)
    ]
    return capacities, itertools.product(
        *(range(capacity + 1) for capacity in capacities)
    )


def preflight(
    root,
    p82,
    runtime,
    parent,
    result281,
    package,
    result280,
    rejected282,
):
    root.mkdir(parents=True, exist_ok=True)
    first_corrected, _ = base282.correction_variant(
        parent, 0, package, result280, p82, runtime
    )
    first_refreshed = base282.base264.refresh_projection_only(first_corrected, p82)
    remaining = [
        row["target_symbol"]
        for row in first_refreshed["active_opportunity_projection"]["opportunities"]
    ]
    branches = []
    observed_capacities = []
    for order in itertools.permutations(remaining):
        capacities, depths = reachable_depths(parent, order, package, p82)
        observed_capacities.append(capacities)
        for depth in depths:
            branches.append(
                base282.prospective_branch(
                    root / ("-".join(order) + "-" + "".join(map(str, depth))),
                    parent,
                    order,
                    depth,
                    package,
                    result280,
                    p82,
                    runtime,
                )
            )
    route, identity = base282.base272.base265.floors(parent)
    evaluation = base282.base268.evaluate_package(package, p82.digest)
    script = Path(__file__).read_text()
    seed = base282.base268.seed_actor(root / "provider-seed", base282.base268.EXAMPLE)
    corpus = "\n".join(
        path.read_text(errors="replace")
        for path in seed.rglob("*")
        if path.is_file()
    )
    seen = base282.base279.seen_world_ids(parent)
    ledger = sorted(parent["local_frontier_ledger"]["targets"])
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "ot0282_rejection_preserved": rejected282["receipt_digest"]
        == OT282_PREFLIGHT_RECEIPT
        and rejected282["checks"]["passed"] is False
        and rejected282["checks"]["all_branches_pass"] is False,
        "parent_exact_correction": parent["artifact_digest"] == PARENT_DIGEST
        and base282.base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0281_exact_promotion": result281["receipt_digest"] == OT281_RECEIPT
        and result281["observer_disposition"] == "promoted"
        and result281["final_subject_digest"] == PARENT_DIGEST,
        "ot0280_exact_package": result280["receipt_digest"] == OT280_RECEIPT
        and result280["full_package_digest"] == evaluation["full_package_digest"],
        "duplicate_input_outcomes_consistent": consistent_input_outcomes(
            package, evaluation, p82
        ),
        "reachable_capacities_exact": observed_capacities
        == [[1, 2, 2], [1, 2, 2]],
        "thirty_six_complete_branches": len(branches) == 36
        and len(remaining) == 2,
        "all_reachable_branches_pass": all(
            row["selections_passed"]
            and row["corrections_passed"]
            and row["saturated"]
            and row["sixth_wait"]
            and row["exact_reobserve"]
            and row["renewal_derived"]
            and row["provider_example_visible"]
            and row["renewal_preserved"]
            and row["conformant"]
            for row in branches
        ),
        "dynamic_surfaces_not_hardcoded": all(
            token not in script
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "provider_seed_excludes_lineage": PARENT_DIGEST not in corpus
        and all(world_id not in corpus for world_id in seen)
        and all(target not in corpus for target in ledger),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "rejected_predecessor_receipt_digest": rejected282["receipt_digest"],
        "branch_count": len(branches),
        "feedback_capacities": observed_capacities[0],
        "checks": checks,
    }
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
        result281,
        package,
        result280,
        core,
        base130,
        rejected282,
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
            result281,
            package,
            result280,
            rejected282,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return base282.advance(
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
