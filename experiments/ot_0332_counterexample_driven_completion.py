from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0331_g11_resumptive_continuation.py"
BASE_SHA256 = "08e88d1a473aa79407debe96f2ef02cfc760e509c7bc7f969fb8ef8f90161b38"
PARENT_DIGEST = "c066765344a9f9390e5b9a4499f6c79af65d3a153df91597f03d4ea7689df0b0"
OT331_RECEIPT = "e3dbb6b0f666e6835bfe03761782c9c0ffba5cea4917fb71c4746f926c139c4b"
AUTHORITY = "ot-0332-counterexample-driven-completion"
MAX_OPERATIONS = 5
MAX_ACTORS = 3
PULSE = None


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0331 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0332_frozen_ot0331", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
driver = base.driver
g11 = base.g11
write_json = base.write_json


def set_authority():
    base.AUTHORITY = AUTHORITY
    base.base.AUTHORITY = AUTHORITY
    for module in (driver, driver.base309, driver.base308, driver.base307):
        module.AUTHORITY = AUTHORITY
    driver.b.AUTHORITY = AUTHORITY
    driver.b.base274.AUTHORITY = AUTHORITY
    driver.b.base274.base273.AUTHORITY = AUTHORITY
    driver.b.base274.base271.AUTHORITY = AUTHORITY
    driver.PULSE = PULSE


set_authority()


def setup(args):
    repo, store, _, p82, runtime, old_parent, result329, operation1, result330, packages, result280, core, base130 = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0332").resolve()
    selector = base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    parent = load("OT-0331", "open-subject-after-partial-ration-correction.json")
    result331 = load("OT-0331", "g11-resumptive-continuation-rejected-aggregate.json")
    operation5 = load("OT-0331", "unresolved-ration-correction-operation.json")
    return repo, store, run, p82, runtime, parent, result331, operation5, result330, packages, result280, core, base130


def preflight(root, p82, runtime, parent, result331, operation5, result330, packages):
    root.mkdir(parents=True, exist_ok=True)
    package, binding = base.base.resolve_package(parent, packages, p82)
    selected = driver.b.base274.base271.selected(parent)
    disclosure = parent["active_correction_disclosure"]
    route, identity = driver.b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "ot0331_exact_budget_rejection": result331["receipt_digest"] == OT331_RECEIPT and result331["observer_disposition"] == "rejected" and result331["boundary"] == {"kind": "actor-budget", "operation": "outward-correct", "after_operation_count": 5} and result331["final_subject_digest"] == PARENT_DIGEST,
        "unresolved_operation_exact": operation5["checks"]["passed"] and operation5["final_subject_digest"] == PARENT_DIGEST and operation5["world"]["result"]["matches"] == 4 and operation5["world"]["unchanged_control"]["matches"] == 2,
        "counterexample_bound": disclosure["status"] == "awaiting-revision" and disclosure["case_count"] == 5 and disclosure["feedback_receipt_digest"] == operation5["feedback"]["receipt_digest"],
        "failed_candidate_uninstalled": selected[0]["installed_source_digest"] != operation5["feedback"]["failed_candidate_source_digest"],
        "g11_exact_active": result330["receipt_digest"] == base.G11_RECEIPT and result330["checks"]["passed"] and g11.evaluate(g11.g11)["pass_count"] == 15,
        "state_resolved_package": binding["active_epoch_id"] == parent["active_opportunity_projection"]["active_epoch_id"],
        "current_operation_derived": driver.derive(parent, p82) == "outward-correct",
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "package_binding": binding, "counterexample_receipt_digest": disclosure["feedback_receipt_digest"], "operation_budget": MAX_OPERATIONS, "actor_budget": MAX_ACTORS, "pulse": PULSE, "checks": checks}
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, parent, result331, operation5, result330, packages, result280, core, base130 = setup(args)
    with tempfile.TemporaryDirectory() as directory:
        frozen = preflight(Path(directory), p82, runtime, parent, result331, operation5, result330, packages)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0332 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0332 preflight failed")
    package, binding = base.base.resolve_package(parent, packages, p82)
    subject = parent
    rows = []
    actor_count = 0
    boundary = None
    overlay = base.base.protected_overlay(parent)
    for index in range(1, MAX_OPERATIONS + 1):
        operation = driver.derive(subject, p82)
        if operation == "expand-environment":
            boundary = {"kind": "subject-derived-censoring-boundary", "operation": operation, "after_operation_count": len(rows)}
            break
        if operation not in {"outward-correct", "refresh-opportunity-projection", driver.base308.REPAIR_OPERATION}:
            boundary = {"kind": "unsupported-operation", "operation": operation, "after_operation_count": len(rows)}
            break
        actor_needed = operation == "outward-correct"
        if actor_count + int(actor_needed) > MAX_ACTORS:
            boundary = {"kind": "actor-budget", "operation": operation, "after_operation_count": len(rows)}
            break
        root = run / f"operation-{index:02d}"
        root.mkdir(parents=True)
        row, final = base.run_operation(index, root, subject, operation, repo, p82, runtime, package, result280, core, base130)
        row.pop("receipt_digest", None)
        row["state_resolved_package_receipt_digest"] = binding["receipt_digest"]
        row["contextual_overlay_exact"] = base.base.protected_overlay(final) == overlay
        row["checks"]["fresh_workspace"] = base.direct_fresh_workspace(root, row["actor"]) if actor_needed else row["checks"].get("fresh_workspace", True)
        row["checks"]["contextual_overlay_exact"] = row["contextual_overlay_exact"]
        row["checks"]["passed"] = base.base.recompute_checks(row["checks"])
        row["receipt_digest"] = p82.digest(row)
        rows.append(row)
        actor_count += row["fresh_actor_count"]
        write_json(run / f"operation-{index:02d}-result.json", row)
        write_json(run / f"operation-{index:02d}-subject.json", final)
        subject = final
        if not row["checks"]["passed"]:
            boundary = {"kind": "failed-operation", "operation": operation, "after_operation_count": len(rows)}
            break
    if boundary is None:
        boundary = {"kind": "operation-budget", "operation": driver.derive(subject, p82), "after_operation_count": len(rows)}
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    prior = corrections[:-1]
    final_correction = corrections[-1] if corrections else None
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "content_free_derived_sequence": 3 <= len(rows) <= MAX_OPERATIONS and operations[-2:] == ["refresh-opportunity-projection", driver.base308.REPAIR_OPERATION] and all(operation == "outward-correct" for operation in operations[:-2]) and all(row["checks"]["passed"] and row["checks"]["content_free"] for row in rows),
        "one_to_three_fresh_correctors": 1 <= actor_count == len(corrections) <= MAX_ACTORS,
        "prior_corrections_remain_unresolved": all(row["transition"] == "unresolved-to-more-correction" and row["world"]["result"]["matches"] < 6 and row["feedback"] for row in prior),
        "final_correction_6_vs_2": bool(final_correction and final_correction["transition"] == "success-to-refresh" and final_correction["world"]["result"]["matches"] == 6 and final_correction["world"]["unchanged_control"]["matches"] == 2),
        "g11_active": bool(corrections and all(row["observer_audit_regime"] == g11.AUTHORITY for row in corrections)),
        "derived_expand_environment_boundary": boundary == {"kind": "subject-derived-censoring-boundary", "operation": "expand-environment", "after_operation_count": len(rows)},
        "zero_remaining_opportunities": subject["active_opportunity_projection"]["opportunity_count"] == 0,
        "contextual_overlay_exact": base.base.protected_overlay(subject) == overlay,
        "final_open_conformant": subject["continuation"]["status"] == "open" and runtime.identity_conforms(subject),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "source_ot0331_receipt_digest": result331["receipt_digest"], "g11_transition_receipt_digest": result330["receipt_digest"], "state_resolved_package_binding": binding, "pulse": PULSE, "operation_receipt_digests": [row["receipt_digest"] for row in rows], "operations": operations, "correction_world_matches": [row["world"]["result"]["matches"] for row in corrections], "fresh_actor_count": actor_count, "boundary": boundary, "checks": checks, "operational_transition_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": subject["continuation"]["status"], "final_subject_digest": subject["artifact_digest"]}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", subject)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
