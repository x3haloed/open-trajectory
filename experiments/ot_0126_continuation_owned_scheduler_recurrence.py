from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0125_fixed_scheduler_selection_recurrence.py"
BASE_SHA256 = "8e8d76845e4442d29d652f6bea2dc7c57a9b479e6d6e1e5dfa657633dd0c416c"
RUN_SHA256 = "a96880f0ccfc29208a13cbc98df36138b9c7359e6641559ad7546db1112c63a7"
AGGREGATE_SHA256 = "a52ddb0962b8df7cfe04bebc22dabc334b8f6f3964a6a3a6ba8fa25d950e0287"
PARENT_DIGEST = "2ce904e9cbdb853e9e0086d050397991fad7fa8cc5bb416d480db3f1ede30aa4"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0125 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0126_frozen_ot0125", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
prior22 = prior.prior22
base = prior.base
prior17 = prior.prior17
prior18 = prior.prior18


def extract(path, destination):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0125" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk():
                raise RuntimeError("unsafe OT-0125 archive")
        archive.extractall(destination, members=members)
    return destination / "OT-0125"


def load_inputs(p82, repo, store, destination):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0125", "fixed-scheduler-selection-recurrence-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0125", "fixed-scheduler-selection-recurrence-aggregate.json")
    if run_manifest["sha256"] != RUN_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0125 evidence")
    raw = extract(run_path, destination)
    aggregate = json.loads(aggregate_path.read_text())
    parent, corrected, precorrection = prior.load_parent(p82, repo, store)
    selection = json.loads((raw / "cycle-1/bound-contact-selection.json").read_text())
    world = json.loads((raw / "cycle-1/selected-world-receipt.json").read_text())
    workspace = raw / "cycle-1-router/actor-workspace"
    route = json.loads((workspace / "route-assimilation.json").read_text())
    opening = json.loads((workspace / "successor-opening.json").read_text())
    action = json.loads((workspace / "continuation-action.json").read_text())
    audit = json.loads((raw / "cycle-1-router/actor-audit.json").read_text())
    return raw, aggregate, parent, corrected, precorrection, selection, world, route, opening, action, audit


def retained_reaudit(p82, parent, corrected, selection, world, route, opening, action, audit, aggregate, raw):
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    next_concepts = prior.STAGES[0]["next_concepts"]
    old_target = parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"]
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "ot0125_rejected_at_cycle_one": not aggregate["recurrent_operational_transition_passed"] and aggregate["completed_cycle_count"] == 0 and len(aggregate["cycles"]) == 1,
        "no_cycle_two_authorized": not (raw / "cycle-2-router").exists() and not (raw / "cycle-2").exists(),
        "active_choice_oracle": selection["active_selection"]["selected_id"] == world["oracle_contact_id"],
        "control_choice_differs": selection["precorrection_control_selection"]["selected_id"] != selection["active_selection"]["selected_id"],
        "route_exact": route["route"] == world["expected_route"] == "extend",
        "case_ids_exact": set(route["settled_case_ids"]) == expected_ids,
        "selector_retained": hashlib.sha256(corrected.encode()).hexdigest() == prior.CORRECTED_SOURCE_SHA256,
        "opening_changed": opening["next_opening"] != parent["continuation"]["next_opening"],
        "opening_is_scheduler_complete": prior.has_concepts(opening["next_opening"], next_concepts),
        "continuation_grounded": prior.has_concepts(opening["continuation_after_contact"], next_concepts),
        "route_uncertainty_grounded": prior.has_concepts(route["remaining_uncertainty"], next_concepts),
        "expected_information_grounded": prior.has_concepts(action["expected_information"], next_concepts),
        "action_structurally_valid": prior18.previous.previous.repaired_action_valid(action, parent),
        "action_target_new": action["action_target"] != old_target,
        "frozen_dual_authority_symptom": not prior.has_concepts(action["action_target"], next_concepts),
        "trace_accepted": bool(audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"] and audit["exact_changes"] and audit["truthful"] and not audit["denial_classification_v2"]["protected_path_named"] and not audit["denial_classification_v2"]["outside_file_changes"]),
        "route_structurally_valid": prior22.valid_route(route),
    }
    checks["passed"] = all(checks.values())
    binding = None
    if checks["passed"]:
        body = {
            "authority": "ot-0126-continuation-owned-retained-route",
            "cycle": 1,
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": selection["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "scheduler_authority": "successor_opening.next_opening",
            "registry_identity_authority": "continuation_action.action_target",
            "reaudit_checks": checks,
            "selector_retention_derived": True,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    return checks, binding


def compressed_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index):
    seed = prior.router_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index)
    (seed / "complete-transition-contract.json").write_text(json.dumps({
        "scheduler_semantic_authority": "successor-opening.next_opening",
        "registry_identity_authority": "continuation-action.action_target",
        "route_semantics": {"extend": "selected consequence settles the current pursuit and leaves grounded uncertainty"},
        "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]),
        "authoritative_opening_must_change": True,
        "authoritative_opening_must_ground": world["selected_branch"]["remaining_uncertainty"],
        "action_kind_exact": "registry-extension",
        "action_target_fullmatch_regex": "[a-z][a-z0-9-]{2,127}",
        "action_target_must_be_new": True,
        "action_target_is_not_a_semantic_scheduler_key": True,
        "selector_is_immutable": True,
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the selected consequence under the separated-authority contract. Cite every case, retain selector.py, ground remaining uncertainty completely in the changed authoritative next opening, and author a new structurally valid registry id. The registry id need not duplicate the full opening. Edit exactly the three permitted JSON files, inspect the diff, and report truthfully.\n")
    return seed


def run_router(prior89, p82, context, cycle_root, parent, corrected, selection, world, stage_index):
    label = f"cycle-{stage_index + 1}-router"
    seed = compressed_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior22.ROUTER_SCHEMA, "Continue the exact subject under the separated-authority transition contract. Let the authoritative next opening carry the complete remaining stake; keep the registry id new and structurally valid; inspect the exact diff; and report truthfully.")
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        action = json.loads((workspace / "continuation-action.json").read_text())
        retained = (workspace / "selector.py").read_text() == corrected
    except (OSError, json.JSONDecodeError):
        route = opening = action = None
        retained = False
    next_concepts = prior.STAGES[stage_index]["next_concepts"]
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    cited = set(route.get("settled_case_ids", [])) if isinstance(route, dict) else set()
    old_target = parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"]
    coherence = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "case_ids_exact": cited == expected_ids,
        "selector_retained": retained,
        "opening_changed": bool(opening and opening.get("next_opening") != parent["continuation"]["next_opening"]),
        "opening_grounded": bool(opening and prior.has_concepts(opening.get("next_opening"), next_concepts)),
        "continuation_grounded": bool(opening and prior.has_concepts(opening.get("continuation_after_contact"), next_concepts)),
        "remaining_uncertainty_grounded": bool(route and prior.has_concepts(route.get("remaining_uncertainty"), next_concepts)),
        "expected_information_grounded": bool(action and prior.has_concepts(action.get("expected_information"), next_concepts)),
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
            "authority": "ot-0126-continuation-owned-live-route",
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
    run = (args.evidence_root or store / "runs/OT-0126").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    with tempfile.TemporaryDirectory() as directory:
        inputs = load_inputs(p82, repo, store, Path(directory) / "source")
        raw, aggregate, parent, corrected, precorrection, selection, world, route, opening, action, audit = inputs
        retained_checks, retained_binding = retained_reaudit(p82, parent, corrected, selection, world, route, opening, action, audit, aggregate, raw)
        retained_subject, retained_promotion = prior22.promote(p82, parent, selection, world, retained_binding) if retained_binding else (parent, None)
        dry_root = Path(directory) / "dry-cycle-2"
        dry_root.mkdir()
        dry_selection = prior.bind_selection(p82, dry_root, retained_subject, corrected, precorrection, 1)
        dry_world = prior.open_world(p82, dry_root, dry_selection, 1)
        dry_seed = compressed_seed(prior89, dry_root, retained_subject, corrected, dry_selection, dry_world, 1)
        dry_files = {path.name for path in dry_seed.iterdir() if path.is_file()}
    required_files = {"README.md", "bound-selected-contact.json", "complete-transition-contract.json", "continuation-action.json", "mutation-envelope.json", "route-assimilation.json", "selected-world-consequence.json", "selector.py", "subject-position.json", "successor-opening-contract.json", "successor-opening.json"}
    stage_checks = [prior.stage_conformance(index, corrected, precorrection) for index in (1, 2)]
    checks = {
        "retained_cycle_one_passes_separated_authority": retained_checks["passed"],
        "retained_subject_sounding": bool(retained_promotion and runtime.identity_conforms(retained_subject)),
        "retained_scheduler_matches_cycle_two": prior.has_concepts(retained_subject["continuation"]["next_opening"], prior.STAGES[1]["current_concepts"]),
        "remaining_stage_fixtures_pass": all(item["passed"] for item in stage_checks),
        "compressed_actor_seed_conforms": dry_files == required_files,
        "router_schema_present": prior22.ROUTER_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "run_sha256": RUN_SHA256, "aggregate_sha256": AGGREGATE_SHA256, "retained_checks": retained_checks, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0126 evidence")
    run.mkdir(parents=True)
    (run / "retained-cycle-1-checks.json").write_text(json.dumps(retained_checks, indent=2, sort_keys=True) + "\n")
    (run / "bound-retained-cycle-1-route.json").write_text(json.dumps(retained_binding, indent=2, sort_keys=True) + "\n")
    (run / "fixture-conformance.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    current = retained_subject
    cycles = [{"cycle": 1, "retained_exact": True, "selection_binding": selection, "world": world, "route_binding": retained_binding, "promotion": retained_promotion, "operational_transition_passed": True, "final_subject_digest": current["artifact_digest"]}]
    for stage_index in (1, 2):
        cycle_root = run / f"cycle-{stage_index + 1}"
        cycle_root.mkdir()
        incoming_match = prior.has_concepts(current["continuation"]["next_opening"], prior.STAGES[stage_index]["current_concepts"])
        if not incoming_match:
            cycles.append({"cycle": stage_index + 1, "incoming_scheduler_match": False})
            break
        current_source = current["allocation_machinery"][-1]["source"]
        selected = prior.bind_selection(p82, cycle_root, current, current_source, precorrection, stage_index)
        selected_world = prior.open_world(p82, cycle_root, selected, stage_index)
        routed = run_router(prior89, p82, context, cycle_root, current, current_source, selected, selected_world, stage_index)
        prior_subject = current
        promotion = None
        if routed["binding"]:
            current, promotion = prior22.promote(p82, prior_subject, selected, selected_world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and prior.has_concepts(current["continuation"]["next_opening"], prior.STAGES[stage_index]["next_concepts"]))
        cycles.append({"cycle": stage_index + 1, "incoming_scheduler_match": incoming_match, "selection_binding": selected, "world": selected_world, "route": p82.compact(routed), "promotion": promotion, "operational_transition_passed": operational, "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"]})
        if not operational:
            break
    recurrent = bool(len(cycles) == 3 and all(item.get("operational_transition_passed") for item in cycles) and all(item["selection_binding"]["active_selection"]["selected_id"] == item["world"]["oracle_contact_id"] for item in cycles) and all(item["selection_binding"]["precorrection_control_selection"]["selected_id"] != item["selection_binding"]["active_selection"]["selected_id"] for item in cycles) and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and prior.has_concepts(current["continuation"]["next_opening"], prior.STAGES[-1]["next_concepts"]))
    result = {
        "authority": "ot-0126-continuation-owned-scheduler-recurrence-driver",
        "source_subject_digest": parent["artifact_digest"],
        "scheduler_semantic_authority": "continuation.next_opening",
        "registry_identity_authority": "continuation_action.action_target",
        "cycles": cycles,
        "completed_cycle_count": sum(bool(item.get("operational_transition_passed")) for item in cycles),
        "recurrent_operational_transition_passed": recurrent,
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
