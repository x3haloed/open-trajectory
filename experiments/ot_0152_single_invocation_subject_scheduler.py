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
BASE_PATH = ROOT / "ot_0151_subject_stake_world_recurrence.py"
BASE_SHA256 = "9fd41cba0e0367f1ff7d2f164481c3753abe693deed3e23a8d1280e756177190"
PARENT_DIGEST = "f1fcfba3742e8302f4c0e36f1c92faf6e173c112e78ef20fc9a8fcb2e992f787"
ENCOUNTER_BUDGET = 3


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0151 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0152_frozen_ot0151", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
contact_base = previous.previous
worlds = previous.worlds
prior131 = worlds.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def run_contact_actor(
    context,
    p82,
    label: str,
    root: Path,
    subject: dict[str, Any],
    stake: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    seed = worlds.contact_seed(root, subject, stake, route)
    output, base_audit, workspace, _ = context.run_actor(
        label,
        seed,
        contact_base.CONTACT_SCHEMA,
        (seed / "README.md").read_text().strip(),
    )
    prop = route["selected_property"]
    try:
        policy = json.loads((workspace / "policy.json").read_text())
        action = json.loads((workspace / "contact-action.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        policy, action, immutable_ok = None, None, False
    surface = worlds.SURFACES[prop]
    public = worlds.evaluate(prop, policy, surface["public_cases"]) if isinstance(policy, dict) and set(policy) == {"mode"} and policy.get("mode") in surface["allowed_modes"] else None
    valid = bool(
        public
        and public["passed"]
        and immutable_ok
        and isinstance(action, dict)
        and set(action) == {"action", "property", "rationale"}
        and action["action"] == "apply-policy"
        and action["property"] == prop
        and prior131.valid_text(action["rationale"])
    )
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-action.json", "policy.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0150-bound-selected-world-policy",
            "source_subject_digest": subject["artifact_digest"],
            "stake_binding_digest": stake["binding_digest"],
            "route_digest": route["route_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "property": prop,
            "surface_id": route["selected_surface"]["surface_id"],
            "policy": policy,
            "action": action,
            "public_evaluation": public,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "policy": policy, "action": action, "public": public, "binding": binding}


def run_assimilator(
    context,
    p82,
    label: str,
    root: Path,
    subject: dict[str, Any],
    stake: dict[str, Any],
    route: dict[str, Any],
    policy: dict[str, Any],
    world: dict[str, Any],
) -> dict[str, Any]:
    seed = worlds.assimilation_seed(root, subject, stake, route, policy, world)
    output, base_audit, workspace, _ = context.run_actor(
        label,
        seed,
        worlds.ASSIMILATION_SCHEMA,
        (seed / "README.md").read_text().strip(),
    )
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        assimilation, immutable_ok = None, False
    valid = bool(
        isinstance(assimilation, dict)
        and set(assimilation) == {"disposition", "evidence_receipt_digest", "next_stake"}
        and assimilation["disposition"] == "retire"
        and assimilation["evidence_receipt_digest"] == world["receipt_digest"]
        and worlds.valid_stake(assimilation["next_stake"])
        and assimilation["next_stake"]["property"] != stake["stake"]["property"]
        and immutable_ok
    )
    audit = context.audit_actor(label, output, base_audit, valid, ["assimilation.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0149-bound-selected-world-assimilation",
            "source_subject_digest": subject["artifact_digest"],
            "stake_binding_digest": stake["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "assimilation": assimilation,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "assimilation": assimilation, "binding": binding}


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    binding = previous.bind_carried_stake(p82, parent)
    catalog = worlds.catalog(p82)
    route = worlds.compile_route(p82, parent, binding, catalog) if binding else None
    evaluations = {
        prop: worlds.evaluate(prop, worlds.SURFACES[prop]["passing_policy"], worlds.SURFACES[prop]["hidden_cases"])
        for prop in worlds.PROPERTIES
    }
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "parent_has_exact_prior_capabilities": len(parent.get("subject_selected_world_capabilities", [])) == 2,
        "carried_stake_binds": bool(binding and binding["stake"] == parent["active_developmental_stake"]),
        "carried_option_expansion_routes_branching": bool(route and route["selected_property"] == "option-expansion" and route["selected_surface"]["surface_id"] == "viable-branch-carrier"),
        "all_catalog_worlds_executable": all(result["passed"] and result["pass_count"] == 3 for result in evaluations.values()),
        "unchanged_schemas": contact_base.CONTACT_SCHEMA.is_file() and worlds.ASSIMILATION_SCHEMA.is_file(),
        "fixed_budget_positive": ENCOUNTER_BUDGET == 3,
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "catalog": catalog, "initial_binding": binding, "initial_route": route, "hidden_fixtures": evaluations}


def route_controls(p82, subject: dict[str, Any], binding: dict[str, Any], route: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    erased = copy.deepcopy(binding)
    erased["stake"].pop("property", None)
    erased_route = worlds.compile_route(p82, subject, erased, catalog)
    current = binding["stake"]["property"]
    other = worlds.PROPERTIES[(worlds.PROPERTIES.index(current) + 1) % len(worlds.PROPERTIES)]
    counterfactual = copy.deepcopy(binding)
    counterfactual["stake"]["property"] = other
    counterfactual["binding_digest"] = p82.digest({key: value for key, value in counterfactual.items() if key != "binding_digest"})
    counterfactual_route = worlds.compile_route(p82, subject, counterfactual, catalog)
    return {
        "property_erased_route": erased_route,
        "counterfactual_route": counterfactual_route,
        "passed": erased_route is None and counterfactual_route["selected_surface"]["surface_id"] != route["selected_surface"]["surface_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0152").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0151", "open-subject-with-third-actor-authored-stake.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0152 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    catalog = fixtures["catalog"]
    current = parent
    encounters: list[dict[str, Any]] = []

    for number in range(1, ENCOUNTER_BUDGET + 1):
        encounter_root = run / f"encounter-{number}"
        encounter_root.mkdir()
        source = current
        binding = previous.bind_carried_stake(p82, source)
        route = worlds.compile_route(p82, source, binding, catalog) if binding else None
        (encounter_root / "bound-subject-carried-stake.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        (encounter_root / "compiled-subject-world-route.json").write_text(json.dumps(route, indent=2, sort_keys=True) + "\n")
        if not binding or not route:
            encounters.append({"encounter": number, "source_subject_digest": source["artifact_digest"], "completed": False, "failure": "stake-did-not-route"})
            break

        contact_root = encounter_root / "selected-world-contact"
        contact_root.mkdir()
        contact = run_contact_actor(context, p82, f"encounter-{number}-contact", contact_root, source, binding, route)
        world = worlds.hidden_world(p82, contact["binding"]) if contact["binding"] else None
        if world:
            (contact_root / "sealed-hidden-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
        assimilation_root = encounter_root / "consequence-assimilation"
        assimilation_root.mkdir()
        assimilation = run_assimilator(context, p82, f"encounter-{number}-assimilation", assimilation_root, source, binding, route, contact["binding"], world) if world and world["result"]["passed"] else None

        successor = source
        transition = None
        if assimilation and assimilation["binding"]:
            successor, transition = worlds.seal_successor(p82, source, binding, route, contact["binding"], world, assimilation["binding"])
        controls = route_controls(p82, source, binding, route, catalog)
        (encounter_root / "post-seal-route-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
        completed = bool(
            contact["binding"]
            and world
            and world["result"]["passed"]
            and world["result"]["pass_count"] == 3
            and assimilation
            and assimilation["binding"]
            and controls["passed"]
            and runtime.identity_conforms(successor)
            and successor["continuation"]["status"] == "open"
        )
        encounter = {
            "encounter": number,
            "source_subject_digest": source["artifact_digest"],
            "carried_property": binding["stake"]["property"],
            "surface_id": route["selected_surface"]["surface_id"],
            "stake_binding": binding,
            "route": route,
            "contact": p82.compact(contact),
            "hidden_world": world,
            "assimilation": p82.compact(assimilation) if assimilation else None,
            "transition_receipt": transition,
            "controls": controls,
            "successor_subject_digest": successor["artifact_digest"],
            "next_stake": successor.get("active_developmental_stake"),
            "completed": completed,
        }
        encounter["receipt_digest"] = p82.digest(encounter)
        encounters.append(encounter)
        current = successor
        if not completed:
            break

    properties = [item["carried_property"] for item in encounters if item.get("completed")]
    surfaces = [item["surface_id"] for item in encounters if item.get("completed")]
    actor_audits = [
        audit
        for item in encounters
        if item.get("completed")
        for audit in [item["contact"]["audit"], item["assimilation"]["audit"]]
    ]
    actor_labels = [f"encounter-{number}-{role}" for number in range(1, ENCOUNTER_BUDGET + 1) for role in ["contact", "assimilation"]]
    exact_subject_sequence = bool(
        len(encounters) == ENCOUNTER_BUDGET
        and all(item.get("completed") for item in encounters)
        and all(
            encounters[index + 1]["source_subject_digest"] == encounters[index]["successor_subject_digest"]
            and encounters[index + 1]["carried_property"] == encounters[index]["next_stake"]["property"]
            for index in range(ENCOUNTER_BUDGET - 1)
        )
    )
    checks = {
        "three_encounters_complete": len(encounters) == ENCOUNTER_BUDGET and all(item.get("completed") for item in encounters),
        "six_fresh_accepted_actors": len(actor_audits) == 6 and len(set(actor_labels)) == 6 and all((run / label).is_dir() for label in actor_labels) and all(prior131.audit_accepted(audit) for audit in actor_audits),
        "exact_successor_sequence_drives_worlds": exact_subject_sequence,
        "every_consequence_authors_different_property": all(item["next_stake"]["property"] != item["carried_property"] for item in encounters if item.get("completed")),
        "at_least_two_properties_and_surfaces": len(set(properties)) >= 2 and len(set(surfaces)) >= 2,
        "all_prior_capabilities_retained": all(current.get(key) == parent.get(key) for key in ["adaptive_contact_strategy_capabilities", "recovery_cadence_capabilities", "deadline_recovery_capabilities", "constitutional_selector_program_capabilities"]),
        "five_selected_world_capabilities": len(current.get("subject_selected_world_capabilities", [])) == 5 and current["subject_selected_world_capabilities"][:2] == parent["subject_selected_world_capabilities"],
        "fourth_actor_authored_stake_open": bool(encounters and encounters[-1].get("next_stake") == current.get("active_developmental_stake") and current["active_developmental_stake"]["question"] in current["continuation"]["next_opening"]),
        "final_subject_sounding_open": runtime.identity_conforms(current) and current["continuation"]["status"] == "open",
        "observer_stopped_subject_continues": len(encounters) == ENCOUNTER_BUDGET and current["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0152-single-invocation-subject-scheduler",
        "source_subject_digest": parent["artifact_digest"],
        "encounter_budget": ENCOUNTER_BUDGET,
        "property_itinerary": None,
        "encounters": encounters,
        "checks": checks,
        "single_invocation_recurrence_passed": checks["passed"],
        "observer_disposition": "bounded-observation-complete" if checks["passed"] else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "fresh_actor_count": len(actor_audits),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
