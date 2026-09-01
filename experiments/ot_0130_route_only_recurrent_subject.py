from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0129_compiled_continuation_recurrence.py"
BASE_SHA256 = "2c0fa88180209949ec3f7148ae28ac3dfb60a98bc155af06bc99f27e2ad34848"
PARENT_DIGEST = "2ce904e9cbdb853e9e0086d050397991fad7fa8cc5bb416d480db3f1ede30aa4"
ACTOR_SCHEMA = REPO / "spec/ot-0130-route-only.schema.json"
COMPILER_VERSION = "ot-0130-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0129 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0130_frozen_ot0129", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior = previous.prior
prior22 = previous.prior22
base = previous.base
prior17 = previous.prior17
prior18 = previous.prior18


def compile_action(route, cycle):
    uncertainty = route["remaining_uncertainty"]
    suffix = hashlib.sha256(uncertainty.encode()).hexdigest()[:12]
    return {
        "action_kind": "registry-extension",
        "action_target": f"continuation-{cycle}-{suffix}",
        "expected_information": uncertainty,
        "rationale": f"{route['route']} after {route['selected_contact_id']}: {route['consequence_summary']}",
        "surrender_condition": route["surrender_condition"],
    }


def stage_grounded(stage_index, value):
    return previous.stage_grounded(stage_index, value)


def actor_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index):
    seed = previous.actor_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index)
    (seed / "continuation-action.json").unlink()
    (seed / "compiled-continuation-contract.json").unlink()
    (seed / "route-only-compiler-contract.json").write_text(json.dumps({
        "compiler_version": COMPILER_VERSION,
        "actor_authored_file": "route-assimilation.json",
        "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]),
        "route_exact": "extend",
        "compiled_action_target": "continuation-<cycle>-<sha256(remaining_uncertainty)[0:12]>",
        "compiled_action_expected_information": "exact remaining_uncertainty",
        "compiled_opening": "ot-0129-v1 projection of route and compiled action",
        "selector_is_immutable": True,
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["route-assimilation.json"],
        "immutable": ["selector.py", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "route-only-compiler-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the selected consequence exactly once in route-assimilation.json. Cite every exact case and ground the remaining uncertainty; the substrate compiles action and canonical opening. Retain selector.py, edit only the route file, inspect the diff, and report truthfully.\n")
    return seed


def run_actor(prior89, p82, context, cycle_root, parent, corrected, selection, world, stage_index):
    label = f"cycle-{stage_index + 1}-route"
    seed = actor_seed(prior89, cycle_root, parent, corrected, selection, world, stage_index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ACTOR_SCHEMA, "Assimilate the exact selected consequence once under the route-only compiler contract. Author the grounded route, cite every exact case, inspect the one-file diff, and report truthfully.")
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        retained = (workspace / "selector.py").read_text() == corrected
    except (OSError, json.JSONDecodeError):
        route = None
        retained = False
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    cited = set(route.get("settled_case_ids", [])) if isinstance(route, dict) else set()
    actor_checks = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "case_ids_exact": cited == expected_ids,
        "selector_retained": retained,
        "remaining_uncertainty_grounded": bool(route and stage_grounded(stage_index, route.get("remaining_uncertainty"))),
    }
    actor_checks["passed"] = all(actor_checks.values())
    valid = bool(prior22.valid_route(route) and actor_checks["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json"])
    accepted = bool(audit["conformant"] and audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"] and not audit["denial_classification_v2"]["protected_path_named"] and not audit["denial_classification_v2"]["outside_file_changes"])
    route_binding = None
    action = None
    opening = None
    compiler_checks = {"passed": False}
    if accepted:
        route_body = {
            "authority": "ot-0130-grounded-route",
            "cycle": stage_index + 1,
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": selection["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "actor_checks": actor_checks,
            "selector_retention_derived": retained,
            "route_assimilation": route,
        }
        actor_binding = {**route_body, "binding_digest": p82.digest(route_body)}
        action = compile_action(route, stage_index + 1)
        opening = previous.compile_opening(route, action)
        compiler_checks = {
            "action_valid": prior18.previous.previous.repaired_action_valid(action, parent),
            "target_new": action["action_target"] not in prior22.kernel.registered(parent),
            "expected_information_exact": action["expected_information"] == route["remaining_uncertainty"],
            "opening_structurally_valid": prior89.valid_successor(opening),
            "uncertainty_retained_exactly": opening["unresolved"] == route["remaining_uncertainty"] and route["remaining_uncertainty"] in opening["next_opening"] and route["remaining_uncertainty"] in opening["continuation_after_contact"],
            "opening_grounded": stage_grounded(stage_index, opening["next_opening"]),
            "compiler_deterministic": action == compile_action(route, stage_index + 1) and opening == previous.compile_opening(route, action),
        }
        compiler_checks["passed"] = all(compiler_checks.values())
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(actor_binding, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "compiled-continuation-action.json").write_text(json.dumps(action, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "compiled-successor-opening.json").write_text(json.dumps(opening, indent=2, sort_keys=True) + "\n")
        if compiler_checks["passed"]:
            body = {
                "authority": "ot-0130-route-only-compiled-continuation",
                "cycle": stage_index + 1,
                "source_subject_digest": parent["artifact_digest"],
                "selection_binding_digest": selection["binding_digest"],
                "world_receipt_digest": world["receipt_digest"],
                "actor_binding_digest": actor_binding["binding_digest"],
                "compiler_version": COMPILER_VERSION,
                "compiler_checks": compiler_checks,
                "selector_retention_derived": retained,
                "route_assimilation": route,
                "successor_opening": opening,
                "continuation_action": action,
            }
            route_binding = {**body, "binding_digest": p82.digest(body)}
            (context.evidence(label) / "bound-compiled-route.json").write_text(json.dumps(route_binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "actor_checks": actor_checks, "compiler_checks": compiler_checks, "compiled_action": action, "compiled_opening": opening, "binding": route_binding}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0130").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent, corrected, precorrection = prior.load_parent(p82, repo, store)
    stage_checks = [prior.stage_conformance(index, corrected, precorrection) for index in range(3)]
    sample_route = {"route": "extend", "selected_contact_id": "sample", "consequence_summary": "settled", "settled_case_ids": ["case"], "remaining_uncertainty": "Whether recovery latency transfers remains unresolved.", "selection_rule_disposition": "extend", "surrender_condition": "Surrender if absent."}
    sample_action = compile_action(sample_route, 1)
    sample_opening = previous.compile_opening(sample_route, sample_action)
    with tempfile.TemporaryDirectory() as directory:
        dry_root = Path(directory) / "cycle-1"
        dry_root.mkdir()
        dry_selection = prior.bind_selection(p82, dry_root, parent, corrected, precorrection, 0)
        dry_world = prior.open_world(p82, dry_root, dry_selection, 0)
        dry_seed = actor_seed(prior89, dry_root, parent, corrected, dry_selection, dry_world, 0)
        dry_files = {path.name for path in dry_seed.iterdir() if path.is_file()}
    required_files = {"README.md", "bound-selected-contact.json", "mutation-envelope.json", "route-assimilation.json", "route-only-compiler-contract.json", "selected-world-consequence.json", "selector.py", "subject-position.json"}
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "all_stage_fixtures_pass": all(item["passed"] for item in stage_checks),
        "one_file_seed_conforms": dry_files == required_files,
        "actor_schema_present": ACTOR_SCHEMA.is_file(),
        "compiled_target_deterministic": sample_action == compile_action(sample_route, 1) and sample_action["action_target"].startswith("continuation-1-"),
        "compiled_action_grounded": sample_action["expected_information"] == sample_route["remaining_uncertainty"],
        "compiled_action_structurally_valid": prior18.previous.previous.repaired_action_valid(sample_action, parent),
        "compiled_opening_grounded": sample_route["remaining_uncertainty"] in sample_opening["next_opening"],
        "contextual_rule_frozen": previous.previous.previous.contextual_transfer_grounded("in materially different contexts") and not previous.previous.previous.contextual_transfer_grounded("generic boundary"),
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "compiler_version": COMPILER_VERSION, "stage_checks": stage_checks, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0130 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "stage_checks": stage_checks, "sample_action": sample_action, "sample_opening": sample_opening}, indent=2, sort_keys=True) + "\n")
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
        routed = run_actor(prior89, p82, context, cycle_root, current, current_source, selection, world, stage_index)
        prior_subject = current
        promotion = None
        if routed["binding"]:
            current, promotion = prior22.promote(p82, prior_subject, selection, world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and stage_grounded(stage_index, current["continuation"]["next_opening"]))
        cycles.append({"cycle": stage_index + 1, "incoming_scheduler_match": incoming_match, "selection_binding": selection, "world": world, "route": p82.compact(routed), "promotion": promotion, "operational_transition_passed": operational, "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"]})
        if not operational:
            break
    recurrent = bool(len(cycles) == 3 and all(item.get("operational_transition_passed") for item in cycles) and all(item["selection_binding"]["active_selection"]["selected_id"] == item["world"]["oracle_contact_id"] for item in cycles) and all(item["selection_binding"]["precorrection_control_selection"]["selected_id"] != item["selection_binding"]["active_selection"]["selected_id"] for item in cycles) and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and previous.previous.previous.contextual_transfer_grounded(current["continuation"]["next_opening"]))
    result = {
        "authority": "ot-0130-route-only-recurrent-subject-driver",
        "source_subject_digest": parent["artifact_digest"],
        "compiler_version": COMPILER_VERSION,
        "cycles": cycles,
        "fresh_actor_count": len(cycles),
        "completed_cycle_count": sum(bool(item.get("operational_transition_passed")) for item in cycles),
        "route_only_three_cycle_recurrence_passed": recurrent,
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
