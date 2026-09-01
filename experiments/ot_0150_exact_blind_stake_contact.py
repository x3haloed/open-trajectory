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
BASE_PATH = ROOT / "ot_0149_blind_stake_world_selection.py"
BASE_SHA256 = "3842d6f1e8c56afa663b03640c74b0099b7c47b77c548c0a5c44a93bfa377dac"
PARENT_DIGEST = "7fa070fde9478fcd83ca2e20c2b94f5db1c5a9f2d5208c675ccf5f7e5d6c5263"
CONTACT_SCHEMA = REPO / "spec/ot-0150-contact.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0149 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0150_frozen_ot0149", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def reconstruct(p82, parent: dict[str, Any], stake: dict[str, Any], route: dict[str, Any], audit: dict[str, Any], events: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not previous.valid_stake(stake):
        return None, None, None
    if not (audit.get("exact_changes") and audit.get("truthful") and audit.get("changed_paths") == ["next-stake.json"] and audit.get("trace_regime", {}).get("accepted") and audit.get("denial_classification_v2", {}).get("accepted")):
        return None, None, None
    body = {"authority": "ot-0149-bound-blind-developmental-stake", "source_subject_digest": parent["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "stake": stake, "world_catalog_visible_to_actor": False}
    binding = {**body, "binding_digest": p82.digest(body)}
    world_catalog = previous.catalog(p82)
    compiled = previous.compile_route(p82, parent, binding, world_catalog)
    pre_generation = len(events) == 4 and [item.get("type") for item in events] == ["thread.started", "turn.started", "error", "turn.failed"] and "invalid_json_schema" in json.dumps(events)
    if binding["binding_digest"] != route.get("stake_binding_digest") or compiled != route or not pre_generation:
        return None, None, None
    return binding, world_catalog, compiled


def preflight(p82, parent: dict[str, Any], stake: dict[str, Any], route: dict[str, Any], audit: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    binding, world_catalog, compiled = reconstruct(p82, parent, stake, route, audit, events)
    prop = binding["stake"]["property"] if binding else None
    passing = previous.evaluate(prop, previous.SURFACES[prop]["passing_policy"], previous.SURFACES[prop]["hidden_cases"]) if prop else None
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "exact_stake_reconstruction": bool(binding and binding["binding_digest"] == route["stake_binding_digest"]),
        "exact_route_reconstruction": compiled == route,
        "selected_option_expansion": bool(compiled and compiled["selected_property"] == "option-expansion" and compiled["selected_surface"]["surface_id"] == "viable-branch-carrier"),
        "world_executable": bool(passing and passing["passed"] and passing["pass_count"] == 3),
        "compatible_contact_schema": CONTACT_SCHEMA.is_file() and "uniqueItems" not in CONTACT_SCHEMA.read_text(),
        "assimilation_schema_present": previous.ASSIMILATION_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "stake_binding": binding, "catalog": world_catalog, "route": compiled, "hidden_fixture": passing}


def run_contact_actor(context, p82, root: Path, subject: dict[str, Any], stake: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    label = "selected-world-contact-author"
    seed = previous.contact_seed(root, subject, stake, route)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    prop = route["selected_property"]
    try:
        policy = json.loads((workspace / "policy.json").read_text())
        action = json.loads((workspace / "contact-action.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        policy, action, immutable_ok = None, None, False
    public = previous.evaluate(prop, policy, previous.SURFACES[prop]["public_cases"]) if isinstance(policy, dict) and set(policy) == {"mode"} and policy["mode"] in previous.SURFACES[prop]["allowed_modes"] else None
    valid = bool(public and public["passed"] and immutable_ok and isinstance(action, dict) and set(action) == {"action", "property", "rationale"} and action["action"] == "apply-policy" and action["property"] == prop and prior131.valid_text(action["rationale"]))
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-action.json", "policy.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0150-bound-selected-world-policy", "source_subject_digest": subject["artifact_digest"], "stake_binding_digest": stake["binding_digest"], "route_digest": route["route_digest"], "actor_patch_digest": audit["patch_digest"], "property": prop, "surface_id": route["selected_surface"]["surface_id"], "policy": policy, "action": action, "public_evaluation": public}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "policy": policy, "action": action, "public": public, "binding": binding}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0150").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0148", "open-subject-with-cross-world-corrected-program.json")
    stake = load_artifact(p82, repo, store, "OT-0149", "exact-blind-option-expansion-stake.json")
    route = load_artifact(p82, repo, store, "OT-0149", "compiled-option-expansion-world-route.json")
    audit = json.loads((store / "runs/OT-0149/blind-next-stake-author/actor-audit.json").read_text())
    events = [json.loads(line) for line in (store / "runs/OT-0149/selected-world-contact-author/events.jsonl").read_text().splitlines()]
    fixtures = preflight(p82, parent, stake, route, audit, events)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0150 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    binding = fixtures["stake_binding"]
    compiled = fixtures["route"]
    (run / "reconstructed-stake-binding.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    (run / "reconstructed-world-route.json").write_text(json.dumps(compiled, indent=2, sort_keys=True) + "\n")
    contact_root = run / "selected-world-contact"
    contact_root.mkdir()
    contact = run_contact_actor(context, p82, contact_root, parent, binding, compiled)
    world = previous.hidden_world(p82, contact["binding"]) if contact["binding"] else None
    if world:
        (contact_root / "sealed-hidden-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "consequence-assimilation"
    assimilation_root.mkdir()
    assimilation = previous.run_assimilator(context, p82, assimilation_root, parent, binding, compiled, contact["binding"], world) if world and world["result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = previous.seal_successor(p82, parent, binding, compiled, contact["binding"], world, assimilation["binding"])
    world_catalog = fixtures["catalog"]
    erased = copy.deepcopy(binding)
    erased["stake"].pop("property", None)
    erased_route = previous.compile_route(p82, parent, erased, world_catalog)
    current = binding["stake"]["property"]
    other = previous.PROPERTIES[(previous.PROPERTIES.index(current) + 1) % len(previous.PROPERTIES)]
    counterfactual = copy.deepcopy(binding)
    counterfactual["stake"]["property"] = other
    counterfactual["binding_digest"] = p82.digest({key: value for key, value in counterfactual.items() if key != "binding_digest"})
    counterfactual_route = previous.compile_route(p82, parent, counterfactual, world_catalog)
    controls = {"property_erased_route": erased_route, "counterfactual_route": counterfactual_route}
    (run / "post-seal-route-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    checks = {
        "two_fresh_actors": bool(contact["binding"] and assimilation and assimilation["binding"]),
        "exact_stake_and_route": binding["binding_digest"] == route["stake_binding_digest"] and compiled == route,
        "selected_branching_contact_passes": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 3),
        "consequence_authors_different_next_stake": bool(assimilation and assimilation["binding"] and assimilation["assimilation"]["next_stake"]["property"] != binding["stake"]["property"]),
        "erasure_blocks_route": erased_route is None,
        "different_property_changes_world": counterfactual_route["selected_surface"]["surface_id"] != compiled["selected_surface"]["surface_id"],
        "parent_capabilities_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities") and final.get("constitutional_selector_program_capabilities") == parent.get("constitutional_selector_program_capabilities")),
        "selected_world_capability_retained": bool(final.get("subject_selected_world_capabilities") and final["subject_selected_world_capabilities"][-1]["world_receipt_digest"] == world["receipt_digest"]),
        "actor_authored_opening": bool(final.get("active_developmental_stake") == assimilation["assimilation"]["next_stake"] and assimilation["assimilation"]["next_stake"]["question"] in final["continuation"]["next_opening"]),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0150-exact-blind-stake-contact-driver", "source_subject_digest": parent["artifact_digest"], "reconstructed_stake_binding": binding, "reconstructed_route": compiled, "selected_world_contact": p82.compact(contact), "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "post_seal_controls": controls, "checks": checks, "exact_blind_stake_contact_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [contact, assimilation]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
