from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0127_contextual_transfer_grounding.py"
BASE_SHA256 = "6f653079f50044d78c36e6bd7ca508d9ed2311ad15f03a20345ce79bbe2cdea2"
PARENT_DIGEST = "2ce904e9cbdb853e9e0086d050397991fad7fa8cc5bb416d480db3f1ede30aa4"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0127 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0128_frozen_ot0127", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
scheduler = previous.previous
prior = previous.prior
prior22 = previous.prior22
base = previous.base
prior17 = scheduler.prior17
prior18 = previous.prior18


def stage_grounded(stage_index, value):
    if stage_index == 2:
        return previous.contextual_transfer_grounded(value)
    return prior.has_concepts(value, prior.STAGES[stage_index]["next_concepts"])


def run_router(prior89, p82, context, cycle_root, parent, corrected, selection, world, stage_index):
    label = f"cycle-{stage_index + 1}-router"
    seed = scheduler.compressed_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index)
    if stage_index == 2:
        contract = json.loads((seed / "complete-transition-contract.json").read_text())
        contract["contextual_transfer_equivalence"] = "context and (cross or different)"
        (seed / "complete-transition-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior22.ROUTER_SCHEMA, "Continue the exact subject under the final continuation-owned scheduler contract. Let the authoritative next opening carry the complete remaining stake, keep the registry id new and structurally valid, inspect the exact diff, and report truthfully.")
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        action = json.loads((workspace / "continuation-action.json").read_text())
        retained = (workspace / "selector.py").read_text() == corrected
    except (OSError, json.JSONDecodeError):
        route = opening = action = None
        retained = False
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    cited = set(route.get("settled_case_ids", [])) if isinstance(route, dict) else set()
    old_target = parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"]
    coherence = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "case_ids_exact": cited == expected_ids,
        "selector_retained": retained,
        "opening_changed": bool(opening and opening.get("next_opening") != parent["continuation"]["next_opening"]),
        "opening_grounded": bool(opening and stage_grounded(stage_index, opening.get("next_opening"))),
        "continuation_grounded": bool(opening and stage_grounded(stage_index, opening.get("continuation_after_contact"))),
        "remaining_uncertainty_grounded": bool(route and stage_grounded(stage_index, route.get("remaining_uncertainty"))),
        "expected_information_grounded": bool(action and stage_grounded(stage_index, action.get("expected_information"))),
        "action_valid": bool(action and prior18.previous.previous.repaired_action_valid(action, parent)),
        "action_target_changed": bool(action and action.get("action_target") != old_target),
    }
    coherence["passed"] = all(coherence.values())
    valid = bool(prior22.valid_route(route) and prior89.valid_successor(opening) and coherence["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json", "successor-opening.json", "continuation-action.json"])
    accepted = bool(audit["conformant"] and audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"] and not audit["denial_classification_v2"]["protected_path_named"] and not audit["denial_classification_v2"]["outside_file_changes"])
    binding = None
    if accepted:
        body = {
            "authority": "ot-0128-clean-recurrent-route",
            "cycle": stage_index + 1,
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": selection["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "scheduler_authority": "successor_opening.next_opening",
            "registry_identity_authority": "continuation_action.action_target",
            "coherence": coherence,
            "selector_retention_derived": retained,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "coherence": coherence, "binding": binding}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0128").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent, corrected, precorrection = prior.load_parent(p82, repo, store)
    stage_checks = [prior.stage_conformance(index, corrected, precorrection) for index in range(3)]
    with tempfile.TemporaryDirectory() as directory:
        dry_root = Path(directory) / "cycle-1"
        dry_root.mkdir()
        dry_selection = prior.bind_selection(p82, dry_root, parent, corrected, precorrection, 0)
        dry_world = prior.open_world(p82, dry_root, dry_selection, 0)
        dry_seed = scheduler.compressed_seed(prior89, dry_root, parent, corrected, dry_selection, dry_world, 0)
        dry_files = {path.name for path in dry_seed.iterdir() if path.is_file()}
    required_files = {"README.md", "bound-selected-contact.json", "complete-transition-contract.json", "continuation-action.json", "mutation-envelope.json", "route-assimilation.json", "selected-world-consequence.json", "selector.py", "subject-position.json", "successor-opening-contract.json", "successor-opening.json"}
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "parent_sounding": runtime.identity_conforms(parent),
        "parent_open": parent["continuation"]["status"] == "open",
        "parent_matches_first_node": prior.has_concepts(parent["continuation"]["next_opening"], prior.STAGES[0]["current_concepts"]),
        "all_stage_fixtures_pass": all(item["passed"] for item in stage_checks),
        "fresh_actor_seed_conforms": dry_files == required_files,
        "router_schema_present": prior22.ROUTER_SCHEMA.is_file(),
        "contextual_equivalence_frozen": previous.contextual_transfer_grounded("in materially different contexts") and not previous.contextual_transfer_grounded("a generic transfer boundary"),
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "stage_checks": stage_checks, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0128 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "stage_checks": stage_checks}, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    current = parent
    cycles = []
    for stage_index in range(3):
        cycle_root = run / f"cycle-{stage_index + 1}"
        cycle_root.mkdir()
        incoming_match = prior.has_concepts(current["continuation"]["next_opening"], prior.STAGES[stage_index]["current_concepts"])
        if not incoming_match:
            cycles.append({"cycle": stage_index + 1, "incoming_scheduler_match": False})
            break
        current_source = current["allocation_machinery"][-1]["source"]
        selection = prior.bind_selection(p82, cycle_root, current, current_source, precorrection, stage_index)
        world = prior.open_world(p82, cycle_root, selection, stage_index)
        routed = run_router(prior89, p82, context, cycle_root, current, current_source, selection, world, stage_index)
        prior_subject = current
        promotion = None
        if routed["binding"]:
            current, promotion = prior22.promote(p82, prior_subject, selection, world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and stage_grounded(stage_index, current["continuation"]["next_opening"]))
        cycles.append({"cycle": stage_index + 1, "incoming_scheduler_match": incoming_match, "selection_binding": selection, "world": world, "route": p82.compact(routed), "promotion": promotion, "operational_transition_passed": operational, "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"]})
        if not operational:
            break
    recurrent = bool(len(cycles) == 3 and all(item.get("operational_transition_passed") for item in cycles) and all(item["selection_binding"]["active_selection"]["selected_id"] == item["world"]["oracle_contact_id"] for item in cycles) and all(item["selection_binding"]["precorrection_control_selection"]["selected_id"] != item["selection_binding"]["active_selection"]["selected_id"] for item in cycles) and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and previous.contextual_transfer_grounded(current["continuation"]["next_opening"]))
    result = {
        "authority": "ot-0128-clean-three-cycle-reproduction-driver",
        "source_subject_digest": parent["artifact_digest"],
        "scheduler_semantic_authority": "continuation.next_opening",
        "registry_identity_authority": "continuation_action.action_target",
        "cycles": cycles,
        "fresh_actor_count": len(cycles),
        "completed_cycle_count": sum(bool(item.get("operational_transition_passed")) for item in cycles),
        "clean_three_cycle_reproduction_passed": recurrent,
        "observer_disposition": "promoted" if recurrent else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if recurrent else 2


if __name__ == "__main__":
    raise SystemExit(main())
