from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0222_reusable_pulse_driven_invoker.py"
BASE_SHA256 = "311c4341274861e5a06dfcf9b3a4458a89c7f7fcd93eacde547503e660fe35ee"
PARENT_DIGEST = "5a205d35fd7bcda2f32ba365d9e459559ad45bca29dee42042bce19713cd91a7"
OT222_RECEIPT = "d635699003821ca4f546a93cc260ca4b6bcc86e92c41e45ebc98a139ee07bc26"
GENERATOR_SEED = 223_706_151
AUTHORITY = "G7-verification-debt-frontier-liveness"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0222 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0223_frozen_ot0222", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base222 = load_base()
base221 = base222.base221
base220 = base222.base220
base219 = base222.base219
base217 = base220.base217
base213 = base222.base213
authority_base = base222.authority_base


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def derive_ledger(subject: dict[str, Any]) -> dict[str, Any]:
    worlds = subject.get("g6_recurrence_world_receipts", [])
    capabilities = subject.get("semantic_move_capabilities", [])
    entries = {}
    for target in sorted(base217.TARGETS):
        admitted = [row for row in capabilities if row.get("target_symbol") == target]
        target_worlds = [row for row in worlds if row.get("target_symbol") == target]
        latest = target_worlds[-1] if target_worlds else None
        if latest and latest.get("outcome") == "unresolved":
            status = "unresolved"
        elif admitted:
            status = "verified-local"
        else:
            status = "uncontacted"
        entries[target] = {
            "status": status,
            "admitted_capability_receipts": [row.get("world_receipt_digest") for row in admitted],
            "correction_receipts": [row.get("correction_binding_digest") for row in admitted if row.get("correction_binding_digest")],
            "independent_success_receipts": [row["receipt_digest"] for row in target_worlds if row.get("outcome") == "success"],
            "latest_world_receipt_digest": latest.get("receipt_digest") if latest else None,
            "latest_world_outcome": latest.get("outcome") if latest else None,
        }
    return {"authority": AUTHORITY, "targets": entries}


def g7(decision: Any, registry: dict[str, Any], available: dict[str, tuple[Any, Any]], ledger: dict[str, Any]) -> dict[str, Any]:
    floor = base219.g6(decision, registry, available)
    if not floor["accepted"]:
        return {"action": "reject", "reason": floor["reason"], "g6": floor}
    target = decision["next_contact"]["target_symbol"]
    status = ledger["targets"].get(target, {"status": "uncontacted"})["status"]
    if status == "unresolved":
        action, reason = "correct", "retained-unresolved-consequence"
    elif status in {"uncontacted", "verification-due"}:
        action, reason = "contact", "world-contact-still-owed"
    elif status == "verified-local":
        action, reason = "widen", "target-locally-verified"
    else:
        action, reason = "reject", "invalid-ledger-state"
    return {"action": action, "reason": reason, "target_status": status, "g6": floor}


def fresh_contact(target: str, offset: int) -> dict[str, Any]:
    cases = []
    for index in range(4):
        capacity = 3 + index
        rows = [
            base217.item(f"x{offset}-{index}-a", target, 20 + offset + index, 2 + index, .31 + index * .07, 2),
            base217.item(f"x{offset}-{index}-b", target, 13 + offset + index, 9 - index, .83 - index * .06, 3),
            base217.item(f"x{offset}-{index}-c", target, 7 + offset + index, 4 + index, .57 + index * .03, 1),
        ]
        cases.append(base217.case(f"g7-{target}-{offset}-{index}", target, capacity, rows))
    return {"contact_id": f"g7-{target}-{offset}", "target_path": base217.TARGET_PATH, "target_symbol": target, "abi": base219.ABI, "stake": "Determine whether this bounded target still contains decision-relevant contact.", "cases": cases, "predicates": copy.deepcopy(base219.PREDICATES)}


def heldout(parent: dict[str, Any]) -> list[dict[str, Any]]:
    fixtures = []
    targets = sorted(base217.TARGETS)
    for index, target in enumerate(targets):
        contact = fresh_contact(target, 30 + index)
        for status, expected in (("uncontacted", "contact"), ("verification-due", "contact"), ("unresolved", "correct"), ("verified-local", "widen")):
            ledger = derive_ledger(parent)
            ledger["targets"][target]["status"] = status
            fixtures.append({"id": f"{status}-{target}", "expected": expected, "decision": base219.decision("Continue only if this frontier remains live.", copy.deepcopy(contact)), "ledger": ledger})
    historical = base219.historical_contact(parent["semantic_move_capabilities"][0]["package"])
    invalid = fresh_contact(targets[0], 99)
    invalid["cases"] = invalid["cases"][:3]
    ledger = derive_ledger(parent)
    fixtures.extend([
        {"id": "exact-completed", "expected": "reject", "decision": base219.decision("Old.", historical), "ledger": ledger},
        {"id": "decorated-completed", "expected": "reject", "decision": base219.decision("Decorated old.", base219.decorated(historical, top=True, nested=True)), "ledger": ledger},
        {"id": "malformed", "expected": "reject", "decision": base219.decision("Malformed.", invalid), "ledger": ledger},
        {"id": "prose-only", "expected": "reject", "decision": {"next_pursuit": "Words only.", "next_contact": None}, "ledger": ledger},
    ])
    random.Random(GENERATOR_SEED).shuffle(fixtures)
    return fixtures


def evaluate(fixtures: list[dict[str, Any]], registry: dict[str, Any], available: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    rows = []
    for fixture in fixtures:
        incumbent = base219.g6(fixture["decision"], registry, available)
        incumbent_action = "contact" if incumbent["accepted"] else "reject"
        challenger = g7(fixture["decision"], registry, available, fixture["ledger"])
        rows.append({"id": fixture["id"], "expected": fixture["expected"], "g6_action": incumbent_action, "g7_action": challenger["action"], "g6_correct": incumbent_action == fixture["expected"], "g7_correct": challenger["action"] == fixture["expected"]})
    return {"case_count": len(rows), "g6_correct_count": sum(row["g6_correct"] for row in rows), "g7_correct_count": sum(row["g7_correct"] for row in rows), "passed": all(row["g7_correct"] for row in rows), "rows": rows}


def compile_candidate(parent: dict[str, Any], ledger: dict[str, Any], current: dict[str, Any], bundle: dict[str, Any], p82) -> tuple[dict[str, Any], dict[str, Any]]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    body = {"authority": "ot-0223-evaluation-regime-transition", "from_regime": "G6-behavioral-ABI-projected-contact-identity", "to_regime": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "ledger_digest": p82.digest(ledger), "heldout_digest": p82.digest(bundle), "historical_rescoring": False}
    transition = {**body, "receipt_digest": p82.digest(body)}
    child["evaluation_regime_transitions"] = [*child.get("evaluation_regime_transitions", []), transition]
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state["phase"] = current["action"]
    child["fixed_g6_recurrence_driver"] = state
    pending = child["pending_contact_bearing_continuations"][-1]
    child["continuation_liveness"] = {"authority": AUTHORITY, "status": "locally-saturated", "reason": current["reason"], "preserved_pending_contact_identity": pending["contact_identity"], "saturated_targets": sorted(target for target, row in ledger["targets"].items() if row["status"] == "verified-local"), "transition_receipt_digest": transition["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Widen beyond locally verified registered targets without an observer-supplied target."}
    child["unresolved"] = "The registered target frontier is locally saturated; authorize a fresh widening encounter rather than another parameter-only pulse."
    return p82.seal(child), transition


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0223").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0222", "open-subject-after-two-reusable-invocations.json")
    result222 = selector_base.load_artifact(p82, repo, store, "OT-0222", "reusable-pulse-invoker-aggregate.json")
    fixture_root = run.parent / "OT-0223-preflight"
    import shutil
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    available = base220.available_at(fixture_root / "environment", parent)
    registry = base220.completed_registry(parent, available)
    ledger = derive_ledger(parent)
    package = parent["pending_contact_bearing_continuations"][-1]["package"]
    decision = base219.decision(parent["continuation"]["next_opening"], package)
    incumbent = base219.g6(decision, registry, available)
    current = g7(decision, registry, available, ledger)
    bundle = evaluate(heldout(parent), registry, available)
    candidate, transition = compile_candidate(parent, ledger, current, bundle, p82)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent),
        "ot0222_exact_promotion": result222["observer_disposition"] == "promoted" and result222["receipt_digest"] == OT222_RECEIPT and result222["final_subject_digest"] == PARENT_DIGEST,
        "ledger_all_three_verified_local": set(ledger["targets"]) == set(base217.TARGETS) and all(row["status"] == "verified-local" for row in ledger["targets"].values()),
        "heldout_16_of_16": bundle["passed"] and bundle["case_count"] == 16 and bundle["g7_correct_count"] == 16,
        "g7_improves_over_g6": bundle["g7_correct_count"] > bundle["g6_correct_count"],
        "current_g6_valid": incumbent["accepted"],
        "current_g7_widens": current["action"] == "widen" and current["target_status"] == "verified-local",
        "pending_bytes_exact": candidate["pending_contact_bearing_continuations"] == parent["pending_contact_bearing_continuations"],
        "historical_operational_state_exact": all(candidate.get(key) == value for key, value in parent.items() if key not in {"artifact_digest", "evaluation_regime_transitions", "local_frontier_ledger", "fixed_g6_recurrence_driver", "continuation_liveness", "continuation", "unresolved"}),
        "transition_append_exact": candidate["evaluation_regime_transitions"] == [*parent["evaluation_regime_transitions"], transition],
        "driver_widens_only": candidate["fixed_g6_recurrence_driver"] == {**parent["fixed_g6_recurrence_driver"], "phase": "widen"},
        "reusable_pulse_disabled": not base222.pulse_eligible(candidate),
        "prospective_successor_conforms": runtime.identity_conforms(candidate) and candidate["continuation"]["status"] == "open",
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0223-g7-transition", "generator_seed": GENERATOR_SEED, "source_subject_digest": parent["artifact_digest"], "ledger": ledger, "current_g6": incumbent, "current_g7": current, "heldout": bundle, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0223 evidence")
    run.mkdir(parents=True)
    write_json(run / "transition-fixtures.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    final, transition = compile_candidate(parent, ledger, current, bundle, p82)
    final_ok = runtime.identity_conforms(final)
    checks["successor_identity_conforms"] = final_ok
    checks["passed"] = checks["passed"] and final_ok
    result = {"authority": "ot-0223-verification-debt-frontier-liveness", "source_subject_digest": parent["artifact_digest"], "transition": transition if final_ok else None, "ledger": ledger, "current_disposition": current, "heldout": bundle, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "continuation_liveness": final["continuation_liveness"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"]}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
