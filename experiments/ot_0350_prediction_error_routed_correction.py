from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import secrets
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0349_actionable_policy_prediction_error.py"
BASE_SHA256 = "3b38d41a079699a61fbac544871c55ecf947b9d05143f6f2b460183ac70dc84e"
PARENT_DIGEST = "708ea5a38b4a6dfc130095483d40e5339623b2d71a884add458118e9c8491cd6"
OT0349_AGGREGATE_DIGEST = "01b8deab59860ffe844fffb52c420f8e810cb6d0cf36e20ce74d15737e36d794"
AUTHORITY = "ot-0350-prediction-error-routed-correction"


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


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0350_frozen_ot0349")
prior = base.base
write_json = prior.write_json


def setup(args):
    repo, store, _, p82, runtime, core, base130, parent, aggregate348, training = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0350").resolve()
    manifest = json.loads((repo / "evidence/manifests/OT-0349/actionable-prediction-error-aggregate.json").read_text())
    aggregate349 = json.loads(prior.object_path(store, manifest["sha256"]).read_bytes())
    return repo, store, run, p82, runtime, core, base130, parent, aggregate348, training, aggregate349


def compile_branch(parent, training, discrepancy, p82, *, erase_linkage):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    consequence_ref = {
        "authority": AUTHORITY + "-retained-delayed-consequence",
        "source_subject_digest": parent["artifact_digest"],
        "source_receipt_digest": training["receipt_digest"],
        "world_rows_digest": p82.digest(training["worlds"]),
        "world_authority": True,
        "outcome_authority": True,
        "scoring_authority": True,
        "actor_authority": False,
    }
    consequence_ref["receipt_digest"] = p82.digest(consequence_ref)
    child["delayed_continuation_consequences"] = [*child.get("delayed_continuation_consequences", []), consequence_ref]
    if erase_linkage:
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Test the retained world-consequence policy on a fresh consequence catalog without sacrificing the global 40/40 floor."}
    else:
        child["selection_prediction_errors"] = [*child.get("selection_prediction_errors", []), discrepancy]
        child["active_selection_prediction_error"] = discrepancy
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Resolve the active selection prediction error before further policy reuse."}
    return p82.seal(child), consequence_ref


def next_operation(subject, p82):
    error = subject.get("active_selection_prediction_error")
    if error:
        valid = bool(
            error.get("status") == "unresolved"
            and error.get("next_operation") == "resolve-selection-prediction-error"
            and error.get("violation") is True
            and error.get("source_subject_digest") == PARENT_DIGEST
            and error.get("source_policy_binding_digest") == subject["active_world_consequence_policy"]["binding_digest"]
            and any(row.get("source_receipt_digest") == error.get("source_consequence_receipt_digest") for row in subject.get("delayed_continuation_consequences", []))
        )
        return "resolve-selection-prediction-error" if valid else None
    architecture = subject.get("active_selection_architecture", {})
    if architecture.get("next_operation") == "test-world-consequence-policy-reuse" and "fresh consequence catalog" in subject.get("continuation", {}).get("next_opening", ""):
        return "test-world-consequence-policy-reuse"
    return None


def incumbent_binding(subject, training, p82):
    body = {
        "authority": AUTHORITY + "-compiled-incumbent-policy",
        "source_subject_digest": subject["artifact_digest"],
        "source_policy_binding_digest": subject["active_world_consequence_policy"]["binding_digest"],
        "training_consequence_digest": p82.digest(training["worlds"]),
        "policy_source": prior.INCUMBENT_SOURCE,
        "policy_source_digest": hashlib.sha256(prior.INCUMBENT_SOURCE.encode()).hexdigest(),
        "selection_authority": True,
        "world_authority": False,
        "outcome_authority": False,
        "scoring_authority": False,
    }
    return {**body, "binding_digest": p82.digest(body)}


def compile_control_child(subject, binding, heldout_rows, selector, contact_actor, selected_world, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    selection = {
        "authority": AUTHORITY + "-control-heldout-selection",
        "source_subject_digest": subject["artifact_digest"],
        "policy_binding_digest": binding["binding_digest"],
        "heldout_rows_digest": p82.digest(heldout_rows),
        "decision": selector["decision"],
        "actor_patch_digest": selector["audit"]["patch_digest"],
        "selection_authority": True,
        "world_authority": False,
        "outcome_authority": False,
    }
    selection["receipt_digest"] = p82.digest(selection)
    consequence = {
        "authority": AUTHORITY + "-control-contact-consequence",
        "source_subject_digest": subject["artifact_digest"],
        "selected_world_id": selected_world["world_id"],
        "source_contact_id": contact_actor["contact_id"],
        "source_actor_patch_digest": contact_actor["audit"]["patch_digest"],
        "public_result": contact_actor["public_result"],
        "hidden_result": contact_actor["hidden_result"],
        "verified_downstream_contact_ids": [row["contact_id"] for row in selected_world["future_contacts"]],
        "world_authority": True,
        "outcome_authority": True,
        "scoring_authority": True,
        "actor_authority": False,
    }
    consequence["receipt_digest"] = p82.digest(consequence)
    child["delayed_continuation_policy_selections"] = [*child.get("delayed_continuation_policy_selections", []), selection]
    child["completed_contact_consequences"] = [*child.get("completed_contact_consequences", []), consequence]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Test the retained world-consequence policy on a fresh consequence catalog without sacrificing the global 40/40 floor."}
    child["unresolved"] = "Can raw policy reuse discover and correct its immediate-count proxy failure without a routed prediction error?"
    return p82.seal(child), selection, consequence


def preflight(parent, aggregate348, training, aggregate349, p82, runtime):
    discrepancy = base.compile_prediction_error(parent, training, p82)
    active, active_consequence = compile_branch(parent, training, discrepancy, p82, erase_linkage=False)
    erased, erased_consequence = compile_branch(parent, training, discrepancy, p82, erase_linkage=True)
    stripped_active = copy.deepcopy(active)
    stripped_erased = copy.deepcopy(erased)
    for row in (stripped_active, stripped_erased):
        row.pop("artifact_digest", None)
        row.pop("continuation", None)
    stripped_active.pop("selection_prediction_errors", None)
    stripped_active.pop("active_selection_prediction_error", None)
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and prior.base.next_operation(parent, p82) == "test-world-consequence-policy-reuse",
        "ot0348_exact_negative_source": aggregate348["receipt_digest"] == base.OT0348_AGGREGATE_DIGEST and aggregate348["observer_disposition"] == "rejected",
        "ot0349_exact_conditional_source": aggregate349["receipt_digest"] == OT0349_AGGREGATE_DIGEST and aggregate349["operational_transition_passed"] and not aggregate349["prediction_error_substrate_causal_claim_supported"],
        "branches_share_exact_raw_consequence": active_consequence == erased_consequence and stripped_active == stripped_erased,
        "active_routes_correction": next_operation(active, p82) == "resolve-selection-prediction-error",
        "erasure_routes_policy_reuse": next_operation(erased, p82) == "test-world-consequence-policy-reuse",
        "malformed_error_fails_closed": next_operation({**active, "active_selection_prediction_error": {**discrepancy, "violation": False}}, p82) is None,
        "incumbent_binding_is_exact": incumbent_binding(erased, training, p82)["policy_source_digest"] == hashlib.sha256(prior.INCUMBENT_SOURCE.encode()).hexdigest(),
        "g13_12_of_12": prior.base.base.anchors()["pass_count"] == prior.base.base.anchors()["case_count"] == 12,
        "g12_10_of_10": prior.world_base.base.anchors()["pass_count"] == prior.world_base.base.anchors()["case_count"] == 10,
        "g11_15_of_15": prior.base.base.g11.evaluate(prior.base.base.g11.g11)["pass_count"] == prior.base.base.g11.evaluate(prior.base.base.g11.g11)["case_count"] == 15,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0349_aggregate_digest": aggregate349["receipt_digest"], "active_branch_digest": active["artifact_digest"], "erased_branch_digest": erased["artifact_digest"], "prediction_error": discrepancy, "checks": checks}
    return {**body, "receipt_digest": p82.digest(body)}, active, erased


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--heldout-seed-output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, parent, aggregate348, training, aggregate349 = setup(args)
    report, active_subject, control_subject = preflight(parent, aggregate348, training, aggregate349, p82, runtime)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0350 evidence")
    if args.heldout_seed_output is None or args.heldout_seed_output.exists():
        raise SystemExit("a nonexistent --heldout-seed-output is required")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    write_json(run / "active-subject-before-routing.json", active_subject)
    write_json(run / "control-subject-before-routing.json", control_subject)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0350 preflight failed")

    active_context = prior.world_base.policy_base.contact.base305.actor_context(runtime, core, base130, run / "active-actors", repo)
    # The fixed driver opens a corrector only on the active route.
    corrector = base.run_corrector(active_context, run / "active-corrector", active_subject, training, report["prediction_error"], erased=False)
    improves = bool(corrector["accepted"] and corrector["changed"] and corrector["selected_yield"] is not None and corrector["selected_yield"] > training["incumbent_realized_continuation_yield"])
    active_binding = prior.bind_policy(active_subject, corrector, training["worlds"], p82) if improves else None
    control_binding = incumbent_binding(control_subject, training, p82) if active_binding else None

    # Seal both policy identities before generating the held-out world or
    # running any control actor.
    if active_binding:
        write_json(run / "sealed-active-policy-binding.json", active_binding)
        write_json(run / "sealed-control-policy-binding.json", control_binding)
        heldout_seed = secrets.token_bytes(32)
        args.heldout_seed_output.parent.mkdir(parents=True, exist_ok=True)
        args.heldout_seed_output.write_bytes(heldout_seed)
        worlds = prior.derive_worlds(heldout_seed, heldout=True)
    else:
        heldout_seed, worlds = None, []
    rows = prior.public_rows(worlds)

    active_choice = prior.choose(active_binding["policy_source"], rows) if active_binding else None
    control_choice = prior.choose(control_binding["policy_source"], rows) if control_binding else None
    active_yield = next((prior.continuation_yield(row) for row in rows if row["world_id"] == active_choice), None)
    control_yield = next((prior.continuation_yield(row) for row in rows if row["world_id"] == control_choice), None)

    active_selector = prior.run_selector(active_context, run / "active-selector", active_binding, worlds) if active_binding else None
    active_world = next((world for world in worlds if active_selector and world["world_id"] == active_selector["decision"]["selected_world_id"]), None)
    active_contact = prior.run_contact(active_context, run / "active-contact", active_selector["decision"], active_world) if active_selector and active_selector["accepted"] and active_world else None

    control_context = prior.world_base.policy_base.contact.base305.actor_context(runtime, core, base130, run / "control-actors", repo)
    control_selector = prior.run_selector(control_context, run / "control-selector", control_binding, worlds) if control_binding else None
    control_world = next((world for world in worlds if control_selector and world["world_id"] == control_selector["decision"]["selected_world_id"]), None)
    control_contact = prior.run_contact(control_context, run / "control-contact", control_selector["decision"], control_world) if control_selector and control_selector["accepted"] and control_world else None

    if active_contact and active_contact["accepted"]:
        active_child, active_selection_receipt, active_frontier = prior.compile_child(active_subject, active_binding, report["prediction_error"], rows, active_selector, active_contact, active_world, p82)
        active_child.pop("active_selection_prediction_error", None)
        active_child = p82.seal({key: value for key, value in active_child.items() if key != "artifact_digest"})
    else:
        active_child, active_selection_receipt, active_frontier = active_subject, None, None
    if control_contact and control_contact["accepted"]:
        control_child, control_selection_receipt, control_consequence = compile_control_child(control_subject, control_binding, rows, control_selector, control_contact, control_world, p82)
    else:
        control_child, control_selection_receipt, control_consequence = control_subject, None, None

    checks = {
        "preflight_passed": report["checks"]["passed"],
        "driver_routes_differ": next_operation(active_subject, p82) == "resolve-selection-prediction-error" and next_operation(control_subject, p82) == "test-world-consequence-policy-reuse",
        "only_active_received_correction_actor": corrector["accepted"],
        "active_revision_improves_training": improves,
        "active_bound_before_heldout_and_control": bool(active_binding and heldout_seed),
        "both_selectors_clean": bool(active_selector and control_selector and active_selector["accepted"] and control_selector["accepted"]),
        "both_contacts_clean": bool(active_contact and control_contact and active_contact["accepted"] and control_contact["accepted"]),
        "both_public_3_of_3": bool(active_contact and control_contact and all(actor["public_result"]["pass_count"] == actor["public_result"]["case_count"] == 3 for actor in (active_contact, control_contact))),
        "both_hidden_5_of_5": bool(active_contact and control_contact and all(actor["hidden_result"]["pass_count"] == actor["hidden_result"]["case_count"] == 5 for actor in (active_contact, control_contact))),
        "active_four_control_zero": active_yield == 4 and control_yield == 0 and active_choice != control_choice,
        "machinery_erasure_reproduces_control": active_binding is not None and prior.choose(prior.INCUMBENT_SOURCE, rows) == control_choice,
        "active_frontier_actionable": active_child is not active_subject and active_child["continuation"]["status"] == "open" and prior.materializes(active_child) and runtime.identity_conforms(active_child),
        "control_reopens_policy_reuse": control_child is not control_subject and control_child["continuation"]["status"] == "open" and next_operation(control_child, p82) == "test-world-consequence-policy-reuse" and runtime.identity_conforms(control_child),
        "exact_floor_40_both": active_child["active_world_seeking_stake"] == parent["active_world_seeking_stake"] and control_child["active_world_seeking_stake"] == parent["active_world_seeking_stake"],
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "preflight_receipt_digest": report["receipt_digest"], "active_route": next_operation(active_subject, p82), "control_route": next_operation(control_subject, p82), "active_corrector": corrector, "active_policy_binding": active_binding, "control_policy_binding": control_binding, "heldout_seed_digest": hashlib.sha256(heldout_seed).hexdigest() if heldout_seed else None, "heldout_rows_digest": p82.digest(rows) if rows else None, "active_selection": active_choice, "control_selection": control_choice, "active_yield": active_yield, "control_yield": control_yield, "active_selector": active_selector, "control_selector": control_selector, "active_contact": active_contact, "control_contact": control_contact, "active_selection_receipt": active_selection_receipt, "control_selection_receipt": control_selection_receipt, "active_frontier": active_frontier, "control_consequence": control_consequence, "checks": checks, "prediction_error_routing_causal_claim_supported": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "active_subject_disposition": active_child["continuation"]["status"] if checks["active_frontier_actionable"] else "quarantined", "control_subject_disposition": control_child["continuation"]["status"] if checks["control_reopens_policy_reuse"] else "quarantined", "final_active_subject_digest": active_child["artifact_digest"], "final_control_subject_digest": control_child["artifact_digest"], "fresh_actor_count": 1 + int(active_selector is not None) + int(active_contact is not None) + int(control_selector is not None) + int(control_contact is not None)}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-active-subject.json", active_child)
    write_json(run / "final-control-subject.json", control_child)
    if checks["active_frontier_actionable"]:
        write_json(run / "open-subject-after-routed-policy-correction.json", active_child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
