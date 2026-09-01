from __future__ import annotations

import argparse, copy, hashlib, importlib.util, itertools, json, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0121_contradictory_selector_correction.py"
BASE_SHA256 = "858701ad6fcdc59eff0e418d37553459aa8df9d682cfd77caeb0665acaaff6b1"
PARENT_OBJECT_SHA256 = "9cf2c12727748086c311d3565e50e552f1dcb9131a6c1d66018b96cbed47ad07"
PARENT_DIGEST = "1d309731183215aaa650f20a46164415ba6ca0348453ac383acdf45b18609aa5"
CORRECTED_SOURCE_SHA256 = "1699abded9259e8ce07cb73beb41a87f637844ca3d40554b0f655ecf5c393e5e"
PRECORRECTION_SOURCE_SHA256 = "e326934759bfa1ba9122c095e1b3e3f76485e889f850f92bef8ce901c703312d"
ROUTER_SCHEMA = REPO / "spec/ot-0122-router.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0121 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0122_frozen_ot0121", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior17 = previous.prior17
prior18 = previous.prior18
base = previous.base
kernel = previous.kernel


def load_parent(p82, repo, store):
    manifest, path = p82.materialize(repo, store, "OT-0121", "open-subject-with-corrected-selector.json")
    parent = json.loads(path.read_text())
    if manifest["sha256"] != PARENT_OBJECT_SHA256 or parent["artifact_digest"] != PARENT_DIGEST:
        raise RuntimeError("wrong OT-0121 parent")
    corrected = parent["allocation_machinery"][-1]["source"]
    precorrection = parent["allocation_machinery"][-2]["source"]
    if hashlib.sha256(corrected.encode()).hexdigest() != CORRECTED_SOURCE_SHA256:
        raise RuntimeError("wrong corrected selector")
    if hashlib.sha256(precorrection.encode()).hexdigest() != PRECORRECTION_SOURCE_SHA256:
        raise RuntimeError("wrong pre-correction selector")
    return parent, corrected, precorrection


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


def envelope():
    return [
        contact("carry-heavy-boundary", "carry-heavy-probe", 108, 44, 2, 2, 30, 3),
        contact("coordination-boundary", "coordination-interaction", 94, 32, 7, 2, 10, 1),
        contact("recovery-boundary", "recovery-interaction", 92, 30, 2, 7, 9, 1),
        contact("joint-boundary", "joint-coordination-recovery", 100, 36, 5, 4, 12, 1),
    ]


BRANCHES = {
    "carry-heavy-boundary": {
        "realized_information": 18.0,
        "zero_term_projection": False,
        "reproducible_winner_boundary": False,
        "settles_current_pursuit": False,
        "remaining_uncertainty": "Whether coordination and recovery jointly move the boundary remains untouched.",
        "cases": [
            {"case_id": "carry-01", "pressure": 0, "coordination": 2, "recovery": 2, "winner": "reserve"},
            {"case_id": "carry-02", "pressure": 3, "coordination": 2, "recovery": 2, "winner": "calibrated"},
        ],
    },
    "coordination-boundary": {
        "realized_information": 58.0,
        "zero_term_projection": True,
        "reproducible_winner_boundary": True,
        "settles_current_pursuit": False,
        "remaining_uncertainty": "Recovery volatility remains unvaried.",
        "cases": [
            {"case_id": "coord-01", "pressure": 0, "coordination": 2, "recovery": 3, "winner": "resilient"},
            {"case_id": "coord-02", "pressure": 2, "coordination": 7, "recovery": 3, "winner": "calibrated"},
        ],
    },
    "recovery-boundary": {
        "realized_information": 56.0,
        "zero_term_projection": True,
        "reproducible_winner_boundary": True,
        "settles_current_pursuit": False,
        "remaining_uncertainty": "Coordination load remains unvaried.",
        "cases": [
            {"case_id": "recovery-01", "pressure": 0, "coordination": 3, "recovery": 2, "winner": "resilient"},
            {"case_id": "recovery-02", "pressure": 2, "coordination": 3, "recovery": 7, "winner": "calibrated"},
        ],
    },
    "joint-boundary": {
        "realized_information": 92.0,
        "zero_term_projection": True,
        "reproducible_winner_boundary": True,
        "settles_current_pursuit": True,
        "remaining_uncertainty": "Whether the joint boundary transfers when resource scarcity becomes an independent pressure remains unresolved.",
        "cases": [
            {"case_id": "joint-zero-01", "pressure": 0, "coordination": 2, "recovery": 2, "winner": "resilient"},
            {"case_id": "joint-coordination-02", "pressure": 2, "coordination": 7, "recovery": 2, "winner": "calibrated"},
            {"case_id": "joint-recovery-03", "pressure": 2, "coordination": 2, "recovery": 7, "winner": "calibrated"},
            {"case_id": "joint-composed-04", "pressure": 2, "coordination": 7, "recovery": 7, "winner": "reserve"},
        ],
    },
}


def choose(source, rows):
    selector = prior17.load_selector(source)
    original = copy.deepcopy(rows)
    try:
        selected = selector(copy.deepcopy(rows)) if selector else None
    except Exception:
        selected = None
    return {"selected_id": selected, "input_unchanged": rows == original, "valid": selected in {row["id"] for row in rows}}


def selection_conformance(corrected, precorrection):
    rows = envelope()
    corrected_choices = set()
    precorrection_choices = set()
    for permutation in itertools.permutations(rows):
        corrected_choices.add(choose(corrected, list(permutation))["selected_id"])
        precorrection_choices.add(choose(precorrection, list(permutation))["selected_id"])
    renamed = [{**row, "id": f"surface-{index}"} for index, row in enumerate(reversed(rows), 1)]
    corrected_renamed = choose(corrected, renamed)
    precorrection_renamed = choose(precorrection, renamed)
    corrected_surface = next((row["surface"] for row in renamed if row["id"] == corrected_renamed["selected_id"]), None)
    precorrection_surface = next((row["surface"] for row in renamed if row["id"] == precorrection_renamed["selected_id"]), None)
    oracle = max(BRANCHES, key=lambda item: (BRANCHES[item]["realized_information"], item))
    checks = {
        "corrected_loads": bool(prior17.load_selector(corrected)),
        "precorrection_loads": bool(prior17.load_selector(precorrection)),
        "corrected_permutation_invariant": corrected_choices == {"joint-boundary"},
        "precorrection_permutation_invariant": precorrection_choices == {"carry-heavy-boundary"},
        "corrected_renaming_invariant": corrected_surface == "joint-coordination-recovery",
        "precorrection_renaming_invariant": precorrection_surface == "carry-heavy-probe",
        "sealed_oracle_is_joint": oracle == "joint-boundary",
        "branch_ids_exact": set(BRANCHES) == {row["id"] for row in rows},
    }
    checks["passed"] = all(checks.values())
    return checks


def bind_selection(p82, run, parent, corrected, precorrection):
    rows = envelope()
    active = choose(corrected, rows)
    control = choose(precorrection, rows)
    body = {
        "authority": "ot-0122-subject-selector-contact-binding",
        "source_subject_digest": parent["artifact_digest"],
        "envelope_digest": p82.digest(rows),
        "corrected_selector_digest": hashlib.sha256(corrected.encode()).hexdigest(),
        "precorrection_selector_digest": hashlib.sha256(precorrection.encode()).hexdigest(),
        "active_selection": active,
        "precorrection_control_selection": control,
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    (run / "bound-contact-selection.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return binding


def open_world(p82, run, binding):
    selected = binding["active_selection"]["selected_id"]
    branch = copy.deepcopy(BRANCHES[selected])
    oracle = max(BRANCHES, key=lambda item: (BRANCHES[item]["realized_information"], item))
    if selected != oracle:
        route = "correct"
    elif branch["settles_current_pursuit"] and branch["remaining_uncertainty"]:
        route = "extend"
    elif branch["reproducible_winner_boundary"]:
        route = "use"
    else:
        route = "surrender"
    hidden_body = {
        "authority": "ot-0122-sealed-multi-surface-world",
        "selection_binding_digest": binding["binding_digest"],
        "all_branch_digest": p82.digest(BRANCHES),
        "selected_contact_id": selected,
        "selected_branch": branch,
        "oracle_contact_id": oracle,
        "expected_route": route,
    }
    receipt = {**hidden_body, "receipt_digest": p82.digest(hidden_body)}
    (run / "hidden-world-envelope.json").write_text(json.dumps(BRANCHES, indent=2, sort_keys=True) + "\n")
    (run / "selected-world-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


ROUTE_KEYS = {
    "route", "selected_contact_id", "consequence_summary", "settled_case_ids",
    "remaining_uncertainty", "selection_rule_disposition", "surrender_condition",
}


def route_template():
    return {
        "route": "__REPLACE__",
        "selected_contact_id": "__REPLACE__",
        "consequence_summary": "__REPLACE__",
        "settled_case_ids": [],
        "remaining_uncertainty": "__REPLACE__",
        "selection_rule_disposition": "__REPLACE__",
        "surrender_condition": "__REPLACE__",
    }


def valid_route(value):
    if not isinstance(value, dict) or set(value) != ROUTE_KEYS:
        return False
    if value.get("route") not in {"use", "correct", "extend", "surrender"}:
        return False
    if not isinstance(value.get("settled_case_ids"), list) or not value["settled_case_ids"]:
        return False
    textual = ROUTE_KEYS - {"settled_case_ids"}
    return all(isinstance(value.get(key), str) and value[key].strip() and "__REPLACE__" not in value[key] for key in textual)


def router_seed(prior89, run, parent, corrected, binding, world):
    seed = run / "router-seed"
    seed.mkdir()
    selected_id = binding["active_selection"]["selected_id"]
    selected_contact = next(row for row in envelope() if row["id"] == selected_id)
    actor_receipt = {key: value for key, value in world.items() if key != "expected_route"}
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-selected-contact.json").write_text(json.dumps({"binding": binding, "selected_contact": selected_contact}, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps(actor_receipt, indent=2, sort_keys=True) + "\n")
    (seed / "route-contract.json").write_text(json.dumps({
        "use": "machinery supported; current pursuit unresolved",
        "correct": "realized ranking contradicts installed selector",
        "extend": "machinery supported; current pursuit settled; grounded uncertainty remains",
        "surrender": "surrender condition met; no supported successor remains",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(corrected)
    (seed / "route-assimilation.json").write_text(json.dumps(route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action.json").write_text(json.dumps(kernel.foundation.prior.prior.action_template(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action-contract.json").write_text(json.dumps({
        "exact_keys": sorted(kernel.ACTION_KEYS),
        "action_kinds": ["registered-contact", "registry-extension", "surrender"],
        "registry-extension": "new lowercase hyphenated target, 3 to 128 characters",
        "surrender": "target exactly none",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["route-assimilation.json", "successor-opening.json", "continuation-action.json"],
        "immutable": ["selector.py", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "route-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "Assimilate only the selected branch consequence. Determine whether it calls for use, correction, extension, or surrender from the route contract; retain selector.py exactly unless the consequence requires correction; cite every settled case; bind the next action and opening; edit exactly the three permitted JSON files; inspect the diff; and report truthfully.\n"
    )
    return seed


def run_router(prior89, p82, context, run, parent, corrected, binding, world):
    seed = router_seed(prior89, run, parent, corrected, binding, world)
    prompt = "Continue the exact subject from the selected world consequence. Derive the route from the contract and evidence, cite every settled case, preserve the selector bytes, bind the next action and opening, inspect the exact diff, and report truthfully."
    output, base_audit, workspace, _ = context.run_actor("consequence-router", seed, ROUTER_SCHEMA, prompt)
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
    route_matches = bool(route and route.get("route") == world["expected_route"])
    action_matches = bool(
        action and ((route_matches and world["expected_route"] == "surrender" and action.get("action_kind") == "surrender")
        or (route_matches and world["expected_route"] != "surrender" and action.get("action_kind") != "surrender"))
    )
    valid = bool(
        valid_route(route)
        and route["selected_contact_id"] == world["selected_contact_id"]
        and cited == expected_ids
        and route_matches
        and action_matches
        and prior89.valid_successor(opening)
        and prior18.previous.previous.repaired_action_valid(action, parent)
        and retained
    )
    audit = context.audit_actor("consequence-router", output, base_audit, valid, ["route-assimilation.json", "successor-opening.json", "continuation-action.json"])
    bound = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0122-grounded-consequence-route",
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": binding["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "selector_retention_derived": retained,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        bound = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("consequence-router") / "bound-route.json").write_text(json.dumps(bound, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "grounded": cited == expected_ids, "route_matches": route_matches, "binding": bound}


def promote(p82, parent, binding, world, routed):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    action = routed["continuation_action"]
    opening = routed["successor_opening"]
    receipt_body = {
        "authority": "world-promoted-subject-selected-contact",
        "source_subject_digest": parent["artifact_digest"],
        "selection_binding_digest": binding["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "route_binding_digest": routed["binding_digest"],
        "selected_contact_id": world["selected_contact_id"],
        "route": routed["route_assimilation"]["route"],
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["subject_selected_contact_receipts"] = [*child.get("subject_selected_contact_receipts", []), receipt]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": routed["route_assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []), {
        "authority": "ot-0122-subject-selected-contact-opening",
        "binding_digest": routed["binding_digest"],
        "opening": opening,
        "continuation_action": action,
    }]
    child["active_pursuit"] = {
        "authority": "ot-0122-subject-selected-contact-opening",
        "selected_area": action["action_target"],
        "next_pursuit": opening["next_opening"],
        "world_receipt_digest": world["receipt_digest"],
    }
    child["continuation"] = {**child["continuation"], "status": "closed" if action["action_kind"] == "surrender" else "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]
    child["runtime"] = "sounding"
    return p82.seal(child), receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0122").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent, corrected, precorrection = load_parent(p82, repo, store)
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "parent_sounding": runtime.identity_conforms(parent),
        "parent_open": parent["continuation"]["status"] == "open",
        "active_joint_resilience_pursuit": "coordination-recovery-resilience" in parent["active_pursuit"]["selected_area"],
        "selection_conformance": selection_conformance(corrected, precorrection),
        "route_schema_present": ROUTER_SCHEMA.is_file(),
    }
    checks["passed"] = all(value if not isinstance(value, dict) else value.get("passed", False) for key, value in checks.items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0122 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-actor conformance failed")
    started = time.time()
    binding = bind_selection(p82, run, parent, corrected, precorrection)
    world = open_world(p82, run, binding)
    context = prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    routed = run_router(prior89, p82, context, run, parent, corrected, binding, world)
    current = parent
    promotion = None
    if routed["binding"]:
        current, promotion = promote(p82, parent, binding, world, routed["binding"])
    expected_open = world["expected_route"] != "surrender"
    operational = bool(
        promotion
        and runtime.identity_conforms(current)
        and (current["continuation"]["status"] == "open") == expected_open
        and current["subject_selected_contact_receipts"][-1]["selected_contact_id"] == world["selected_contact_id"]
    )
    causal = bool(
        binding["active_selection"]["selected_id"] == world["oracle_contact_id"]
        and binding["precorrection_control_selection"]["selected_id"] != binding["active_selection"]["selected_id"]
    )
    result = {
        "authority": "ot-0122-subject-selected-world-contact-driver",
        "source_subject_digest": parent["artifact_digest"],
        "selection_binding": binding,
        "world": world,
        "consequence_route": p82.compact(routed),
        "promotion": promotion,
        "subject_selection_causal_passed": causal,
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational and causal else 2


if __name__ == "__main__":
    raise SystemExit(main())
