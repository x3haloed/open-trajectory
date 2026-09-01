from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0122_subject_selected_world_contact.py"
BASE_SHA256 = "f96abf55d416fc5391af77e13785ae920e29f72984435fa7e00f5299811eb124"
RUN_SHA256 = "236648fe8a522db556e431680cfd7a9708f54dafccfc6daf80ced3163d082a9a"
AGGREGATE_SHA256 = "1ff70dc18ba986b915aa5c6ad4a4410cdf15689dd3567735c9e26c9454558149"
PARENT_DIGEST = "1d309731183215aaa650f20a46164415ba6ca0348453ac383acdf45b18609aa5"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0122 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0123_frozen_ot0122", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
base = previous.base
prior17 = previous.prior17
prior18 = previous.prior18
kernel = previous.kernel


def extract(path, destination):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0122" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk():
                raise RuntimeError("unsafe OT-0122 archive")
        archive.extractall(destination, members=members)
    return destination / "OT-0122"


def load_inputs(p82, repo, store, destination):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0122", "subject-selected-world-contact-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0122", "subject-selected-world-contact-aggregate.json")
    if run_manifest["sha256"] != RUN_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0122 evidence")
    raw = extract(run_path, destination)
    aggregate = json.loads(aggregate_path.read_text())
    parent, corrected, _ = previous.load_parent(p82, repo, store)
    selection = json.loads((raw / "bound-contact-selection.json").read_text())
    world = json.loads((raw / "selected-world-receipt.json").read_text())
    first_route = json.loads((raw / "consequence-router/actor-workspace/route-assimilation.json").read_text())
    first_opening = json.loads((raw / "consequence-router/actor-workspace/successor-opening.json").read_text())
    first_audit = json.loads((raw / "consequence-router/actor-audit.json").read_text())
    return parent, corrected, selection, world, first_route, first_opening, first_audit, aggregate


def exact_case_ids(world):
    return {row["case_id"] for row in world["selected_branch"]["cases"]}


def has_resource_scarcity(value):
    text = value.lower().replace("-", " ") if isinstance(value, str) else ""
    return "resource" in text and "scarcity" in text


def retained_checks(parent, selection, world, first_route, first_opening, first_audit, aggregate):
    expected_ids = {"joint-zero-01", "joint-coordination-02", "joint-recovery-03", "joint-composed-04"}
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "raw_apparent_promotion": bool(aggregate["operational_transition_passed"]),
        "active_selection_exact": selection["active_selection"]["selected_id"] == "joint-boundary",
        "control_selection_exact": selection["precorrection_control_selection"]["selected_id"] == "carry-heavy-boundary",
        "selection_receipt_linked": world["selection_binding_digest"] == selection["binding_digest"],
        "world_route_exact": world["expected_route"] == "extend",
        "world_oracle_exact": world["oracle_contact_id"] == world["selected_contact_id"] == "joint-boundary",
        "case_ids_exact": exact_case_ids(world) == expected_ids,
        "first_route_extend": first_route["route"] == "extend",
        "first_trace_clean": bool(first_audit["conformant"] and first_audit["trace_regime"]["accepted"] and first_audit["denial_classification_v2"]["accepted"]),
        "rejected_symptom_exact": first_opening["next_opening"] == parent["continuation"]["next_opening"],
        "new_uncertainty_grounded_elsewhere": has_resource_scarcity(first_route["remaining_uncertainty"]),
    }
    checks["passed"] = all(checks.values())
    return checks


def router_seed(prior89, run, parent, corrected, selection, world):
    seed = run / "coherent-router-seed"
    seed.mkdir()
    actor_receipt = {key: value for key, value in world.items() if key != "expected_route"}
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-contact-selection.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps(actor_receipt, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(corrected)
    (seed / "route-assimilation.json").write_text(json.dumps(previous.route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action.json").write_text(json.dumps(kernel.foundation.prior.prior.action_template(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action-contract.json").write_text(json.dumps({
        "exact_keys": sorted(kernel.ACTION_KEYS),
        "required_action_kind": "registry-extension",
        "required_new_target_concepts": ["resource", "scarcity"],
        "target_must_differ_from": parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "extension-coherence-contract.json").write_text(json.dumps({
        "required_route": "extend",
        "required_exact_case_ids": sorted(exact_case_ids(world)),
        "authoritative_next_opening_must_differ_from": parent["continuation"]["next_opening"],
        "required_new_opening_concepts": ["resource", "scarcity"],
        "required_new_target_concepts": ["resource", "scarcity"],
        "principle": "An extension exists only if the newly grounded uncertainty causally changes the authoritative next opening and action target.",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["route-assimilation.json", "successor-opening.json", "continuation-action.json"],
        "immutable": ["selector.py", "subject-position.json", "bound-contact-selection.json", "selected-world-consequence.json", "extension-coherence-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "Assimilate the exact retained selected consequence as a coherent extension. Cite all exact cases, preserve selector.py, and make the newly grounded resource-scarcity question causally present in both the authoritative next opening and a materially new registry-extension target. Edit exactly the three permitted JSON files, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_router(prior89, p82, context, run, parent, corrected, selection, world):
    seed = router_seed(prior89, run, parent, corrected, selection, world)
    prompt = "Assimilate the exact retained consequence under the extension-coherence contract. Preserve the selector, cite every exact case, encode resource scarcity in the authoritative next opening and a new action target, inspect the exact diff, and report truthfully."
    output, base_audit, workspace, _ = context.run_actor("coherent-router", seed, previous.ROUTER_SCHEMA, prompt)
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        action = json.loads((workspace / "continuation-action.json").read_text())
        retained = (workspace / "selector.py").read_text() == corrected
    except (OSError, json.JSONDecodeError):
        route = opening = action = None
        retained = False
    cited = set(route.get("settled_case_ids", [])) if isinstance(route, dict) else set()
    old_target = parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"]
    coherence = {
        "route_extend": bool(route and route.get("route") == "extend"),
        "case_ids_exact": cited == exact_case_ids(world),
        "selector_retained": retained,
        "opening_changed": bool(opening and opening.get("next_opening") != parent["continuation"]["next_opening"]),
        "opening_carries_resource_scarcity": bool(opening and has_resource_scarcity(opening.get("next_opening"))),
        "continuation_carries_resource_scarcity": bool(opening and has_resource_scarcity(opening.get("continuation_after_contact"))),
        "remaining_uncertainty_carries_resource_scarcity": bool(route and has_resource_scarcity(route.get("remaining_uncertainty"))),
        "action_is_extension": bool(action and action.get("action_kind") == "registry-extension"),
        "action_target_changed": bool(action and action.get("action_target") != old_target),
        "action_target_carries_resource_scarcity": bool(action and has_resource_scarcity(action.get("action_target"))),
        "expected_information_carries_resource_scarcity": bool(action and has_resource_scarcity(action.get("expected_information"))),
    }
    coherence["passed"] = all(coherence.values())
    valid = bool(
        previous.valid_route(route)
        and prior89.valid_successor(opening)
        and prior18.previous.previous.repaired_action_valid(action, parent)
        and coherence["passed"]
    )
    audit = context.audit_actor("coherent-router", output, base_audit, valid, ["route-assimilation.json", "successor-opening.json", "continuation-action.json"])
    bound = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0123-authoritative-extension-coherence",
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": selection["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "coherence": coherence,
            "selector_retention_derived": retained,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        bound = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("coherent-router") / "bound-route.json").write_text(json.dumps(bound, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "coherence": coherence, "binding": bound}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0123").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    with tempfile.TemporaryDirectory() as directory:
        parent, corrected, selection, world, first_route, first_opening, first_audit, aggregate = load_inputs(p82, repo, store, Path(directory))
    checks = retained_checks(parent, selection, world, first_route, first_opening, first_audit, aggregate)
    checks["parent_sounding"] = runtime.identity_conforms(parent)
    checks["passed"] = all(value for key, value in checks.items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "run_sha256": RUN_SHA256, "aggregate_sha256": AGGREGATE_SHA256, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0123 evidence")
    run.mkdir(parents=True)
    (run / "retained-input-checks.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("retained input conformance failed")
    context = prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    routed = run_router(prior89, p82, context, run, parent, corrected, selection, world)
    current = parent
    promotion = None
    if routed["binding"]:
        current, promotion = previous.promote(p82, parent, selection, world, routed["binding"])
    operational = bool(
        promotion
        and runtime.identity_conforms(current)
        and current["continuation"]["status"] == "open"
        and current["continuation"]["next_opening"] == routed["binding"]["successor_opening"]["next_opening"]
        and has_resource_scarcity(current["continuation"]["next_opening"])
    )
    result = {
        "authority": "ot-0123-authoritative-extension-coherence-driver",
        "source_subject_digest": parent["artifact_digest"],
        "selection_binding_digest": selection["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "retained_input_checks": checks,
        "coherent_route": p82.compact(routed),
        "promotion": promotion,
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
