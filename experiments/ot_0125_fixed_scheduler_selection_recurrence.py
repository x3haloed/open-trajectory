from __future__ import annotations

import argparse, copy, hashlib, importlib.util, itertools, json, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0124_published_action_target_abi.py"
BASE_SHA256 = "38f149a5ed8bfeca37029b210718b5f3a3b54e8267a709e5982158b5cfbb6a16"
PARENT_OBJECT_SHA256 = "3b23424da18906eb4e869525e6c53badfc3ef0b5f5e4fc16aa2dc66f06277dad"
PARENT_DIGEST = "2ce904e9cbdb853e9e0086d050397991fad7fa8cc5bb416d480db3f1ede30aa4"
CORRECTED_SOURCE_SHA256 = "1699abded9259e8ce07cb73beb41a87f637844ca3d40554b0f655ecf5c393e5e"
PRECORRECTION_SOURCE_SHA256 = "e326934759bfa1ba9122c095e1b3e3f76485e889f850f92bef8ce901c703312d"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0124 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0125_frozen_ot0124", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior22 = previous.prior22
base = previous.base
prior17 = previous.prior17
prior18 = previous.prior18
kernel = prior22.kernel


STAGES = [
    {
        "node_id": "resource-scarcity",
        "current_concepts": ["resource", "scarcity"],
        "next_concepts": ["recovery", "latency"],
        "remaining_uncertainty": "Whether the resource-scarcity boundary transfers when recovery latency becomes an independent pressure remains unresolved.",
    },
    {
        "node_id": "recovery-latency",
        "current_concepts": ["recovery", "latency"],
        "next_concepts": ["demand", "volatility"],
        "remaining_uncertainty": "Whether the recovery-latency boundary transfers when demand volatility becomes an independent pressure remains unresolved.",
    },
    {
        "node_id": "demand-volatility",
        "current_concepts": ["demand", "volatility"],
        "next_concepts": ["cross", "context"],
        "remaining_uncertainty": "Whether the demand-volatility boundary transfers across materially different contexts remains unresolved.",
    },
]


def load_parent(p82, repo, store):
    manifest, path = p82.materialize(repo, store, "OT-0124", "open-subject-after-subject-selected-contact.json")
    parent = json.loads(path.read_text())
    if manifest["sha256"] != PARENT_OBJECT_SHA256 or parent["artifact_digest"] != PARENT_DIGEST:
        raise RuntimeError("wrong OT-0124 parent")
    corrected = parent["allocation_machinery"][-1]["source"]
    precorrection = parent["allocation_machinery"][-2]["source"]
    if hashlib.sha256(corrected.encode()).hexdigest() != CORRECTED_SOURCE_SHA256 or hashlib.sha256(precorrection.encode()).hexdigest() != PRECORRECTION_SOURCE_SHA256:
        raise RuntimeError("wrong selector lineage")
    return parent, corrected, precorrection


def has_concepts(value, concepts):
    text = value.lower().replace("-", " ") if isinstance(value, str) else ""
    return all(concept in text for concept in concepts)


def contact(identifier, surface, expansion, regret, coordination, recovery, resilience, carry):
    return {
        "id": identifier,
        "surface": surface,
        "world_valid": True,
        "world_contact": True,
        "held_repeat": False,
        "reversible": True,
        "completed_floors": ["recovery-safety", "resource-schedule"],
        "predicted_expansion": float(expansion),
        "public_regret": float(regret),
        "coordination_load": float(coordination),
        "recovery_volatility": float(recovery),
        "resilience_margin": float(resilience),
        "resilience_carry_cost": float(carry),
    }


def envelope(stage_index):
    stem = STAGES[stage_index]["node_id"]
    offset = stage_index * 2
    return [
        contact(f"{stem}-overbuilt", "overbuilt-high-resilience", 110 + offset, 44, 2, 2, 30, 3),
        contact(f"{stem}-coordination", "isolated-coordination", 94 + offset, 32, 7, 2, 10, 1),
        contact(f"{stem}-recovery", "isolated-recovery", 92 + offset, 30, 2, 7, 9, 1),
        contact(f"{stem}-joint", "joint-boundary", 100 + offset, 36, 5, 4, 12, 1),
    ]


def branches(stage_index):
    stage = STAGES[stage_index]
    stem = stage["node_id"]
    return {
        f"{stem}-overbuilt": {"realized_information": 18.0, "settles_current_pursuit": False, "remaining_uncertainty": stage["remaining_uncertainty"], "cases": [{"case_id": f"{stem}-overbuilt-01", "winner": "reserve"}]},
        f"{stem}-coordination": {"realized_information": 55.0, "settles_current_pursuit": False, "remaining_uncertainty": stage["remaining_uncertainty"], "cases": [{"case_id": f"{stem}-coordination-01", "winner": "calibrated"}, {"case_id": f"{stem}-coordination-02", "winner": "calibrated"}]},
        f"{stem}-recovery": {"realized_information": 53.0, "settles_current_pursuit": False, "remaining_uncertainty": stage["remaining_uncertainty"], "cases": [{"case_id": f"{stem}-recovery-01", "winner": "calibrated"}, {"case_id": f"{stem}-recovery-02", "winner": "reserve"}]},
        f"{stem}-joint": {"realized_information": 92.0, "settles_current_pursuit": True, "remaining_uncertainty": stage["remaining_uncertainty"], "cases": [
            {"case_id": f"{stem}-zero-01", "pressure": 0, "coordination": 2, "recovery": 2, "winner": "resilient"},
            {"case_id": f"{stem}-coordination-02", "pressure": 2, "coordination": 7, "recovery": 2, "winner": "calibrated"},
            {"case_id": f"{stem}-recovery-03", "pressure": 2, "coordination": 2, "recovery": 7, "winner": "calibrated"},
            {"case_id": f"{stem}-composed-04", "pressure": 2, "coordination": 7, "recovery": 7, "winner": "reserve"},
        ]},
    }


def choose(source, rows):
    selector = prior17.load_selector(source)
    original = copy.deepcopy(rows)
    try:
        selected = selector(copy.deepcopy(rows)) if selector else None
    except Exception:
        selected = None
    return {"selected_id": selected, "input_unchanged": rows == original, "valid": selected in {row["id"] for row in rows}}


def stage_conformance(stage_index, corrected, precorrection):
    rows = envelope(stage_index)
    expected_active = f"{STAGES[stage_index]['node_id']}-joint"
    expected_control = f"{STAGES[stage_index]['node_id']}-overbuilt"
    active_choices = {choose(corrected, list(order))["selected_id"] for order in itertools.permutations(rows)}
    control_choices = {choose(precorrection, list(order))["selected_id"] for order in itertools.permutations(rows)}
    renamed = [{**row, "id": f"renamed-{index}"} for index, row in enumerate(reversed(rows), 1)]
    active_renamed = choose(corrected, renamed)["selected_id"]
    control_renamed = choose(precorrection, renamed)["selected_id"]
    active_surface = next((row["surface"] for row in renamed if row["id"] == active_renamed), None)
    control_surface = next((row["surface"] for row in renamed if row["id"] == control_renamed), None)
    oracle = max(branches(stage_index), key=lambda item: (branches(stage_index)[item]["realized_information"], item))
    checks = {
        "active_permutation_invariant": active_choices == {expected_active},
        "control_permutation_invariant": control_choices == {expected_control},
        "active_renaming_invariant": active_surface == "joint-boundary",
        "control_renaming_invariant": control_surface == "overbuilt-high-resilience",
        "oracle_is_active": oracle == expected_active,
    }
    checks["passed"] = all(checks.values())
    return checks


def bind_selection(p82, cycle_root, parent, corrected, precorrection, stage_index):
    rows = envelope(stage_index)
    body = {
        "authority": "ot-0125-recurrent-subject-selector-binding",
        "cycle": stage_index + 1,
        "scheduler_node": STAGES[stage_index]["node_id"],
        "source_subject_digest": parent["artifact_digest"],
        "envelope_digest": p82.digest(rows),
        "corrected_selector_digest": hashlib.sha256(corrected.encode()).hexdigest(),
        "precorrection_selector_digest": hashlib.sha256(precorrection.encode()).hexdigest(),
        "active_selection": choose(corrected, rows),
        "precorrection_control_selection": choose(precorrection, rows),
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    (cycle_root / "bound-contact-selection.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return binding


def open_world(p82, cycle_root, binding, stage_index):
    all_branches = branches(stage_index)
    selected = binding["active_selection"]["selected_id"]
    oracle = max(all_branches, key=lambda item: (all_branches[item]["realized_information"], item))
    body = {
        "authority": "ot-0125-fixed-scheduler-world",
        "cycle": stage_index + 1,
        "scheduler_node": STAGES[stage_index]["node_id"],
        "selection_binding_digest": binding["binding_digest"],
        "all_branch_digest": p82.digest(all_branches),
        "selected_contact_id": selected,
        "selected_branch": all_branches[selected],
        "oracle_contact_id": oracle,
        "expected_route": "extend" if selected == oracle and all_branches[selected]["settles_current_pursuit"] else "correct",
        "next_concepts": STAGES[stage_index]["next_concepts"],
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (cycle_root / "hidden-world-envelope.json").write_text(json.dumps(all_branches, indent=2, sort_keys=True) + "\n")
    (cycle_root / "selected-world-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def router_seed(prior89, cycle_root, parent, corrected, binding, world, stage_index):
    seed = cycle_root / "router-seed"
    seed.mkdir()
    actor_world = {key: value for key, value in world.items() if key not in {"expected_route", "next_concepts"}}
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-selected-contact.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps(actor_world, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(corrected)
    (seed / "route-assimilation.json").write_text(json.dumps(prior22.route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action.json").write_text(json.dumps(kernel.foundation.prior.prior.action_template(), indent=2, sort_keys=True) + "\n")
    (seed / "complete-transition-contract.json").write_text(json.dumps({
        "route_semantics": {"extend": "selected consequence settles the current pursuit and leaves grounded uncertainty"},
        "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]),
        "authoritative_opening_must_change": True,
        "next_opening_and_target_must_ground": world["selected_branch"]["remaining_uncertainty"],
        "action_kind_exact": "registry-extension",
        "action_target_fullmatch_regex": "[a-z][a-z0-9-]{2,127}",
        "action_target_must_be_new": True,
        "selector_is_immutable": True,
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["route-assimilation.json", "successor-opening.json", "continuation-action.json"], "immutable": ["selector.py", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "complete-transition-contract.json"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the selected consequence under the complete transition contract. Let the consequence determine the route, cite every exact case, retain selector.py, and ground remaining uncertainty in a changed authoritative opening and new valid registry target. Edit exactly the three permitted JSON files, inspect the diff, and report truthfully.\n")
    return seed


def run_router(prior89, p82, context, cycle_root, parent, corrected, binding, world, stage_index):
    label = f"cycle-{stage_index + 1}-router"
    seed = router_seed(prior89, cycle_root, parent, corrected, binding, world, stage_index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior22.ROUTER_SCHEMA, "Continue the exact subject from this selected consequence under the complete transition contract. Ground the remaining uncertainty in the authoritative opening and a new valid action target, inspect the exact diff, and report truthfully.")
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
    next_concepts = STAGES[stage_index]["next_concepts"]
    old_target = parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"]
    coherence = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "case_ids_exact": cited == expected_ids,
        "selector_retained": retained,
        "opening_changed": bool(opening and opening.get("next_opening") != parent["continuation"]["next_opening"]),
        "opening_grounded": bool(opening and has_concepts(opening.get("next_opening"), next_concepts)),
        "continuation_grounded": bool(opening and has_concepts(opening.get("continuation_after_contact"), next_concepts)),
        "remaining_uncertainty_grounded": bool(route and has_concepts(route.get("remaining_uncertainty"), next_concepts)),
        "action_valid": bool(action and prior18.previous.previous.repaired_action_valid(action, parent)),
        "action_target_changed": bool(action and action.get("action_target") != old_target),
        "action_target_grounded": bool(action and has_concepts(action.get("action_target"), next_concepts)),
        "expected_information_grounded": bool(action and has_concepts(action.get("expected_information"), next_concepts)),
    }
    coherence["passed"] = all(coherence.values())
    valid = bool(prior22.valid_route(route) and prior89.valid_successor(opening) and coherence["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json", "successor-opening.json", "continuation-action.json"])
    accepted_trace = bool(audit["conformant"] and audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"] and not audit["denial_classification_v2"]["protected_path_named"] and not audit["denial_classification_v2"]["outside_file_changes"])
    binding_out = None
    if accepted_trace:
        body = {
            "authority": "ot-0125-recurrent-grounded-route",
            "cycle": stage_index + 1,
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": binding["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "coherence": coherence,
            "selector_retention_derived": retained,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        binding_out = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(binding_out, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "coherence": coherence, "binding": binding_out}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0125").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent, corrected, precorrection = load_parent(p82, repo, store)
    stage_checks = [stage_conformance(index, corrected, precorrection) for index in range(len(STAGES))]
    with tempfile.TemporaryDirectory() as directory:
        dry_root = Path(directory) / "cycle-1"
        dry_root.mkdir()
        dry_selection = bind_selection(p82, dry_root, parent, corrected, precorrection, 0)
        dry_world = open_world(p82, dry_root, dry_selection, 0)
        dry_seed = router_seed(prior89, dry_root, parent, corrected, dry_selection, dry_world, 0)
        dry_seed_files = {path.name for path in dry_seed.iterdir() if path.is_file()}
    required_seed_files = {
        "README.md", "bound-selected-contact.json", "complete-transition-contract.json",
        "continuation-action.json", "mutation-envelope.json", "route-assimilation.json",
        "selected-world-consequence.json", "selector.py", "subject-position.json",
        "successor-opening-contract.json", "successor-opening.json",
    }
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "parent_sounding": runtime.identity_conforms(parent),
        "parent_open": parent["continuation"]["status"] == "open",
        "parent_matches_first_node": has_concepts(parent["active_pursuit"]["selected_area"], STAGES[0]["current_concepts"]),
        "three_frozen_nodes": len(STAGES) == 3,
        "stage_conformance": stage_checks,
        "all_stage_fixtures_pass": all(item["passed"] for item in stage_checks),
        "router_schema_present": prior22.ROUTER_SCHEMA.is_file(),
        "route_validator_available": callable(prior22.valid_route),
        "actor_seed_conforms": dry_seed_files == required_seed_files,
    }
    checks["passed"] = all(value for key, value in checks.items() if key not in {"passed", "stage_conformance"}) and checks["all_stage_fixtures_pass"]
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0125 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    current = parent
    cycles = []
    for stage_index, stage in enumerate(STAGES):
        cycle_root = run / f"cycle-{stage_index + 1}"
        cycle_root.mkdir()
        incoming_matches = has_concepts(current["active_pursuit"]["selected_area"], stage["current_concepts"])
        if not incoming_matches:
            cycles.append({"cycle": stage_index + 1, "incoming_scheduler_match": False})
            break
        current_source = current["allocation_machinery"][-1]["source"]
        selection = bind_selection(p82, cycle_root, current, current_source, precorrection, stage_index)
        world = open_world(p82, cycle_root, selection, stage_index)
        routed = run_router(prior89, p82, context, cycle_root, current, current_source, selection, world, stage_index)
        prior_subject = current
        promotion = None
        if routed["binding"]:
            current, promotion = prior22.promote(p82, prior_subject, selection, world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and has_concepts(current["active_pursuit"]["selected_area"], stage["next_concepts"]))
        cycles.append({
            "cycle": stage_index + 1,
            "incoming_scheduler_match": incoming_matches,
            "selection_binding": selection,
            "world": world,
            "route": p82.compact(routed),
            "promotion": promotion,
            "operational_transition_passed": operational,
            "final_subject_digest": current["artifact_digest"],
            "next_target": current["active_pursuit"]["selected_area"],
        })
        if not operational:
            break
    recurrent = bool(
        len(cycles) == 3
        and all(item.get("operational_transition_passed") for item in cycles)
        and all(item["selection_binding"]["active_selection"]["selected_id"] == item["world"]["oracle_contact_id"] for item in cycles)
        and all(item["selection_binding"]["precorrection_control_selection"]["selected_id"] != item["selection_binding"]["active_selection"]["selected_id"] for item in cycles)
        and runtime.identity_conforms(current)
        and current["continuation"]["status"] == "open"
        and has_concepts(current["active_pursuit"]["selected_area"], STAGES[-1]["next_concepts"])
    )
    result = {
        "authority": "ot-0125-fixed-scheduler-selection-recurrence-driver",
        "source_subject_digest": parent["artifact_digest"],
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
