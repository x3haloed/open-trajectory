from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0348_delayed_continuation_policy_correction.py"
BASE_SHA256 = "2bd06152108337de24b70d87f14f58c4aec64892a0d817b016301063e4db8215"
PARENT_DIGEST = "708ea5a38b4a6dfc130095483d40e5339623b2d71a884add458118e9c8491cd6"
OT0348_AGGREGATE_DIGEST = "4082e293d0b095411f0377707b4ad876edc9114281aaf48d4ea1a5f9ccee615a"
OT0348_TRAINING_RECEIPT = "dce3fe17e44fd9447f9094c86a6a4d5f07a39376af6eab36a7ec2f82c489e649"
AUTHORITY = "ot-0349-actionable-policy-prediction-error"


def import_frozen(path: Path, expected: str, name: str):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name}: {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0349_frozen_ot0348")
write_json = base.write_json


def setup(args):
    repo, store, _, p82, runtime, core, base130, parent = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0349").resolve()
    aggregate_manifest = json.loads((repo / "evidence/manifests/OT-0348/delayed-policy-correction-aggregate.json").read_text())
    training_manifest = json.loads((repo / "evidence/manifests/OT-0348/delayed-policy-training-consequence.json").read_text())
    aggregate = json.loads(base.object_path(store, aggregate_manifest["sha256"]).read_bytes())
    training = json.loads(base.object_path(store, training_manifest["sha256"]).read_bytes())
    return repo, store, run, p82, runtime, core, base130, parent, aggregate, training


def compile_prediction_error(parent, training, p82):
    rows = training["worlds"]
    selected_id = training["incumbent_selected_world_id"]
    selected = next(row for row in rows if row["world_id"] == selected_id)
    alternatives = [row for row in rows if row["world_id"] != selected_id and row["admissible"] and row["floor_preserved"]]
    counterexample = max(alternatives, key=lambda row: (base.continuation_yield(row), -row["metrics"]["viable_contact_count"], row["world_id"]))
    selected_yield = base.continuation_yield(selected)
    counterexample_yield = base.continuation_yield(counterexample)
    body = {
        "authority": AUTHORITY + "-prediction-error",
        "source_subject_digest": parent["artifact_digest"],
        "source_policy_binding_digest": parent["active_world_consequence_policy"]["binding_digest"],
        "source_policy_program_digest": hashlib.sha256(base.INCUMBENT_SOURCE.encode()).hexdigest(),
        "source_consequence_receipt_digest": training["receipt_digest"],
        "declared_objective": parent["active_world_consequence_policy"]["policy"]["rationale"],
        "operative_proxy": "viable_contact_count",
        "predicted_relation": "A larger primary continuation proxy should not produce fewer independently verified reopened contacts than an admissible lower-proxy alternative.",
        "selected_observation": {"world_id": selected_id, "proxy_value": selected["metrics"]["viable_contact_count"], "verified_reopened_contact_count": selected_yield},
        "admissible_counterexample": {"world_id": counterexample["world_id"], "proxy_value": counterexample["metrics"]["viable_contact_count"], "verified_reopened_contact_count": counterexample_yield},
        "violation": selected["metrics"]["viable_contact_count"] > counterexample["metrics"]["viable_contact_count"] and selected_yield < counterexample_yield,
        "status": "unresolved",
        "next_operation": "resolve-selection-prediction-error",
        "selection_authority": False,
        "outcome_authority": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def seed_corrector(root: Path, parent, training, discrepancy, *, erase_linkage: bool):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "subject-position.json", {
        "source_subject_digest": parent["artifact_digest"],
        "continuation": parent["continuation"],
        "unresolved": parent["unresolved"],
        "exact_floor": {"pass_count": 40, "case_count": 40},
        "active_policy": parent["active_world_consequence_policy"]["policy"],
        "active_prediction_error": None if erase_linkage else discrepancy,
    })
    write_json(seed / "consequence.json", {"worlds": training["worlds"], "incumbent_selected_world_id": training["incumbent_selected_world_id"]})
    (seed / "policy.py").write_text(base.INCUMBENT_SOURCE)
    write_json(seed / "decision.json", {"decision": "retain", "rationale": "Replace with a grounded decision after inspecting the complete subject position and consequence."})
    (seed / "check_policy.py").write_text(base.POLICY_CHECKER)
    immutable = ["subject-position.json", "consequence.json", "check_policy.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["policy.py", "decision.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Continue from this exact subject position. Inspect the complete position and completed world consequence, then decide whether the inherited executable selection policy should be retained or revised. The policy must implement select_world(rows) and may use any actor-visible row structure, but must remain deterministic, order-invariant, id-generic, floor-preserving, and return only an admissible world id or None. The checker validates only this contract; it does not encode what should matter. Edit decision.json and edit policy.py only if revising. Run python3 check_policy.py, inspect the exact diff, and return the required report. Future catalogs, hidden contact cases, sibling output, controls, evaluator, role labels, and expected decision are unavailable.\n"
    )
    return seed


def run_corrector(context, root, parent, training, discrepancy, *, erased):
    label = "prediction-error-corrector-erased" if erased else "prediction-error-corrector"
    seed = seed_corrector(root, parent, training, discrepancy, erase_linkage=erased)
    output, audit0, workspace, _ = context.run_actor(label, seed, base.CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        source = (workspace / "policy.py").read_text()
        decision = json.loads((workspace / "decision.json").read_text())
        changed = source != base.INCUMBENT_SOURCE
        checker = subprocess.run([sys.executable, "check_policy.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        selected = base.choose(source, training["worlds"])
        # The retained public receipt omits private role/cutoff fields, so scan
        # its complete public identity surface directly.
        generic = not any(row["world_id"] in source or any(cid in source for cid in row["contact_ids"]) for row in training["worlds"])
        semantic = bool(immutable_ok and checker.returncode == 0 and generic and isinstance(decision, dict) and set(decision) == {"decision", "rationale"} and decision["decision"] in {"revise", "retain"} and ((decision["decision"] == "revise") == changed) and base.correction_output_valid(output, decision["decision"], changed))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        source, decision, changed, selected, generic = None, None, False, None, False
        immutable_ok = semantic = False
    files = ["policy.py", "decision.json"] if changed else ["decision.json"]
    audit, regime = base.audit_g13(context, label, output, audit0, semantic, files)
    selected_yield = next((base.continuation_yield(row) for row in training["worlds"] if row["world_id"] == selected), None)
    return {"accepted": bool(semantic and regime["challenger_accepted"]), "source": source, "source_digest": hashlib.sha256(source.encode()).hexdigest() if source else None, "decision": decision, "changed": changed, "selected_world_id": selected, "selected_yield": selected_yield, "generic": generic, "immutable_ok": immutable_ok, "output": output, "audit": audit, "g13": regime, "prediction_error_erased": erased}


def source_equivalent(left, right):
    for index in range(6):
        rows = base.public_rows(base.derive_worlds(hashlib.sha256(f"ot0349-equivalence-{index}".encode()).digest(), heldout=bool(index % 2)))
        if base.choose(left, rows) != base.choose(right, rows):
            return False
    return True


def preflight(parent, aggregate, training, p82, runtime):
    discrepancy = compile_prediction_error(parent, training, p82)
    selected = discrepancy["selected_observation"]
    counterexample = discrepancy["admissible_counterexample"]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        active_seed = seed_corrector(root / "active", parent, training, discrepancy, erase_linkage=False)
        erased_seed = seed_corrector(root / "erased", parent, training, discrepancy, erase_linkage=True)
        active_position = json.loads((active_seed / "subject-position.json").read_text())
        erased_position = json.loads((erased_seed / "subject-position.json").read_text())
        active_link = active_position.pop("active_prediction_error")
        erased_link = erased_position.pop("active_prediction_error")
        consequence_bytes_match = (active_seed / "consequence.json").read_bytes() == (erased_seed / "consequence.json").read_bytes()
        policy_and_checker_bytes_match = (active_seed / "policy.py").read_bytes() == (erased_seed / "policy.py").read_bytes() and (active_seed / "check_policy.py").read_bytes() == (erased_seed / "check_policy.py").read_bytes()
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and base.base.next_operation(parent, p82) == "test-world-consequence-policy-reuse",
        "ot0348_rejected_without_successor": aggregate["receipt_digest"] == OT0348_AGGREGATE_DIGEST and aggregate["observer_disposition"] == "rejected" and aggregate["final_subject_digest"] == PARENT_DIGEST and aggregate["heldout_seed_digest"] is None,
        "exact_training_receipt": training["receipt_digest"] == OT0348_TRAINING_RECEIPT and training["source_subject_digest"] == PARENT_DIGEST,
        "prediction_error_uses_retained_authorities": discrepancy["source_policy_binding_digest"] == parent["active_world_consequence_policy"]["binding_digest"] and discrepancy["source_consequence_receipt_digest"] == training["receipt_digest"],
        "proxy_outcome_inversion": discrepancy["violation"] and selected["proxy_value"] > counterexample["proxy_value"] and selected["verified_reopened_contact_count"] < counterexample["verified_reopened_contact_count"],
        "artifact_has_no_authority": not discrepancy["selection_authority"] and not discrepancy["outcome_authority"],
        "linkage_erasure_preserves_raw_consequence": consequence_bytes_match,
        "linkage_is_only_subject_position_difference": active_position == erased_position and active_link == discrepancy and erased_link is None,
        "matched_policy_and_checker_bytes": policy_and_checker_bytes_match,
        "reference_revision_improves": base.continuation_yield(next(row for row in training["worlds"] if row["world_id"] == base.choose(base.reference_source(), training["worlds"]))) > training["incumbent_realized_continuation_yield"],
        "g13_12_of_12": base.base.base.anchors()["pass_count"] == base.base.base.anchors()["case_count"] == 12,
        "g12_10_of_10": base.world_base.base.anchors()["pass_count"] == base.world_base.base.anchors()["case_count"] == 10,
        "g11_15_of_15": base.base.base.g11.evaluate(base.base.base.g11.g11)["pass_count"] == base.base.base.g11.evaluate(base.base.base.g11.g11)["case_count"] == 15,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0348_aggregate_digest": aggregate["receipt_digest"], "prediction_error": discrepancy, "checks": checks}
    return {**body, "receipt_digest": p82.digest(body)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--heldout-seed-output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, parent, aggregate348, training = setup(args)
    report = preflight(parent, aggregate348, training, p82, runtime)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0349 evidence")
    if args.heldout_seed_output is None or args.heldout_seed_output.exists():
        raise SystemExit("a nonexistent --heldout-seed-output is required")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0349 preflight failed")
    discrepancy = report["prediction_error"]
    context = base.world_base.policy_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    active = run_corrector(context, run / "active-corrector", parent, training, discrepancy, erased=False)
    erased = run_corrector(context, run / "erased-corrector", parent, training, discrepancy, erased=True)
    active_improves = bool(active["accepted"] and active["changed"] and active["selected_yield"] is not None and active["selected_yield"] > training["incumbent_realized_continuation_yield"])
    binding = base.bind_policy(parent, active, training["worlds"], p82) if active_improves else None
    if binding:
        import secrets
        heldout_seed = secrets.token_bytes(32)
        args.heldout_seed_output.parent.mkdir(parents=True, exist_ok=True)
        args.heldout_seed_output.write_bytes(heldout_seed)
        heldout_worlds = base.derive_worlds(heldout_seed, heldout=True)
    else:
        heldout_seed, heldout_worlds = None, []
    heldout_rows = base.public_rows(heldout_worlds)
    changed_choice = base.choose(binding["policy_source"], heldout_rows) if binding else None
    unchanged_choice = base.choose(base.INCUMBENT_SOURCE, heldout_rows) if binding else None
    changed_yield = next((base.continuation_yield(row) for row in heldout_rows if row["world_id"] == changed_choice), None)
    unchanged_yield = next((base.continuation_yield(row) for row in heldout_rows if row["world_id"] == unchanged_choice), None)
    selector = base.run_selector(context, run / "heldout-selector", binding, heldout_worlds) if binding and changed_yield is not None and changed_yield > unchanged_yield else None
    selected_world = next((world for world in heldout_worlds if selector and world["world_id"] == selector["decision"]["selected_world_id"]), None)
    contact_actor = base.run_contact(context, run / "heldout-contact", selector["decision"], selected_world) if selector and selector["accepted"] and selected_world else None
    if contact_actor and contact_actor["accepted"]:
        child, selection_receipt, frontier = base.compile_child(parent, binding, discrepancy, heldout_rows, selector, contact_actor, selected_world, p82)
    else:
        child, selection_receipt, frontier = parent, None, None
    erased_equivalent = bool(erased["accepted"] and erased["changed"] and erased["source"] and source_equivalent(erased["source"], active["source"]))
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "active_corrector_clean": active["accepted"],
        "active_revision_improves_training": active_improves,
        "linkage_erased_lacks_equivalent_revision": erased["accepted"] and not erased_equivalent,
        "policy_bound_before_heldout_derivation": bool(binding and heldout_seed),
        "heldout_absent_from_bound_source": bool(binding and base.source_is_generic(binding["policy_source"], heldout_worlds)),
        "changed_beats_unchanged_heldout": changed_yield is not None and unchanged_yield is not None and changed_yield > unchanged_yield and changed_choice != unchanged_choice,
        "machinery_erasure_restores_immediate_choice": unchanged_choice is not None and next(world["role"] for world in heldout_worlds if world["world_id"] == unchanged_choice) == "immediate",
        "heldout_selector_clean": bool(selector and selector["accepted"]),
        "selected_contact_clean": bool(contact_actor and contact_actor["accepted"]),
        "selected_contact_public_3_of_3": bool(contact_actor and contact_actor["public_result"]["pass_count"] == contact_actor["public_result"]["case_count"] == 3),
        "selected_contact_hidden_5_of_5": bool(contact_actor and contact_actor["hidden_result"]["pass_count"] == contact_actor["hidden_result"]["case_count"] == 5),
        "exact_floor_40_preserved": child.get("active_world_seeking_stake") == parent["active_world_seeking_stake"],
        "subject_only_actionable_frontier": child is not parent and child.get("continuation", {}).get("status") == "open" and base.materializes(child) and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "source_ot0348_aggregate_digest": aggregate348["receipt_digest"], "prediction_error": discrepancy, "active_corrector": active, "linkage_erased_corrector": erased, "policy_binding": binding, "heldout_seed_digest": hashlib.sha256(heldout_seed).hexdigest() if heldout_seed else None, "heldout_rows_digest": p82.digest(heldout_rows) if heldout_rows else None, "changed_heldout_selection": changed_choice, "unchanged_heldout_selection": unchanged_choice, "changed_heldout_yield": changed_yield, "unchanged_heldout_yield": unchanged_yield, "heldout_selector": selector, "heldout_contact_actor": contact_actor, "selection_receipt": selection_receipt, "frontier_binding": frontier, "checks": checks, "operational_transition_passed": checks["subject_only_actionable_frontier"], "prediction_error_substrate_causal_claim_supported": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else ("conditional" if checks["subject_only_actionable_frontier"] else "rejected"), "subject_disposition": child.get("continuation", {}).get("status") if child is not parent else "quarantined", "final_subject_digest": child["artifact_digest"], "fresh_actor_count": 2 + int(selector is not None) + int(contact_actor is not None)}
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", child)
    if checks["subject_only_actionable_frontier"]:
        write_json(run / "open-subject-after-actionable-prediction-error.json", child)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
