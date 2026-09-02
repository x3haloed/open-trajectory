from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0329_state_resolved_resumptive_continuation.py"
BASE_SHA256 = "5fb6277dd593ff53f3e381e6aa077cc017e7dd15ae1ad3e0e69d1dd499d24690"
G11_PATH = ROOT / "ot_0330_attributed_command_failure_audit.py"
G11_SHA256 = "f80d3f90ccbf4e5488d0d1b4fbad776e2c5816a9f3ddf1b435f833e9c0eaf2d9"
PARENT_DIGEST = "10c27b8e2f8a01a20d0e182192243f5010fd070da4f90440b3d0ad7d81552dc1"
OT329_RECEIPT = "eefe883564424fb748b432f350b7e67513625726ea5af906bbfee7c8d050a1da"
G11_RECEIPT = "c3cc1114e07d73a2f862488b079c019153b885bb2bb2f3de2759c7fefa73df0f"
AUTHORITY = "ot-0331-g11-resumptive-continuation"
MAX_OPERATIONS = 7
MAX_ACTORS = 3
PULSE = None


def load_module(name, path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name} {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_module("ot0331_frozen_ot0329", BASE_PATH, BASE_SHA256)
g11 = load_module("ot0331_frozen_g11", G11_PATH, G11_SHA256)
driver = base.driver
write_json = base.write_json


def set_authority():
    base.AUTHORITY = AUTHORITY
    for module in (driver, driver.base309, driver.base308, driver.base307):
        module.AUTHORITY = AUTHORITY
    driver.b.AUTHORITY = AUTHORITY
    driver.b.base274.AUTHORITY = AUTHORITY
    driver.b.base274.base273.AUTHORITY = AUTHORITY
    driver.b.base274.base271.AUTHORITY = AUTHORITY
    driver.b.base272.base252.AUTHORITY = AUTHORITY
    driver.b.base272.base245.AUTHORITY = AUTHORITY
    driver.b.base272.base270.AUTHORITY = AUTHORITY
    driver.PULSE = PULSE


set_authority()


def setup(args):
    repo, store, _, p82, runtime, parent326, seed326, parent327, result327, reconstruction327, private327, core, base130 = base.base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0331").resolve()
    selector = base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    parent = load("OT-0329", "open-subject-after-first-resumed-selection.json")
    result329 = load("OT-0329", "state-resolved-resumptive-continuation-rejected-aggregate.json")
    operation1 = load("OT-0329", "reconstructed-first-selection-operation.json")
    result330 = load("OT-0330", "attributed-command-failure-audit-aggregate.json")
    packages = [load("OT-0305", f"subject-blind-provider-{index:02d}-world-package.json") for index in range(1, 5)]
    result280 = load("OT-0280", "import-stable-world-evaluator-aggregate.json")
    return repo, store, run, p82, runtime, parent, result329, operation1, result330, packages, result280, core, base130


def g11_context(original_context, runtime, root, repo):
    context = original_context(runtime, root, repo)
    original_audit = context.audit_actor

    def audit(label, output, base_audit, artifact_valid, expected_changes):
        retained = original_audit(label, output, base_audit, artifact_valid, expected_changes)
        evidence = context.evidence(label)
        events = (evidence / "events.jsonl").read_text()
        stderr = (evidence / "stderr.txt").read_text()
        classified = g11.retained_row(retained, events, stderr)
        body = {
            "authority": g11.AUTHORITY,
            "event_trace_sha256": hashlib.sha256(events.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
            "incumbent_accepted": g11.incumbent(classified),
            "challenger_accepted": g11.g11(classified),
        }
        body["recovery_applied"] = bool(not body["incumbent_accepted"] and body["challenger_accepted"])
        retained["g11_attributed_command_audit"] = body
        return retained

    context.audit_actor = audit
    return context


def run_g11_correction(index, root, subject, repo, p82, runtime, package, result280, core, base130):
    base236 = driver.b.base274.base271.base236
    original_classify = base236.classify_retained
    original_g10 = base236.g10
    context_module = driver.base307.base274
    original_context = context_module.context_for

    def classify(audit, trace):
        normalized = original_classify(audit, trace)
        certificate = audit.get("g11_attributed_command_audit", {})
        normalized["g11_recovery_applied"] = bool(
            certificate.get("authority") == g11.AUTHORITY
            and certificate.get("recovery_applied")
        )
        return normalized

    def admitted(normalized):
        return bool(original_g10(normalized) or normalized.get("g11_recovery_applied"))

    def context_for(core_arg, base130_arg, runtime_arg, root_arg, repo_arg):
        return g11_context(lambda r, x, q: original_context(core_arg, base130_arg, r, x, q), runtime_arg, root_arg, repo_arg)

    base236.classify_retained = classify
    base236.g10 = admitted
    context_module.context_for = context_for
    driver.b.base274.context_for = context_for
    try:
        row, final = driver.run_operation(index, root, subject, "outward-correct", repo, p82, runtime, package, result280, core, base130)
    finally:
        base236.classify_retained = original_classify
        base236.g10 = original_g10
        context_module.context_for = original_context
        driver.b.base274.context_for = original_context
    row["observer_audit_regime"] = g11.AUTHORITY
    row["g11_recovery_applied"] = bool(row["actor"]["audit"].get("g11_attributed_command_audit", {}).get("recovery_applied"))
    return row, final


def run_operation(index, root, subject, operation, repo, p82, runtime, package, result280, core, base130):
    if operation == "outward-correct":
        return run_g11_correction(index, root, subject, repo, p82, runtime, package, result280, core, base130)
    row, final = driver.run_operation(index, root, subject, operation, repo, p82, runtime, package, result280, core, base130)
    row["observer_audit_regime"] = "G10-contained-denial-authority" if row.get("actor") else None
    row["g11_recovery_applied"] = False
    return row, final


def direct_fresh_workspace(root, actor):
    certificate = actor.get("audit", {}).get("g11_attributed_command_audit")
    if not certificate:
        return base.direct_fresh_workspace(root, actor)
    workspaces = sorted(root.glob("*/actor-workspace"))
    if len(workspaces) != 1:
        return False
    workspace = workspaces[0]
    evidence = workspace.parent
    seed = root / "actor/seed"
    try:
        retained = json.loads((evidence / "actor-audit.json").read_text())
        events = (evidence / "events.jsonl").read_text()
        stderr = (evidence / "stderr.txt").read_text()
    except (OSError, json.JSONDecodeError):
        return False
    expected = copy.deepcopy(actor["audit"])
    expected.pop("g11_attributed_command_audit", None)
    certificate_exact = bool(
        certificate.get("authority") == g11.AUTHORITY
        and certificate.get("event_trace_sha256") == hashlib.sha256(events.encode()).hexdigest()
        and certificate.get("stderr_sha256") == hashlib.sha256(stderr.encode()).hexdigest()
        and certificate.get("challenger_accepted") is True
    )
    return bool(
        workspace.resolve().is_relative_to(root.resolve())
        and workspace.resolve() != seed.resolve()
        and (workspace / ".git").is_dir()
        and seed.is_dir()
        and retained == expected
        and retained.get("conformant")
        and retained.get("trace_regime", {}).get("accepted")
        and retained.get("denial_classification_v2", {}).get("accepted")
        and certificate_exact
    )


def reconstruct_audit_annotation_failure(run, p82):
    aggregate = json.loads((run / "aggregate.json").read_text())
    row = json.loads((run / "operation-01-result.json").read_text())
    subject = json.loads((run / "operation-01-subject.json").read_text())
    failed = [key for key, value in row["checks"].items() if not value]
    exact = bool(
        aggregate.get("observer_disposition") == "rejected"
        and aggregate.get("boundary") == {"kind": "failed-operation", "operation": "outward-correct", "after_operation_count": 1}
        and failed == ["fresh_workspace", "passed"]
        and row.get("observer_audit_regime") == g11.AUTHORITY
        and row.get("actor", {}).get("accepted")
        and row.get("actor", {}).get("g10_disposition")
        and row.get("world", {}).get("result", {}).get("matches") == 6
        and row.get("world", {}).get("unchanged_control", {}).get("matches") == 2
        and row.get("final_subject_digest") == subject.get("artifact_digest")
        and direct_fresh_workspace(run / "operation-01", row["actor"])
    )
    if not exact:
        raise RuntimeError("existing OT-0331 output is not the audit-annotation-only failure")
    write_json(run / "aggregate-before-audit-annotation-repair.json", aggregate)
    write_json(run / "operation-01-before-audit-annotation-repair.json", row)
    body = {
        "authority": AUTHORITY + "-audit-annotation-repair",
        "failed_aggregate_receipt_digest": aggregate["receipt_digest"],
        "failed_operation_receipt_digest": row["receipt_digest"],
        "actor_patch_digest": row["actor"]["audit"]["patch_digest"],
        "failure": "post-audit G11 certificate made the in-memory audit a strict superset of the retained base audit",
        "repair": "compare retained base audit exactly after removing only the G11 certificate and verify that certificate against retained trace and stderr digests",
        "actor_resampled": False,
        "world_resampled": False,
        "scientific_information_changed": False,
    }
    repair = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "audit-annotation-repair.json", repair)
    row.pop("receipt_digest", None)
    row["audit_annotation_repair_receipt_digest"] = repair["receipt_digest"]
    row["checks"]["fresh_workspace"] = True
    row["checks"]["passed"] = base.recompute_checks(row["checks"])
    row["receipt_digest"] = p82.digest(row)
    write_json(run / "operation-01-result.json", row)
    return [row], subject, 1, repair


def preflight(root, repo, p82, runtime, parent, result329, operation1, result330, packages):
    root.mkdir(parents=True, exist_ok=True)
    package, binding = base.resolve_package(parent, packages, p82)
    selected = driver.b.base274.base271.selected(parent)
    inherited_target = {"target_path": selected[5], "target_symbol": selected[4]}
    remaining = parent["active_opportunity_projection"]["opportunities"]
    route, identity = driver.b.base272.base265.floors(parent)
    heldout = g11.evaluate(g11.g11)
    checks = {
        "source_hashes_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256 and hashlib.sha256(G11_PATH.read_bytes()).hexdigest() == G11_SHA256,
        "exact_open_partial_parent": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "ot0329_exact_rejection": result329["receipt_digest"] == OT329_RECEIPT and result329["observer_disposition"] == "rejected" and result329["final_subject_digest"] == PARENT_DIGEST,
        "operation_one_exact_source": operation1["checks"]["passed"] and operation1["final_subject_digest"] == PARENT_DIGEST and operation1["pulse"]["derived_operation"] == "expanded-select",
        "g11_exact_promotion": result330["receipt_digest"] == G11_RECEIPT and result330["observer_disposition"] == "promoted" and result330["checks"]["passed"],
        "g11_heldout_15_of_15": heldout["pass_count"] == heldout["case_count"] == 15,
        "state_resolved_package": binding["active_epoch_id"] == parent["active_opportunity_projection"]["active_epoch_id"],
        "current_operation_derived": driver.derive(parent, p82) == "outward-correct",
        "selected_target_still_projected": inherited_target in remaining,
        "two_live_surfaces": len(remaining) == 2,
        "rejected_patch_not_in_subject": parent["actor_authored_environment_epochs"][-1]["visible_sources"][selected[5]]["source"] != "def enter_archive(case):\n    return 18 <= case[\"hour\"] < 23\n",
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "package_binding": binding, "inherited_selected_target": inherited_target, "operation_budget": MAX_OPERATIONS, "actor_budget": MAX_ACTORS, "pulse": PULSE, "checks": checks}
    report = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, parent, result329, operation1, result330, packages, result280, core, base130 = setup(args)
    with tempfile.TemporaryDirectory() as directory:
        frozen = preflight(Path(directory), repo, p82, runtime, parent, result329, operation1, result330, packages)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    repair = None
    if (run / "aggregate.json").exists():
        rows, subject, actor_count, repair = reconstruct_audit_annotation_failure(run, p82)
    elif run.exists():
        raise SystemExit("preserve incomplete OT-0331 evidence")
    else:
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", frozen)
        rows = []
        subject = parent
        actor_count = 0
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0331 preflight failed")
    package, binding = base.resolve_package(parent, packages, p82)
    boundary = None
    overlay = base.protected_overlay(parent)
    allowed = {"outward-correct", "refresh-opportunity-projection", driver.base308.REPAIR_OPERATION, "expanded-select"}
    for index in range(len(rows) + 1, MAX_OPERATIONS + 1):
        operation = driver.derive(subject, p82)
        if operation not in allowed:
            boundary = {"kind": "subject-derived-censoring-boundary", "operation": operation, "after_operation_count": len(rows)}
            break
        actor_needed = operation in {"expanded-select", "outward-correct"}
        if actor_count + int(actor_needed) > MAX_ACTORS:
            boundary = {"kind": "actor-budget", "operation": operation, "after_operation_count": len(rows)}
            break
        op_root = run / f"operation-{index:02d}"
        op_root.mkdir(parents=True)
        row_value, final = run_operation(index, op_root, subject, operation, repo, p82, runtime, package, result280, core, base130)
        row_value.pop("receipt_digest", None)
        row_value["state_resolved_package_receipt_digest"] = binding["receipt_digest"]
        row_value["contextual_overlay_exact"] = base.protected_overlay(final) == overlay
        row_value["checks"]["fresh_workspace"] = direct_fresh_workspace(op_root, row_value["actor"]) if actor_needed else row_value["checks"].get("fresh_workspace", True)
        row_value["checks"]["contextual_overlay_exact"] = row_value["contextual_overlay_exact"]
        row_value["checks"]["passed"] = base.recompute_checks(row_value["checks"])
        row_value["receipt_digest"] = p82.digest(row_value)
        rows.append(row_value)
        actor_count += row_value["fresh_actor_count"]
        write_json(run / f"operation-{index:02d}-result.json", row_value)
        write_json(run / f"operation-{index:02d}-subject.json", final)
        subject = final
        if not row_value["checks"]["passed"]:
            boundary = {"kind": "failed-operation", "operation": operation, "after_operation_count": len(rows)}
            break
    if boundary is None:
        boundary = {"kind": "operation-budget", "operation": driver.derive(subject, p82), "after_operation_count": len(rows)}
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    selections = [row for row in rows if row["pulse"]["derived_operation"] == "expanded-select"]
    inherited_target = driver.b.base274.base271.selected(parent)[4:6]
    selected_targets = [(inherited_target[1], inherited_target[0])] + [(row["actor"]["decision"]["next_contact"]["target_path"], row["actor"]["decision"]["next_contact"]["target_symbol"]) for row in selections]
    initial = [(row["target_path"], row["target_symbol"]) for row in parent["active_opportunity_projection"]["opportunities"]]
    expected = ["outward-correct", "refresh-opportunity-projection", driver.base308.REPAIR_OPERATION, "expanded-select", "outward-correct", "refresh-opportunity-projection", driver.base308.REPAIR_OPERATION]
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "exact_state_driven_sequence": operations == expected,
        "all_operations_pass": len(rows) == MAX_OPERATIONS and all(row["checks"]["passed"] and row["checks"]["content_free"] for row in rows),
        "both_targets_completed_once": sorted(selected_targets) == sorted(initial),
        "inherited_and_new_contradiction": operation1["world"]["result"]["matches"] == 2 and len(selections) == 1 and selections[0]["world"]["result"]["matches"] == 2,
        "two_independent_corrections": len(corrections) == 2 and all(row["world"]["result"]["matches"] == 6 and row["world"]["unchanged_control"]["matches"] == 2 for row in corrections),
        "g11_active_for_corrections": len(corrections) == 2 and all(row["observer_audit_regime"] == g11.AUTHORITY for row in corrections),
        "three_fresh_actors": actor_count == MAX_ACTORS == sum(row["fresh_actor_count"] for row in rows),
        "derived_expand_environment_boundary": boundary == {"kind": "operation-budget", "operation": "expand-environment", "after_operation_count": MAX_OPERATIONS},
        "zero_remaining_opportunities": subject["active_opportunity_projection"]["opportunity_count"] == 0,
        "contextual_overlay_exact": base.protected_overlay(subject) == overlay,
        "final_open_conformant": subject["continuation"]["status"] == "open" and runtime.identity_conforms(subject),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "source_ot0329_receipt_digest": result329["receipt_digest"], "g11_transition_receipt_digest": result330["receipt_digest"], "audit_annotation_repair": repair, "state_resolved_package_binding": binding, "pulse": PULSE, "operation_receipt_digests": [row["receipt_digest"] for row in rows], "operations": operations, "selected_targets": selected_targets, "fresh_actor_count": actor_count, "boundary": boundary, "checks": checks, "operational_transition_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": subject["continuation"]["status"], "final_subject_digest": subject["artifact_digest"]}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", subject)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
