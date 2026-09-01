from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0150_exact_blind_stake_contact.py"
BASE_SHA256 = "60b682bef6be2a290b701ff7a8640942a7cb254339eecbd9c33e092f54d1d91b"
PARENT_DIGEST = "7b7ac1eb99804860379006dcbe7341975c3d8a4ad169d3f0514d6fb9ffaa0585"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0150 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0151_frozen_ot0150", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
worlds = previous.previous
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def bind_carried_stake(p82, subject: dict[str, Any]) -> dict[str, Any] | None:
    stake = subject.get("active_developmental_stake")
    if not worlds.valid_stake(stake):
        return None
    body = {"authority": "ot-0151-bound-subject-carried-stake", "source_subject_digest": subject["artifact_digest"], "source_transition_receipt_digest": subject["subject_selected_world_transition_receipts"][-1]["receipt_digest"], "stake": stake, "world_catalog_visible_to_originating_actor": False}
    return {**body, "binding_digest": p82.digest(body)}


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    binding = bind_carried_stake(p82, parent)
    catalog = worlds.catalog(p82)
    route = worlds.compile_route(p82, parent, binding, catalog) if binding else None
    prop = route["selected_property"] if route else None
    hidden = worlds.evaluate(prop, worlds.SURFACES[prop]["passing_policy"], worlds.SURFACES[prop]["hidden_cases"]) if prop else None
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "carried_stake_exact": bool(binding and binding["stake"] == parent["active_developmental_stake"] and binding["stake"]["question"] in parent["continuation"]["next_opening"]),
        "continuity_routes_reset": bool(route and route["selected_property"] == "continuity-under-reset" and route["selected_surface"]["surface_id"] == "reset-carrier"),
        "reset_world_executable": bool(hidden and hidden["passed"] and hidden["pass_count"] == 3),
        "unchanged_schemas": previous.CONTACT_SCHEMA.is_file() and worlds.ASSIMILATION_SCHEMA.is_file(),
        "prior_selected_world_capability": len(parent.get("subject_selected_world_capabilities", [])) == 1,
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "stake_binding": binding, "catalog": catalog, "route": route, "hidden_fixture": hidden}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0151").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0150", "open-subject-with-actor-authored-continuity-stake.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0151 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    binding = fixtures["stake_binding"]
    route = fixtures["route"]
    (run / "bound-subject-carried-stake.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    (run / "compiled-subject-world-route.json").write_text(json.dumps(route, indent=2, sort_keys=True) + "\n")
    contact_root = run / "selected-world-contact"
    contact_root.mkdir()
    contact = previous.run_contact_actor(context, p82, contact_root, parent, binding, route)
    world = worlds.hidden_world(p82, contact["binding"]) if contact["binding"] else None
    if world:
        (contact_root / "sealed-hidden-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "consequence-assimilation"
    assimilation_root.mkdir()
    assimilation = worlds.run_assimilator(context, p82, assimilation_root, parent, binding, route, contact["binding"], world) if world and world["result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = worlds.seal_successor(p82, parent, binding, route, contact["binding"], world, assimilation["binding"])
    erased = copy.deepcopy(binding)
    erased["stake"].pop("property", None)
    erased_route = worlds.compile_route(p82, parent, erased, fixtures["catalog"])
    current = binding["stake"]["property"]
    other = worlds.PROPERTIES[(worlds.PROPERTIES.index(current) + 1) % len(worlds.PROPERTIES)]
    counterfactual = copy.deepcopy(binding)
    counterfactual["stake"]["property"] = other
    counterfactual["binding_digest"] = p82.digest({key: value for key, value in counterfactual.items() if key != "binding_digest"})
    counterfactual_route = worlds.compile_route(p82, parent, counterfactual, fixtures["catalog"])
    controls = {"property_erased_route": erased_route, "counterfactual_route": counterfactual_route}
    (run / "post-seal-route-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    checks = {
        "two_fresh_actors": bool(contact["binding"] and assimilation and assimilation["binding"]),
        "subject_stake_selects_reset": route["selected_property"] == "continuity-under-reset" and route["selected_surface"]["surface_id"] == "reset-carrier",
        "reset_contact_passes": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 3),
        "consequence_authors_third_stake": bool(assimilation and assimilation["binding"] and assimilation["assimilation"]["next_stake"]["property"] != binding["stake"]["property"]),
        "erasure_blocks_route": erased_route is None,
        "different_property_changes_world": counterfactual_route["selected_surface"]["surface_id"] != route["selected_surface"]["surface_id"],
        "two_selected_world_capabilities": len(final.get("subject_selected_world_capabilities", [])) == 2,
        "prior_capabilities_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities") and final.get("constitutional_selector_program_capabilities") == parent.get("constitutional_selector_program_capabilities")),
        "actor_authored_third_opening": bool(final.get("active_developmental_stake") == assimilation["assimilation"]["next_stake"] and assimilation["assimilation"]["next_stake"]["question"] in final["continuation"]["next_opening"]),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0151-subject-stake-world-recurrence-driver", "source_subject_digest": parent["artifact_digest"], "bound_carried_stake": binding, "compiled_route": route, "selected_world_contact": p82.compact(contact), "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "post_seal_controls": controls, "checks": checks, "subject_stake_world_recurrence_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [contact, assimilation]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
